import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from core.logger import logger
from core.exceptions import DataFetchError
from config import settings

class BinanceDataClient:
    def __init__(self):
        self.client = Client(settings.API_KEY, settings.API_SECRET, testnet=settings.TESTNET)
        
    def get_historical_klines(self, symbol: str, interval: str, limit: int = 1500) -> pd.DataFrame:
        """Fetch historical futures klines."""
        try:
            logger.info(f"Fetching {limit} historical klines for {symbol} at {interval}")
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh').dt.tz_localize(None)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            df.set_index('timestamp', inplace=True)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            raise DataFetchError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error fetching data: {e}")
            raise DataFetchError(str(e))
