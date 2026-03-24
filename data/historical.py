from data.provider import DataProvider
from data.binance_client import BinanceDataClient
import pandas as pd
import os

class HistoricalDataProvider(DataProvider):
    def __init__(self):
        self.client = BinanceDataClient()
        
    def get_historical_data(self, symbol: str, timeframe: str, limit: int = 1500) -> pd.DataFrame:
        df = self.client.get_historical_klines(symbol, timeframe, limit)
        
        # Lưu data tải về vào file csv
        os.makedirs("data", exist_ok=True)
        csv_filename = f"data/{symbol}_{timeframe}.csv"
        df.to_csv(csv_filename)
        print(f"Data saved to {csv_filename}")
        
        return df
