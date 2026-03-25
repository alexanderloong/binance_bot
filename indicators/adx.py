import pandas as pd
import numpy as np

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX) using Wilder's smoothing.
    Requires columns: 'high', 'low', 'close'
    Adds columns: 'plus_di', 'minus_di', 'dx', 'adx'
    """
    df = df.copy()
    
    # Calculate True Range (TR)
    high_low = df['high'] - df['low']
    high_close_prev = (df['high'] - df['close'].shift(1)).abs()
    low_close_prev = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    
    # Calculate Directional Movement (+DM and -DM)
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)
    
    # Wilder's Smoothing (alpha = 1 / period)
    alpha = 1.0 / period
    tr_smoothed = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smoothed = plus_dm.ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smoothed = minus_dm.ewm(alpha=alpha, adjust=False).mean()
    
    # Calculate DI
    plus_di = 100 * (plus_dm_smoothed / tr_smoothed)
    minus_di = 100 * (minus_dm_smoothed / tr_smoothed)
    
    # Calculate DX
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di)).fillna(0)
    
    # Calculate ADX
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    df['dx'] = dx
    df['adx'] = adx
    
    return df
