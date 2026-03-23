import os
import time
import sys
import pandas as pd

# Add project root to sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from module.bot.data_processor import DataProcessor
from resource.config import (
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

LIMIT = 10000
WORKERS = 5
SLEEP = 1.5
GEN_CHART = True


def get_backtest_data(limit=LIMIT):
    loader = BacktestDataLoader(
        symbol=SYMBOL, timeframe=TIMEFRAME, workers=WORKERS, sleep=SLEEP
    )
    return loader.get_data(limit=limit)


def simulate(
    df_final,
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
    # FIX [2][3]: pass df_final (HA-processed, has ATR on HA candles) — not raw df
    return sim.run(df_final)


def apply_htf_filter(
    df_final,
    df,
    htf_timeframe=HTF_TIMEFRAME,
    st_length=SUPERTREND_LENGTH,
    st_factor=SUPERTREND_FACTOR,
):
    """
    Merges HTF SuperTrend trend direction into df_final.

    FIX [1]: use merge_asof with direction='backward' on the SHIFTED timestamp
    so that each LTF candle gets the trend of the LAST *COMPLETED* HTF candle
    (same as live bot which uses df_htf_st.iloc[-2]).
    Shifting by 1 period ensures we never use the still-forming HTF candle.
    """
    print(f"Computing HTF ({htf_timeframe}) SuperTrend...")
    df_htf_raw = DataProcessor.resample_to_htf(df, htf=htf_timeframe)
    df_htf_ha = DataProcessor.calculate_heikin_ashi(df_htf_raw)
    df_htf_st = DataProcessor.calculate_supertrend(df_htf_ha)
    st_dir_col = f"SUPERTd_{st_length}_{st_factor}"

    df_htf_trend = df_htf_st[["timestamp", st_dir_col]].copy()
    df_htf_trend = df_htf_trend.rename(columns={st_dir_col: "HTF_TREND"})

    # Shift timestamp forward by 1 HTF period so the trend value of a completed
    # HTF candle only becomes visible to LTF candles that open AFTER that candle closes.
    # This matches live bot behaviour where iloc[-2] is the last closed HTF candle.
    from module.bot.utils import parse_timeframe_to_seconds

    htf_seconds = parse_timeframe_to_seconds(htf_timeframe)
    df_htf_trend["timestamp"] = df_htf_trend["timestamp"] + pd.Timedelta(
        seconds=htf_seconds
    )

    # FIX: normalize both sides to same datetime unit (ms) before merging
    # merge_asof errors when left is datetime64[ms, tz] and right is datetime64[us, tz]
    df_final = df_final.copy()
    df_final["timestamp"] = df_final["timestamp"].dt.as_unit("ms")
    df_htf_trend["timestamp"] = df_htf_trend["timestamp"].dt.as_unit("ms")

    df_final = pd.merge_asof(
        df_final.sort_values("timestamp"),
        df_htf_trend.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    )
    up = (df_final["HTF_TREND"] == 1).sum()
    down = (df_final["HTF_TREND"] == -1).sum()
    print(f"  HTF trend added — Uptrend: {up}, Downtrend: {down} candles")
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
        use_ema_filter=False,
        use_volume_filter=False,
        use_htf_filter=False,
        use_breakeven=False,
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
