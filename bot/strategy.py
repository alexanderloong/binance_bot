from .data_processor import DataProcessor
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, TIMEFRAME
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
        # self.logger.info("Fetching market data...")
        # Fetch 300 candles to ensure EMA 100 and SuperTrend have enough history to stabilize
        df = self.client.fetch_ohlcv(limit=300)
        
        if df is None or df.empty:
            self.logger.error("No data received.")
            return False

        # --- FIX: Prevent Multi-Entry on same candle ---
        try:
            # Get timestamp of the last CLOSED candle (second to last row)
            last_closed_candle = df.iloc[-2]
            last_closed_time = last_closed_candle['timestamp'] # This is pd.Timestamp (tz aware)
            
            if self.last_candle_time == last_closed_time:
                # Candle already processed. Skip.
                return False
            
            # New candle detected
            self.last_candle_time = last_closed_time
            
            # --- STALENESS CHECK ---
            # If the candle closed too long ago, we should skip processing to avoid late entries
            # Example: Candle 01:15 closes at 01:30. If Now is 01:44, it is STALE.
            
            # Calculate when this candle should have closed
            candle_close_time = last_closed_time + timedelta(seconds=self.tf_seconds)
            
            # Get current time in same timezone (Asia/Ho_Chi_Minh or whatever df uses)
            now = datetime.now(last_closed_time.tzinfo)
            
            # Calculate delay
            delay_seconds = (now - candle_close_time).total_seconds()
            
            # Tolerance: If we are more than 2 minutes (120s) late after close, it's stale
            STALE_TOLERANCE = 120 
            
            if delay_seconds > STALE_TOLERANCE:
                self.logger.warning(f"Candle {last_closed_time} is STALE (Closed {int(delay_seconds)}s ago). Skipping trade logic.")
                return False
                
            self.logger.info(f"Processing new candle: {last_closed_time} (Latency: {delay_seconds:.1f}s)")
            
        except Exception as e:
            self.logger.error(f"Error checking candle timestamp: {e}")
            return False
        # -----------------------------------------------

        self.logger.info("Calculating Heikin Ashi, SuperTrend, and EMA...")
        df_ha = DataProcessor.calculate_heikin_ashi(df)
        df_st = DataProcessor.calculate_supertrend(df_ha)
        df_final = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)
        
        # Get the last closed candle (second to last row, as last row is unfinished)
        last_candle = df_final.iloc[-2]
        prev_candle = df_final.iloc[-3]
        
        # SuperTrend columns will be named like SUPERT_15_1.5, SUPERTd_15_1.5 (direction), SUPERTl_15_1.5 (long), SUPERTs_15_1.5 (short)
        st_col = f"SUPERT_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
        st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}" # 1 for Buy, -1 for Sell
        
        current_trend = last_candle[st_dir_col]
        previous_trend = prev_candle[st_dir_col]
        
        close_price = last_candle['close']
        ema_val = last_candle[f'EMA_{EMA_LENGTH}']
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        
        self.logger.info(f"Analysis Complete for candle {candle_time}. Close: {close_price}, Trend: {current_trend}, EMA {EMA_LENGTH}: {ema_val:.2f}")
        
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
            signal = 'LONG'
        elif current_trend == -1 and previous_trend == 1 and is_downtrend_short:
            signal = 'SHORT'
            
        # Only open if we have NO position (Empty State)
        if signal and current_pos_amt == 0:
            self.logger.info(f"SIGNAL DETECTED: {signal} (Position is Empty)")
            self.open_position(signal, close_price)

    def close_all_positions(self):
        self.logger.info("Closing all existing positions...")
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
            # Calculate trade amount using leverage
            # Amount in USDT (Buying Power) = Balance * Position_Size % * Leverage
            amount_usdt = balance * POSITION_SIZE_PERCENT * LEVERAGE
            trade_amount = amount_usdt / price
            
            self.logger.info(f"Opening {side} position at {price} (Size: {POSITION_SIZE_PERCENT*100}% of Balance: {balance} USDT, Leverage: {LEVERAGE}x -> {trade_amount:.4f} BTC)")
            
            if side == 'LONG':
                self.client.create_order('buy', trade_amount)
            else:
                self.client.create_order('sell', trade_amount)
            self.in_position = True
            self.trade_history.append(time.time())
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
