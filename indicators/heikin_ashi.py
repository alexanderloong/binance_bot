import pandas as pd

def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Heikin Ashi candles from standard OHLC dataframe.
    """
    ha_df = df.copy()
    
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    ha_df['ha_open'] = 0.0
    ha_df.iloc[0, ha_df.columns.get_loc('ha_open')] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2

    # Vectorized computation isn't straightforward for ha_open due to dependency
    # on previous ha_open, using traditional iteration for simplicity/correctness.
    ha_open_col_idx = ha_df.columns.get_loc('ha_open')
    ha_close_col_idx = ha_df.columns.get_loc('ha_close')
    
    for i in range(1, len(df)):
        ha_df.iloc[i, ha_open_col_idx] = (ha_df.iloc[i-1, ha_open_col_idx] + ha_df.iloc[i-1, ha_close_col_idx]) / 2
        
    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return ha_df
