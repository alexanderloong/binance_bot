import ccxt
import pandas as pd
import logging
from config import API_KEY, SECRET, USE_TESTNET, SYMBOL, TIMEFRAME, LEVERAGE

class ExchangeClient:
    def __init__(self):
        self.logger = logging.getLogger("BinanceBot")
        self.exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
            }
        })
        if USE_TESTNET:
            self.exchange.set_sandbox_mode(True)
        
        # Verify connection and set leverage
        try:
            self.exchange.load_markets()
            self.exchange.set_leverage(LEVERAGE, SYMBOL)
            
            balance = self.get_balance()
            self.logger.info(f"Successfully connected to Binance. Leverage set to {LEVERAGE}x for {SYMBOL}")
            self.logger.info(f"Current Wallet Balance: {balance} USDT")
        except Exception as e:
            self.logger.error(f"Error connecting to Binance: {e}")

    def fetch_ohlcv(self, limit=100):
        try:
            bars = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return None

    def fetch_history(self, limit=1000):
        try:
            bars = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching history: {e}")
            return None

    def create_order(self, side, amount):
        try:
            order = self.exchange.create_market_order(SYMBOL, side, amount)
            return order
        except Exception as e:
            self.logger.error(f"Error creating order: {e}")
            return None

    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return 0.0
