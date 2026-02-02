
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER, ADX_THRESHOLD

def run_simulation(rsi_ob, rsi_os, df_final):
    # Use current best settings for other parameters
    res, _ = simulate(df_final,
                      rsi_overbought=rsi_ob,
                      rsi_oversold=rsi_os)
    return {
        'rsi_overbought': rsi_ob,
        'rsi_oversold': rsi_os,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("RSI Threshold Optimization")
    
    print(f"Current Settings: ADX Th: {ADX_THRESHOLD}, TP Mult: {PARTIAL_TP_MULTIPLIER}, TP%: {PARTIAL_TP_PERCENT}, SL Mult: {ATR_MULTIPLIER}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for RSI Thresholds
    # Overbought: 60 to 85, steps of 2
    # Oversold: 15 to 40, steps of 2
    rsi_ob_range = np.arange(60, 71, 1)
    rsi_os_range = np.arange(30, 41, 1)
    
    tasks = []
    for ob in rsi_ob_range:
        for os in rsi_os_range:
            tasks.append((ob, os))
            
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_rsi.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        best_overall = opt_df[opt_df['mdd'] < 20].sort_values(by='pnl_pct', ascending=False).head(1)
        
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED RSI THRESHOLDS:")
            print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
