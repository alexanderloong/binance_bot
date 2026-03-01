
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate

def run_simulation(roi_tp, df_final):
    # Test ROI Take Profit
    res, _ = simulate(df_final, roi_tp=roi_tp)
    return {
        'roi_tp_pct': round(roi_tp, 1),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ROI Take Profit Optimization")
    
    print("Strategy: Pure Trend Following + ROI Take Profit")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for ROI TP (%)
    # Testing from 10% to 500% ROI
    # 0 means disabled
    roi_targets = [0] + list(np.arange(77, 78, 0.1))
    
    tasks = [(target,) for target in roi_targets]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_roi_tp.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Sort by PnL and show top 5
        print("\n🌟 BEST ROI TP SETTINGS:")
        print(opt_df.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))
        
        # Compare with 0 (No TP)
        no_tp = opt_df[opt_df['roi_tp_pct'] == 0].iloc[0]
        print(f"\n📈 Baseline (No TP): PnL: {no_tp['pnl_pct']:.2f}%, MDD: {no_tp['mdd']:.2f}%, PF: {no_tp['pf']:.2f}")

if __name__ == "__main__":
    run_optimization()
