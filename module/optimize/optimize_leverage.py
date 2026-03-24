import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate
from resource.config import (
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
    EMA_LENGTH,
    VOLUME_MA_LENGTH,
    ATR_MULTIPLIER,
)

# ============================================================================
# OPTIMIZATION TARGETS
# ============================================================================
TARGET_MAX_DRAWDOWN = 25.0
TARGET_MIN_PROFIT_FACTOR = 1.5

# ============================================================================


def run_simulation(leverage, pos_size, df_final):
    """Run simulation with specific leverage and position size."""
    res, _ = simulate(
        df_final,
        use_ema_filter=True,
        use_volume_filter=True,
        use_stoploss=True,
        leverage=leverage,
        position_size_percent=pos_size,
        st_length=SUPERTREND_LENGTH,
        st_factor=SUPERTREND_FACTOR,
        ema_length=EMA_LENGTH,
        volume_ma_length=VOLUME_MA_LENGTH,
        sl_multiplier=ATR_MULTIPLIER,
    )

    return {
        "leverage": leverage,
        "position_size": round(pos_size, 2),
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("Leverage & Position Size Optimization")

    if not optimizer.load_and_prepare_data():
        return

    # Define ranges
    leverage_range = np.arange(1, 26, 1)
    position_size_range = np.arange(0.1, 1.01, 0.05)

    # Create tasks
    tasks = [(int(lev), round(float(pos), 2)) for lev in leverage_range for pos in position_size_range]

    results = optimizer.run_parallel(tasks, run_simulation)

    opt_df = optimizer.save_and_analyze(
        results, "../../resource/optimization_results_leverage.csv"
    )

    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        print(f"\n🔍 Findings (MDD < {TARGET_MAX_DRAWDOWN}%):")
        valid_mdd = opt_df[opt_df["mdd"] < TARGET_MAX_DRAWDOWN]

        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL:")
            print(
                valid_mdd.sort_values(by="pnl_pct", ascending=False)
                .head(5)
                .to_string(index=False)
            )

            print("\n🛡️ BEST BY PROFIT FACTOR:")
            print(
                valid_mdd.sort_values(by="pf", ascending=False)
                .head(5)
                .to_string(index=False)
            )
        else:
            print(f"\n⚠️ No configuration found with MDD < {TARGET_MAX_DRAWDOWN}%. Showing best by PnL:")
            print(
                opt_df.sort_values(by="pnl_pct", ascending=False)
                .head(5)
                .to_string(index=False)
            )


if __name__ == "__main__":
    run_optimization()
