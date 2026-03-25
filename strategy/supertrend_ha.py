import pandas as pd
from strategy.base import BaseStrategy
from indicators.heikin_ashi import calculate_heikin_ashi
from indicators.supertrend import calculate_supertrend
from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from config import settings

class SupertrendHAStrategy(BaseStrategy):
    def __init__(self, period=None, multiplier=None, atr_period=None, ema_period=None, use_ema=None):
        super().__init__("Supertrend HA")
        self.period = period if period is not None else settings.SUPERTREND_PERIOD
        self.multiplier = multiplier if multiplier is not None else settings.SUPERTREND_MULTIPLIER
        self.atr_period = atr_period if atr_period is not None else settings.ATR_PERIOD
        self.ema_period = ema_period if ema_period is not None else settings.EMA_PERIOD
        self.use_ema = use_ema if use_ema is not None else getattr(settings, 'USE_EMA', True)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate ATR
        df = calculate_atr(df, period=self.atr_period)
        
        # Calculate EMA
        df = calculate_ema(df, period=self.ema_period)
        
        # Calculate HA candles
        df = calculate_heikin_ashi(df)
        
        # Calculate Supertrend
        df = calculate_supertrend(df, period=self.period, multiplier=self.multiplier)
        
        df['signal'] = 0
        
        # Detect flips
        st_shifted = df['supertrend'].shift(1)
        
        # Long entry / Short exit: previous was -1 or 0, now 1
        flip_to_long = (st_shifted <= 0) & (df['supertrend'] == 1)
        long_condition = flip_to_long
        close_short_only = pd.Series(False, index=df.index)
        if self.use_ema:
            long_condition = flip_to_long & (df['close'] > df['ema'])
            close_short_only = flip_to_long & ~(df['close'] > df['ema'])
            
        # Short entry / Long exit: previous was 1 or 0, now -1
        flip_to_short = (st_shifted >= 0) & (df['supertrend'] == -1)
        short_condition = flip_to_short
        close_long_only = pd.Series(False, index=df.index)
        if self.use_ema:
            short_condition = flip_to_short & (df['close'] < df['ema'])
            close_long_only = flip_to_short & ~(df['close'] < df['ema'])
        
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[close_short_only, 'signal'] = 2
        df.loc[close_long_only, 'signal'] = -2
        
        df['trend_state'] = df['supertrend']
        
        return df
