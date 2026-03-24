from abc import ABC, abstractmethod
import pandas as pd

class DataProvider(ABC):
    @abstractmethod
    def get_historical_data(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        pass
