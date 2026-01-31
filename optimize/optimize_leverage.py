
import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from backtest import simulate

# ============================================================================
# OPTIMIZATION TARGETS
# ============================================================================
TARGET_MAX_DRAWDOWN = 25.0      # Maximum acceptable drawdown (%)
TARGET_MIN_PROFIT_FACTOR = 1.7  # Minimum acceptable profit factor

# Search ranges
LEVERAGE_MIN = 5
LEVERAGE_MAX = 25
LEVERAGE_STEP = 5

POSITION_SIZE_MIN = 0.10  # 10%
POSITION_SIZE_MAX = 1.00  # 100%
POSITION_SIZE_STEP = 0.05  # 5%
# ============================================================================

def run_simulation(leverage, pos_size, df_final):
    """Run simulation with specific leverage and position size."""
    # Use backtest.simulate which now supports leverage and position_size_percent
    # We pass other params as defaults (or explicit if needed, but defaults should closely match what was there)
    res, _ = simulate(df_final, leverage=leverage, position_size_percent=pos_size)
    
    return {
        'leverage': leverage,
        'position_size': round(pos_size, 2),
        'pnl_pct': res['pnl_pct'],
        'final_balance': res['final_balance'],
        'max_drawdown': res['max_drawdown'],
        'profit_factor': res['profit_factor']
    }

def run_optimization():
    optimizer = BaseOptimizer("Leverage & Position Size Optimizer")
    
    print(f"=" * 70)
    print(f"\n🎯 Target Criteria:")
    print(f"   • Max Drawdown ≤ {TARGET_MAX_DRAWDOWN}%")
    print(f"   • Profit Factor ≥ {TARGET_MIN_PROFIT_FACTOR}")
    print(f"\n📋 Search Range:")
    print(f"   • Leverage: {LEVERAGE_MIN}x to {LEVERAGE_MAX}x (step {LEVERAGE_STEP})")
    print(f"   • Position Size: {POSITION_SIZE_MIN*100:.0f}% to {POSITION_SIZE_MAX*100:.0f}% (step {POSITION_SIZE_STEP*100:.0f}%)")

    if not optimizer.load_and_prepare_data():
        return

    # Define ranges
    leverage_range = np.arange(LEVERAGE_MIN, LEVERAGE_MAX + 1, LEVERAGE_STEP)
    position_size_range = np.arange(POSITION_SIZE_MIN, POSITION_SIZE_MAX + 0.01, POSITION_SIZE_STEP)
    
    tasks = []
    for lev in leverage_range:
        for pos in position_size_range:
            tasks.append((lev, pos))

    results = optimizer.run_parallel(tasks, run_simulation)
    
    # Use base analyzer to save and show generic top lists
    opt_df = optimizer.save_and_analyze(results, "optimization_results_leverage.csv")
    
    # Custom post-analysis for Leverage Specifics
    if opt_df is None or opt_df.empty:
        return

    # Filter by targets
    matching = opt_df[
        (opt_df['max_drawdown'] <= TARGET_MAX_DRAWDOWN) &
        (opt_df['profit_factor'] >= TARGET_MIN_PROFIT_FACTOR)
    ].sort_values(by='pnl_pct', ascending=False)
    
    if not matching.empty:
        print(f"\n🎉 Found {len(matching)} configurations matching your criteria!")
        print("\n🏆 Top 10 Matching Configurations (sorted by PnL):")
        print(matching.head(10).to_string(index=False))
        
        # Show best by different metrics
        best_pnl = matching.iloc[0]
        best_pf = matching.sort_values(by='profit_factor', ascending=False).iloc[0]
        best_mdd = matching.sort_values(by='max_drawdown').iloc[0]
        
        print("\n" + "="*70)
        print("📌 RECOMMENDED CONFIGURATIONS:")
        print("="*70)
        
        print(f"\n💰 Best PnL (Highest Return):")
        print(f"   Leverage: {best_pnl['leverage']}x | Position Size: {best_pnl['position_size']*100:.0f}%")
        print(f"   PnL: {best_pnl['pnl_pct']:.2f}% | MDD: {best_pnl['max_drawdown']:.2f}% | PF: {best_pnl['profit_factor']:.2f}")
        
        print(f"\n💎 Best Profit Factor (Most Consistent):")
        print(f"   Leverage: {best_pf['leverage']}x | Position Size: {best_pf['position_size']*100:.0f}%")
        print(f"   PnL: {best_pf['pnl_pct']:.2f}% | MDD: {best_pf['max_drawdown']:.2f}% | PF: {best_pf['profit_factor']:.2f}")
        
        print(f"\n🛡️ Safest (Lowest Drawdown):")
        print(f"   Leverage: {best_mdd['leverage']}x | Position Size: {best_mdd['position_size']*100:.0f}%")
        print(f"   PnL: {best_mdd['pnl_pct']:.2f}% | MDD: {best_mdd['max_drawdown']:.2f}% | PF: {best_mdd['profit_factor']:.2f}")
        
    else:
        print(f"\n⚠️ No configurations found matching your exact criteria.")
        print(f"   (Check the CSV file for top performers regardless of constraints)")

if __name__ == "__main__":
    run_optimization()
