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
SUPERTREND_MULTIPLIER = 3.5
ATR_PERIOD = 14

USE_SL = True
SL_ATR_MULTIPLIER = 3.0   

# Indicators Filter
EMA_PERIOD = 200

USE_HTF_EMA = True
HTF_EMA_TIMEFRAME = 'h'
HTF_EMA_PERIOD = 50

# Risk Management
RISK_PER_TRADE_PCNT = 0.01  # 1% risk per trade
LEVERAGE = 10
