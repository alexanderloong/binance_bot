import os
from dotenv import load_dotenv
from dataclasses import dataclass

# ==========================================
# BINANCE TRADING BOT CONFIGURATION
# Version: 1.15.0 (Production Stable Release 2026)
# Date: 2026-02-06
# Strategy: Pure Trend Following (SuperTrend + EMA + ADX + RSI + Vol)
# ==========================================

# Load .env from project root or resource directory
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), 'resource', '.env')
load_dotenv(env_path)

@dataclass(frozen=True)
class TradingConfig:
    # Credentials
    API_KEY: str = os.getenv("API_KEY", "")
    SECRET: str = os.getenv("SECRET", "")
    USE_TESTNET: bool = os.getenv("USE_TESTNET", "True").lower() == "true"
    LARK_WEBHOOK_URL: str = os.getenv("LARK_WEBHOOK_URL", "")

    # Strategy Settings
    SYMBOL: str = "BTC/USDT"
    TIMEFRAME: str = "15m"
    
    # Trend Indicators
    SUPERTREND_LENGTH: int = 18
    SUPERTREND_FACTOR: float = 1.45
    EMA_LENGTH: int = 102
    
    # Risk Management
    LEVERAGE: int = 10
    POSITION_SIZE_PERCENT: float = 0.2
    
    # Safety
    MAX_TRADES_PER_HOUR: int = 5
    
    # Filters
    ADX_LENGTH: int = 14
    ADX_THRESHOLD: int = 18
    ATR_LENGTH: int = 14
    ATR_MULTIPLIER: float = 0.7
    
    # Momentum (RSI)
    RSI_LENGTH: int = 14
    RSI_OVERBOUGHT: int = 64
    RSI_OVERSOLD: int = 36
    RSI_LONG_THRESHOLD: int = 53
    
    # Volume
    VOLUME_MA_LENGTH: int = 177
    
    # Rule 2: EMA Slope
    EMA_SLOPE_EMA_LENGTH: int = 200
    EMA_SLOPE_LOOKBACK: int = 20
    EMA_SLOPE_THRESHOLD: float = 0.002
    REDUCED_POSITION_SIZE_PERCENT: float = 0.15
    
    # Rule 3: RSI Divergence
    RSI_DIV_LOOKBACK: int = 14
    RSI_DIV_MIN_RSI: int = 78
    RSI_DIV_PARTIAL_CLOSE_PCT: float = 0.1

# Instantiate global settings
settings = TradingConfig()

# Expose global variables for backward compatibility
API_KEY = settings.API_KEY
SECRET = settings.SECRET
USE_TESTNET = settings.USE_TESTNET
LARK_WEBHOOK_URL = settings.LARK_WEBHOOK_URL
SYMBOL = settings.SYMBOL
TIMEFRAME = settings.TIMEFRAME
SUPERTREND_LENGTH = settings.SUPERTREND_LENGTH
SUPERTREND_FACTOR = settings.SUPERTREND_FACTOR
EMA_LENGTH = settings.EMA_LENGTH
LEVERAGE = settings.LEVERAGE
POSITION_SIZE_PERCENT = settings.POSITION_SIZE_PERCENT
MAX_TRADES_PER_HOUR = settings.MAX_TRADES_PER_HOUR
ADX_LENGTH = settings.ADX_LENGTH
ADX_THRESHOLD = settings.ADX_THRESHOLD
ATR_LENGTH = settings.ATR_LENGTH
ATR_MULTIPLIER = settings.ATR_MULTIPLIER
RSI_LENGTH = settings.RSI_LENGTH
RSI_OVERBOUGHT = settings.RSI_OVERBOUGHT
RSI_OVERSOLD = settings.RSI_OVERSOLD
RSI_LONG_THRESHOLD = settings.RSI_LONG_THRESHOLD
VOLUME_MA_LENGTH = settings.VOLUME_MA_LENGTH
EMA_SLOPE_EMA_LENGTH = settings.EMA_SLOPE_EMA_LENGTH
EMA_SLOPE_LOOKBACK = settings.EMA_SLOPE_LOOKBACK
EMA_SLOPE_THRESHOLD = settings.EMA_SLOPE_THRESHOLD
REDUCED_POSITION_SIZE_PERCENT = settings.REDUCED_POSITION_SIZE_PERCENT
RSI_DIV_LOOKBACK = settings.RSI_DIV_LOOKBACK
RSI_DIV_MIN_RSI = settings.RSI_DIV_MIN_RSI
RSI_DIV_PARTIAL_CLOSE_PCT = settings.RSI_DIV_PARTIAL_CLOSE_PCT
