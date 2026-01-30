import pandas as pd
import numpy as np
from backtest import simulate, get_backtest_data
from bot.data_processor import DataProcessor
from config import EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, ATR_MULTIPLIER
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_simulation(adx_th, df_final):
    # Use current best settings for other parameters
    res, _ = simulate(df_final, 
                      use_ema_filter=True, 
                      tp_multiplier=PARTIAL_TP_MULTIPLIER, 
                      tp_percent=PARTIAL_TP_PERCENT,
                      sl_multiplier=ATR_MULTIPLIER,
                      adx_threshold=adx_th)
    return {
        'adx_threshold': round(adx_th, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    print(f"🚀 Starting Multi-threaded ADX Threshold Optimization...")
    print(f"Current Settings: TP Mult: {PARTIAL_TP_MULTIPLIER}, TP%: {PARTIAL_TP_PERCENT}, SL Mult: {ATR_MULTIPLIER}")
    
    # 1. Load data
    df = get_backtest_data()
    if df is None:
        print("❌ Could not load data.")
        return

    # 2. Pre-calculate technical indicators
    print("📊 Pre-calculating indicators...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_final = df_st

    # 3. Define range for ADX Threshold
    # Testing from 10 to 40 with 1 step
    adx_thresholds = np.arange(10, 41, 1)
    
    print(f"🔍 Testing {len(adx_thresholds)} ADX Threshold combinations...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, th, df_final) for th in adx_thresholds]
        
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 10 == 0 or (i + 1) == len(adx_thresholds):
                print(f"✅ Progress: {i+1}/{len(adx_thresholds)} completed...")

    # 4. Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_adx.csv", index=False)
    print("\n✅ Results saved to optimization_results_adx.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
    
    # Sort by Profit Factor
    best_pf = opt_df[opt_df['pf'] != float('inf')].sort_values(by='pf', ascending=False).head(10)
    
    print("\n🏆 Top 10 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    print("\n💎 Top 10 by Profit Factor:")
    print(best_pf.to_string(index=False))

    # Recommend the best overall (Limit MDD and find highest PnL)
    best_overall = opt_df[opt_df['mdd'] < 25].sort_values(by='pnl_pct', ascending=False).head(1)
    
    if not best_overall.empty:
        print("\n🌟 RECOMMENDED ADX THRESHOLD:")
        print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
