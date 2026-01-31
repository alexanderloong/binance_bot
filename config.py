import os
from dotenv import load_dotenv

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

API_KEY = os.getenv("API_KEY")
SECRET = os.getenv("SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Strategy Settings
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"             # Changed to 15m to reduce noise and fees
SUPERTREND_LENGTH = 15
SUPERTREND_FACTOR = 1.5       # Higher factor = more stable trend
EMA_LENGTH = 106              # Stronger trend filter
LEVERAGE = 20                 # Optimal leverage for BTC
POSITION_SIZE_PERCENT = 0.2   # Use 30% of balance per position (Balanced Risk/Reward)
MAX_TRADES_PER_HOUR = 5       # Safety: Limit trades per hour to prevent API spam
ADX_LENGTH = 14               # Standard ADX length
ADX_THRESHOLD = 19         # Trend strength threshold (common: 20 or 25)
ATR_LENGTH = 14               # Standard ATR length
ATR_MULTIPLIER = 0.9          # ATR multiplier for Stop Loss (Proposed: 1.5 - 2.0)

# RSI Filter Settings
RSI_LENGTH = 14
RSI_OVERBOUGHT = 66
RSI_OVERSOLD = 35

# Volume MA Filter Settings
VOLUME_MA_LENGTH = 55

# Partial Take Profit Settings
PARTIAL_TP_ENABLED = True
PARTIAL_TP_MULTIPLIER = 5.3   # Take profit at 2.0x ATR
PARTIAL_TP_PERCENT = 0.1      # Close 50% of position


# Protection Settings
# (Stop Loss removed as per user request)
