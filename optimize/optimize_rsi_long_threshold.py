
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from config import (
    ATR_MULTIPLIER, 
    ADX_THRESHOLD, RSI_OVERSOLD, RSI_OVERBOUGHT
)

def run_simulation(rsi_long_th, df_final):
    """
    Run simulation with a specific RSI Long Threshold.
    """
    # Use current best settings for other parameters
    res, _ = simulate(df_final,
                      rsi_long_threshold=rsi_long_th,
                      rsi_overbought=RSI_OVERBOUGHT,
                      rsi_oversold=RSI_OVERSOLD)
    return {
        'rsi_long_threshold': rsi_long_th,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("RSI Long Threshold Optimization")
    
    print(f"Strategy Config: OB={RSI_OVERBOUGHT}, OS={RSI_OVERSOLD}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for RSI Long Threshold (e.g. 30 to 55)
    rsi_th_range = np.arange(30, 60, 1)
    
    tasks = [(th,) for th in rsi_th_range]
            
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_rsi_long_threshold.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        valid_mdd = opt_df[opt_df['mdd'] < 20]
        
        if not valid_mdd.empty:
            print("\n🌟 RECOMMENDED CONFIG (MDD < 20%):")
            print("Sorted by PnL:")
            print(valid_mdd.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))
            
            print("\nSorted by Profit Factor:")
            print(valid_mdd.sort_values(by='pf', ascending=False).head(5).to_string(index=False))
        else:
            print("\n⚠️ No configuration found with MDD < 20%. Best available:")
            print(opt_df.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
