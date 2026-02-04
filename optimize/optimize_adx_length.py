
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ATR_MULTIPLIER, ADX_THRESHOLD,
    VOLUME_MA_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD
)

def run_simulation(adx_len, df_base):
    """
    Run simulation with a specific ADX length.
    Threshold is fixed from config.
    """
    # Recalculate ADX with the test length
    df_wk = df_base.copy()
    df_wk['ADX'] = DataProcessor.calculate_adx(df_wk, length=adx_len)
    
    # Run simulation
    res, _ = simulate(df_wk, adx_threshold=ADX_THRESHOLD, volume_ma_length=VOLUME_MA_LENGTH)
    
    return {
        'adx_length': adx_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("ADX Length Optimization")
    
    print(f"Pure Trend Following Strategy - SL Mult: {ATR_MULTIPLIER}")
    print(f"Fixed: ADX Threshold={ADX_THRESHOLD}, Volume MA Length={VOLUME_MA_LENGTH}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define ADX length range
    adx_lengths = np.arange(7, 21, 1)
    
    print(f"Testing {len(adx_lengths)} ADX lengths...")
    
    tasks = [(adx_len,) for adx_len in adx_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_adx_length.csv")
    
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
