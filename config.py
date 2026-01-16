import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET = os.getenv("BINANCE_SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Strategy Settings
SYMBOL = "BTC/USDT"
TIMEFRAME = "1d"
SUPERTREND_LENGTH = 15
SUPERTREND_FACTOR = 3.0
POSITION_SIZE_PERCENT = 1.00
