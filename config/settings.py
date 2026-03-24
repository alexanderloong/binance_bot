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
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# Risk Management
RISK_PER_TRADE_PCNT = 0.01  # 1% risk per trade
LEVERAGE = 10
