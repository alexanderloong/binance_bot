from .data_processor import DataProcessor
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH

class Strategy:
    def __init__(self, exchange_client, logger):
        self.client = exchange_client
        self.logger = logger
        self.in_position = False # Simple state tracking, ideally check balance or active orders

    def run_analysis(self):
        self.logger.info("Fetching market data...")
        df = self.client.fetch_ohlcv(limit=100)
        
        if df is None or df.empty:
            self.logger.error("No data received.")
            return

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
        
        self.logger.info(f"Analysis Complete. Close: {close_price}, Trend: {current_trend}, EMA {EMA_LENGTH}: {ema_val:.2f}")
        
        # Determine Signal based on Trend Flip + EMA Filter
        signal = None
        
        # Filter: Long if Price > EMA, Short if Price < EMA
        is_uptrend_long = close_price > ema_val
        is_downtrend_short = close_price < ema_val
        
        if current_trend == 1 and previous_trend == -1:
            if is_uptrend_long:
                signal = 'LONG' # Trend Green + Above EMA
            else:
                self.logger.info(f"LONG signal ignored (Price < EMA {EMA_LENGTH})")
        elif current_trend == -1 and previous_trend == 1:
            if is_downtrend_short:
                signal = 'SHORT' # Trend Red + Below EMA
            else:
                self.logger.info(f"SHORT signal ignored (Price > EMA {EMA_LENGTH})")
            
        if signal:
            self.logger.info(f"SIGNAL DETECTED: {signal}")
            
            # 1. Close Opposite Positions
            self.close_all_positions()
            
            # 2. Open New Position
            self.open_position(signal, close_price)

    def close_all_positions(self):
        # Placeholder for closing all open positions logic
        self.logger.info("Closing all existing positions...")
        # self.client.close_all_orders() or similar
        self.in_position = False

    def open_position(self, side, price):
        from config import POSITION_SIZE_PERCENT
        # Calculate amount based on % balance
        # balance = self.client.get_balance()
        # trade_amount = (balance * POSITION_SIZE_PERCENT) / price
        
        self.logger.info(f"Opening {side} position at {price} (Size: {POSITION_SIZE_PERCENT*100}% of Balance)")
        # if side == 'LONG':
        #     self.client.create_order('buy', trade_amount)
        # else:
        #     self.client.create_order('sell', trade_amount)
        self.in_position = True
