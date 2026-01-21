import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET = os.getenv("SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Strategy Settings
SYMBOL = "BTC/USDT"
TIMEFRAME = "1m"
SUPERTREND_LENGTH = 15
SUPERTREND_FACTOR = 1.5
EMA_LENGTH = 100
LEVERAGE = 12
POSITION_SIZE_PERCENT = 1
