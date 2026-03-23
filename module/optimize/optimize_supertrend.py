import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate
from module.bot.data_processor import DataProcessor


def run_simulation(st_len, st_factor, df_final):
    """
    Run simulation with a specific SuperTrend length.
    EMA and SuperTrend factor are fixed from config.
    """

    # Working on a copy
    df_st = df_final.copy()

    # Calculate SuperTrend with specific length
    df_st = DataProcessor.calculate_supertrend(
        df_st, length=st_len, multiplier=st_factor
    )

    # Pass parameters to simulate
    res, _ = simulate(df_st, st_length=st_len, st_factor=st_factor)

    return {
        "st_length": st_len,
        "st_factor": st_factor,
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("SuperTrend Optimization")

    if not optimizer.load_and_prepare_data():
        return

    # Define SuperTrend length range
    st_lengths = np.arange(18, 20, 1)
    st_factors = np.arange(2.6, 2.86, 0.05)

    # Create tasks
    tasks = [(st_len, st_factor) for st_len in st_lengths for st_factor in st_factors]

    results = optimizer.run_parallel(tasks, run_simulation)

    opt_df = optimizer.save_and_analyze(
        results, "resource/optimization_results_supertrend.csv"
    )

    if opt_df is not None and not opt_df.empty:
        # Recommend the best overall (Balance MDD and PnL)
        print("\n🔍 Findings (MDD < 20%):")
        valid_mdd = opt_df[opt_df["mdd"] < 20]

        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL:")
            print(
                valid_mdd.sort_values(by="pnl_pct", ascending=False)
                .head(3)
                .to_string(index=False)
            )

            print("\n🛡️ BEST BY PROFIT FACTOR:")
            print(
                valid_mdd.sort_values(by="pf", ascending=False)
                .head(3)
                .to_string(index=False)
            )
        else:
            print("\n⚠️ No configuration found with MDD < 20%. Showing best by PnL:")
            print(
                opt_df.sort_values(by="pnl_pct", ascending=False)
                .head(3)
                .to_string(index=False)
            )


if __name__ == "__main__":
    run_optimization()
