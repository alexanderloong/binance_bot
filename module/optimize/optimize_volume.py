import numpy as np
from base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate
from module.bot.data_processor import DataProcessor
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH


def run_simulation(vol_len, df_final):
    """Run simulation with a specific Volume MA length."""
    df_wk = df_final.copy()
    df_wk = DataProcessor.calculate_volume_ma(df_wk, length=vol_len)

    res, _ = simulate(
        df_wk, use_ema_filter=True, use_volume_filter=True, volume_ma_length=vol_len
    )

    return {
        "vol_ma_len": vol_len,
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "calmar": res["calmar_ratio"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("Volume MA Length Optimization")

    print(
        f"Fixed: SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, EMA {EMA_LENGTH}"
    )

    if not optimizer.load_and_prepare_data():
        return

    vol_lengths = np.arange(150, 180, 1)
    print(f"Testing {len(vol_lengths)} Volume MA lengths...")

    tasks = [(vol_len,) for vol_len in vol_lengths]
    results = optimizer.run_parallel(tasks, run_simulation)
    opt_df = optimizer.save_and_analyze(results, "optimization_results_volume.csv")

    if opt_df is not None and not opt_df.empty:
        valid_mdd = opt_df[opt_df["mdd"] < 40]

        if not valid_mdd.empty:
            print("\n🌟 BEST BY PNL (MDD < 40%):")
            print(
                valid_mdd.sort_values(by="pnl_pct", ascending=False)
                .head(5)
                .to_string(index=False)
            )
            print("\n🏆 BEST BY CALMAR:")
            print(
                valid_mdd.sort_values(by="calmar", ascending=False)
                .head(5)
                .to_string(index=False)
            )
        else:
            print("\n⚠️ No configuration found with MDD < 40%. Best available:")
            print(
                opt_df.sort_values(by="pnl_pct", ascending=False)
                .head(5)
                .to_string(index=False)
            )


if __name__ == "__main__":
    run_optimization()
