import numpy as np
from base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate
from module.bot.data_processor import DataProcessor
from resource.config import (
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
)


def run_simulation(ema_len, df_final):
    """Run simulation with a specific EMA length."""
    df_st = df_final.copy()
    df_st = DataProcessor.calculate_ema(df_st, length=ema_len)
    df_st["EMA_FILTER"] = df_st[f"EMA_{ema_len}"]

    res, _ = simulate(df_st, use_ema_filter=True, ema_length=ema_len)

    return {
        "ema_length": ema_len,
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "calmar": res["calmar_ratio"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("EMA Length Optimization")

    print(
        f"Fixed: SuperTrend Length={SUPERTREND_LENGTH}, SuperTrend Factor={SUPERTREND_FACTOR}"
    )

    if not optimizer.load_and_prepare_data():
        return

    ema_lengths = np.arange(70, 161, 1)
    tasks = [(ema_len,) for ema_len in ema_lengths]
    results = optimizer.run_parallel(tasks, run_simulation)
    opt_df = optimizer.save_and_analyze(results, "optimization_results_ema.csv")

    if opt_df is not None and not opt_df.empty:
        print("\n🔍 Findings (MDD < 40%):")
        valid_mdd = opt_df[opt_df["mdd"] < 40]

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
            print("\n⚠️ No configuration found with MDD < 40%. Showing best by PnL:")
            print(
                opt_df.sort_values(by="pnl_pct", ascending=False)
                .head(3)
                .to_string(index=False)
            )


if __name__ == "__main__":
    run_optimization()
