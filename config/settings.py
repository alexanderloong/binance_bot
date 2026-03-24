import os
from dotenv import load_dotenv

load_dotenv()

# Binance API Credentials
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() == "true"

# Trading Pair Configuration
SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"

# Strategy Parameters
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# Risk Management
RISK_PER_TRADE_PCNT = 0.01  # 1% risk per trade
LEVERAGE = 10
