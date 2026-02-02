
import numpy as np
import pandas as pd
import itertools
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER

def run_simulation(params, df_final):
    """
    Run simulation with ADX Threshold and Volume MA Length.
    """
    adx_th, vol_len = params
    
    # Work on a copy to avoid side effects
    df_wk = df_final.copy()
    
    # Calculate specific Volume MA
    # DataProcessor.calculate_volume_ma adds f'VOL_MA_{length}' column
    df_wk = DataProcessor.calculate_volume_ma(df_wk, length=vol_len)
    
    # Run simulation
    res, _ = simulate(df_wk, adx_threshold=adx_th, volume_ma_length=vol_len)
    
    return {
        'adx_threshold': adx_th,
        'vol_ma_len': vol_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ADX & Volume Filter Optimization")
    
    print(f"Current Settings: TP Mult: {PARTIAL_TP_MULTIPLIER}, TP%: {PARTIAL_TP_PERCENT}, SL Mult: {ATR_MULTIPLIER}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define ranges
    # ADX Threshold: 15 to 35
    adx_thresholds = np.arange(19, 22, 1)
    
    # Volume MA Length: 20 to 120, step 5
    vol_lengths = np.arange(145, 160, 1)
    
    # Create combinations
    combinations = list(itertools.product(adx_thresholds, vol_lengths))
    
    print(f"Testing {len(combinations)} combinations...")
    
    tasks = [(c,) for c in combinations]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_adx_vol.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Filter for acceptable drawdown (e.g. < 20%)
        # Then find best PnL
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
