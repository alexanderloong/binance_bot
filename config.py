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
LEVERAGE = 12
POSITION_SIZE_PERCENT = 0.9   # Trading with 90% of balance per position
MAX_TRADES_PER_HOUR = 5       # Safety: Limit max trades per hour to prevent spamming

# Protection Settings
STOP_LOSS_PERCENT = 0.03      # 2% stop loss từ giá entry
USE_MARK_PRICE_FOR_STOP = True # Dùng Mark Price để tránh râu nến quét ảo
