import pandas as pd
from indicators.ema import calculate_ema

def calculate_htf_ema(df: pd.DataFrame, htf_timeframe: str, htf_period: int, column_name: str = 'ema_htf') -> pd.DataFrame:
    """
    Resamples data to a higher timeframe, calculates EMA, and merges back with lookahead bias prevention.
    """
    df = df.copy()
    
    # Ensure index is datetime for resampling
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
        
    htf_df = df[['open', 'high', 'low', 'close', 'volume']].resample(
        htf_timeframe, label='right', closed='right'
    ).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Calculate EMA on HTF
    htf_df = calculate_ema(htf_df, period=htf_period, column_name=column_name)
    
    # STRICT: Shift by 1 to avoid lookahead bias. 
    # The value at 13:00 must be the EMA calculated from candles closing BEFORE 13:00 (i.e. up to 12:00).
    htf_df[column_name] = htf_df[column_name].shift(1)
    
    # Merge back to original timeframe and forward-fill
    df = df.merge(htf_df[[column_name]], left_index=True, right_index=True, how='left')
    df[column_name] = df[column_name].ffill()
    
    return df
