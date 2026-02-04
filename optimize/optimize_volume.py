
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ATR_MULTIPLIER,
    ADX_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD
)

def run_simulation(vol_len, df_final):
    """
    Run simulation with a specific Volume MA length.
    ADX threshold is fixed from config.
    """
    # Work on a copy to avoid side effects
    df_wk = df_final.copy()
    
    # Calculate specific Volume MA
    # DataProcessor.calculate_volume_ma adds f'VOL_MA_{length}' column
    df_wk = DataProcessor.calculate_volume_ma(df_wk, length=vol_len)
    
    # Run simulation with specific Volume MA length
    res, _ = simulate(df_wk, adx_threshold=ADX_THRESHOLD, volume_ma_length=vol_len)
    
    return {
        'vol_ma_len': vol_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("Volume MA Length Optimization")
    
    print(f"Pure Trend Following Strategy - SL Mult: {ATR_MULTIPLIER}")
    print(f"Fixed: ADX Threshold={ADX_THRESHOLD}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define Volume MA length range
    vol_lengths = np.arange(170, 183, 1)
    
    print(f"Testing {len(vol_lengths)} Volume MA lengths...")
    
    tasks = [(vol_len,) for vol_len in vol_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_volume.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Filter for acceptable drawdown (e.g. < 20%)
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
