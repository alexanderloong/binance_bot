import pandas as pd
from strategy.base import BaseStrategy
from indicators.heikin_ashi import calculate_heikin_ashi
from indicators.supertrend import calculate_supertrend
from config import settings

class SupertrendHAStrategy(BaseStrategy):
    def __init__(self, period=None, multiplier=None):
        super().__init__("Supertrend HA")
        self.period = period if period is not None else settings.SUPERTREND_PERIOD
        self.multiplier = multiplier if multiplier is not None else settings.SUPERTREND_MULTIPLIER

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate HA candles
        df = calculate_heikin_ashi(df)
        
        # Calculate Supertrend
        df = calculate_supertrend(df, period=self.period, multiplier=self.multiplier)
        
        df['signal'] = 0
        
        # Detect flips
        st_shifted = df['supertrend'].shift(1)
        
        # Long entry: previous was -1 or 0, now 1
        long_condition = (st_shifted <= 0) & (df['supertrend'] == 1)
        # Short entry: previous was 1 or 0, now -1
        short_condition = (st_shifted >= 0) & (df['supertrend'] == -1)
        
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        
        df['trend_state'] = df['supertrend']
        
        return df
