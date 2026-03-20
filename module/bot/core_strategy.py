import pandas as pd
from typing import Optional, Dict, Any
from config import settings

def evaluate_signal(df_final: pd.DataFrame, current_pos_amt: float) -> tuple[Optional[str], float, str]:
    """
    Evaluates the trading signal based on the unified strategy rules.
    
    Args:
        df_final: The dataframe containing all prepared indicators.
        current_pos_amt: Current position size (positive for long, negative for short, 0 for none).
        
    Returns:
        tuple containing:
            - signal (str or None): 'LONG', 'SHORT', 'CLOSE_LONG', 'CLOSE_SHORT', or None
            - suggested_pos_size_pct (float): Recommended position sizing % based on EMA slope
            - reason (str): Explanatory reason for logging
    """
    if len(df_final) < 3:
        return None, settings.POSITION_SIZE_PERCENT, "Not enough data"
        
    last_candle = df_final.iloc[-2]
    prev_candle = df_final.iloc[-3]
    
    st_dir_col = f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
    
    current_trend = last_candle[st_dir_col]
    previous_trend = prev_candle[st_dir_col]
    
    close_price = last_candle['close']
    ema_val = last_candle[f'EMA_{settings.EMA_LENGTH}']
    
    # Retrieve dynamic settings with fallback
    adx_length = getattr(settings, 'ADX_LENGTH', 14)
    adx_threshold = getattr(settings, 'ADX_THRESHOLD', 20.0)
    rsi_length = getattr(settings, 'RSI_LENGTH', 14)
    rsi_long_threshold = getattr(settings, 'RSI_LONG_THRESHOLD', 30.0)
    rsi_overbought = getattr(settings, 'RSI_OVERBOUGHT', 70.0)
    rsi_oversold = getattr(settings, 'RSI_OVERSOLD', 30.0)
    ema_slope_ema_length = getattr(settings, 'EMA_SLOPE_EMA_LENGTH', settings.EMA_LENGTH)
    ema_slope_lookback = getattr(settings, 'EMA_SLOPE_LOOKBACK', 3)
    ema_slope_threshold = getattr(settings, 'EMA_SLOPE_THRESHOLD', 0.001)
    reduced_size_pct = getattr(settings, 'REDUCED_POSITION_SIZE_PERCENT', settings.POSITION_SIZE_PERCENT)
    
    adx_val = last_candle.get('ADX', 0)
    atr_val = last_candle.get('ATR', 0)
    rsi_val = last_candle.get('RSI', 50)
    vol_ma_val = last_candle.get(f'VOL_MA_{settings.VOLUME_MA_LENGTH}', 0)
    current_volume = last_candle.get('volume', 0)
    htf_trend = last_candle.get('HTF_TREND', current_trend) # defaults to current if missing
    
    ema_slope_val = last_candle.get(f'EMA_{ema_slope_ema_length}', ema_val)
    slope_idx = -(ema_slope_lookback + 2)
    if abs(slope_idx) <= len(df_final):
        ema_slope_prev = df_final.iloc[slope_idx].get(f'EMA_{ema_slope_ema_length}', ema_val)
    else:
        ema_slope_prev = ema_slope_val  # not enough history yet, treat as flat
    ema_slope_pct = (ema_slope_val - ema_slope_prev) / ema_slope_prev if ema_slope_prev != 0 else 0
    is_flat_slope = abs(ema_slope_pct) < ema_slope_threshold
    
    actual_pos_size = reduced_size_pct if is_flat_slope else settings.POSITION_SIZE_PERCENT
    
    is_trending = adx_val > adx_threshold
    rsi_long_ok = rsi_long_threshold < rsi_val < rsi_overbought
    rsi_short_ok = rsi_val > rsi_oversold
    vol_ok = current_volume > vol_ma_val
    is_uptrend_long = close_price > ema_val
    is_downtrend_short = close_price < ema_val
    htf_long_ok = htf_trend == 1
    htf_short_ok = htf_trend == -1
    
    # 1. Exit Priority
    if current_pos_amt > 0 and current_trend == -1:
        return 'CLOSE_LONG', 0.0, "Trend flipped to RED."
    elif current_pos_amt < 0 and current_trend == 1:
        return 'CLOSE_SHORT', 0.0, "Trend flipped to GREEN."
        
    signal = None
    reason = "No entry signal."
    
    # 2. Entry Logic
    if current_trend == 1 and previous_trend == -1 and is_uptrend_long and htf_long_ok:
        if is_trending and rsi_long_ok and vol_ok:
            signal = 'LONG'
            reason = f"{signal} Validated. Flat={is_flat_slope}"
        else:
            reasons = []
            if not is_trending: reasons.append("ADX low")
            if not rsi_long_ok: reasons.append("RSI invalid")
            if not vol_ok: reasons.append("Volume low")
            reason = f"LONG detected but {', '.join(reasons)}."
    elif current_trend == -1 and previous_trend == 1 and is_downtrend_short and htf_short_ok:
        if is_trending and rsi_short_ok and vol_ok:
            signal = 'SHORT'
            reason = f"{signal} Validated. Flat={is_flat_slope}"
        else:
            reasons = []
            if not is_trending: reasons.append("ADX low")
            if not rsi_short_ok: reasons.append("RSI oversold")
            if not vol_ok: reasons.append("Volume low")
            reason = f"SHORT detected but {', '.join(reasons)}."
            
    if signal and current_pos_amt == 0:
        return signal, actual_pos_size, reason
        
    return None, actual_pos_size, reason
