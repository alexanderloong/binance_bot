# Changelog

All notable changes to this project will be documented in this file.
 
## [1.2.0] - 2026-01-25
### Added
- **Trend Strength Filter (ADX):** Integrated Average Directional Index (ADX) to filter out weak trends. Bot now only enters trades when ADX > 25, significantly reducing noise in sideways markets.
- **Volatility Tracking (ATR):** Added Average True Range (ATR) calculation for better market volatility awareness.
- **Startup Analysis:** Bot now performs a full market analysis immediately upon startup, providing instant feedback on indicators (ADX, ATR, EMA, Trend).
- **Stop Loss Removal:** Removed automated Stop Loss logic due to Binance API migration constraints and simplified risk management.

### Changed
- **Backtest Synchronicity:** Refactored `backtest.py` to match the exact logic of `main.py`, including ADX filters and commission-adjusted PnL.
- **Indicator Optimization:** Updated `DataProcessor` with robust Wilders-style smoothing for ADX and ATR.

### Fixed
- **Staleness Tracking:** Improved the "Stale Candle" logic to allow indicator logging even if the candle is too old for a new trade entry.
- **Variable scoping:** Fixed a potential crash in `strategy.py` related to uninitialized delay variables in error paths.
- **Environment fixes:** Updated `requirements.txt` with missing dependencies (`schedule`, `numpy`, `pytz`).


## [1.1.2] - 2026-01-22
### CRITICAL FIXES (SAFETY UPDATE)
- **Prevented "Spam" Trading:** Fixed a major issue where the bot would repeatedly open/close positions on the same candle. Added `last_candle_time` tracking to ensure each 15m candle is processed exactly once.
- **Real-time State Verification:** Discarded unreliable internal state (`in_position`). Bot now fetches active positions directly from Binance API before making decisions, preventing double-entry and ensuring correct Trend Flip execution.
- **Smart Polling:** Replaced `schedule` with a high-frequency polling loop (10s) combined with the new deduplication logic to ensure fastest reaction time without spam.

### Added
- **Circuit Breaker:** Implemented `MAX_TRADES_PER_HOUR` (default: 5) in `config.py` to hard-stop the bot if abnormal trading activity is detected.

### Fixed
- **Docker Config:** Added explicit validation and error logging for missing `API_KEY` / `SECRET` in `config.py`, helping debug Docker environment issues.

### Fixed
- **Critical Order Size Fix:** Resolved "amount must be greater than minimum amount precision" error by correctly multiplying the trade quantity by the configured leverage.
- **Backtest Accuracy:** Fixed Max Drawdown calculation and added detailed trade logging with 0.05% transaction fees included.

### Changed
- **Strategy Tuning:** Updated default configuration to Leverage x20, Position Size 0.9 (90%), EMA 99, and SuperTrend 15/1.5 based on backtest optimization.

### Added
- Integrated official **Binance Connector** (`binance-connector` & `binance-futures-connector`).
- Implemented `UMFutures` (USD-M Futures) class in `ExchangeClient` to replace `ccxt` logic.
- Automated Symbol normalization (removing slashes and upper-casing) for official API compatibility.
- Implemented non-blocking leverage setting mechanism to handle Testnet `-1000` errors gracefully.

### Changed
- **Refactored ExchangeClient:** Optimized `fetch_ohlcv` and `create_order` methods using the official SDK.
- **Backtest Optimization:** Updated `backtest.py` to utilize the new client, improving data accuracy.
- **Dependencies Cleanup:** Streamlined `requirements.txt` and removed deprecated libraries like `ccxt`.

### Fixed
- Resolved `Invalid symbol` errors caused by incorrect symbol formatting.
- Fixed `ModuleNotFoundError: No module named 'binance'` by properly configuring the `.venv` environment.

---

## [1.0.0] - 2026-01-20
### Added
- Initial project setup for the Binance Trading Bot.
- Strategy Implementation: Heikin Ashi candles + SuperTrend + EMA filter.
- Environment configuration system via `.env` and `config.py`.
- Basic Backtesting engine using local CSV data caching.
- Project Dockerization (Dockerfile & docker-compose.yml).
