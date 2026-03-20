import os
import time
import sys
import pandas as pd

# Add project root to sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from module.bot.data_processor import DataProcessor
from config import (
    SYMBOL,
    TIMEFRAME,
    HTF_TIMEFRAME,
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
    EMA_LENGTH,
    POSITION_SIZE_PERCENT,
    LEVERAGE,
    VOLUME_MA_LENGTH,
    ATR_LENGTH,
    ATR_MULTIPLIER,
    TAKER_FEE_RATE,
    BREAKEVEN_MULTIPLIER,
)

from module.backtest.data_loader import BacktestDataLoader
from module.backtest.simulator import Simulator
from module.backtest.reporter import BacktestReporter

LIMIT = 1000
WORKERS = 5
SLEEP = 1.5
GEN_CHART = True


def get_backtest_data(limit=LIMIT):
    loader = BacktestDataLoader(
        symbol=SYMBOL, timeframe=TIMEFRAME, workers=WORKERS, sleep=SLEEP
    )
    return loader.get_data(limit=limit)


def simulate(
    df,
    use_ema_filter=True,
    use_volume_filter=True,
    use_htf_filter=True,
    use_breakeven=True,
    breakeven_multiplier=BREAKEVEN_MULTIPLIER,
    st_length=SUPERTREND_LENGTH,
    st_factor=SUPERTREND_FACTOR,
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
        ema_length=EMA_LENGTH,
        use_htf_filter=use_htf_filter,
        use_breakeven=use_breakeven,
        breakeven_multiplier=breakeven_multiplier,
    )
    return sim.run(df)


def apply_htf_filter(
    df_final,
    df,
    htf_timeframe=HTF_TIMEFRAME,
    st_length=SUPERTREND_LENGTH,
    st_factor=SUPERTREND_FACTOR,
):
    print(f"Computing HTF ({htf_timeframe}) SuperTrend...")
    df_htf_raw = DataProcessor.resample_to_htf(df, htf=htf_timeframe)
    df_htf_ha = DataProcessor.calculate_heikin_ashi(df_htf_raw)
    df_htf_st = DataProcessor.calculate_supertrend(df_htf_ha)
    st_dir_col = f"SUPERTd_{st_length}_{st_factor}"
    df_htf_trend = df_htf_st[["timestamp", st_dir_col]].rename(
        columns={st_dir_col: "HTF_TREND"}
    )
    # Merge into 15m df: each 15m candle gets the HTF trend of the last completed HTF candle
    df_final = pd.merge_asof(
        df_final.sort_values("timestamp"),
        df_htf_trend.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    )
    print(
        f"  HTF trend column added. Uptrend: {(df_final['HTF_TREND'] == 1).sum()}, Downtrend: {(df_final['HTF_TREND'] == -1).sum()} candles"
    )
    return df_final


def run_backtest():
    print(f"--- Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    print(
        f"Strategy: SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, EMA {EMA_LENGTH}, Vol MA {VOLUME_MA_LENGTH}"
    )

    df = get_backtest_data(limit=LIMIT)
    if df is None:
        return

    print(f"Processing {len(df)} candles...")
    df_final = DataProcessor.prepare_all_indicators(df)

    # HTF Filter: resample to higher timeframe and compute SuperTrend
    df_final = apply_htf_filter(df_final, df)

    # Run simulation
    res, trades = simulate(
        df_final,
        use_ema_filter=True,
        use_volume_filter=True,
        use_htf_filter=True,
        use_breakeven=True,
    )

    # Log results
    BacktestReporter.log_results(res, trades, df)

    try:
        if GEN_CHART:
            from module.optimize.plot_results import plot_performance

            print("\nGenerating Performance Chart...")
            plot_performance(df_final, trades, res)
    except Exception as e:
        print(f"Could not generate chart: {e}")

    return res, trades


if __name__ == "__main__":
    run_backtest()
