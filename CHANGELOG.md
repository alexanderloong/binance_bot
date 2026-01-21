# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-01-21
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
