from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a dataframe of historical data, computes indicators,
        and returns the dataframe adding a 'signal' column.
        signal: 1 for long, -1 for short, 0 for flat.
        """
        pass
