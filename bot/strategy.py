from .data_processor import DataProcessor
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, TIMEFRAME, ADX_LENGTH, ADX_THRESHOLD, ATR_LENGTH
from datetime import datetime, timedelta
import pytz

class Strategy:
    def __init__(self, exchange_client, logger):
        self.client = exchange_client
        self.logger = logger
        self.in_position = False 
        self.last_candle_time = None
        self.trade_history = [] # For rate limiting
        
        # Parse timeframe for stale candle checking
        self.tf_seconds = 900 # Default 15m
        try:
            val = int(''.join(c for c in TIMEFRAME if c.isdigit()))
            unit = ''.join(c for c in TIMEFRAME if c.isalpha()).lower()
            if unit == 'm': self.tf_seconds = val * 60
            elif unit == 'h': self.tf_seconds = val * 3600
            elif unit == 'd': self.tf_seconds = val * 86400
        except:
            pass

    def check_rate_limit(self):
        from config import MAX_TRADES_PER_HOUR
        import time
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
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        
        self.logger.info(f"Market Data: {candle_time} | Close: {close_price} | Trend: {current_trend} | EMA{EMA_LENGTH}: {ema_val:.2f} | ADX: {adx_val:.2f} | ATR: {atr_val:.2f}")

        # --- STALENESS CHECK (Only skip TRADE logic, not analysis logging) ---
        STALE_TOLERANCE = 120 
        
        if delay_seconds > STALE_TOLERANCE:
            if self.last_candle_time is None or last_closed_ts_val > self.last_candle_time:
                self.last_candle_time = last_closed_ts_val
            self.logger.warning(f"Candle {last_closed_time} is STALE (Closed {int(delay_seconds)}s ago). Skipping trade logic.")
            return False

        # Determine Trend Strength
        is_trending = adx_val > ADX_THRESHOLD
        
        # Determine Signal based on Trend Flip + EMA Filter
        signal = None
        
        # Determine EMA filter
        is_uptrend_long = close_price > ema_val
        is_downtrend_short = close_price < ema_val
        
        # 0. Get Real Position from Exchange
        current_pos_amt = self.client.get_current_position()
        
        # 1. LOGIC ĐÓNG LỆNH (Exit Priority)
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
            if is_trending:
                signal = 'LONG'
            else:
                self.logger.info(f"LONG signal detected, but ADX ({adx_val:.2f}) is below threshold ({ADX_THRESHOLD}). Skipping.")
        elif current_trend == -1 and previous_trend == 1 and is_downtrend_short:
            if is_trending:
                signal = 'SHORT'
            else:
                self.logger.info(f"SHORT signal detected, but ADX ({adx_val:.2f}) is below threshold ({ADX_THRESHOLD}). Skipping.")
            
        if signal:
            if current_pos_amt == 0:
                self.logger.info(f"SIGNAL DETECTED: {signal} (Position is Empty)")
                self.open_position(signal, close_price)
            else:
                self.logger.info(f"SIGNAL DETECTED: {signal}, but already in position ({current_pos_amt}). Skipping.")
        else:
            self.logger.info(f"No entry signal for {candle_time} (Current Trend: {current_trend}, Position: {current_pos_amt})")

    def close_all_positions(self):
        self.logger.info("Closing all positions and canceling orders...")
        # ExchangeClient.close_all_positions already handles canceling
        if self.client.close_all_positions():
            self.in_position = False

    def open_position(self, side, price):
        from config import POSITION_SIZE_PERCENT, LEVERAGE
        import time
        
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
            
            from config import STOP_LOSS_PERCENT
            
            if side == 'LONG':
                # 1. Open Market Long
                order_resp = self.client.create_order('buy', trade_amount)
                if order_resp:
                    # 2. Set Stop Loss (Sell order)
                    stop_price = price * (1 - STOP_LOSS_PERCENT)
                    self.client.create_stop_loss_order('sell', trade_amount, stop_price)
            else:
                # 1. Open Market Short
                order_resp = self.client.create_order('sell', trade_amount)
                if order_resp:
                    # 2. Set Stop Loss (Buy order)
                    stop_price = price * (1 + STOP_LOSS_PERCENT)
                    self.client.create_stop_loss_order('buy', trade_amount, stop_price)
            
            self.in_position = True
            self.trade_history.append(time.time())
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
