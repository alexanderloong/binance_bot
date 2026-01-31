
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER

def run_simulation(adx_th, df_final):
    # Use current best settings for other parameters
    res, _ = simulate(df_final, adx_threshold=adx_th)
    return {
        'adx_threshold': round(adx_th, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ADX Threshold Optimization")
    
    print(f"Current Settings: TP Mult: {PARTIAL_TP_MULTIPLIER}, TP%: {PARTIAL_TP_PERCENT}, SL Mult: {ATR_MULTIPLIER}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for ADX Threshold
    # Testing from 10 to 40 with 1 step
    adx_thresholds = np.arange(10, 41, 1)
    
    # Needs to be a list of tuples for run_parallel
    tasks = [(th,) for th in adx_thresholds]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_adx.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Limit MDD and find highest PnL)
        best_overall = opt_df[opt_df['mdd'] < 25].sort_values(by='pnl_pct', ascending=False).head(1)
        
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED ADX THRESHOLD:")
            print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
