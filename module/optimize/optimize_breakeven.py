import os
import sys

# Add project root to sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import numpy as np
from module.optimize.base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate, apply_htf_filter
from module.bot.data_processor import DataProcessor
from config import (
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
    VOLUME_MA_LENGTH,
    ATR_LENGTH,
    HTF_TIMEFRAME,
    EMA_LENGTH,
)


def run_simulation(be_mult, df_final):
    """Run simulation with a specific Breakeven multiplier."""
    res, _ = simulate(
        df_final,
        use_ema_filter=True,
        use_volume_filter=True,
        use_htf_filter=True,
        use_breakeven=True,
        breakeven_multiplier=be_mult,
    )
    return {
        "be_multiplier": round(be_mult, 2),
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "calmar": res["calmar_ratio"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("Breakeven Multiplier Optimization")
    if not optimizer.load_and_prepare_data():
        return

    print(f"Applying HTF Filter...")
    optimizer.df_final = apply_htf_filter(optimizer.df_final, optimizer.df_final, htf_timeframe=HTF_TIMEFRAME)

    # Search space: 0.5 to 3.0 in steps of 0.25
    be_multipliers = np.arange(0.5, 3.25, 0.25)
    tasks = [(mult,) for mult in be_multipliers]

    results = optimizer.run_parallel(tasks, run_simulation)
    opt_df = optimizer.save_and_analyze(results, "optimization_results_breakeven.csv")

    if opt_df is not None and not opt_df.empty:
        print("\n🔍 Findings (MDD < 30%):")
        valid_mdd = opt_df[opt_df["mdd"] < 30]

        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL:")
            print(
                valid_mdd.sort_values(by="pnl_pct", ascending=False)
                .head(3)
                .to_string(index=False)
            )
            print("\n🏆 BEST BY CALMAR:")
            print(
                valid_mdd.sort_values(by="calmar", ascending=False)
                .head(3)
                .to_string(index=False)
            )
        else:
            print("\n⚠️ No configuration found with MDD < 30%. Showing best by PnL:")
            print(
                opt_df.sort_values(by="pnl_pct", ascending=False)
                .head(3)
                .to_string(index=False)
            )


if __name__ == "__main__":
    run_optimization()
