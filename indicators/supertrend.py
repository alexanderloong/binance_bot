import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 10) -> pd.Series:
    high = df['ha_high'] if 'ha_high' in df.columns else df['high']
    low = df['ha_low'] if 'ha_low' in df.columns else df['low']
    close = df['ha_close'] if 'ha_close' in df.columns else df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    high = df['ha_high'] if 'ha_high' in df.columns else df['high']
    low = df['ha_low'] if 'ha_low' in df.columns else df['low']
    close = df['ha_close'] if 'ha_close' in df.columns else df['close']
    
    atr = calculate_atr(df, period)
    hl2 = (high + low) / 2
    
    final_upperband = hl2 + (multiplier * atr)
    final_lowerband = hl2 - (multiplier * atr)
    supertrend = pd.Series(0.0, index=df.index)
    
    # Needs a loop to properly calculate Supertrend due to step dependencies
    for i in range(1, len(df.index)):
        if close.iloc[i-1] <= final_upperband.iloc[i-1]:
            final_upperband.iloc[i] = min(final_upperband.iloc[i], final_upperband.iloc[i-1])
        if close.iloc[i-1] >= final_lowerband.iloc[i-1]:
            final_lowerband.iloc[i] = max(final_lowerband.iloc[i], final_lowerband.iloc[i-1])
            
        if close.iloc[i] > final_upperband.iloc[i-1]:
            supertrend.iloc[i] = 1
        elif close.iloc[i] < final_lowerband.iloc[i-1]:
            supertrend.iloc[i] = -1
        else:
            supertrend.iloc[i] = supertrend.iloc[i-1]
            
    df['supertrend'] = supertrend
    return df
