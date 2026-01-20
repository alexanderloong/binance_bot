from .data_processor import DataProcessor
from config import SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH

class Strategy:
    def __init__(self, exchange_client, logger):
        self.client = exchange_client
        self.logger = logger
        self.in_position = False # Simple state tracking, ideally check balance or active orders

    def run_analysis(self):
        self.logger.info("Fetching market data...")
        # Fetch 300 candles to ensure EMA 100 and SuperTrend have enough history to stabilize
        df = self.client.fetch_ohlcv(limit=300)
        
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
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        
        self.logger.info(f"Analysis Complete for candle {candle_time}. Close: {close_price}, Trend: {current_trend}, EMA {EMA_LENGTH}: {ema_val:.2f}")
        
        # Determine Signal based on Trend Flip + EMA Filter
        signal = None
        
        # Determine EMA filter
        is_uptrend_long = close_price > ema_val
        is_downtrend_short = close_price < ema_val
        
        # 1. LOGIC ĐÓNG LỆNH: Đóng ngay khi Trend đổi màu (bảo vệ lợi nhuận)
        # (LƯU Ý: Trong thực tế bạn nên check API xem có lệnh đang mở thật không)
        if (self.in_position and current_trend == -1 and previous_trend != -1): # Trend đổi sang Đỏ
             self.logger.info(f"Trend flipped to RED. Closing positions if any.")
             self.close_all_positions()
        elif (self.in_position and current_trend == 1 and previous_trend != 1): # Trend đổi sang Xanh
             self.logger.info(f"Trend flipped to GREEN. Closing positions if any.")
             self.close_all_positions()

        # 2. LOGIC MỞ LỆNH: Cần Trend Flip + EMA Filter
        signal = None
        if current_trend == 1 and previous_trend == -1 and is_uptrend_long:
            signal = 'LONG'
        elif current_trend == -1 and previous_trend == 1 and is_downtrend_short:
            signal = 'SHORT'
            
        if signal and not self.in_position:
            self.logger.info(f"SIGNAL DETECTED: {signal}")
            self.open_position(signal, close_price)

    def close_all_positions(self):
        # Placeholder for closing all open positions logic
        self.logger.info("Closing all existing positions...")
        # self.client.close_all_orders() or similar
        self.in_position = False

    def open_position(self, side, price):
        from config import POSITION_SIZE_PERCENT
        # Calculate amount based on % balance
        try:
            balance = self.client.get_balance()
            trade_amount = (balance * POSITION_SIZE_PERCENT) / price
            
            self.logger.info(f"Opening {side} position at {price} (Size: {POSITION_SIZE_PERCENT*100}% of Balance: {balance} USDT -> {trade_amount:.4f} BTC)")
            
            if side == 'LONG':
                self.client.create_order('buy', trade_amount)
            else:
                self.client.create_order('sell', trade_amount)
            self.in_position = True
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")
