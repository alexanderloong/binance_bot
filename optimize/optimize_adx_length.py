
import numpy as np
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ProcessPoolExecutor, as_completed
from backtest import get_backtest_data, simulate
from bot.data_processor import DataProcessor
from config import (
    ATR_MULTIPLIER, EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR,
    ADX_THRESHOLD, ATR_LENGTH, RSI_LENGTH, VOLUME_MA_LENGTH
)

def run_simulation(adx_length, df_raw, df_base):
    """
    Run simulation with a specific ADX length.
    ADX needs to be recalculated for each length.
    """
    # Work on a copy to avoid side effects
    df_wk = df_base.copy()
    
    # Recalculate ADX with specific length
    df_wk['ADX'] = DataProcessor.calculate_adx(df_raw, length=adx_length)
    
    # Run simulation with default threshold
    res, _ = simulate(df_wk, adx_threshold=ADX_THRESHOLD, volume_ma_length=VOLUME_MA_LENGTH)
    
    return {
        'adx_length': adx_length,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    print("🚀 Starting ADX Length Optimization...")
    print(f"Pure Trend Following Strategy - SL Mult: {ATR_MULTIPLIER}")
    print(f"Fixed: ADX Threshold={ADX_THRESHOLD}")
    
    # 1. Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # 2. Pre-calculate base indicators (everything except ADX)
    print("📊 Pre-calculating base indicators...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    
    df_base = df_st  # Base dataframe without ADX
    df_raw = df      # Raw dataframe for ADX calculation

    # Define ADX length range
    adx_lengths = np.arange(10, 30, 1)  # 10 to 29
    
    print(f"🔍 Testing {len(adx_lengths)} ADX lengths...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, length, df_raw, df_base) for length in adx_lengths]
        
        for i, future in enumerate(as_completed(futures)):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                print(f"❌ Error in task: {e}")

            if (i + 1) % 5 == 0 or (i + 1) == len(adx_lengths):
                print(f"✅ Progress: {i+1}/{len(adx_lengths)} completed...")
    
    # Save and analyze results
    if not results:
        print("⚠️ No results to analyze.")
        return
        
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_adx_length.csv", index=False)
    print(f"\n✅ Results saved to optimization_results_adx_length.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
    print(f"\n🏆 Top 10 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    # Sort by Profit Factor
    valid_pf = opt_df[opt_df['pf'] != float('inf')]
    best_pf = valid_pf.sort_values(by='pf', ascending=False).head(10)
    print(f"\n💎 Top 10 by Profit Factor:")
    print(best_pf.to_string(index=False))
    
    # Filter for acceptable drawdown (e.g. < 20%)
    valid_mdd = opt_df[opt_df['mdd'] < 20]
    
    if not valid_mdd.empty:
        print("\n🌟 RECOMMENDED CONFIG (MDD < 20%):")
        print("Sorted by PnL:")
        print(valid_mdd.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))
        
        print("\nSorted by Profit Factor:")
        print(valid_mdd.sort_values(by='pf', ascending=False).head(5).to_string(index=False))
    else:
        print("\n⚠️ No configuration found with MDD < 20%. Best available:")
        print(opt_df.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
