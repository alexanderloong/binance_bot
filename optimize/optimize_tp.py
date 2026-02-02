
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate

def run_simulation(tp_mult, tp_pct, df_final):
    res, _ = simulate(df_final, tp_multiplier=tp_mult, tp_percent=tp_pct)
    return {
        'multiplier': round(tp_mult, 2),
        'percent': round(tp_pct, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown']
    }

def run_optimization():
    optimizer = BaseOptimizer("Partial TP Optimization")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define grid
    multipliers = np.arange(5.0, 10, 0.1) # 1.0 to 5.0
    percentages = np.arange(0.1, 0.2, 0.1) # 0.1 to 0.9
    
    tasks = []
    for tp_mult in multipliers:
        for tp_pct in percentages:
            tasks.append((tp_mult, tp_pct))

    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_tp.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (high PF and decent PnL)
        best_overall = opt_df[(opt_df['pf'] > 1.05) & (opt_df['mdd'] < 30)].sort_values(by='pnl_pct', ascending=False).head(1)
        
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED SETTING (Balanced PnL/Risk):")
            print(best_overall.to_string(index=False))
        else:
            print("\n⚠️ No highly stable settings found. Consider adjusting other strategy parameters.")

if __name__ == "__main__":
    run_optimization()
