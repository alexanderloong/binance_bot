import pandas as pd
from strategy.base import BaseStrategy
from indicators.heikin_ashi import calculate_heikin_ashi
from indicators.supertrend import calculate_supertrend
from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
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
        
        # HTF EMA settings
        self.use_htf_ema = getattr(settings, 'USE_HTF_EMA', False)
        self.htf_ema_timeframe = getattr(settings, 'HTF_EMA_TIMEFRAME', '1H')
        self.htf_ema_period = getattr(settings, 'HTF_EMA_PERIOD', 50)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Calculate ATR
        df = calculate_atr(df, period=self.atr_period)
        
        # Calculate EMA (Primary Timeframe)
        df = calculate_ema(df, period=self.ema_period)
        
        # Calculate HTF EMA
        if self.use_htf_ema:
            # Resample to HTF (e.g. 15m -> 1H)
            # Ensure index is datetime for resampling
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
                
            htf_df = df[['open', 'high', 'low', 'close', 'volume']].resample(
                self.htf_ema_timeframe, label='right', closed='right'
            ).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Calculate EMA on HTF
            htf_df = calculate_ema(htf_df, period=self.htf_ema_period, column_name='ema_htf')
            
            # STRICT: Shift by 1 to avoid lookahead bias. 
            # The value at 13:00 must be the EMA calculated from candles closing BEFORE 13:00 (i.e. up to 12:00).
            htf_df['ema_htf'] = htf_df['ema_htf'].shift(1)
            
            # Merge back to 15m and forward-fill
            df = df.merge(htf_df[['ema_htf']], left_index=True, right_index=True, how='left')
            df['ema_htf'] = df['ema_htf'].ffill()
        
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
            
        # If flipped but entry condition not met, it's a close-only signal
        close_short_only = flip_to_long & ~long_condition
        close_long_only = flip_to_short & ~short_condition
        
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[close_short_only, 'signal'] = 2
        df.loc[close_long_only, 'signal'] = -2
        
        df['trend_state'] = df['supertrend']
        
        return df
