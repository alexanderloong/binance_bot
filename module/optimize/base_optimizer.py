
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import os

# Add project root to sys.path if not present
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from module.backtest.orchestrator import get_backtest_data
from module.bot.data_processor import DataProcessor
from resource.config import (
    EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, 
    ATR_LENGTH, VOLUME_MA_LENGTH
)

class BaseOptimizer:
    def __init__(self, name="Generic Optimizer"):
        self.name = name
        self.df_final = None

    def load_and_prepare_data(self):
        """Loads data and pre-calculates the standard indicators."""
        print(f"🚀 Starting {self.name}...")
        
        # 1. Load data
        df = get_backtest_data()
        if df is None:
            print("❌ Could not load data.")
            return False

        # 2. Pre-calculate technical indicators
        print("📊 Pre-calculating indicators...")
        df_ha = DataProcessor.calculate_heikin_ashi(df)
        df_st = DataProcessor.calculate_supertrend(df_ha)
        df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
        df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
        df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
        
        self.df_final = df_st
        return True

    def run_parallel(self, tasks, worker_func):
        """Runs the worker function in parallel over the list of tasks."""
        if self.df_final is None:
            print("❌ Data not loaded. Call load_and_prepare_data() first.")
            return []

        print(f"🔍 Testing {len(tasks)} combinations using multi-processing...")
        
        results = []
        with ProcessPoolExecutor() as executor:
            # We must pass df_final to the worker. 
            # Note: passing large has overhead, but it's what was done in original files.
            # Using shared memory would be better but keeping it simple for now to match original behavior.
            
            # The worker_func is expected to take (*args, df_final)
            futures = [executor.submit(worker_func, *task_args, self.df_final) for task_args in tasks]
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    print(f"❌ Error in task: {e}")

                if (i + 1) % 20 == 0 or (i + 1) == len(tasks):
                    print(f"✅ Progress: {i+1}/{len(tasks)} completed...")
                    
        return results

    def save_and_analyze(self, results, filename, top_n=10):
        """Saves results to CSV and prints analysis."""
        if not results:
            print("⚠️ No results into analyze.")
            return

        opt_df = pd.DataFrame(results)
        # Save in the same directory as the optimizer script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(current_dir, filename)
        opt_df.to_csv(save_path, index=False)
        print(f"\n✅ Results saved to {save_path}")
        
        # Sort by PnL
        if 'pnl_pct' in opt_df.columns:
            best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(top_n)
            print(f"\n🏆 Top {top_n} by Net Profit (PnL %):")
            print(best_pnl.to_string(index=False))
        
        # Sort by Profit Factor
        if 'pf' in opt_df.columns:
            # Filter out inf
            valid_pf = opt_df[opt_df['pf'] != float('inf')]
            best_pf = valid_pf.sort_values(by='pf', ascending=False).head(top_n)
            print(f"\n💎 Top {top_n} by Profit Factor:")
            print(best_pf.to_string(index=False))
        elif 'profit_factor' in opt_df.columns:
             # Standardize column name usage if possible, but handle both for now
            valid_pf = opt_df[opt_df['profit_factor'] != float('inf')]
            best_pf = valid_pf.sort_values(by='profit_factor', ascending=False).head(top_n)
            print(f"\n💎 Top {top_n} by Profit Factor:")
            print(best_pf.to_string(index=False))

        return opt_df
