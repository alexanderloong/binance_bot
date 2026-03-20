import pandas as pd
from typing import Optional
from resource.config import settings


def evaluate_signal(
    df_final: pd.DataFrame,
    current_pos_amt: float,
    use_ema_filter: bool = True,
    use_volume_filter: bool = True,
    use_htf_filter: bool = True,
) -> tuple[Optional[str], float, str]:
    """
    Evaluates the trading signal.

    Args:
        df_final:          Processed OHLCV DataFrame with indicators.
        current_pos_amt:   Current open position size (0 if flat).
        use_ema_filter:    If False, skip the EMA trend-direction gate.
        use_volume_filter: If False, skip the Volume > Vol MA gate.
        use_htf_filter:    If False, skip the HTF SuperTrend gate.
    """
    if len(df_final) < 3:
        return None, settings.POSITION_SIZE_PERCENT, "Not enough data"

    last_candle = df_final.iloc[-2]
    prev_candle = df_final.iloc[-3]

    st_dir_col = f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"

    current_trend  = last_candle[st_dir_col]
    previous_trend = prev_candle[st_dir_col]

    close_price    = last_candle["close"]
    ema_val        = last_candle[f"EMA_{settings.EMA_LENGTH}"]
    vol_ma_val     = last_candle.get(f"VOL_MA_{settings.VOLUME_MA_LENGTH}", 0)
    current_volume = last_candle.get("volume", 0)
    htf_trend      = last_candle.get("HTF_TREND", current_trend)

    actual_pos_size = settings.POSITION_SIZE_PERCENT

    # --- Filter conditions (each can be disabled independently) ---
    ema_long_ok  = (close_price > ema_val)       if use_ema_filter    else True
    ema_short_ok = (close_price < ema_val)       if use_ema_filter    else True
    vol_ok       = (current_volume > vol_ma_val) if use_volume_filter else True
    htf_long_ok  = (htf_trend == 1)              if use_htf_filter    else True
    htf_short_ok = (htf_trend == -1)             if use_htf_filter    else True

    # 1. Exit Priority (always active — never skip exits)
    if current_pos_amt > 0 and current_trend == -1:
        return "CLOSE_LONG", 0.0, "Trend flipped to RED."
    elif current_pos_amt < 0 and current_trend == 1:
        return "CLOSE_SHORT", 0.0, "Trend flipped to GREEN."

    signal = None
    reason = "No entry signal."

    # 2. Entry Logic
    if current_trend == 1 and previous_trend == -1 and ema_long_ok and htf_long_ok:
        if vol_ok:
            signal = "LONG"
            reason = "LONG Validated."
        else:
            reason = "LONG detected but Volume low."
    elif current_trend == -1 and previous_trend == 1 and ema_short_ok and htf_short_ok:
        if vol_ok:
            signal = "SHORT"
            reason = "SHORT Validated."
        else:
            reason = "SHORT detected but Volume low."

    if signal and current_pos_amt == 0:
        return signal, actual_pos_size, reason

    return None, actual_pos_size, reason
