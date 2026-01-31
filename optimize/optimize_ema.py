
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import (
    ADX_LENGTH, ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, 
    ATR_MULTIPLIER, ADX_THRESHOLD, RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH
)

def run_simulation(ema_len, df_final):
    """
    Run simulation with a specific EMA length.
    We need to recalculate EMA for each iteration.
    """
    # Working on a copy to avoid side effects (though MP serialization usually handles this)
    df_st = df_final.copy()
    
    # Calculate EMA with custom length
    # Note: df_final already has standard indicators, but we need specific EMA len
    df_st = DataProcessor.calculate_ema(df_st, length=ema_len)
    
    # The new column is f'EMA_{ema_len}'
    # We map it to 'EMA_FILTER' which simulate uses if present
    df_st['EMA_FILTER'] = df_st[f'EMA_{ema_len}']
    
    res, _ = simulate(df_st)
    
    return {
        'ema_length': ema_len,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("EMA Length Optimization")
    
    print(f"Base Settings: ADX>{ADX_THRESHOLD}, RSI<{RSI_OVERBOUGHT}/>{RSI_OVERSOLD}, Vol MA>{VOLUME_MA_LENGTH}")
    
    if not optimizer.load_and_prepare_data():
        return

    # Define range for EMA Length
    # Testing from 90 to 110 with step of 1 (as per previous file content, simplified)
    # You can expand this range if needed
    ema_lengths = np.arange(85, 115, 1)
    
    tasks = [(length,) for length in ema_lengths]
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_ema.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        best_overall = opt_df[opt_df['mdd'] < 20].sort_values(by='pnl_pct', ascending=False).head(1)
        
        if not best_overall.empty:
            print("\n🌟 RECOMMENDED EMA LENGTH:")
            print(best_overall.to_string(index=False))
        else:
            print("\n⚠️ No configuration found with MDD < 20%. Showing best by PnL:")
            print(opt_df.sort_values(by='pnl_pct', ascending=False).head(1).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
