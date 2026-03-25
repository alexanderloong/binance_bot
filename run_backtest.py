import argparse
from config import settings
from core.logger import logger
from data.historical import HistoricalDataProvider
from strategy.supertrend_ha import SupertrendHAStrategy
from execution.backtest import BacktestEngine


def run_backtest():
    logger.info("=== Starting Backtest ===")
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=70000)

    strategy = SupertrendHAStrategy(atr_period=settings.ATR_PERIOD)
    df_signals = strategy.generate_signals(df)

    engine = BacktestEngine(
        initial_capital=1000.0, 
        sl_atr_multiplier=settings.SL_ATR_MULTIPLIER if getattr(settings, 'USE_SL', True) else 0.0
    )
    engine.run(df_signals)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Binance Bot Backtest")
    parser.parse_args()
    run_backtest()
