
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT

def run_simulation(sl_mult, df_final):
    # Use the current best TP settings we found earlier
    res, _ = simulate(df_final, sl_multiplier=sl_mult)
    return {
        'atr_multiplier': round(sl_mult, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ATR Multiplier Optimization")
    
    print(f"Stats: Using TP Multiplier: {PARTIAL_TP_MULTIPLIER}, TP Percent: {PARTIAL_TP_PERCENT}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for ATR Multiplier
    # Testing from 0.5 to 5.0 with 0.1 step
    sl_multipliers = np.arange(0.5, 5.1, 0.1)
    
    tasks = [(sl,) for sl in sl_multipliers]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_atr.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance between high PnL and low MDD)
        best_overall = opt_df[opt_df['mdd'] < 25].sort_values(by='pnl_pct', ascending=False).head(1)
        
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED ATR SETTING:")
            print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
