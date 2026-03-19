import pandas as pd
import numpy as np
from typing import List
from config import settings

class DataProcessor:
    @staticmethod
    def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates Heikin Ashi candles.
        
        Args:
            df (pd.DataFrame): Input dataframe with open, high, low, close.
            
        Returns:
            pd.DataFrame: DataFrame with added ha_open, ha_high, ha_low, ha_close columns.
        """
        heikin_ashi_df = df.copy()
        
        # ha_close = (open + high + low + close) / 4
        heikin_ashi_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        # ha_open = (prev_ha_open + prev_ha_close) / 2
        # Use a list to iterate quickly (Vectorization is hard for recursive calculation)
        ha_open = [df['open'].iloc[0]]
        ha_close = heikin_ashi_df['ha_close'].values
        
        for i in range(1, len(df)):
            ha_open.append((ha_open[i-1] + ha_close[i-1]) / 2)
            
        heikin_ashi_df['ha_open'] = ha_open
        heikin_ashi_df['ha_high'] = heikin_ashi_df[['high', 'ha_open', 'ha_close']].max(axis=1)
        heikin_ashi_df['ha_low'] = heikin_ashi_df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        return heikin_ashi_df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, length: int) -> pd.Series:
        """
        Calculates Trend (ATR).
        """
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
    def calculate_adx(df: pd.DataFrame, length: int) -> pd.Series:
        """
        Calculates ADX (Average Directional Index).
        """
        # Standard Wilders DMI calculation
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        
        # Determine movement direction
        # If +DM < 0, set to 0
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # Compare +DM vs -DM
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
        
        # Avoid division by zero
        plus_di = 100 * (plus_dm_smoothed / atr_smoothed.replace(0, np.nan))
        minus_di = 100 * (minus_dm_smoothed / atr_smoothed.replace(0, np.nan))
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1/length, adjust=False).mean()
        
        return adx.fillna(0)

    @staticmethod
    def calculate_ema(df: pd.DataFrame, length: int = 200) -> pd.DataFrame:
        df[f'EMA_{length}'] = df['close'].ewm(span=length, adjust=False).mean()
        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    @staticmethod
    def calculate_volume_ma(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
        """Calculate Volume Moving Average."""
        df[f'VOL_MA_{length}'] = df['volume'].rolling(window=length).mean()
        return df

    @staticmethod
    def resample_to_htf(df: pd.DataFrame, htf: str) -> pd.DataFrame:
        """
        Resample base timeframe OHLCV dataframe to a higher timeframe.

        Args:
            df: Base timeframe df with 'timestamp' column (timezone-aware).
            htf: Target timeframe string, e.g. '1h', '4h', '1d'.

        Returns:
            Resampled DataFrame with OHLCV columns and DatetimeIndex.
        """
        # Map timeframe string to pandas offset alias
        alias_map = {
            "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
            "30m": "30min", "1h": "1h", "2h": "2h", "4h": "4h",
            "6h": "6h", "8h": "8h", "12h": "12h", "1d": "1D", "1w": "1W",
        }
        offset = alias_map.get(htf, htf)

        df_indexed = df.set_index("timestamp")
        df_htf = df_indexed["close"].resample(offset).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        # Need to resample all OHLCV columns properly
        df_htf = df_indexed.resample(offset).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).dropna()

        df_htf = df_htf.reset_index().rename(columns={"timestamp": "timestamp"})
        return df_htf

    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, length: int = settings.SUPERTREND_LENGTH, multiplier: float = settings.SUPERTREND_FACTOR) -> pd.DataFrame:
        """
        Calculates SuperTrend indicator.
        Note: Needs HA candles if intending to run on Heikin Ashi data.
        """
        df = df.copy()
        
        high = df['ha_high']
        low = df['ha_low']
        close_ha = df['ha_close']
        prev_close_ha = close_ha.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close_ha).abs()
        tr3 = (low - prev_close_ha).abs()
        
        # Calculate ATR for SuperTrend
        # Typically uses ATR of the input source (HA or Normal)
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

    @staticmethod
    def check_bearish_divergence(df: pd.DataFrame, lookback: int = 10, min_rsi: int = 60) -> bool:
        """
        Detects Bearish Divergence:
        - Price makes Higher High
        - RSI makes Lower High
        - Current RSI Peak > min_rsi
        Returns True if divergence is detected on the last closed candle.
        """
        if len(df) < lookback + 5:
            return False

        highs = df['high'].values
        rsi = df['RSI'].values
        
        # We look at historical peaks within the window ending at -2 (last closed candle)
        # Because index -1 is the current forming candle
        current_idx = len(df) - 2
        
        start_scan = current_idx - lookback
        if start_scan < 0: start_scan = 0
        
        # Find peaks indices: i where rsi[i] > rsi[i-1] and rsi[i] > rsi[i+1]
        peak_indices: List[int] = []
        
        for i in range(start_scan, current_idx): 
            # safety check for boundaries
            if i - 1 >= 0 and i + 1 < len(rsi):
                if rsi[i] > rsi[i-1] and rsi[i] > rsi[i+1]:
                    if rsi[i] > min_rsi:
                        peak_indices.append(i)
                    
        if len(peak_indices) < 2:
            return False
            
        # P2 is the most recent peak
        p2_idx = peak_indices[-1]
        # P1 is the previous peak
        p1_idx = peak_indices[-2]
        
        # Check if P2 is "recent enough" to effectively be the "current" signal
        # E.g., if peak happened 1-3 bars ago, we consider it active divergence
        if current_idx - p2_idx > 3:
            return False
            
        price_p2 = highs[p2_idx]
        rsi_p2 = rsi[p2_idx]
        
        price_p1 = highs[p1_idx]
        rsi_p1 = rsi[p1_idx]
        
        # Bearish Divergence:
        # Price Higher High: P2_price > P1_price
        # RSI Lower High: P2_rsi < P1_rsi
        if price_p2 > price_p1 and rsi_p2 < rsi_p1:
            return True
            
        return False
