import numpy as np
import pandas as pd
from base_optimizer import BaseOptimizer
from module.backtest.orchestrator import simulate
from module.bot.data_processor import DataProcessor
from resource.config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, VOLUME_MA_LENGTH


def run_simulation(atr_len, sl_multiplier, df_final):
    """
    Run simulation with a specific ATR length and Stop Loss multiplier.
    """
    df_atr = df_final.copy()

    # Recalculate ATR with specific length
    df_atr["ATR"] = DataProcessor.calculate_atr(df_atr, length=atr_len)

    # Pass parameters to simulate with stoploss enabled
    res, _ = simulate(
        df_atr,
        use_stoploss=True,
        use_ema_filter=True,
        use_volume_filter=True,
        sl_multiplier=sl_multiplier,
        st_length=SUPERTREND_LENGTH,
        st_factor=SUPERTREND_FACTOR,
        ema_length=EMA_LENGTH,
        volume_ma_length=VOLUME_MA_LENGTH,
    )

    return {
        "atr_length": atr_len,
        "sl_multiplier": sl_multiplier,
        "pnl_pct": res["pnl_pct"],
        "win_rate": res["win_rate"],
        "pf": res["profit_factor"],
        "mdd": res["max_drawdown"],
        "total_trades": res["total_trades"],
    }


def run_optimization():
    optimizer = BaseOptimizer("ATR Stop Loss Optimization")

    if not optimizer.load_and_prepare_data():
        return

    # Define ranges for ATR length and SL multiplier
    atr_lengths = np.arange(18, 23, 1)
    sl_multipliers = np.arange(1, 1.75, 0.05)

    # Create tasks
    tasks = [(int(atr_len), round(sl_mult, 2)) for atr_len in atr_lengths for sl_mult in sl_multipliers]

    results = optimizer.run_parallel(tasks, run_simulation)

    opt_df = optimizer.save_and_analyze(
        results, "../../resource/optimization_results_atr_sl.csv"
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
