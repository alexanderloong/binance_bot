
import itertools
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate
from bot.data_processor import DataProcessor
from config import EMA_SLOPE_EMA_LENGTH, EMA_LENGTH

def run_simulation(use_ema, use_adx, use_rsi, use_vol, use_slope, use_div, df_final):
    """
    Run simulation with a specific combination of boolean indicators.
    Now includes ADX.
    """
    
    df_sim = df_final.copy()
    
    # Map EMA to filter column if it's not already there
    if f'EMA_{EMA_LENGTH}' in df_sim.columns:
        df_sim['EMA_FILTER'] = df_sim[f'EMA_{EMA_LENGTH}']
        
    # Pass parameters to simulate
    res, _ = simulate(
        df_sim, 
        use_ema_filter=use_ema,
        use_adx_filter=use_adx,
        use_rsi_filter=use_rsi,
        use_volume_filter=use_vol,
        use_ema_slope_sizing=use_slope,
        use_divergence_filter=use_div
    )
    
    return {
        'use_ema': use_ema,
        'use_adx': use_adx,
        'use_rsi': use_rsi,
        'use_vol': use_vol,
        'use_slope': use_slope,
        'use_div': use_div,
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    optimizer = BaseOptimizer("Indicator Combination Optimization")
    
    if not optimizer.load_and_prepare_data():
        return

    # Add extra indicators not in BaseOptimizer
    print(f"📊 Calculating additional indicators (EMA Slope {EMA_SLOPE_EMA_LENGTH})...")
    optimizer.df_final[f'EMA_{EMA_SLOPE_EMA_LENGTH}'] = DataProcessor.calculate_ema(
        optimizer.df_final, length=EMA_SLOPE_EMA_LENGTH
    )[f'EMA_{EMA_SLOPE_EMA_LENGTH}']

    # Define boolean combinations
    # [use_ema, use_adx, use_rsi, use_vol, use_slope, use_div]
    flags = [True, False]
    combinations = list(itertools.product(flags, repeat=6))
    
    # Create tasks
    tasks = combinations
    
    print(f"Testing {len(combinations)} combinations of indicators...")
    
    results = optimizer.run_parallel(tasks, run_simulation)
    
    opt_df = optimizer.save_and_analyze(results, "optimization_results_indicators.csv")
    
    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall
        print("\n🔍 Findings (MDD < 20%):")
        valid_mdd = opt_df[opt_df['mdd'] < 20]
        
        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL:")
            print(valid_mdd.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))
            
            print("\n🛡️ BEST BY PROFIT FACTOR:")
            print(valid_mdd.sort_values(by='pf', ascending=False).head(5).to_string(index=False))
        else:
            print("\n⚠️ No configuration found with MDD < 20%. Showing best by PnL:")
            print(opt_df.sort_values(by='pnl_pct', ascending=False).head(5).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
