import pandas as pd

def calculate_volume_ma(df: pd.DataFrame, period: int = 20, column_name: str = 'volume_ma') -> pd.DataFrame:
    """
    Calculates the Simple Moving Average (SMA) of Volume.
    Shifted by 1 to avoid lookahead bias.
    """
    df = df.copy()
    df[column_name] = df['volume'].rolling(window=period).mean().shift(1)
    return df
