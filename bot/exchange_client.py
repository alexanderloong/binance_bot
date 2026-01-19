import ccxt
import pandas as pd
from config import API_KEY, SECRET, USE_TESTNET, SYMBOL, TIMEFRAME

class ExchangeClient:
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Assuming futures trading for SuperTrend usually
            }
        })
        if USE_TESTNET:
            self.exchange.set_sandbox_mode(True)
        
        # Verify connection
        try:
            self.exchange.load_markets()
            print("Successfully connected to Binance")
        except Exception as e:
            print(f"Error connecting to Binance: {e}")

    def fetch_ohlcv(self, limit=100):
        try:
            bars = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def fetch_history(self, limit=1000):
        # Fetch larger history with basic pagination if needed, 
        # but for 1000, binance usually allows it in one go or we loop
        # For simplicity in this demo, we'll request the max allowed per call recursively or just one big call if supported
        try:
            # Binance limit is often 1000
            bars = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching history: {e}")
            return None

    def create_order(self, side, amount):
        try:
            order = self.exchange.create_market_order(SYMBOL, side, amount)
            return order
        except Exception as e:
            print(f"Error creating order: {e}")
            return None

    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0
