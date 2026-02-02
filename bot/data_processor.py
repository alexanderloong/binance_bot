import pandas as pd
import numpy as np
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR

class DataProcessor:
    @staticmethod
    def calculate_heikin_ashi(df):
        heikin_ashi_df = df.copy()
        
        # ha_close = (open + high + low + close) / 4
        heikin_ashi_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        # ha_open = (prev_ha_open + prev_ha_close) / 2
        # Use a list to iterate quickly
        ha_open = [df['open'].iloc[0]]
        ha_close = heikin_ashi_df['ha_close'].values
        
        for i in range(1, len(df)):
            ha_open.append((ha_open[i-1] + ha_close[i-1]) / 2)
            
        heikin_ashi_df['ha_open'] = ha_open
        heikin_ashi_df['ha_high'] = heikin_ashi_df[['high', 'ha_open', 'ha_close']].max(axis=1)
        heikin_ashi_df['ha_low'] = heikin_ashi_df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        return heikin_ashi_df

    @staticmethod
    def calculate_atr(df, length):
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Wilders Smoothing (equivalent to EWM with alpha=1/length)
        atr = tr.ewm(alpha=1/length, adjust=False).mean()
        return atr

    @staticmethod
    def calculate_adx(df, length):
        # Standard Wilders DMI calculation
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        plus_dm_mask = (plus_dm > minus_dm)
        minus_dm_mask = (minus_dm > plus_dm)
        
        plus_dm[~plus_dm_mask] = 0
        minus_dm[~minus_dm_mask] = 0
        
        tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        
        # Smoothed values using Wilders (EWM)
        atr_smoothed = tr.ewm(alpha=1/length, adjust=False).mean()
        plus_dm_smoothed = plus_dm.ewm(alpha=1/length, adjust=False).mean()
        minus_dm_smoothed = minus_dm.ewm(alpha=1/length, adjust=False).mean()
        
        plus_di = 100 * (plus_dm_smoothed / atr_smoothed)
        minus_di = 100 * (minus_dm_smoothed / atr_smoothed)
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/length, adjust=False).mean()
        
        return adx

    @staticmethod
    def calculate_ema(df, length=200):
        df[f'EMA_{length}'] = df['close'].ewm(span=length, adjust=False).mean()
        return df

    @staticmethod
    def calculate_rsi(df, length=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_volume_ma(df, length=20):
        """Calculate Volume Moving Average."""
        df[f'VOL_MA_{length}'] = df['volume'].rolling(window=length).mean()
        return df

    @staticmethod
    def calculate_supertrend(df, length=SUPERTREND_LENGTH, multiplier=SUPERTREND_FACTOR):
        # Manual SuperTrend Implementation
        
        df = df.copy()
        # SuperTrend usually uses HA candles if passed, or standard ones.
        # Let's use the internal calculate_atr logic but specific to HA for SuperTrend
        high = df['ha_high']
        low = df['ha_low']
        close_ha = df['ha_close']
        prev_close_ha = close_ha.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close_ha).abs()
        tr3 = (low - prev_close_ha).abs()
        atr_ha = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).ewm(alpha=1/length, adjust=False).mean()
        
        hl2 = (df['ha_high'] + df['ha_low']) / 2
        
        basic_upperband = hl2 + (multiplier * atr_ha)
        basic_lowerband = hl2 - (multiplier * atr_ha)
        
        upperband = basic_upperband.copy()
        lowerband = basic_lowerband.copy()
        trend = np.zeros(len(df))
        
        close = df['ha_close'].values
        
        # Iterative calculation for SuperTrend
        # Start from index 1 (since 0 has no prev)
        for i in range(1, len(df)):
            # Calculate Upper Band
            if basic_upperband.iloc[i] < upperband.iloc[i-1] or close[i-1] > upperband.iloc[i-1]:
                upperband.iloc[i] = basic_upperband.iloc[i]
            else:
                upperband.iloc[i] = upperband.iloc[i-1]

            # Calculate Lower Band
            if basic_lowerband.iloc[i] > lowerband.iloc[i-1] or close[i-1] < lowerband.iloc[i-1]:
                lowerband.iloc[i] = basic_lowerband.iloc[i]
            else:
                lowerband.iloc[i] = lowerband.iloc[i-1]
                
            # Calculate Trend
            # 1 is UpTrend (Green), -1 is DownTrend (Red)
            # Default to previous trend if no switch
            prev_trend = trend[i-1] if i > 0 else 1
            
            if prev_trend == 1:
                if close[i] < lowerband.iloc[i]:
                    trend[i] = -1 # Switch to Downtrend
                else:
                    trend[i] = 1
            else:
                if close[i] > upperband.iloc[i]:
                    trend[i] = 1 # Switch to Uptrend
                else:
                    trend[i] = -1
                    
        df[f'SUPERT_{length}_{multiplier}'] = np.where(trend == 1, lowerband, upperband)
        df[f'SUPERTd_{length}_{multiplier}'] = trend
        
        return df
