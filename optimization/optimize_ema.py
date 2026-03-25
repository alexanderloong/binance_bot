import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data.historical import HistoricalDataProvider
from strategy.supertrend_ha import SupertrendHAStrategy
from execution.backtest import BacktestEngine
from core.trading_metrics import score_bot
from config import settings
from core.logger import logger
import logging
import multiprocessing as mp
import concurrent.futures

def evaluate_params(args):
    ema_p, df = args
    try:
        # We explicitly enforce use_ema=True for testing, even if it's False in settings
        strategy = SupertrendHAStrategy(
            period=settings.SUPERTREND_PERIOD, 
            multiplier=settings.SUPERTREND_MULTIPLIER,
            ema_period=ema_p,
            use_ema=True
        )
        df_signals = strategy.generate_signals(df.copy())

        engine = BacktestEngine(
            initial_capital=1000.0,
            sl_atr_multiplier=settings.SL_ATR_MULTIPLIER if getattr(settings, 'USE_SL', True) else 0.0
        )
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
        print(f"\n[Worker Error on ema_p={ema_p}]: {str(e)}")

    return {"ema_period": ema_p, "total_score": total_score, "pnl": total_pnl}

def run_optimization():
    logger.setLevel(logging.WARNING)
    print("Fetching historical data...")
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=70000)

    # Quét dải EMA từ 20 đến 500 với bước nhảy 10
    ema_periods = list(range(50, 201, 1))
    args_list = [(p, df) for p in ema_periods]
    total_iterations = len(args_list)

    print(
        f"Starting search across {total_iterations} combinations (EMA {ema_periods[0]} to {ema_periods[-1]}) using {mp.cpu_count()} processes...\n"
    )

    best_score = -1
    best_params = None
    results = []
    completed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        future_to_args = {
            executor.submit(evaluate_params, args): args for args in args_list
        }
        for future in concurrent.futures.as_completed(future_to_args):
            result = future.result()
            results.append(result)
            completed += 1
            ema_p = result["ema_period"]
            total_score = result["total_score"]
            total_pnl = result["pnl"]

            print(
                f"\rProgress: {completed}/{total_iterations} | Tested EMA_P={ema_p}...",
                end="",
                flush=True,
            )

            if total_score > best_score:
                best_score = total_score
                best_params = ema_p
                print(
                    f"\n>>> NEW BEST FOUND -> EMA Period: {ema_p} | Score: {total_score:.4f}/100 | PnL: {total_pnl:.2f} USDT"
                )

    print("\n" + "=" * 40)
    print("=> EMA OPTIMIZATION RESULT")
    print("=" * 40)
    if best_params:
        print(f"Best EMA Period:                       {best_params}")
        print(f"Best Total Score:                      {best_score:.4f}/100")
        best_result = next((r for r in results if r["ema_period"] == best_params), None)
        if best_result:
            print(f"Total PnL of best config:              {best_result['pnl']:.2f} USDT")
    else:
        print("Optimization failed.")

if __name__ == "__main__":
    mp.freeze_support()
    run_optimization()
