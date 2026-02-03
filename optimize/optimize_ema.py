
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR
)

import itertools

def run_simulation(ema_len, df_final):
    """
    Run simulation with a specific EMA length.
    SuperTrend parameters are fixed from config.
    """
    
    # Working on a copy
    df_st = df_final.copy()
    
    # Calculate EMA
    df_st = DataProcessor.calculate_ema(df_st, length=ema_len)
    
    # Calculate SuperTrend with config params
    df_st = DataProcessor.calculate_supertrend(df_st)
    
    # Map EMA to filter column
    df_st['EMA_FILTER'] = df_st[f'EMA_{ema_len}']
    
    # Pass parameters to simulate
    res, _ = simulate(df_st)
    
    return {
        'ema_length': ema_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("EMA Length Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    print(f"Fixed: SuperTrend Length={SUPERTREND_LENGTH}, SuperTrend Factor={SUPERTREND_FACTOR}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define EMA length range
    ema_lengths = np.arange(95, 106, 1)
    
    # Create tasks
    tasks = [(ema_len,) for ema_len in ema_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_ema.csv")
    
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
