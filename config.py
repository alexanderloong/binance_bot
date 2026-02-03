import os
from dotenv import load_dotenv

# ==========================================
# BINANCE TRADING BOT CONFIGURATION
# Version: 1.10.0
# Date: 2026-02-02
# Strategy: Trend Following (SuperTrend + EMA + ADX + RSI + Vol)
# ==========================================

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

API_KEY = os.getenv("API_KEY")
SECRET = os.getenv("SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() == "true"

# ------------------------------------------
# STRATEGY SETTINGS
# ------------------------------------------
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"             # Timeframe: 15m (Balance between noise and trend)

# Trend Indicators
# Optimized for capturing major swings while filtering chop
SUPERTREND_LENGTH = 16        # Length for ATR calculation in SuperTrend
SUPERTREND_FACTOR = 1.45      # Multiplier for Band width (1.45 offers tight trail)
EMA_LENGTH = 106              # EMA Baseline (Price > EMA = Bullish)

# Risk Management
# High Leverage / Controlled Drawdown approach
LEVERAGE = 15                 # Leverage 15x
POSITION_SIZE_PERCENT = 0.25  # Allocating 25% of Equity per Trade

# Safety
MAX_TRADES_PER_HOUR = 5       # API Rate Limit Protection

# Filters
# Additional conditions to improve Win/Loss Quality
ADX_LENGTH = 14               
ADX_THRESHOLD = 19            # Trend Strength (Buy only if ADX > 19)

ATR_LENGTH = 14
ATR_MULTIPLIER = 0.9          # Tight SL (0.9x ATR) to cut losses fast

# Momentum (RSI)
# Avoid entering at extreme exhaustion points
RSI_LENGTH = 14
RSI_OVERBOUGHT = 65           # Long limit
RSI_OVERSOLD = 35             # Short limit

# Volume
# Confirm breakout validity
VOLUME_MA_LENGTH = 147        # Long-term Volume MA to detect anomalous activity

# ------------------------------------------
# EXIT SETTINGS
# ------------------------------------------
# Pure Trend Following: No Partial TP, ride until reversal.
PARTIAL_TP_ENABLED = False
PARTIAL_TP_MULTIPLIER = 2   
PARTIAL_TP_PERCENT = 0.2

# Protection Settings
# Stop Loss is handled dynamically by ATR logic in bot

