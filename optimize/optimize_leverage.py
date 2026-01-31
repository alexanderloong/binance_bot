"""
Leverage & Position Size Optimizer
Finds optimal leverage and position size based on target criteria.
"""

# ============================================================================
# OPTIMIZATION TARGETS (Change these values as needed)
# ============================================================================
TARGET_MAX_DRAWDOWN = 25.0      # Maximum acceptable drawdown (%)
TARGET_MIN_PROFIT_FACTOR = 1.7  # Minimum acceptable profit factor

# Search ranges
LEVERAGE_MIN = 5
LEVERAGE_MAX = 50
LEVERAGE_STEP = 5

POSITION_SIZE_MIN = 0.10  # 10%
POSITION_SIZE_MAX = 1.00  # 100%
POSITION_SIZE_STEP = 0.05  # 5%
# ============================================================================

import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import get_backtest_data
from bot.data_processor import DataProcessor
from config import (
    EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, 
    ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH
)

def simulate_with_leverage(df, leverage, position_size):
    """Simulate trading with specific leverage and position size."""
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    stop_loss_price = 0
    partial_tp_hit = False
    take_profit_price = 0
    commission_rate = 0.0005
    
    equity_curve = [initial_balance]
    total_wins = 0
    total_losses = 0
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    ema_col = f'EMA_{EMA_LENGTH}'

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]
        price = current_candle['close']
        
        # EXIT LOGIC
        if position_amt > 0 and curr_trend == -1:
            raw_pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            position_amt = 0
            if pnl > 0:
                total_wins += pnl
            else:
                total_losses += abs(pnl)
            
        elif position_amt < 0 and curr_trend == 1:
            raw_pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            position_amt = 0
            if pnl > 0:
                total_wins += pnl
            else:
                total_losses += abs(pnl)

        # Partial TP
        if position_amt != 0 and not partial_tp_hit:
            is_tp_hit = (position_amt > 0 and price >= take_profit_price) or (position_amt < 0 and price <= take_profit_price)
            if is_tp_hit:
                close_amt = position_amt * PARTIAL_TP_PERCENT
                raw_pnl = (take_profit_price - entry_price) * close_amt if position_amt > 0 else (entry_price - take_profit_price) * abs(close_amt)
                fee = (take_profit_price * abs(close_amt)) * commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                position_amt -= close_amt
                partial_tp_hit = True
                if pnl > 0:
                    total_wins += pnl
                else:
                    total_losses += abs(pnl)

        # Stop Loss
        if position_amt > 0 and price <= stop_loss_price:
            raw_pnl = (stop_loss_price - entry_price) * position_amt
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            position_amt = 0
            if pnl > 0:
                total_wins += pnl
            else:
                total_losses += abs(pnl)
                
        elif position_amt < 0 and price >= stop_loss_price:
            raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            position_amt = 0
            if pnl > 0:
                total_wins += pnl
            else:
                total_losses += abs(pnl)

        # ENTRY LOGIC
        is_uptrend = price > ema_val
        is_downtrend = price < ema_val
        
        adx_val = current_candle['ADX']
        is_trending = adx_val > ADX_THRESHOLD
        
        rsi_val = current_candle['RSI']
        rsi_long_ok = rsi_val < RSI_OVERBOUGHT
        rsi_short_ok = rsi_val > RSI_OVERSOLD
        
        vol_ma_col = f'VOL_MA_{VOLUME_MA_LENGTH}'
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
            trade_value = balance * position_size * leverage
            entry_fee = trade_value * commission_rate
            balance -= entry_fee
            
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            
            atr_val = current_candle['ATR']
            if signal == 'LONG':
                stop_loss_price = entry_price - (atr_val * ATR_MULTIPLIER)
                take_profit_price = entry_price + (atr_val * PARTIAL_TP_MULTIPLIER)
            else:
                stop_loss_price = entry_price + (atr_val * ATR_MULTIPLIER)
                take_profit_price = entry_price - (atr_val * PARTIAL_TP_MULTIPLIER)
            
            partial_tp_hit = False
        
        equity_curve.append(balance)

    # Close final position
    if position_amt != 0:
        last_price = df.iloc[-1]['close']
        raw_pnl = (last_price - entry_price) * position_amt if position_amt > 0 else (entry_price - last_price) * abs(position_amt)
        fee = (last_price * abs(position_amt)) * commission_rate
        pnl = raw_pnl - fee
        balance += pnl
        if pnl > 0:
            total_wins += pnl
        else:
            total_losses += abs(pnl)

    # Calculate metrics
    total_pnl = balance - initial_balance
    pnl_pct = (total_pnl / initial_balance) * 100
    
    # Calculate Max Drawdown
    peak = initial_balance
    max_dd = 0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = ((equity - peak) / peak) * 100
        if dd < max_dd:
            max_dd = dd
    
    # Calculate Profit Factor
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'max_drawdown': abs(max_dd),
        'profit_factor': profit_factor
    }

def run_simulation(leverage, pos_size, df_final):
    """Run simulation with specific leverage and position size."""
    res = simulate_with_leverage(df_final, leverage, pos_size)
    
    return {
        'leverage': leverage,
        'position_size': round(pos_size, 2),
        'pnl_pct': res['pnl_pct'],
        'final_balance': res['final_balance'],
        'max_drawdown': res['max_drawdown'],
        'profit_factor': res['profit_factor']
    }

def run_optimization():
    print(f"🚀 Leverage & Position Size Optimizer")
    print(f"=" * 70)
    print(f"\n🎯 Target Criteria:")
    print(f"   • Max Drawdown ≤ {TARGET_MAX_DRAWDOWN}%")
    print(f"   • Profit Factor ≥ {TARGET_MIN_PROFIT_FACTOR}")
    print(f"\n📋 Search Range:")
    print(f"   • Leverage: {LEVERAGE_MIN}x to {LEVERAGE_MAX}x (step {LEVERAGE_STEP})")
    print(f"   • Position Size: {POSITION_SIZE_MIN*100:.0f}% to {POSITION_SIZE_MAX*100:.0f}% (step {POSITION_SIZE_STEP*100:.0f}%)")
    
    # Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # Pre-calculate indicators
    print("\n📊 Pre-calculating indicators...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    df_final = df_st

    # Define ranges
    leverage_range = np.arange(LEVERAGE_MIN, LEVERAGE_MAX + 1, LEVERAGE_STEP)
    position_size_range = np.arange(POSITION_SIZE_MIN, POSITION_SIZE_MAX + 0.01, POSITION_SIZE_STEP)
    
    tasks = []
    for lev in leverage_range:
        for pos in position_size_range:
            tasks.append((lev, pos))
    
    print(f"🔍 Testing {len(tasks)} combinations...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, lev, pos, df_final) for lev, pos in tasks]
        
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 20 == 0 or (i + 1) == len(tasks):
                print(f"✅ Progress: {i+1}/{len(tasks)} completed...")

    # Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_leverage.csv", index=False)
    print("\n✅ Results saved to optimization_results_leverage.csv")
    
    # Filter by targets
    matching = opt_df[
        (opt_df['max_drawdown'] <= TARGET_MAX_DRAWDOWN) &
        (opt_df['profit_factor'] >= TARGET_MIN_PROFIT_FACTOR)
    ].sort_values(by='pnl_pct', ascending=False)
    
    if not matching.empty:
        print(f"\n🎉 Found {len(matching)} configurations matching your criteria!")
        print("\n🏆 Top 10 Matching Configurations (sorted by PnL):")
        print(matching.head(10).to_string(index=False))
        
        # Show best by different metrics
        best_pnl = matching.iloc[0]
        best_pf = matching.sort_values(by='profit_factor', ascending=False).iloc[0]
        best_mdd = matching.sort_values(by='max_drawdown').iloc[0]
        
        print("\n" + "="*70)
        print("📌 RECOMMENDED CONFIGURATIONS:")
        print("="*70)
        
        print(f"\n💰 Best PnL (Highest Return):")
        print(f"   Leverage: {best_pnl['leverage']}x | Position Size: {best_pnl['position_size']*100:.0f}%")
        print(f"   PnL: {best_pnl['pnl_pct']:.2f}% | MDD: {best_pnl['max_drawdown']:.2f}% | PF: {best_pnl['profit_factor']:.2f}")
        
        print(f"\n💎 Best Profit Factor (Most Consistent):")
        print(f"   Leverage: {best_pf['leverage']}x | Position Size: {best_pf['position_size']*100:.0f}%")
        print(f"   PnL: {best_pf['pnl_pct']:.2f}% | MDD: {best_pf['max_drawdown']:.2f}% | PF: {best_pf['profit_factor']:.2f}")
        
        print(f"\n🛡️ Safest (Lowest Drawdown):")
        print(f"   Leverage: {best_mdd['leverage']}x | Position Size: {best_mdd['position_size']*100:.0f}%")
        print(f"   PnL: {best_mdd['pnl_pct']:.2f}% | MDD: {best_mdd['max_drawdown']:.2f}% | PF: {best_mdd['profit_factor']:.2f}")
        
    else:
        print(f"\n⚠️ No configurations found matching your criteria.")
        print(f"   Showing top 10 by PnL regardless of constraints...\n")
        
        best_overall = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
        print("🔍 Top 10 Configurations by PnL:")
        print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
