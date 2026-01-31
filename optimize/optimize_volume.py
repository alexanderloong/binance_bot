
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER
)

def run_simulation(vol_len, df_final):
    res, _ = simulate(df_final, volume_ma_length=vol_len)
    return {
        'volume_ma_length': vol_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("Volume MA Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define Range for Volume MA Length
    # Trying from 10 to 100, step 5
    ma_lengths = np.arange(10, 105, 5)
    
    # Pre-calculate ALL Volume MAs to avoid re-calculating inside threads
    print(f"📊 Pre-calculating {len(ma_lengths)} Volume MA columns...")
    
    # We modify optimizer.df_final directly
    for length in ma_lengths:
        optimizer.df_final = DataProcessor.calculate_volume_ma(optimizer.df_final, length)
        
    tasks = [(length,) for length in ma_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_volume.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend
        best_overall = opt_df[opt_df['mdd'] < 20].sort_values(by='pnl_pct', ascending=False).head(1)
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED VOLUME MA LENGTH:")
            print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
