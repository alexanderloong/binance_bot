
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH, EMA_LENGTH, SUPERTREND_FACTOR
)

import itertools

def run_simulation(st_len, df_final):
    """
    Run simulation with a specific SuperTrend length.
    EMA and SuperTrend factor are fixed from config.
    """
    
    # Working on a copy
    df_st = df_final.copy()
    
    # Calculate EMA with config param
    df_st = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)
    
    # Calculate SuperTrend with specific length
    df_st = DataProcessor.calculate_supertrend(df_st, length=st_len, multiplier=SUPERTREND_FACTOR)
    
    # Map EMA to filter column
    df_st['EMA_FILTER'] = df_st[f'EMA_{EMA_LENGTH}']
    
    # Pass parameters to simulate
    res, _ = simulate(df_st, st_length=st_len, st_factor=SUPERTREND_FACTOR)
    
    return {
        'st_length': st_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("SuperTrend Length Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    print(f"Fixed: EMA Length={EMA_LENGTH}, SuperTrend Factor={SUPERTREND_FACTOR}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define SuperTrend length range
    st_lengths = np.arange(10, 22, 1)
    
    # Create tasks
    tasks = [(st_len,) for st_len in st_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_st_length.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        print("\n🔍 Findings (MDD < 20%):")
        valid_mdd = opt_df[opt_df['mdd'] < 20]
        
        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL:")
            print(valid_mdd.sort_values(by='pnl_pct', ascending=False).head(3).to_string(index=False))
            
            print("\n🛡️ BEST BY PROFIT FACTOR:")
            print(valid_mdd.sort_values(by='pf', ascending=False).head(3).to_string(index=False))
        else:
            print("\n⚠️ No configuration found with MDD < 20%. Showing best by PnL:")
            print(opt_df.sort_values(by='pnl_pct', ascending=False).head(3).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
