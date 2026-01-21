import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, POSITION_SIZE_PERCENT, LEVERAGE
import os
from datetime import datetime, date

def simulate(df_final, use_ema_filter=True):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    trades = []
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    ema_col = f'EMA_{EMA_LENGTH}'

    for i in range(1, len(df_final)):
        current_candle = df_final.iloc[i]
        prev_candle = df_final.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]
        
        price = current_candle['close']
        timestamp = current_candle['timestamp']
        
        # 1. EXIT LOGIC
        if position_amt > 0 and curr_trend == -1:
            pnl = (price - entry_price) * position_amt
            trades.append({'type': 'CLOSE_LONG', 'time': timestamp, 'price': price, 'pnl': pnl})
            balance += pnl
            position_amt = 0
            
        elif position_amt < 0 and curr_trend == 1:
            pnl = (entry_price - price) * abs(position_amt)
            trades.append({'type': 'CLOSE_SHORT', 'time': timestamp, 'price': price, 'pnl': pnl})
            balance += pnl
            position_amt = 0

        # 2. ENTRY LOGIC
        is_uptrend_long = price > ema_val if use_ema_filter else True
        is_downtrend_short = price < ema_val if use_ema_filter else True
        
        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend_long:
            signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend_short:
            signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * POSITION_SIZE_PERCENT * LEVERAGE
            amount = trade_value / price
            
            if signal == 'LONG':
                position_amt = amount
                entry_price = price
                trades.append({'type': 'OPEN_LONG', 'time': timestamp, 'price': price})
            elif signal == 'SHORT':
                position_amt = -amount
                entry_price = price
                trades.append({'type': 'OPEN_SHORT', 'time': timestamp, 'price': price})

    # Close final position
    if position_amt != 0:
        last_price = df_final.iloc[-1]['close']
        pnl = (last_price - entry_price) * position_amt if position_amt > 0 else (entry_price - last_price) * abs(position_amt)
        balance += pnl
        trades.append({'type': 'FINAL_CLOSE', 'time': df_final.iloc[-1]['timestamp'], 'price': last_price, 'pnl': pnl})

    # Stats calculation
    total_trades = sum(1 for t in trades if 'CLOSE' in t['type'])
    wins = sum(1 for t in trades if 'CLOSE' in t['type'] and t['pnl'] > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl_total = balance - initial_balance
    pnl_pct = (pnl_total / initial_balance) * 100
    
    # Max Drawdown
    curr_equity = initial_balance
    peak = initial_balance
    mdd = 0
    for t in trades:
        if 'pnl' in t:
            curr_equity += t['pnl']
            peak = max(peak, curr_equity)
            drawdown = (peak - curr_equity) / peak
            mdd = max(mdd, drawdown)

    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'max_drawdown': mdd * 100
    }

def run_comparison():
    print(f"--- Multi-Strategy Comparison for {SYMBOL} ({TIMEFRAME}) ---")
    
    cache_file = "backtest_data.csv"
    df = None
    
    if os.path.exists(cache_file):
        print("Loading data from local cache...")
        df = pd.read_csv(cache_file)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('Asia/Ho_Chi_Minh')
    
    if df is None or df.empty:
        client = ExchangeClient()
        df = client.fetch_history(limit=1000)
        if df is not None:
            df.to_csv(cache_file, index=False)
    
    if df is None or df.empty:
        print("No data.")
        return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    
    # Calculate different EMAs
    df_final = df_st.copy()
    for length in [20, 50, 100]:
        df_final = DataProcessor.calculate_ema(df_final, length=length)

    strategies = [
        ("No EMA", False, 0),
        ("EMA 20", True, 20),
        ("EMA 50", True, 50),
        ("EMA 100", True, 100)
    ]
    
    results = []
    for name, use_ema, length in strategies:
        # Override global EMA_LENGTH for simulation
        if use_ema:
            # We need to hack the simulate slightly to use the correct column
            # For simplicity, let's just create a temporary column named 'EMA_TEMP'
            df_sim = df_final.copy()
            df_sim['EMA_FILTER'] = df_sim[f'EMA_{length}']
            # We modify simulate to accept a custom EMA column name or just use a fixed one
        else:
            df_sim = df_final.copy()
            df_sim['EMA_FILTER'] = df_sim['close'] # Dummy
            
        res = simulate_custom(df_sim, use_ema_filter=use_ema)
        res['name'] = name
        results.append(res)

    print("\n" + "="*70)
    print(f"{'Strategy':<15} | {'Balance':<12} | {'PnL %':<10} | {'Trades':<8} | {'Win%':<8} | {'MaxDD':<8}")
    print("-" * 70)
    for r in results:
        print(f"{r['name']:<15} | {r['final_balance']:>10.1f} | {r['pnl_pct']:>8.2f}% | {r['total_trades']:>8} | {r['win_rate']:>7.1f}% | {r['max_drawdown']:>7.1f}%")
    print("="*70)

def simulate_custom(df, use_ema_filter=True):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    trades = []
    commission_rate = 0.0005 # 0.05% (Standard Binance Fees for Taker/Market Order)
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle['EMA_FILTER']
        
        price = current_candle['close']
        
        # EXIT LOGIC
        if position_amt > 0 and curr_trend == -1:
            pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            balance += (pnl - fee)
            trades.append({'pnl': pnl - fee})
            position_amt = 0
            
        elif position_amt < 0 and curr_trend == 1:
            pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            balance += (pnl - fee)
            trades.append({'pnl': pnl - fee})
            position_amt = 0

        # ENTRY LOGIC
        is_uptrend = price > ema_val if use_ema_filter else True
        is_downtrend = price < ema_val if use_ema_filter else True
        
        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend:
            signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend:
            signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * POSITION_SIZE_PERCENT * LEVERAGE
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            # Pay entry fee
            balance -= (trade_value * commission_rate)

    # CRITICAL FIX: Close final position at last price
    if position_amt != 0:
        last_price = df.iloc[-1]['close']
        if position_amt > 0:
            pnl = (last_price - entry_price) * position_amt
        else:
            pnl = (entry_price - last_price) * abs(position_amt)
        fee = (last_price * abs(position_amt)) * commission_rate
        balance += (pnl - fee)
        trades.append({'pnl': pnl - fee})

    total_trades = len(trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl_total = balance - initial_balance
    pnl_pct = (pnl_total / initial_balance) * 100
    
    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'max_drawdown': 0 
    }

if __name__ == "__main__":
    run_comparison()
