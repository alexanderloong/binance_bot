import os
from dotenv import load_dotenv
from dataclasses import dataclass

# ==========================================
# BINANCE TRADING BOT CONFIGURATION
# Strategy: SuperTrend + EMA Filter + Volume
# ==========================================

env_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), "resource", ".env")
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
    HTF_TIMEFRAME: str = "4h"
    BREAKEVEN_MULTIPLIER: float = 2.0

    # Strategy Parameters
    SUPERTREND_LENGTH: int = 19
    SUPERTREND_FACTOR: float = 2.7
    EMA_LENGTH: int = 97

    # Risk Management
    LEVERAGE: int = 1
    POSITION_SIZE_PERCENT: float = 1

    # ATR Stop Loss
    ATR_LENGTH: int = 14
    ATR_MULTIPLIER: float = 0.74

    # Fee Rate (Taker - Binance Futures, no BNB discount)
    TAKER_FEE_RATE: float = 0.0005

    # Safety
    MAX_TRADES_PER_HOUR: int = 5
    CONSOLE_TRADE_LIMIT: int = 15

    # Volume
    VOLUME_MA_LENGTH: int = 166


# Instantiate global settings
settings = TradingConfig()

# Expose global variables for backward compatibility
API_KEY = settings.API_KEY
SECRET = settings.SECRET
USE_TESTNET = settings.USE_TESTNET
LARK_WEBHOOK_URL = settings.LARK_WEBHOOK_URL
SYMBOL = settings.SYMBOL
TIMEFRAME = settings.TIMEFRAME
HTF_TIMEFRAME = settings.HTF_TIMEFRAME
BREAKEVEN_MULTIPLIER = settings.BREAKEVEN_MULTIPLIER
SUPERTREND_LENGTH = settings.SUPERTREND_LENGTH
SUPERTREND_FACTOR = settings.SUPERTREND_FACTOR
EMA_LENGTH = settings.EMA_LENGTH
LEVERAGE = settings.LEVERAGE
POSITION_SIZE_PERCENT = settings.POSITION_SIZE_PERCENT
ATR_LENGTH = settings.ATR_LENGTH
ATR_MULTIPLIER = settings.ATR_MULTIPLIER
MAX_TRADES_PER_HOUR = settings.MAX_TRADES_PER_HOUR
CONSOLE_TRADE_LIMIT = settings.CONSOLE_TRADE_LIMIT
VOLUME_MA_LENGTH = settings.VOLUME_MA_LENGTH
TAKER_FEE_RATE = settings.TAKER_FEE_RATE
