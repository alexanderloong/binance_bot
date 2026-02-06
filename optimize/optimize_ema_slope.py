
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import (
    ATR_MULTIPLIER, 
    ADX_THRESHOLD, RSI_OVERSOLD, RSI_OVERBOUGHT, RSI_LONG_THRESHOLD,
    EMA_SLOPE_EMA_LENGTH, POSITION_SIZE_PERCENT
)

def run_simulation(slope_th, reduced_size_pct, df_final):
    """
    Run simulation with different EMA Slope Thresholds and Reduced Sizes.
    """
    # Use current best settings for other parameters
    # Note: simulate signature updated with defaults, so we override what we need
    res, _ = simulate(df_final,
                      ema_slope_threshold=slope_th,
                      reduced_size_percent=reduced_size_pct,
                      use_ema_slope_sizing=True
                      )
    return {
        'ema_slope_threshold': slope_th,
        'reduced_size_pct': reduced_size_pct,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("EMA Slope Filtering Optimization")
    
    print(f"Strategy Config: EMA {EMA_SLOPE_EMA_LENGTH} Slope")
    print(f"Normal Size: {POSITION_SIZE_PERCENT*100}%")
    
    if not optimizer.load_and_prepare_data():
        return

    # Add Slope EMA to dataframe if not present (BaseOptimizer calculates standard ones)
    if f'EMA_{EMA_SLOPE_EMA_LENGTH}' not in optimizer.df_final.columns:
         from bot.data_processor import DataProcessor
         optimizer.df_final[f'EMA_{EMA_SLOPE_EMA_LENGTH}'] = DataProcessor.calculate_ema(optimizer.df_final, length=EMA_SLOPE_EMA_LENGTH)[f'EMA_{EMA_SLOPE_EMA_LENGTH}']

    # Define ranges
    # Slope Threshold: 0.1% to 0.5% (0.001 to 0.005)
    slope_th_range = np.arange(0.001, 0.006, 0.001)
    
    # Reduced Size: 5% or 10% (0.05, 0.10)
    size_range = np.arange(0.05, 0.35, 0.05)
    
    tasks = []
    for slope in slope_th_range:
        for size in size_range:
            tasks.append((slope, size))
            
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_ema_slope.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        print("\n🌟 RECOMMENDED CONFIG:")
        print("Sorted by PnL:")
        print(opt_df.sort_values(by='pnl_pct', ascending=False).head(10).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
