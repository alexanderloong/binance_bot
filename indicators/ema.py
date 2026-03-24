import pandas as pd

def calculate_ema(df: pd.DataFrame, period: int = 200) -> pd.DataFrame:
    """
    Calculates the Exponential Moving Average (EMA).
    Expects df to have a 'close' column.
    """
    df = df.copy()
    df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
    return df
