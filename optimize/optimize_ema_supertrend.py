
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_LENGTH, ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH
)

import itertools

def run_simulation(params, df_final):
    """
    Run simulation with a specific combination of EMA length, SuperTrend Length, and Factor.
    """
    ema_len, st_len, st_fac = params
    
    # Working on a copy
    df_st = df_final.copy()
    
    # Calculate EMA
    df_st = DataProcessor.calculate_ema(df_st, length=ema_len)
    
    # Calculate SuperTrend with specific params
    df_st = DataProcessor.calculate_supertrend(df_st, length=st_len, multiplier=st_fac)
    
    # Map EMA to filter column
    df_st['EMA_FILTER'] = df_st[f'EMA_{ema_len}']
    
    # Pass parameters to simulate
    res, _ = simulate(df_st, st_length=st_len, st_factor=st_fac)
    
    return {
        'ema_length': ema_len,
        'st_length': st_len,
        'st_factor': st_fac,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("EMA & SuperTrend Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define ranges
    ema_lengths = np.arange(106, 108, 1)
    st_lengths = np.arange(15, 18, 1)
    st_factors = np.arange(1.4, 1.51, 0.01)
    
    # Create combinations
    combinations = list(itertools.product(ema_lengths, st_lengths, st_factors))
    
    tasks = [(c,) for c in combinations]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_ema_st.csv")
    
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
