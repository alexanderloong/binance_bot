import os
from dotenv import load_dotenv

# ==========================================
# BINANCE TRADING BOT CONFIGURATION
# Version: 1.11.0
# Date: 2026-02-03
# Strategy: Pure Trend Following (SuperTrend + EMA + ADX + RSI + Vol)
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
SUPERTREND_LENGTH = 18        # Length for ATR calculation in SuperTrend
SUPERTREND_FACTOR = 1.5       # Multiplier for Band width
EMA_LENGTH = 102              # EMA Baseline (Price > EMA = Bullish)

# Risk Management
LEVERAGE = 1                  # Leverage multiplier
POSITION_SIZE_PERCENT = 1     # 100% of Equity per Trade

# Safety
MAX_TRADES_PER_HOUR = 5       # API Rate Limit Protection

# Filters
# Additional conditions to improve Win/Loss Quality
ADX_LENGTH = 14               
ADX_THRESHOLD = 18            # Trend Strength (Buy only if ADX > 18)

ATR_LENGTH = 14
ATR_MULTIPLIER = 0.8          # Tight SL (0.8x ATR) to cut losses fast

# Momentum (RSI)
# Avoid entering at extreme exhaustion points
RSI_LENGTH = 14
RSI_OVERBOUGHT = 64           # Long limit
RSI_OVERSOLD = 36             # Short limit

# Volume
# Confirm breakout validity
VOLUME_MA_LENGTH = 177        # Long-term Volume MA to detect anomalous activity

# ------------------------------------------
# EXIT SETTINGS
# ------------------------------------------
# Pure Trend Following: No Partial TP, ride until reversal.
# Stop Loss is handled dynamically by ATR logic in bot
