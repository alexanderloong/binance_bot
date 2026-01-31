import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import simulate, get_backtest_data
from bot.data_processor import DataProcessor
from config import (
    SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, 
    ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH
)

def run_simulation(ema_len, df_ha, df):
    """
    Run simulation with a specific EMA length.
    We need to recalculate EMA and SuperTrend for each iteration.
    """
    # Calculate SuperTrend (depends on Heikin Ashi)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    
    # Calculate EMA with custom length
    df_st[f'EMA_{ema_len}'] = DataProcessor.calculate_ema(df_st.copy(), length=ema_len)[f'EMA_{ema_len}']
    
    # Add other indicators
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    
    # Temporarily rename EMA column to match simulate expectations
    df_st['EMA_FILTER'] = df_st[f'EMA_{ema_len}']
    
    res, _ = simulate(df_st, 
                      use_ema_filter=True, 
                      tp_multiplier=PARTIAL_TP_MULTIPLIER, 
                      tp_percent=PARTIAL_TP_PERCENT,
                      sl_multiplier=ATR_MULTIPLIER,
                      adx_threshold=ADX_THRESHOLD,
                      use_rsi_filter=True,
                      rsi_overbought=RSI_OVERBOUGHT,
                      rsi_oversold=RSI_OVERSOLD,
                      use_volume_filter=True)
    
    return {
        'ema_length': ema_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    print(f"🚀 Starting Multi-threaded EMA Length Optimization...")
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    
    # 1. Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # 2. Pre-calculate Heikin Ashi (common for all EMA lengths)
    print("📊 Pre-calculating Heikin Ashi candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    
    # 3. Define range for EMA Length
    # Testing from 20 to 200 with step of 10
    ema_lengths = np.arange(90, 110, 1)
    
    print(f"🔍 Testing {len(ema_lengths)} EMA Lengths...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, length, df_ha, df) for length in ema_lengths]
        
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 5 == 0 or (i + 1) == len(ema_lengths):
                print(f"✅ Progress: {i+1}/{len(ema_lengths)} completed...")

    # 4. Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_ema.csv", index=False)
    print("\n✅ Results saved to optimization_results_ema.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
    
    # Sort by Profit Factor
    best_pf = opt_df[opt_df['pf'] != float('inf')].sort_values(by='pf', ascending=False).head(10)
    
    print("\n🏆 Top 10 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    print("\n💎 Top 10 by Profit Factor:")
    print(best_pf.to_string(index=False))

    # Recommend the best overall (Balance MDD and PnL)
    best_overall = opt_df[opt_df['mdd'] < 20].sort_values(by='pnl_pct', ascending=False).head(1)
    
    if not best_overall.empty:
        print("\n🌟 RECOMMENDED EMA LENGTH:")
        print(best_overall.to_string(index=False))
    else:
        print("\n⚠️ No configuration found with MDD < 20%. Showing best by PnL:")
        print(opt_df.sort_values(by='pnl_pct', ascending=False).head(1).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
