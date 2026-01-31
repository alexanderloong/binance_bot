import pandas as pd
import numpy as np
from backtest import simulate, get_backtest_data
from bot.data_processor import DataProcessor
from config import EMA_LENGTH, SUPERTREND_LENGTH, SUPERTREND_FACTOR, ADX_LENGTH, ATR_LENGTH, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT, RSI_LENGTH, VOLUME_MA_LENGTH
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_simulation(sl_mult, df_final):
    # Use the current best TP settings we found earlier
    res, _ = simulate(df_final, 
                      use_ema_filter=True, 
                      tp_multiplier=PARTIAL_TP_MULTIPLIER, 
                      tp_percent=PARTIAL_TP_PERCENT,
                      sl_multiplier=sl_mult,
                      use_rsi_filter=True,
                      use_volume_filter=True)
    return {
        'atr_multiplier': round(sl_mult, 2),
        'pnl_pct': res['pnl_pct'],
        'win_rate': res['win_rate'],
        'pf': res['profit_factor'],
        'mdd': res['max_drawdown'],
        'total_trades': res['total_trades']
    }

def run_optimization():
    print(f"🚀 Starting Multi-threaded ATR Multiplier Optimization...")
    print(f"Stats: Using TP Multiplier: {PARTIAL_TP_MULTIPLIER}, TP Percent: {PARTIAL_TP_PERCENT}")
    
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

    # 3. Define range for ATR Multiplier
    # Testing from 0.5 to 5.0 with 0.1 step
    sl_multipliers = np.arange(0.5, 5.1, 0.1)
    
    print(f"🔍 Testing {len(sl_multipliers)} ATR Multiplier combinations...")
    
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, sl, df_final) for sl in sl_multipliers]
        
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 10 == 0 or (i + 1) == len(sl_multipliers):
                print(f"✅ Progress: {i+1}/{len(sl_multipliers)} completed...")

    # 4. Analyze results
    opt_df = pd.DataFrame(results)
    opt_df.to_csv("optimization_results_atr.csv", index=False)
    print("\n✅ Results saved to optimization_results_atr.csv")
    
    # Sort by PnL
    best_pnl = opt_df.sort_values(by='pnl_pct', ascending=False).head(10)
    
    # Sort by Profit Factor
    best_pf = opt_df[opt_df['pf'] != float('inf')].sort_values(by='pf', ascending=False).head(10)
    
    print("\n🏆 Top 10 by Net Profit (PnL %):")
    print(best_pnl.to_string(index=False))
    
    print("\n💎 Top 10 by Profit Factor:")
    print(best_pf.to_string(index=False))

    # Recommend the best overall (Balance between high PnL and low MDD)
    # Filter for reasonable MDD and then sort by PnL
    best_overall = opt_df[opt_df['mdd'] < 25].sort_values(by='pnl_pct', ascending=False).head(1)
    
    if not best_overall.empty:
        print("\n🌟 RECOMMENDED ATR SETTING:")
        print(best_overall.to_string(index=False))

if __name__ == "__main__":
    run_optimization()
