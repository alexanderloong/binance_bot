import os
import time
from bot.data_processor import DataProcessor
from config import (
    SYMBOL,
    TIMEFRAME,
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
    EMA_LENGTH,
    POSITION_SIZE_PERCENT,
    LEVERAGE,
    VOLUME_MA_LENGTH,
    ATR_LENGTH,
    ATR_MULTIPLIER,
    TAKER_FEE_RATE,
)

from bot.backtest.data_loader import BacktestDataLoader
from bot.backtest.simulator import Simulator
from bot.backtest.reporter import BacktestReporter

LIMIT = 150000
WORKERS = 5
SLEEP = 1.5
GEN_CHART = True

def get_backtest_data(limit=LIMIT):
    loader = BacktestDataLoader(
        symbol=SYMBOL, 
        timeframe=TIMEFRAME, 
        workers=WORKERS, 
        sleep=SLEEP
    )
    return loader.get_data(limit=limit)

def simulate(
    df,
    use_ema_filter=True,
    st_length=SUPERTREND_LENGTH,
    st_factor=SUPERTREND_FACTOR,
    use_volume_filter=True,
    volume_ma_length=VOLUME_MA_LENGTH,
    sl_multiplier=ATR_MULTIPLIER,
    leverage=LEVERAGE,
    position_size_percent=POSITION_SIZE_PERCENT,
):
    sim = Simulator(
        timeframe=TIMEFRAME,
        use_ema_filter=use_ema_filter,
        st_length=st_length,
        st_factor=st_factor,
        use_volume_filter=use_volume_filter,
        volume_ma_length=volume_ma_length,
        sl_multiplier=sl_multiplier,
        leverage=leverage,
        position_size_percent=position_size_percent,
        commission_rate=TAKER_FEE_RATE,
        ema_length=EMA_LENGTH
    )
    return sim.run(df)

def run_backtest():
    print(f"--- Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    print(f"Strategy: SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, EMA {EMA_LENGTH}, Vol MA {VOLUME_MA_LENGTH}")

    df = get_backtest_data(limit=LIMIT)
    if df is None:
        return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f"EMA_{EMA_LENGTH}"] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f"EMA_{EMA_LENGTH}"]
    df_st["ATR"] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    df_final = df_st

    # Run simulation
    res, trades = simulate(
        df_final, 
        use_ema_filter=True, 
        use_volume_filter=True
    )

    # Log results
    BacktestReporter.log_results(res, trades, df)

    try:
        if GEN_CHART:
            from optimize.plot_results import plot_performance
            print("\nGenerating Performance Chart...")
            plot_performance(df_final, trades, res)
    except Exception as e:
        print(f"Could not generate chart: {e}")

    return res, trades

if __name__ == "__main__":
    run_backtest()
