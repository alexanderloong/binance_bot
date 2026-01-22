from binance.um_futures import UMFutures
import pandas as pd
import logging
from config import API_KEY, SECRET, USE_TESTNET, SYMBOL, TIMEFRAME, LEVERAGE

class ExchangeClient:
    def __init__(self):
        self.logger = logging.getLogger("BinanceBot")
        
        # Determine base URL
        base_url = "https://fapi.binance.com"
        if USE_TESTNET:
            base_url = "https://testnet.binancefuture.com"
            
        self.client = UMFutures(key=API_KEY, secret=SECRET, base_url=base_url)
        
        # Prepare symbol
        self.symbol = SYMBOL.replace("/", "").upper()
        
        # Time synchronization offset
        self.time_offset = 0
        self.sync_time()
        
        # Verify connection
        try:
            # 1. Test connectivity (Ping)
            self.client.ping()
            self.logger.info("Connection to Binance API established.")
            
            # 2. Try to set leverage
            try:
                self.client.change_leverage(symbol=self.symbol, leverage=LEVERAGE, recvWindow=10000)
                self.logger.info(f"Leverage set to {LEVERAGE}x for {self.symbol}")
            except Exception as lev_e:
                self.logger.warning(f"Note: Could not set leverage (might be already set): {lev_e}")
            
            # 3. Check Balance
            balance = self.get_balance()
            self.logger.info(f"Successfully authenticated. Current Wallet Balance: {balance} USDT")
            
        except Exception as e:
            self.logger.error(f"Critical connection error: {e}")

    def sync_time(self):
        """Calculates the offset between local time and Binance server time."""
        try:
            res = self.client.time()
            server_time = res['serverTime']
            local_time = int(time.time() * 1000)
            self.time_offset = server_time - local_time
            self.logger.info(f"Time synced with Binance server. Offset: {self.time_offset}ms")
            
            # If we are ahead of the server, we should compensate
            if abs(self.time_offset) > 500:
                self.logger.warning(f"Significant time drift detected ({self.time_offset}ms). Applying correction.")
        except Exception as e:
            self.logger.error(f"Failed to sync time with Binance: {e}")
            self.time_offset = 0

    def fetch_ohlcv(self, limit=100):
        try:
            bars = self.client.klines(self.symbol, interval=TIMEFRAME, limit=limit)
            
            df = pd.DataFrame(bars, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
                
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            self.logger.error(f"Error fetching data for {SYMBOL}: {e}")
            return None

    def fetch_history(self, limit=1000):
        return self.fetch_ohlcv(limit=limit)

    def create_order(self, side, amount):
        try:
            side = side.upper()
            
            order = self.client.new_order(
                symbol=self.symbol,
                side=side,
                type='MARKET',
                quantity=round(amount, 3),
                recvWindow=10000
            )
            if order:
                self.logger.info(f"Market Order Successful: {side} {amount} {self.symbol} - ID: {order.get('orderId')}")
            return order
        except Exception as e:
            self.logger.error(f"Error creating market order: {e}")
            return None

    def create_stop_loss_order(self, side, amount, stop_price):
        """Creates a STOP_MARKET order using Mark Price to protect against wicks."""
        try:
            side = side.upper()
            # workingType='MARK_PRICE' is the key to ignore exchange-specific wicks
            order = self.client.new_order(
                symbol=self.symbol,
                side=side,
                type='STOP_MARKET',
                stopPrice=round(stop_price, 2),
                quantity=round(amount, 3),
                workingType='MARK_PRICE',
                reduceOnly=True, # Crucial: SL should only reduce position, not open a new one
                recvWindow=10000
            )
            if order:
                self.logger.info(f"Stop Market Order (SL) Set at {stop_price} (Mark Price) - ID: {order.get('orderId')}")
            return order
        except Exception as e:
            self.logger.error(f"Error creating Stop Loss order: {e}")
            return None

    def cancel_all_orders(self):
        """Cancels all open orders (like old Stop Losses) for the symbol."""
        try:
            self.client.cancel_open_orders(symbol=self.symbol, recvWindow=10000)
            self.logger.info(f"Canceled all open orders for {self.symbol}")
            return True
        except Exception as e:
            self.logger.warning(f"Could not cancel open orders: {e}")
            return False

    def get_balance(self):
        try:
            account_info = self.client.account(recvWindow=10000)
            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return 0.0

    def get_current_position(self):
        try:
            # Using get_position_risk is faster and more specific than account()
            positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    return float(pos['positionAmt'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error fetching position: {e}")
            return 0.0

    def close_all_positions(self):
        """Closes all positions for the current symbol by placing an offsetting market order."""
        try:
            # Get positions using get_position_risk (more efficient)
            positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    amt = float(pos['positionAmt'])
                    if amt != 0:
                        side = 'SELL' if amt > 0 else 'BUY'
                        # 1. Cancel any existing SL orders first
                        self.cancel_all_orders()
                        
                        # 2. Place Market Order to close
                        order = self.client.new_order(
                            symbol=self.symbol,
                            side=side,
                            type='MARKET',
                            quantity=abs(amt),
                            recvWindow=10000
                        )
                        self.logger.info(f"Closed position for {self.symbol}. Amount: {amt} - Order ID: {order.get('orderId')}")
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            return False
