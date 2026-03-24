import os
from dotenv import load_dotenv

load_dotenv()

# Binance API Credentials
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("SECRET", "")
TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# Trading Pair Configuration
SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"

# Strategy Parameters
SUPERTREND_PERIOD = 7
SUPERTREND_MULTIPLIER = 2.0
ATR_PERIOD = 14
SL_ATR_MULTIPLIER = 0.1

# Risk Management
RISK_PER_TRADE_PCNT = 0.01  # 1% risk per trade
LEVERAGE = 10
