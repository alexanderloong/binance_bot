import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data.historical import HistoricalDataProvider
from strategy.supertrend_ha import SupertrendHAStrategy
from execution.backtest import BacktestEngine
from core.trading_metrics import score_bot
from config import settings
import itertools
from core.logger import logger
import logging
import sys
import os
import multiprocessing as mp
import concurrent.futures


def evaluate_params(args):
    p, m, df = args

    try:
        strategy = SupertrendHAStrategy(period=p, multiplier=m)
        df_signals = strategy.generate_signals(df.copy())

        engine = BacktestEngine(initial_capital=1000.0)
        engine.run(df_signals, silent=True)

        trades_df = pd.DataFrame(engine.trades)
        if len(trades_df) > 0 and "CLOSE" in trades_df["action"].values:
            close_trades = trades_df[trades_df["action"] == "CLOSE"]
            trades_pnl = close_trades["pnl"].tolist()
            total_pnl = close_trades["pnl"].sum()
        else:
            trades_pnl = []
            total_pnl = 0

        equity_df = pd.DataFrame(engine.equity_curve)
        if len(equity_df) > 0:
            equity_curve_list = equity_df["equity"].tolist()
            returns = equity_df["equity"].pct_change().fillna(0).tolist()
        else:
            equity_curve_list = []
            returns = []

        scores = score_bot(returns, trades_pnl, equity_curve_list)
        total_score = scores["total_score"]
    except Exception as e:
        total_score = -1
        total_pnl = 0
        print(f"\n[Worker Error on p={p}, m={m}]: {str(e)}")

    return {"period": p, "multiplier": m, "total_score": total_score, "pnl": total_pnl}


def run_optimization():
    logger.setLevel(logging.WARNING)
    print("Setting up grid search parameters...")

    print("Fetching historical data...")
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=70000)

    periods = range(6, 20, 1)
    multipliers = [m / 10.0 for m in range(10, 30, 1)]

    args_list = list(itertools.product(periods, multipliers))
    total_iterations = len(args_list)
    print(
        f"Starting search across {total_iterations} combinations using {mp.cpu_count()} processes...\n"
    )

    best_score = -1
    best_params = None
    results = []
    completed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        # map guarantees order but we just need results as they complete.
        # Actually, using as_completed is better for immediate unordered printing.
        future_to_args = {
            executor.submit(evaluate_params, (p, m, df)): (p, m) for p, m in args_list
        }
        for future in concurrent.futures.as_completed(future_to_args):
            result = future.result()
            results.append(result)
            completed += 1
            p = result["period"]
            m = result["multiplier"]
            total_score = result["total_score"]
            total_pnl = result["pnl"]

            print(
                f"\rProgress: {completed}/{total_iterations} | Tested P={p}, M={m}...",
                end="",
                flush=True,
            )

            if total_score > best_score:
                best_score = total_score
                best_params = (p, m)
                print(
                    f"\n>>> NEW BEST FOUND -> Period: {p}, Multiplier: {m} | Score: {total_score:.4f}/100 | PnL: {total_pnl:.2f} USDT"
                )

    print("\n" + "=" * 40)
    print("=> OPTIMIZATION RESULT")
    print("=" * 40)

    if best_params:
        print(f"Best Period:                           {best_params[0]}")
        print(f"Best Multiplier:                       {best_params[1]}")
        print(f"Best Total Score:                      {best_score:.4f}/100")

        best_result = next(
            (
                r
                for r in results
                if r["period"] == best_params[0] and r["multiplier"] == best_params[1]
            ),
            None,
        )
        if best_result:
            print(
                f"Total PnL of best config:              {best_result['pnl']:.2f} USDT"
            )
    else:
        print("Quá trình chạy bị lỗi. Không tìm thấy thông số nào.")


if __name__ == "__main__":
    mp.freeze_support()
    run_optimization()
