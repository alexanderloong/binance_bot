
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER,
    VOLUME_MA_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD
)

def run_simulation(adx_th, df_final):
    """
    Run simulation with a specific ADX threshold.
    Volume MA length is fixed from config.
    """
    # Work on a copy to avoid side effects
    df_wk = df_final.copy()
    
    # Run simulation with specific ADX threshold
    res, _ = simulate(df_wk, adx_threshold=adx_th, volume_ma_length=VOLUME_MA_LENGTH)
    
    return {
        'adx_threshold': adx_th,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ADX Threshold Optimization")
    
    print(f"Current Settings: TP Mult: {PARTIAL_TP_MULTIPLIER}, TP%: {PARTIAL_TP_PERCENT}, SL Mult: {ATR_MULTIPLIER}")
    print(f"Fixed: Volume MA Length={VOLUME_MA_LENGTH}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define ADX threshold range
    adx_thresholds = np.arange(15, 30, 1)
    
    print(f"Testing {len(adx_thresholds)} ADX thresholds...")
    
    tasks = [(adx_th,) for adx_th in adx_thresholds]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_adx.csv")
    
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
