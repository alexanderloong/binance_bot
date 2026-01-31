import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import get_backtest_data
from bot.data_processor import DataProcessor
from bot.utils import parse_timeframe_to_seconds
from config import (
    EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, 
    ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    SYMBOL, TIMEFRAME, POSITION_SIZE_PERCENT, LEVERAGE, PARTIAL_TP_ENABLED
)

# -----------------------------------------------------------------------------
# Local Helper Functions (Since we are not modifying core files yet)
# -----------------------------------------------------------------------------

def calculate_volume_ma(df, length=20):
    """Calculates Volume Moving Average."""
    df[f'VOL_MA_{length}'] = df['volume'].rolling(window=length).mean()
    return df

def simulate_with_volume(df, volume_ma_length, use_ema_filter=True, 
                         tp_multiplier=PARTIAL_TP_MULTIPLIER, tp_percent=PARTIAL_TP_PERCENT, 
                         sl_multiplier=ATR_MULTIPLIER, adx_threshold=ADX_THRESHOLD, 
                         use_rsi_filter=True, rsi_overbought=RSI_OVERBOUGHT, rsi_oversold=RSI_OVERSOLD):
    """
    Modified simulation function that includes Volume MA Filter logic.
    """
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    stop_loss_price = 0
    partial_tp_hit = False
    take_profit_price = 0
    trades = []
    commission_rate = 0.0005
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    ema_col = 'EMA_FILTER' if 'EMA_FILTER' in df.columns else f'EMA_{EMA_LENGTH}'
    vol_ma_col = f'VOL_MA_{volume_ma_length}'

    # Pre-calculate simple indicators check to speed up loop if possible, 
    # but for simulation we simulate candle by candle.
    
    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]
        
        price = current_candle['close']
        timestamp = current_candle['timestamp']
        
        if i < len(df) - 1:
            execution_time = df.iloc[i+1]['timestamp']
        else:
            tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)
            execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)
        
        # --- EXIT LOGIC ---
        pnl = 0
        fee = 0
        if position_amt > 0 and curr_trend == -1:
            raw_pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'CLOSE_LONG', 'price': price, 'pnl': pnl})
            position_amt = 0
        elif position_amt < 0 and curr_trend == 1:
            raw_pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'CLOSE_SHORT', 'price': price, 'pnl': pnl})
            position_amt = 0

        # Partial TP
        if PARTIAL_TP_ENABLED and position_amt != 0 and not partial_tp_hit:
            is_tp_hit = (position_amt > 0 and price >= take_profit_price) or (position_amt < 0 and price <= take_profit_price)
            if is_tp_hit:
                close_amt = position_amt * tp_percent
                raw_pnl = (take_profit_price - entry_price) * close_amt if position_amt > 0 else (entry_price - take_profit_price) * abs(close_amt)
                fee = (take_profit_price * abs(close_amt)) * commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                position_amt -= close_amt
                partial_tp_hit = True
                trades.append({'time': execution_time, 'type': 'PARTIAL_TP', 'price': take_profit_price, 'pnl': pnl})

        # Stop Loss
        if position_amt > 0 and price <= stop_loss_price:
            raw_pnl = (stop_loss_price - entry_price) * position_amt
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'STOP_LOSS_LONG', 'price': stop_loss_price, 'pnl': pnl})
            position_amt = 0
        elif position_amt < 0 and price >= stop_loss_price:
            raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'STOP_LOSS_SHORT', 'price': stop_loss_price, 'pnl': pnl})
            position_amt = 0

        # --- ENTRY LOGIC ---
        is_uptrend = price > ema_val if use_ema_filter else True
        is_downtrend = price < ema_val if use_ema_filter else True
        
        adx_val = current_candle['ADX']
        is_trending = adx_val > adx_threshold
        
        rsi_val = current_candle['RSI']
        rsi_long_ok = rsi_val < rsi_overbought if use_rsi_filter else True
        rsi_short_ok = rsi_val > rsi_oversold if use_rsi_filter else True
        
        # VOLUME FILTER
        # Only trade if Current Volume > Moving Average Volume
        vol_ok = True
        if vol_ma_col in current_candle:
            vol_ok = current_candle['volume'] > current_candle[vol_ma_col]

        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend:
            if is_trending and rsi_long_ok and vol_ok:
                signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend:
            if is_trending and rsi_short_ok and vol_ok:
                signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * POSITION_SIZE_PERCENT * LEVERAGE
            entry_fee = trade_value * commission_rate
            balance -= entry_fee
            
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            
            atr_val = current_candle['ATR']
            if signal == 'LONG':
                stop_loss_price = entry_price - (atr_val * sl_multiplier)
                take_profit_price = entry_price + (atr_val * tp_multiplier)
            else:
                stop_loss_price = entry_price + (atr_val * sl_multiplier)
                take_profit_price = entry_price - (atr_val * tp_multiplier)
            
            partial_tp_hit = False
            trades.append({'time': execution_time, 'type': f'OPEN_{signal}', 'price': price, 'pnl': -entry_fee, 'amount': abs(amount)})

    total_trades = len([t for t in trades if 'OPEN' in t['type']])
    win_trades = len([t for t in trades if t['pnl'] > 0 and ('CLOSE' in t['type'] or 'PARTIAL' in t['type'])]) 
    # Note: Win rate calculation can be complex with partial TPs. 
    # Simplified: Any event with positive PnL adds to "wins" bucket is one way, 
    # but strictly "Winning Trade" usually means the whole cycle.
    # For optimization comparison, we iterate through PnL events.
    
    pnl_events = [t['pnl'] for t in trades if t['pnl'] != 0]
    gross_profit = sum([p for p in pnl_events if p > 0])
    gross_loss = abs(sum([p for p in pnl_events if p < 0]))
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    total_pnl = balance - initial_balance
    pnl_pct = (total_pnl / initial_balance) * 100
    
    equity_curve = []
    run_bal = initial_balance
    for t in trades:
        if t['pnl'] != 0:
            run_bal += t['pnl']
            equity_curve.append(run_bal)
            
    max_drawdown = 0
    if equity_curve:
        peak = equity_curve[0]
        for val in equity_curve:
            if val > peak: peak = val
            dd = (peak - val) / peak * 100
            if dd > max_drawdown: max_drawdown = dd

    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'win_rate': (win_trades / total_trades * 100) if total_trades > 0 else 0,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'total_trades': total_trades
    }, trades

# -----------------------------------------------------------------------------
# Optimization Logic
# -----------------------------------------------------------------------------

def run_simulation_task(vol_len, df_final):
    res, _ = simulate_with_volume(df_final, 
                                  volume_ma_length=vol_len,
                                  use_ema_filter=True, 
                                  tp_multiplier=PARTIAL_TP_MULTIPLIER, 
                                  tp_percent=PARTIAL_TP_PERCENT,
                                  sl_multiplier=ATR_MULTIPLIER,
                                  adx_threshold=ADX_THRESHOLD,
                                  use_rsi_filter=True,
                                  rsi_overbought=RSI_OVERBOUGHT,
                                  rsi_oversold=RSI_OVERSOLD)
    return {
        'volume_ma_length': vol_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    print(f"🚀 Starting Multi-threaded Volume MA Optimization...")
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}")
    
    # 1. Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # 2. Pre-calculate indicators (Standard)
    print("📊 Pre-calculating standard indicators...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    
    # 3. Define Range for Volume MA Length
    # Trying from 10 to 100, step 5
    ma_lengths = np.arange(10, 105, 5)
    
    # Pre-calculate ALL Volume MAs to avoid re-calculating inside threads if possible, 
    # OR calculate inside simulate. Passing a huge DF with 20 columns is fine.
    print(f"📊 Pre-calculating {len(ma_lengths)} Volume MA columns...")
    for length in ma_lengths:
        df_st = calculate_volume_ma(df_st, length)
        
    df_final = df_st
    
    print(f"🔍 Testing {len(ma_lengths)} Volume MA Lengths...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation_task, length, df_final) for length in ma_lengths]
        
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 5 == 0 or (i + 1) == len(ma_lengths):
                print(f"✅ Progress: {i+1}/{len(ma_lengths)} completed...")

    # 4. Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_volume.csv", index=False)
    print("\n✅ Results saved to optimization_results_volume.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
    
    # Sort by Profit Factor
    best_pf = opt_df[opt_df['pf'] != float('inf')].sort_values(by='pf', ascending=False).head(10)
    
    print("\n🏆 Top 10 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    print("\n💎 Top 10 by Profit Factor:")
    print(best_pf.to_string(index=False))

    # Recommend
    best_overall = opt_df[opt_df['mdd'] < 20].sort_values(by='pnl_pct', ascending=False).head(1)
    if not best_overall.empty:
        print("\n🌟 RECOMMENDED VOLUME MA LENGTH:")
        print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
