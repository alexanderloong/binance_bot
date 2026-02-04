
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_LENGTH, ATR_LENGTH, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH, EMA_LENGTH, SUPERTREND_LENGTH
)

import itertools

def run_simulation(st_fac, df_final):
    """
    Run simulation with a specific SuperTrend factor.
    EMA and SuperTrend length are fixed from config.
    """
    
    # Working on a copy
    df_st = df_final.copy()
    
    # Calculate EMA with config param
    df_st = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)
    
    # Calculate SuperTrend with specific factor
    df_st = DataProcessor.calculate_supertrend(df_st, length=SUPERTREND_LENGTH, multiplier=st_fac)
    
    # Map EMA to filter column
    df_st['EMA_FILTER'] = df_st[f'EMA_{EMA_LENGTH}']
    
    # Pass parameters to simulate
    res, _ = simulate(df_st, st_length=SUPERTREND_LENGTH, st_factor=st_fac)
    
    return {
        'st_factor': st_fac,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("SuperTrend Factor Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    print(f"Fixed: EMA Length={EMA_LENGTH}, SuperTrend Length={SUPERTREND_LENGTH}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define SuperTrend factor range
    st_factors = np.arange(1.2, 2.1, 0.1)
    
    # Create tasks
    tasks = [(st_fac,) for st_fac in st_factors]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_st_factor.csv")
    
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
