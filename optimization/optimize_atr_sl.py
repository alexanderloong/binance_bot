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
import multiprocessing as mp
import concurrent.futures


def evaluate_params(args):
    p, m, atr_m, df = args
    try:
        strategy = SupertrendHAStrategy(period=p, multiplier=m, atr_period=14)
        df_signals = strategy.generate_signals(df.copy())

        engine = BacktestEngine(initial_capital=1000.0, sl_atr_multiplier=atr_m)
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
        print(f"\n[Worker Error on p={p}, m={m}, atr_m={atr_m}]: {str(e)}")

    return {
        "period": p,
        "multiplier": m,
        "atr_m": atr_m,
        "total_score": total_score,
        "pnl": total_pnl,
    }


def run_optimization():
    logger.setLevel(logging.WARNING)
    print("Fetching historical data...")
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=70000)

    # Grid search boundaries
    # Cố định tham số Supertrend theo settings cấu hình sẵn
    periods = [settings.SUPERTREND_PERIOD]
    multipliers = [settings.SUPERTREND_MULTIPLIER]

    # Quét dải SL ATR Multiplier từ 1.0 đến 4.0, bước nhảy 0.25
    # 100, 425, 25 tương đương 1.00, 4.00, +0.25
    atr_multipliers = [m / 100.0 for m in range(100, 425, 25)]
    args_list = list(itertools.product(periods, multipliers, atr_multipliers))
    total_iterations = len(args_list)
    print(
        f"Starting search across {total_iterations} combinations using {mp.cpu_count()} processes...\n"
    )

    best_score = -1
    best_params = None
    results = []
    completed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        future_to_args = {
            executor.submit(evaluate_params, (p, m, atr_m, df)): (p, m, atr_m)
            for p, m, atr_m in args_list
        }
        for future in concurrent.futures.as_completed(future_to_args):
            result = future.result()
            results.append(result)
            completed += 1
            p = result["period"]
            m = result["multiplier"]
            atr_m = result["atr_m"]
            total_score = result["total_score"]
            total_pnl = result["pnl"]

            print(
                f"\rProgress: {completed}/{total_iterations} | Tested P={p}, M={m}, ATR_M={atr_m}...",
                end="",
                flush=True,
            )

            if total_score > best_score:
                best_score = total_score
                best_params = (p, m, atr_m)
                print(
                    f"\n>>> NEW BEST FOUND -> Period: {p}, Multiplier: {m}, SL ATR: {atr_m} | Score: {total_score}/100 | PnL: {total_pnl:.2f} USDT"
                )

    print("\n" + "=" * 40)
    print("=> OPTIMIZATION RESULT")
    print("=" * 40)
    if best_params:
        print(f"Best Period:                           {best_params[0]}")
        print(f"Best Multiplier:                       {best_params[1]}")
        print(f"Best SL ATR Multiplier:                {best_params[2]}")
        print(f"Best Total Score:                      {best_score}/100")
        best_result = next(
            (
                r
                for r in results
                if r["period"] == best_params[0]
                and r["multiplier"] == best_params[1]
                and r["atr_m"] == best_params[2]
            ),
            None,
        )
        if best_result:
            print(
                f"Total PnL of best config:              {best_result['pnl']:.2f} USDT"
            )
    else:
        print("Optimization failed.")


if __name__ == "__main__":
    mp.freeze_support()
    run_optimization()
