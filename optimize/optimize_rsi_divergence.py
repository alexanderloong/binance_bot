
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import (
    ATR_MULTIPLIER, 
    ADX_THRESHOLD, RSI_OVERSOLD, RSI_OVERBOUGHT, RSI_LONG_THRESHOLD,
    EMA_SLOPE_EMA_LENGTH, POSITION_SIZE_PERCENT,
    RSI_DIV_LOOKBACK, RSI_DIV_MIN_RSI, RSI_DIV_PARTIAL_CLOSE_PCT
)

def run_simulation(min_rsi, partial_pct, df_final):
    """
    Run simulation with different Divergence parameters.
    """
    res, _ = simulate(df_final,
                      use_divergence_filter=True,
                      div_min_rsi=min_rsi,
                      div_partial_pct=partial_pct,
                      # Keep default lookback for now
                      div_lookback=RSI_DIV_LOOKBACK
                      )
    return {
        'min_rsi': min_rsi,
        'partial_pct': partial_pct,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("RSI Bearish Divergence Optimization")
    
    print(f"Strategy Config: Div Lookback={RSI_DIV_LOOKBACK}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Check if we need slope EMA? Yes, default simulate uses it.
    # BaseOptimizer might not load it unless we force it.
    if f'EMA_{EMA_SLOPE_EMA_LENGTH}' not in optimizer.df_final.columns:
         from bot.data_processor import DataProcessor
         optimizer.df_final[f'EMA_{EMA_SLOPE_EMA_LENGTH}'] = DataProcessor.calculate_ema(optimizer.df_final, length=EMA_SLOPE_EMA_LENGTH)[f'EMA_{EMA_SLOPE_EMA_LENGTH}']

    # Define ranges
    # Min RSI: 55 to 70
    min_rsi_range = np.arange(65, 80, 1)
    
    # Partial Close %: 20% to 60%
    partial_pct_range = np.arange(0.1, 0.3, 0.05)
    
    tasks = []
    for rsi in min_rsi_range:
        for pct in partial_pct_range:
            tasks.append((rsi, pct))
            
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_rsi_divergence.csv")
    
    if opt_df is not None and not opt_df.empty:
        print("\n🌟 RECOMMENDED CONFIG (Sorted by PnL):")
        print(opt_df.sort_values(by='pnl_pct', ascending=False).head(10).to_string(index=False))
        
        print("\n💎 SORTED BY PROFIT FACTOR:")
        valid_pf = opt_df[opt_df['pf'] != float('inf')]
        print(valid_pf.sort_values(by='pf', ascending=False).head(10).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
