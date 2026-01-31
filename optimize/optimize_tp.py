import pandas as pd
import numpy as np
from backtest import simulate, get_backtest_data
from bot.data_processor import DataProcessor
from config import EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, ATR_LENGTH, RSI_LENGTH, VOLUME_MA_LENGTH

from concurrent.futures import ProcessPoolExecutor, as_completed

def run_simulation(tp_mult, tp_pct, df_final):
    res, _ = simulate(df_final, use_ema_filter=True, tp_multiplier=tp_mult, tp_percent=tp_pct, use_rsi_filter=True, use_volume_filter=True)
    return {
        'multiplier': round(tp_mult, 2),
        'percent': round(tp_pct, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown']
    }

def run_optimization():
    print("🚀 Starting Multi-threaded Optimization for Partial TP Settings...")
    
    # 1. Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # 2. Pre-calculate technical indicators (only once)
    print("📊 Pre-calculating indicators...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    df_final = df_st

    # 3. Define grid
    multipliers = np.arange(1.0, 5.5, 0.5) # 1.0 to 5.0
    percentages = np.arange(0.1, 1.0, 0.1) # 0.1 to 0.9
    
    tasks = []
    for tp_mult in multipliers:
        for tp_pct in percentages:
            tasks.append((tp_mult, tp_pct))

    print(f"🔍 Testing {len(tasks)} combinations using multi-processing...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        # Submit all tasks
        futures = [executor.submit(run_simulation, m, p, df_final) for m, p in tasks]
        
        # Collect results as they complete
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 10 == 0 or (i + 1) == len(tasks):
                print(f"✅ Progress: {i+1}/{len(tasks)} completed...")

    # 4. Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results.csv", index=False)
    print("\n✅ Results saved to optimization_results.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(5)
    # Sort by Profit Factor (higher is better)
    best_pf = opt_df[opt_df['pf'] != float('inf')].sort_values(by='pf', ascending=False).head(5)
    
    print("\n🏆 Top 5 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    print("\n💎 Top 5 by Profit Factor:")
    print(best_pf.to_string(index=False))

    # Recommend the best overall (high PF and decent PnL)
    # We can create a score: PnL / MDD or just look at PF >= 1.2
    best_overall = opt_df[(opt_df['pf'] > 1.05) & (opt_df['mdd'] < 30)].sort_values(by='pnl_pct', ascending=False).head(1)
    
    if not best_overall.empty:
        print("\n🌟 RECOMMENDED SETTING (Balanced PnL/Risk):")
        print(best_overall.to_string(index=False))
    else:
        print("\n⚠️ No highly stable settings found. Consider adjusting other strategy parameters.")

if __name__ == "__main__":
    run_optimization()
