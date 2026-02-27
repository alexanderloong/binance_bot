import time
from datetime import datetime, timedelta
from typing import Optional, List, Any
import pandas as pd # Type hint requirement

from config import settings
from bot.notifier import Notifier
from .data_processor import DataProcessor
from .utils import parse_timeframe_to_seconds

class Strategy:
    def __init__(self, exchange_client: Any, logger: Any, notifier: Optional[Notifier] = None):
        self.client = exchange_client
        self.logger = logger
        self.notifier = notifier
        self.in_position: bool = False 
        self.last_candle_time: Optional[int] = None
        self.trade_history: List[float] = [] # For rate limiting
        self.stop_loss_price: Optional[float] = None
        
        # Parse timeframe for stale candle checking
        self.tf_seconds: int = parse_timeframe_to_seconds(settings.TIMEFRAME)

    def check_rate_limit(self) -> bool:
        current_time = time.time()
        # Keep only trades within last hour (3600 seconds)
        self.trade_history = [t for t in self.trade_history if current_time - t < 3600]
        
        if len(self.trade_history) >= settings.MAX_TRADES_PER_HOUR:
            self.logger.warning(f"RATE LIMIT REACHED: {len(self.trade_history)} trades in last hour. Max is {settings.MAX_TRADES_PER_HOUR}. Skipping trade.")
            return False
        return True

    def run_analysis(self) -> bool:
        """
        Main analysis loop called every cycle.
        Returns False if no action was taken or data was valid but no trade.
        """
        df = self.client.fetch_ohlcv(limit=300)
        
        if df is None or df.empty:
            self.logger.error("No data received from exchange.")
            return False
        
        # --- 1. POSITION MANAGEMENT (Every Poll) ---
        current_pos_amt, entry_price = self.client.get_current_position()
        
        if current_pos_amt != 0:
             self._manage_open_position(df, current_pos_amt, entry_price)
             # If position closed during management, update? 
             # Ideally we return here if SL triggered to avoid entering same candle logic immediately
             # But legacy logic allows continuation if safe. 
             # Logic from old run_analysis: "return # Skip further analysis this cycle" if SL hit.
             if self.stop_loss_price is None and current_pos_amt != 0: 
                 # This implies SL was hit and cleared (and position closing initiated), 
                 # OR it's a new position without SL (unlikely due to open_position logic).
                 # To act exactly like before:
                 pass

        # --- FIX: Prevent Multi-Entry and Flickering ---
        delay_seconds = self._check_new_candle(df)
        if delay_seconds is None:
            return False

        # --- DATA PROCESSING ---
        df_final = self._prepare_indicators(df)
        
        # --- SIGNAL ANALYSIS ---
        self._analyze_market_and_trade(df_final, current_pos_amt, entry_price, delay_seconds)
        return True

    def _manage_open_position(self, df: pd.DataFrame, current_pos_amt: float, entry_price: float) -> None:
        """
        Handles Stop Loss and basic position logic.
        """
        current_price = df['close'].iloc[-1] # Current mark/last price
        
        # Reconstruct Stop Loss if missing (e.g. after bot restart)
        if self.stop_loss_price is None:
            # Fetch ATR of the last closed candle
            df_ha = DataProcessor.calculate_heikin_ashi(df)
            atr_val = DataProcessor.calculate_atr(df_ha, settings.ATR_LENGTH).iloc[-2]
            
            if current_pos_amt > 0:
                self.stop_loss_price = entry_price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                self.stop_loss_price = entry_price + (atr_val * settings.ATR_MULTIPLIER)
            self.logger.info(f"Reconstructed SOFTWARE STOP LOSS at {self.stop_loss_price:.2f} (Entry: {entry_price:.2f})")

        # Check for Stop Loss hit
        is_sl_hit = (current_pos_amt > 0 and current_price <= self.stop_loss_price) or \
                    (current_pos_amt < 0 and current_price >= self.stop_loss_price)
        
        if is_sl_hit:
            self.logger.warning(f"SOFTWARE STOP LOSS HIT at {current_price:.2f} (Target: {self.stop_loss_price:.2f}). Closing position.")
            if self.notifier:
                self.notifier.send_lark_message(f"⚠️ **SOFTWARE STOP LOSS HIT**\nCurrent Price: {current_price:.2f}\nTarget SL: {self.stop_loss_price:.2f}\nClosing position.")
            self.close_all_positions()
            self.stop_loss_price = None

    def _check_new_candle(self, df: pd.DataFrame) -> Optional[float]:
        """
        Checks if the latest data represents a new, valid candle to process.
        Returns:
            Optional[float]: Delay in seconds if valid new candle, None if should skip.
        """
        try:
            # Get timestamp of the last CLOSED candle (second to last row)
            last_closed_candle = df.iloc[-2]
            last_closed_time = last_closed_candle['timestamp'] 
            last_closed_ts_val = int(last_closed_time.timestamp()) 
            
            # 1. If we already processed this EXACT candle, skip
            if self.last_candle_time is not None and self.last_candle_time == last_closed_ts_val:
                return None
                
            # 2. If we see a candle that is OLDER than our last processed one (API Flicker), skip
            if self.last_candle_time is not None and last_closed_ts_val < self.last_candle_time:
                return None

            # Calculate Latency/Delay
            candle_close_time = last_closed_time + timedelta(seconds=self.tf_seconds)
            now = datetime.now(last_closed_time.tzinfo)
            delay_seconds = (now - candle_close_time).total_seconds()
            
            # 3. SUCCESS: It's a fresh, new candle.
            self.last_candle_time = last_closed_ts_val
            self.logger.info(f"Processing new candle: {last_closed_time} (Latency: {delay_seconds:.1f}s)")
            return delay_seconds
            
        except Exception as e:
            self.logger.error(f"Error checking candle timestamp: {e}")
            return None

    def _prepare_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df_ha = DataProcessor.calculate_heikin_ashi(df)
        df_st = DataProcessor.calculate_supertrend(df_ha)
        df_st[f'EMA_{settings.EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=settings.EMA_LENGTH)[f'EMA_{settings.EMA_LENGTH}']
        df_st['ADX'] = DataProcessor.calculate_adx(df, length=settings.ADX_LENGTH)
        df_st['ATR'] = DataProcessor.calculate_atr(df, length=settings.ATR_LENGTH)
        df_st['RSI'] = DataProcessor.calculate_rsi(df, length=settings.RSI_LENGTH)
        df_st = DataProcessor.calculate_volume_ma(df_st, length=settings.VOLUME_MA_LENGTH)
        df_st[f'EMA_{settings.EMA_SLOPE_EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=settings.EMA_SLOPE_EMA_LENGTH)[f'EMA_{settings.EMA_SLOPE_EMA_LENGTH}']
        return df_st

    def _analyze_market_and_trade(self, df_final: pd.DataFrame, current_pos_amt: float, entry_price: float, delay_seconds: float) -> None:
        
        # Get the last closed candle (second to last row, as last row is unfinished)
        last_candle = df_final.iloc[-2]
        prev_candle = df_final.iloc[-3]
        
        # SuperTrend columns will be named like SUPERT_15_1.5
        st_col = f"SUPERT_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
        st_dir_col = f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}" # 1 for Buy, -1 for Sell
        
        current_trend = last_candle[st_dir_col]
        previous_trend = prev_candle[st_dir_col]
        
        close_price = last_candle['close']
        ema_val = last_candle[f'EMA_{settings.EMA_LENGTH}']
        adx_val = last_candle['ADX']
        atr_val = last_candle['ATR']
        rsi_val = last_candle['RSI']
        vol_ma_val = last_candle[f'VOL_MA_{settings.VOLUME_MA_LENGTH}']
        current_volume = last_candle['volume']
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        
        ema_slope_val = last_candle[f'EMA_{settings.EMA_SLOPE_EMA_LENGTH}']
        ema_slope_prev = df_final.iloc[-(settings.EMA_SLOPE_LOOKBACK + 1)][f'EMA_{settings.EMA_SLOPE_EMA_LENGTH}']
        ema_slope_pct = (ema_slope_val - ema_slope_prev) / ema_slope_prev if ema_slope_prev != 0 else 0
        is_flat_slope = abs(ema_slope_pct) < settings.EMA_SLOPE_THRESHOLD

        self.logger.info(f"Market Data: {candle_time} | Close: {close_price} | Trend: {current_trend} | EMA{settings.EMA_LENGTH}: {ema_val:.2f} | ADX: {adx_val:.2f} | ATR: {atr_val:.2f} | RSI: {rsi_val:.2f} | Vol: {current_volume:.0f} (MA: {vol_ma_val:.0f}) | EMA{settings.EMA_SLOPE_EMA_LENGTH} Slope: {ema_slope_pct*100:.3f}% ({'FLAT' if is_flat_slope else 'STEEP'})")

        # --- BEARISH DIVERGENCE CHECK (Rule 3) ---
        bearish_div = DataProcessor.check_bearish_divergence(df_final, lookback=settings.RSI_DIV_LOOKBACK, min_rsi=settings.RSI_DIV_MIN_RSI)
        if bearish_div:
            self.logger.info(f"⚠️ BEARISH DIVERGENCE DETECTED (RSI Peaks in last {settings.RSI_DIV_LOOKBACK} candles)!")

        # --- STALENESS CHECK (Only skip TRADE logic, not analysis logging) ---
        STALE_TOLERANCE = 120 
        if delay_seconds > STALE_TOLERANCE:
            if self.last_candle_time is None: # Should technically be set by _check_new_candle
                 pass 
            self.logger.warning(f"Candle {candle_time} is STALE (Closed {int(delay_seconds)}s ago). Skipping trade logic.")
            return

        # Determine Trend Strength
        is_trending = adx_val > settings.ADX_THRESHOLD
        
        # Determine RSI Conditions
        rsi_long_ok = settings.RSI_LONG_THRESHOLD < rsi_val < settings.RSI_OVERBOUGHT
        rsi_short_ok = rsi_val > settings.RSI_OVERSOLD
        
        # Determine Volume Condition
        vol_ok = current_volume > vol_ma_val
        
        # Determine Signal based on Trend Flip + EMA Filter
        is_uptrend_long = close_price > ema_val
        is_downtrend_short = close_price < ema_val
        
        # 1. LOGIC ĐÓNG LỆNH (Exit Priority)
        if current_pos_amt > 0 and current_trend == -1: # Existing Long & Trend turns Red
             self.logger.info(f"Trend flipped to RED. Closing LONG position ({current_pos_amt}).")
             self.close_all_positions()
             current_pos_amt = 0 
        elif current_pos_amt < 0 and current_trend == 1: # Existing Short & Trend turns Green
             self.logger.info(f"Trend flipped to GREEN. Closing SHORT position ({current_pos_amt}).")
             self.close_all_positions()
             self.close_all_positions()
             current_pos_amt = 0
        
        # 1b. RSI DIVERGENCE - PARTIAL CLOSE & BE
        elif current_pos_amt > 0 and bearish_div:
             # If SL is below entry, we are not at BE.
             is_sl_at_be = self.stop_loss_price is not None and self.stop_loss_price >= entry_price
             
             if not is_sl_at_be:
                 self.logger.info(f"Bearish Divergence on Long. Action: Close {settings.RSI_DIV_PARTIAL_CLOSE_PCT*100}% & Move SL to BE.")
                 
                 # 1. Partial Close
                 close_amt = abs(current_pos_amt) * settings.RSI_DIV_PARTIAL_CLOSE_PCT
                 self.partial_close_position(close_amt, 'sell')
                 
                 # 2. Move SL to Break Even (plus small buffer?)
                 self.stop_loss_price = entry_price * 1.001 # 0.1% buffer
                 self.logger.info(f"Moved Software SL to Break Even: {self.stop_loss_price}")

        # 2. LOGIC MỞ LỆNH (Entry Filtered)
        signal: Optional[str] = None
        if current_trend == 1 and previous_trend == -1 and is_uptrend_long:
            if bearish_div:
                self.logger.info("LONG signal detected but BLOCKED by Bearish Divergence.")
                signal = None
            elif is_trending and rsi_long_ok and vol_ok:
                signal = 'LONG'
            else:
                reasons = []
                if not is_trending: reasons.append("ADX low")
                if not rsi_long_ok: reasons.append(f"RSI invalid (Req: {settings.RSI_LONG_THRESHOLD}-{settings.RSI_OVERBOUGHT})")
                if not vol_ok: reasons.append("Volume low")
                self.logger.info(f"LONG signal detected, but {', '.join(reasons)}. (ADX: {adx_val:.2f}, RSI: {rsi_val:.2f}, Vol: {current_volume:.0f}). Skipping.")
        elif current_trend == -1 and previous_trend == 1 and is_downtrend_short:
            if is_trending and rsi_short_ok and vol_ok:
                signal = 'SHORT'
            else:
                reasons = []
                if not is_trending: reasons.append("ADX low")
                if not rsi_short_ok: reasons.append("RSI oversold")
                if not vol_ok: reasons.append("Volume low")
                self.logger.info(f"SHORT signal detected, but {', '.join(reasons)}. (ADX: {adx_val:.2f}, RSI: {rsi_val:.2f}, Vol: {current_volume:.0f}). Skipping.")
            
        if signal:
            if current_pos_amt == 0:
                self.logger.info(f"SIGNAL DETECTED: {signal} (Position is Empty)")
                # Dynamic Position Sizing based on EMA Slope
                actual_pos_size = settings.REDUCED_POSITION_SIZE_PERCENT if is_flat_slope else settings.POSITION_SIZE_PERCENT
                if is_flat_slope:
                    self.logger.info(f"⚠️ EMA{settings.EMA_SLOPE_EMA_LENGTH} is FLAT (Slope: {ema_slope_pct*100:.3f}% < {settings.EMA_SLOPE_THRESHOLD*100}%). Reducing size to {actual_pos_size*100}%.")
                
                self.open_position(signal, close_price, atr_val, pos_size_pct=actual_pos_size)
            else:
                self.logger.info(f"SIGNAL DETECTED: {signal}, but already in position ({current_pos_amt}). Skipping.")
        else:
            self.logger.info(f"No entry signal for {candle_time} (Current Trend: {current_trend}, Position: {current_pos_amt})")

    def close_all_positions(self) -> None:
        self.logger.info("Closing all positions and canceling orders...")
        if self.client.close_all_positions():
            self.in_position = False
            self.stop_loss_price = None
            if self.notifier:
                self.notifier.send_lark_message("🛑 **All Positions Closed / Orders Canceled**")

    def partial_close_position(self, quantity: float, side: str) -> None:
        self.logger.info(f"Partially closing {quantity:.4f} ({side})...")
        try:
             order = self.client.create_order(side, quantity)
             if order:
                 self.logger.info("Partial close successful.")
                 if self.notifier:
                     self.notifier.send_lark_message(f"✂️ **Partial Close Successful**\nSide: {side}\nQuantity: {quantity:.4f}")
        except Exception as e:
             self.logger.error(f"Failed to partial close: {e}")

    def open_position(self, side: str, price: float, atr_val: float, pos_size_pct: float = settings.POSITION_SIZE_PERCENT) -> None:
        
        # Safety Check: Rate Limit
        if not self.check_rate_limit():
            return

        # Calculate amount based on % balance
        try:
            balance = self.client.get_balance()
            if balance is None:
                self.logger.error("Could not fetch balance. Aborting position opening.")
                return

            # Calculate trade amount using leverage
            amount_usdt = balance * pos_size_pct * settings.LEVERAGE
            trade_amount = amount_usdt / price
            
            self.logger.info(f"Opening {side} position at {price} (Size: {pos_size_pct*100}% of Balance: {balance} USDT, Leverage: {settings.LEVERAGE}x -> {trade_amount:.4f} BTC)")
            
            if side == 'LONG':
                 self.stop_loss_price = price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                 self.stop_loss_price = price + (atr_val * settings.ATR_MULTIPLIER)
            
            self.logger.info(f"Setting SOFTWARE SL: {self.stop_loss_price:.2f} (ATR: {atr_val:.2f})")
            # -------------------------------------

            # Open Market Order (Long or Short)
            order_resp = self.client.create_order('buy' if side == 'LONG' else 'sell', trade_amount)
            
            if order_resp:
                self.in_position = True
                self.trade_history.append(time.time())
                if self.notifier:
                    self.notifier.send_lark_message(
                        f"✅ **Position Opened ({side})**\n"
                        f"Entry Price: {price:.2f}\n"
                        f"Amount: {trade_amount:.4f} BTC\n"
                        f"Stop Loss: {self.stop_loss_price:.2f}\n"
                        f"Leverage: {settings.LEVERAGE}x"
                    )
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
