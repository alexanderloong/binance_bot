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
        
        # Verify connection
        try:
            # 1. Test connectivity (Ping)
            self.client.ping()
            self.logger.info("Connection to Binance API established.")
            
            # 2. Try to set leverage (Often fails with -1000 on Testnet, which we can ignore if it's already set)
            try:
                self.client.change_leverage(symbol=self.symbol, leverage=LEVERAGE)
                self.logger.info(f"Leverage set to {LEVERAGE}x for {self.symbol}")
            except Exception as lev_e:
                # If error is -1000 (Unknown) or leverage is already set, we just log and continue
                self.logger.warning(f"Note: Could not set leverage (might be already set): {lev_e}")
            
            # 3. Check Balance
            balance = self.get_balance()
            self.logger.info(f"Successfully authenticated. Current Wallet Balance: {balance} USDT")
            
        except Exception as e:
            self.logger.error(f"Critical connection error: {e}")

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
                quantity=round(amount, 3)
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
                reduceOnly=True # Crucial: SL should only reduce position, not open a new one
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
            self.client.cancel_open_orders(symbol=self.symbol)
            self.logger.info(f"Canceled all open orders for {self.symbol}")
            return True
        except Exception as e:
            self.logger.warning(f"Could not cancel open orders: {e}")
            return False

    def get_balance(self):
        try:
            account_info = self.client.account()
            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return 0.0

    def get_current_position(self):
        try:
            positions = self.client.account()['positions']
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
            positions = self.client.account()['positions']
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
                            quantity=abs(amt)
                        )
                        self.logger.info(f"Closed position for {self.symbol}. Amount: {amt} - Order ID: {order.get('orderId')}")
            return True
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            return False
