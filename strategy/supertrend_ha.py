import pandas as pd
from strategy.base import BaseStrategy
from indicators.heikin_ashi import calculate_heikin_ashi
from indicators.supertrend import calculate_supertrend
from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from indicators.adx import calculate_adx
from config import settings

class SupertrendHAStrategy(BaseStrategy):
    def __init__(
        self, 
        period=None, 
        multiplier=None, 
        atr_period=None, 
        ema_period=None, 
        use_ema=None,
        use_adx=None,
        adx_period=None,
        adx_threshold=None
    ):
        super().__init__("Supertrend HA")
        self.period = period if period is not None else settings.SUPERTREND_PERIOD
        self.multiplier = multiplier if multiplier is not None else settings.SUPERTREND_MULTIPLIER
        self.atr_period = atr_period if atr_period is not None else settings.ATR_PERIOD
        self.ema_period = ema_period if ema_period is not None else settings.EMA_PERIOD
        self.use_ema = use_ema if use_ema is not None else getattr(settings, 'USE_EMA', True)
        self.use_adx = use_adx if use_adx is not None else getattr(settings, 'USE_ADX', True)
        self.adx_period = adx_period if adx_period is not None else getattr(settings, 'ADX_PERIOD', 14)
        self.adx_threshold = adx_threshold if adx_threshold is not None else getattr(settings, 'ADX_THRESHOLD', 20)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate ATR
        df = calculate_atr(df, period=self.atr_period)
        
        # Calculate EMA
        df = calculate_ema(df, period=self.ema_period)
        
        # Calculate ADX
        df = calculate_adx(df, period=self.adx_period)
        
        # Calculate HA candles
        df = calculate_heikin_ashi(df)
        
        # Calculate Supertrend
        df = calculate_supertrend(df, period=self.period, multiplier=self.multiplier)
        
        df['signal'] = 0
        
        # Detect flips
        st_shifted = df['supertrend'].shift(1)
        
        # Base flips
        flip_to_long = (st_shifted <= 0) & (df['supertrend'] == 1)
        flip_to_short = (st_shifted >= 0) & (df['supertrend'] == -1)
        
        # Cumulative conditions for entry
        long_condition = flip_to_long.copy()
        short_condition = flip_to_short.copy()
        
        if self.use_ema:
            long_condition &= (df['close'] > df['ema'])
            short_condition &= (df['close'] < df['ema'])
            
        if self.use_adx:
            long_condition &= (df['adx'] > self.adx_threshold)
            short_condition &= (df['adx'] > self.adx_threshold)
            
        # If flipped but entry condition not met, it's a close-only signal
        close_short_only = flip_to_long & ~long_condition
        close_long_only = flip_to_short & ~short_condition
        
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[close_short_only, 'signal'] = 2
        df.loc[close_long_only, 'signal'] = -2
        
        df['trend_state'] = df['supertrend']
        
        return df
