import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET = os.getenv("SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Strategy Settings
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"             # Changed to 15m to reduce noise and fees
SUPERTREND_LENGTH = 10
SUPERTREND_FACTOR = 3.0       # Higher factor = more stable trend
EMA_LENGTH = 100              # Stronger trend filter
LEVERAGE = 12
POSITION_SIZE_PERCENT = 0.2   # Trading with 20% of balance per position
