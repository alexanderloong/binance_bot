import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET = os.getenv("SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Strategy Settings
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"             # Changed to 15m to reduce noise and fees
SUPERTREND_LENGTH = 15
SUPERTREND_FACTOR = 1.5       # Higher factor = more stable trend
EMA_LENGTH = 99              # Stronger trend filter
LEVERAGE = 10                 # Optimal leverage for BTC
POSITION_SIZE_PERCENT = 0.2   # Use 20% of balance per position (Balanced Risk/Reward)
MAX_TRADES_PER_HOUR = 5       # Safety: Limit trades per hour to prevent API spam
ADX_LENGTH = 14               # Standard ADX length
ADX_THRESHOLD = 22         # Trend strength threshold (common: 20 or 25)
ATR_LENGTH = 14               # Standard ATR length
ATR_MULTIPLIER = 1.5          # ATR multiplier for Stop Loss (Proposed: 1.5 - 2.0)


# Protection Settings
# (Stop Loss removed as per user request)
