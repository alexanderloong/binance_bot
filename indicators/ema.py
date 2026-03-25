import pandas as pd

def calculate_ema(df: pd.DataFrame, period: int = 200, column_name: str = 'ema') -> pd.DataFrame:
    """
    Calculates the Exponential Moving Average (EMA).
    Expects df to have a 'close' column.
    """
    df = df.copy()
    df[column_name] = df['close'].ewm(span=period, adjust=False).mean()
    return df
