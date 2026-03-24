import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculates the Average True Range (ATR) based on Wilder's Smoothing Method.
    Expects df to have 'high', 'low', 'close' columns.
    """
    df = df.copy()
    
    # Calculate True Range components
    high_low = df['high'] - df['low']
    high_prev_close = np.abs(df['high'] - df['close'].shift(1))
    low_prev_close = np.abs(df['low'] - df['close'].shift(1))
    
    # True Range is the maximum of the three components
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    
    # Calculate ATR using Wilder's Smoothing Method (RMA)
    df['atr'] = tr.ewm(alpha=1/period, adjust=False).mean()
    
    return df
