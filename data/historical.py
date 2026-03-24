import os
import time
import pandas as pd
from data.provider import DataProvider
from data.binance_client import BinanceDataClient

def get_expiration_seconds(timeframe: str) -> int:
    try:
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        if unit == 'm':
            return value * 60 * 1000 # Extended to bypass ban
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 86400
        elif unit == 'w':
            return value * 86400 * 7
        return 300
    except:
        return 300

class HistoricalDataProvider(DataProvider):
    def __init__(self):
        self.client = BinanceDataClient()
        
    def get_historical_data(self, symbol: str, timeframe: str, limit: int = 1500) -> pd.DataFrame:
        os.makedirs("data", exist_ok=True)
        csv_filename = f"data/{symbol}_{timeframe}.csv"
        
        if os.path.exists(csv_filename):
            file_age = time.time() - os.path.getmtime(csv_filename)
            expiration_time = get_expiration_seconds(timeframe)
            
            if file_age < expiration_time:
                try:
                    df = pd.read_csv(csv_filename, index_col='timestamp', parse_dates=True)
                    if len(df) >= limit:
                        print(f"Using cached data from {csv_filename} (Age: {int(file_age)}s)")
                        return df.tail(limit)
                    else:
                        print(f"Cached data has only {len(df)} rows (requested {limit}). Fetching new data.")
                except Exception as e:
                    print(f"Error reading cache: {e}. Fetching new data.")
            else:
                print(f"Cached data expired (Age: {int(file_age)}s). Fetching new data.")
                
        df = self.client.get_historical_klines(symbol, timeframe, limit)
        
        # Lưu data tải về vào file csv
        df.to_csv(csv_filename)
        print(f"Data saved to {csv_filename}")
        
        return df

