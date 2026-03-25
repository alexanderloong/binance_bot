import pandas as pd
from strategy.base import BaseStrategy
from indicators.heikin_ashi import calculate_heikin_ashi
from indicators.supertrend import calculate_supertrend
from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from indicators.volume import calculate_volume_ma
from indicators.htf_ema import calculate_htf_ema
from config import settings

class SupertrendHAStrategy(BaseStrategy):
    def __init__(
        self, 
        period=None, 
        multiplier=None, 
        atr_period=None, 
        ema_period=None, 
        use_ema=None
    ):
        super().__init__("Supertrend HA")
        self.period = period if period is not None else settings.SUPERTREND_PERIOD
        self.multiplier = multiplier if multiplier is not None else settings.SUPERTREND_MULTIPLIER
        self.atr_period = atr_period if atr_period is not None else settings.ATR_PERIOD
        self.ema_period = ema_period if ema_period is not None else settings.EMA_PERIOD
        self.use_ema = use_ema if use_ema is not None else getattr(settings, 'USE_EMA', True)
        
        self.use_htf_ema = getattr(settings, 'USE_HTF_EMA', False)
        self.htf_ema_timeframe = getattr(settings, 'HTF_EMA_TIMEFRAME', '1H')
        self.htf_ema_period = getattr(settings, 'HTF_EMA_PERIOD', 50)

        # Volume Filter settings
        self.use_volume_filter = getattr(settings, 'USE_VOLUME_FILTER', False)
        self.volume_ma_period = getattr(settings, 'VOLUME_MA_PERIOD', 20)
        self.volume_threshold = getattr(settings, 'VOLUME_THRESHOLD', 1.5)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate ATR
        df = calculate_atr(df, period=self.atr_period)
        
        # Calculate EMA (Primary Timeframe)
        df = calculate_ema(df, period=self.ema_period)
        
        # Calculate HTF EMA
        if self.use_htf_ema:
            # logic moved to indicators/htf_ema.py
            df = calculate_htf_ema(df, self.htf_ema_timeframe, self.htf_ema_period)
        
        if self.use_volume_filter:
            # volume_ma calculation moved to indicators/volume.py
            df = calculate_volume_ma(df, period=self.volume_ma_period)
        
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
            
        if self.use_htf_ema:
            # Entry 15m Long only if 15m Close > 1H EMA 50
            long_condition &= (df['close'] > df['ema_htf'])
            # Entry 15m Short only if 15m Close < 1H EMA 50
            short_condition &= (df['close'] < df['ema_htf'])
            
        if self.use_volume_filter:
            # Volume filter: current volume > average volume * threshold
            # volume_ma is already shifted by 1
            volume_condition = (df['volume'] > df['volume_ma'] * self.volume_threshold)
            
            # Apply filter only to entries, not exits (optional, but requested logic is for entry)
            long_condition &= volume_condition
            short_condition &= volume_condition
            
        # If flipped but entry condition not met, it's a close-only signal
        close_short_only = flip_to_long & ~long_condition
        close_long_only = flip_to_short & ~short_condition
        
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[close_short_only, 'signal'] = 2
        df.loc[close_long_only, 'signal'] = -2
        
        df['trend_state'] = df['supertrend']
        
        return df
