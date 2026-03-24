from data.provider import DataProvider
from data.binance_client import BinanceDataClient
import pandas as pd

class HistoricalDataProvider(DataProvider):
    def __init__(self):
        self.client = BinanceDataClient()
        
    def get_historical_data(self, symbol: str, timeframe: str, limit: int = 1500) -> pd.DataFrame:
        return self.client.get_historical_klines(symbol, timeframe, limit)
