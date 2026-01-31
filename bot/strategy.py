import time
from datetime import datetime, timedelta
import pytz
from config import (
    SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, TIMEFRAME, 
    ADX_LENGTH, ADX_THRESHOLD, ATR_LENGTH, ATR_MULTIPLIER, 
    PARTIAL_TP_ENABLED, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT,
    MAX_TRADES_PER_HOUR, POSITION_SIZE_PERCENT, LEVERAGE,
    RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD
)
from .data_processor import DataProcessor
from .utils import parse_timeframe_to_seconds

class Strategy:
    def __init__(self, exchange_client, logger):
        self.client = exchange_client
        self.logger = logger
        self.in_position = False 
        self.last_candle_time = None
        self.trade_history = [] # For rate limiting
        self.stop_loss_price = None
        self.take_profit_price = None
        self.partial_tp_hit = False
        
        # Parse timeframe for stale candle checking
        # Parse timeframe for stale candle checking
        self.tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)

    def check_rate_limit(self):
        current_time = time.time()
        # Keep only trades within last hour (3600 seconds)
        self.trade_history = [t for t in self.trade_history if current_time - t < 3600]
        
        if len(self.trade_history) >= MAX_TRADES_PER_HOUR:
            self.logger.warning(f"RATE LIMIT REACHED: {len(self.trade_history)} trades in last hour. Max is {MAX_TRADES_PER_HOUR}. Skipping trade.")
            return False
        return True

    def run_analysis(self):
        df = self.client.fetch_ohlcv(limit=300)
        
        if df is None or df.empty:
            self.logger.error("No data received from exchange.")
            return False
        
        # --- 1. POSITION MANAGEMENT (Every Poll) ---
        current_pos_amt, entry_price = self.client.get_current_position()
        
        if current_pos_amt != 0:
             current_price = df['close'].iloc[-1] # Current mark/last price
             
             # Reconstruct Stop Loss & Take Profit if missing (e.g. after bot restart)
             if self.stop_loss_price is None or (PARTIAL_TP_ENABLED and self.take_profit_price is None):
                 # Fetch ATR of the last closed candle
                 df_ha = DataProcessor.calculate_heikin_ashi(df)
                 atr_val = DataProcessor.calculate_atr(df_ha, ATR_LENGTH).iloc[-2]
                 
                 if self.stop_loss_price is None:
                    if current_pos_amt > 0:
                        self.stop_loss_price = entry_price - (atr_val * ATR_MULTIPLIER)
                    else:
                        self.stop_loss_price = entry_price + (atr_val * ATR_MULTIPLIER)
                    self.logger.info(f"Reconstructed SOFTWARE STOP LOSS at {self.stop_loss_price:.2f} (Entry: {entry_price:.2f})")
                 
                 if PARTIAL_TP_ENABLED and self.take_profit_price is None:
                    if current_pos_amt > 0:
                        self.take_profit_price = entry_price + (atr_val * PARTIAL_TP_MULTIPLIER)
                    else:
                        self.take_profit_price = entry_price - (atr_val * PARTIAL_TP_MULTIPLIER)
                    self.logger.info(f"Reconstructed PARTIAL TAKE PROFIT at {self.take_profit_price:.2f} (Target: {self.take_profit_price:.2f})")

             # --- PARTIAL TAKE PROFIT CHECK ---
             if PARTIAL_TP_ENABLED and not self.partial_tp_hit:
                 is_tp_hit = (current_pos_amt > 0 and current_price >= self.take_profit_price) or \
                             (current_pos_amt < 0 and current_price <= self.take_profit_price)
                 
                 if is_tp_hit:
                     self.logger.warning(f"PARTIAL TAKE PROFIT HIT at {current_price:.2f} (Target: {self.take_profit_price:.2f}).")
                     self.partial_close_position(current_pos_amt)
                     self.partial_tp_hit = True # Mark as hit for this position

             # Check for Stop Loss hit
             is_sl_hit = (current_pos_amt > 0 and current_price <= self.stop_loss_price) or \
                         (current_pos_amt < 0 and current_price >= self.stop_loss_price)
             
             if is_sl_hit:
                 self.logger.warning(f"SOFTWARE STOP LOSS HIT at {current_price:.2f} (Target: {self.stop_loss_price:.2f}). Closing position.")
                 self.close_all_positions()
                 self.stop_loss_price = None
                 self.take_profit_price = None
                 self.partial_tp_hit = False
                 return # Skip further analysis this cycle

        # --- FIX: Prevent Multi-Entry and Flickering ---
        try:
            # Get timestamp of the last CLOSED candle (second to last row)
            last_closed_candle = df.iloc[-2]
            last_closed_time = last_closed_candle['timestamp'] 
            last_closed_ts_val = int(last_closed_time.timestamp()) 
            
            # 1. If we already processed this EXACT candle, skip
            if self.last_candle_time is not None and self.last_candle_time == last_closed_ts_val:
                return False
                
            # 2. If we see a candle that is OLDER than our last processed one (API Flicker), skip
            if self.last_candle_time is not None and last_closed_ts_val < self.last_candle_time:
                # self.logger.debug(f"API Flicker detected: {last_closed_time} is older than last processed.")
                return False

            # Calculate Latency/Delay
            candle_close_time = last_closed_time + timedelta(seconds=self.tf_seconds)
            now = datetime.now(last_closed_time.tzinfo)
            delay_seconds = (now - candle_close_time).total_seconds()
            
            # 3. SUCCESS: It's a fresh, new candle.
            self.last_candle_time = last_closed_ts_val
            self.logger.info(f"Processing new candle: {last_closed_time} (Latency: {delay_seconds:.1f}s)")
            
        except Exception as e:
            self.logger.error(f"Error checking candle timestamp: {e}")
            return False
        # -----------------------------------------------

        df_ha = DataProcessor.calculate_heikin_ashi(df)
        df_st = DataProcessor.calculate_supertrend(df_ha)
        df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
        df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
        df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
        df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
        df_final = df_st
        
        # Get the last closed candle (second to last row, as last row is unfinished)
        last_candle = df_final.iloc[-2]
        prev_candle = df_final.iloc[-3]
        
        # SuperTrend columns will be named like SUPERT_15_1.5
        st_col = f"SUPERT_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
        st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}" # 1 for Buy, -1 for Sell
        
        current_trend = last_candle[st_dir_col]
        previous_trend = prev_candle[st_dir_col]
        
        close_price = last_candle['close']
        ema_val = last_candle[f'EMA_{EMA_LENGTH}']
        adx_val = last_candle['ADX']
        atr_val = last_candle['ATR']
        rsi_val = last_candle['RSI']
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        
        self.logger.info(f"Market Data: {candle_time} | Close: {close_price} | Trend: {current_trend} | EMA{EMA_LENGTH}: {ema_val:.2f} | ADX: {adx_val:.2f} | ATR: {atr_val:.2f} | RSI: {rsi_val:.2f}")

        # --- STALENESS CHECK (Only skip TRADE logic, not analysis logging) ---
        STALE_TOLERANCE = 120 
        
        if delay_seconds > STALE_TOLERANCE:
            if self.last_candle_time is None or last_closed_ts_val > self.last_candle_time:
                self.last_candle_time = last_closed_ts_val
            self.logger.warning(f"Candle {last_closed_time} is STALE (Closed {int(delay_seconds)}s ago). Skipping trade logic.")
            return False

        # Determine Trend Strength
        is_trending = adx_val > ADX_THRESHOLD
        
        # Determine RSI Conditions
        rsi_long_ok = rsi_val < RSI_OVERBOUGHT
        rsi_short_ok = rsi_val > RSI_OVERSOLD
        
        # Determine Signal based on Trend Flip + EMA Filter
        signal = None
        
        # Determine EMA filter
        is_uptrend_long = close_price > ema_val
        is_downtrend_short = close_price < ema_val
        
        # current_pos_amt already fetched above
        
        # 1. LOGIC ĐÓNG LỆNH (Exit Priority)
        # Note: Position management (SL) is handled at the start of run_analysis
        if current_pos_amt > 0 and current_trend == -1: # Existing Long & Trend turns Red
             self.logger.info(f"Trend flipped to RED. Closing LONG position ({current_pos_amt}).")
             self.close_all_positions()
             current_pos_amt = 0 
        elif current_pos_amt < 0 and current_trend == 1: # Existing Short & Trend turns Green
             self.logger.info(f"Trend flipped to GREEN. Closing SHORT position ({current_pos_amt}).")
             self.close_all_positions()
             current_pos_amt = 0

        # 2. LOGIC MỞ LỆNH (Entry Filtered)
        signal = None
        if current_trend == 1 and previous_trend == -1 and is_uptrend_long:
            if is_trending and rsi_long_ok:
                signal = 'LONG'
            else:
                reason = "ADX low" if not is_trending else "RSI overbought"
                self.logger.info(f"LONG signal detected, but {reason}. (ADX: {adx_val:.2f}, RSI: {rsi_val:.2f}). Skipping.")
        elif current_trend == -1 and previous_trend == 1 and is_downtrend_short:
            if is_trending and rsi_short_ok:
                signal = 'SHORT'
            else:
                reason = "ADX low" if not is_trending else "RSI oversold"
                self.logger.info(f"SHORT signal detected, but {reason}. (ADX: {adx_val:.2f}, RSI: {rsi_val:.2f}). Skipping.")
            
        if signal:
            if current_pos_amt == 0:
                self.logger.info(f"SIGNAL DETECTED: {signal} (Position is Empty)")
                self.open_position(signal, close_price, atr_val)
            else:
                self.logger.info(f"SIGNAL DETECTED: {signal}, but already in position ({current_pos_amt}). Skipping.")
        else:
            self.logger.info(f"No entry signal for {candle_time} (Current Trend: {current_trend}, Position: {current_pos_amt})")

    def close_all_positions(self):
        self.logger.info("Closing all positions and canceling orders...")
        # ExchangeClient.close_all_positions already handles canceling
        if self.client.close_all_positions():
            self.in_position = False
            self.stop_loss_price = None
            self.take_profit_price = None
            self.partial_tp_hit = False

    def partial_close_position(self, current_amt):
        try:
            # Calculate amount to close
            close_amount = abs(current_amt) * PARTIAL_TP_PERCENT
            side = 'sell' if current_amt > 0 else 'buy'
            
            self.logger.info(f"Executing PARTIAL CLOSE of {close_amount:.4f} BTC ({PARTIAL_TP_PERCENT*100}% of current position)")
            order_resp = self.client.create_order(side, close_amount)
            
            if order_resp:
                self.logger.info("Partial close order placed successfully.")
            else:
                self.logger.error("Partial close order failed.")
        except Exception as e:
            self.logger.error(f"Error during partial close: {e}")

    def open_position(self, side, price, atr_val):
        
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
            # Amount in USDT (Buying Power) = Balance * Position_Size % * Leverage
            amount_usdt = balance * POSITION_SIZE_PERCENT * LEVERAGE
            trade_amount = amount_usdt / price
            
            self.logger.info(f"Opening {side} position at {price} (Size: {POSITION_SIZE_PERCENT*100}% of Balance: {balance} USDT, Leverage: {LEVERAGE}x -> {trade_amount:.4f} BTC)")
            
            if side == 'LONG':
                 self.stop_loss_price = price - (atr_val * ATR_MULTIPLIER)
                 self.take_profit_price = price + (atr_val * PARTIAL_TP_MULTIPLIER)
            else:
                 self.stop_loss_price = price + (atr_val * ATR_MULTIPLIER)
                 self.take_profit_price = price - (atr_val * PARTIAL_TP_MULTIPLIER)
            
            self.partial_tp_hit = False
            self.logger.info(f"Setting SOFTWARE SL: {self.stop_loss_price:.2f}, PARTIAL TP: {self.take_profit_price:.2f} (ATR: {atr_val:.2f})")
            # -------------------------------------

            # Open Market Order (Long or Short)
            order_resp = self.client.create_order('buy' if side == 'LONG' else 'sell', trade_amount)
            
            if order_resp:
                self.in_position = True
                self.trade_history.append(time.time())
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
