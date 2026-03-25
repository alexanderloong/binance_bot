import argparse
import multiprocessing
from config import settings
from core.logger import logger
from data.historical import HistoricalDataProvider
from execution.optimizer import GridSearchOptimizer

def main():
    logger.info("=== Bot Grid Search Engine ===")
    
    # Increase dataset significantly to guarantee sufficient sample size (min 1000 trades)
    provider = HistoricalDataProvider()
    # 200,000 bars on 15m is roughly 5.7 years. We pull as much as it caches/supports.
    logger.info(f"Fetching massive historical dataset for '{settings.SYMBOL}' ({settings.TIMEFRAME})")
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=150000)
    
    # ---------------------------------------------------------
    # DEFINE PARAMETER GRID TO EXPLORE
    # You can expand these arrays to search a wider combination space
    # ---------------------------------------------------------
    param_grid = {
        'st_period': [10, 12, 14],               # Supertrend lookback
        'st_multiplier': [2.5, 3.0, 3.5],        # Supertrend sensitivity
        'atr_period': [14],
        'use_ema': [True],
        'ema_period': [100, 200, 300],           # Trend bias speeds
        'use_adx': [True, False],                # Test with and without ADX
        'adx_period': [14],
        'adx_threshold': [20, 25],               # Chop index thresholds
        'sl_atr_multiplier': [1.5, 2.0, 3.0]     # Stop Loss distance (wider is often safer)
    }
    
    # Calculate combinations count implicitly
    import functools, operator
    total_combinations = functools.reduce(operator.mul, [len(v) for v in param_grid.values()])
    logger.info(f"Target logic combinations generated: {total_combinations}")
    
    # Initiate Engine
    # Note: Enforcing strict >= 1000 trades.
    optimizer = GridSearchOptimizer(df, param_grid, min_trades=1000)
    results = optimizer.optimize()
    
    if not results:
        logger.warning(
            "No parameter combinations satisfied the minimum 1000 trades requirement! "
            "Try lowering 'min_trades', fetching more data limit, or tweaking grid parameters."
        )
        return
        
    logger.info("\n==================================")
    logger.info("=== TOP 5 BEST CONFIGURATIONS ===")
    logger.info("==================================")
    
    for i, res in enumerate(results[:5]):
        p = res['params']
        logger.info(
            f"\n[RANK {i+1}] | SCORE: {res['total_score']:.2f}/100\n"
            f" └─> Validated via {res['trades']} Trades\n"
            f" ├─> Total PnL:     {res['total_pnl']:.2f} USDT\n"
            f" ├─> Win Rate:      {res['win_rate']:.2f}%\n"
            f" ├─> Max Drawdown:  {res['max_drawdown']:.2f}%\n"
            f" ├─> Expectancy:    {res['expectancy']:.2f} USDT\n"
            f" └─> Configuration: ST({p['st_period']}, {p['st_multiplier']}) | "
            f"EMA({p['ema_period']}) | ADX(Enable:{p['use_adx']}, Thresh:{p['adx_threshold']}) | "
            f"SL Multiplier({p['sl_atr_multiplier']}x ATR)"
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Binance Bot Grid Search")
    parser.parse_args()
    
    # Required for safe multiprocessing on Windows
    multiprocessing.freeze_support()
    main()
