# Changelog

All notable changes to this project will be documented in this file.

## [1.15.0] - 2026-02-06
### Added
- **Production Anchor**: This version is designated as the stable production anchor for 2026.
### Fixed
- **Statistics Accuracy**: Fixed `backtest.py` logic to correctly aggregate `PARTIAL_DIV` PnL into trade cycles, ensuring Win Rate and Profit Factor match actual data performance.
### Changed
- **Config Finalization**: Re-established production-grade risk parameters (Leverage 10x, Position Size 20%).

## [1.14.1] - 2026-02-06

### Added
-   **Backtest Logging**: Backtest results are now saved to `resource/backtest_logs/`.

### Changed
-   **Risk Config**: Reduced default Leverage to 9x and Position Size to 15% for safer default risk profile.

## [1.14.0] - 2026-02-06

### Added
-   **Strict Type Hinting**: Applied to `bot/exchange_client.py`, `bot/strategy.py`, `bot/data_processor.py`, and `bot/utils.py`.
-   **Config Management**: Introduced `TradingConfig` dataclass in `config.py` for structured settings access.
-   **Developer Guide**: New `DEVELOPER_GUIDE.md` for contributors.
-   **Requirements**: Added `requirements.txt` with pinned dependencies.

### Changed
-   **Refactored Strategy**: `Strategy` class broken down into modular methods (`_check_new_candle`, `_prepare_indicators`, `_analyze_market_and_trade`) for better readability.
-   **Optimized Indicators**: `DataProcessor` methods updated for clarity and strict typing.
-   **Logging**: Improved logging format and timezone handling in `utils.py`.

### Fixed
-   **Rate Limiting**: Enhanced `check_rate_limit` logic and API weight handling in backtest data fetching.

## [1.13.0] - 2026-02-04
-   Initial Trend Following Strategy Implementation.
-   Added RSI Divergence Rule.
-   Added EMA Slope Position Sizing Rule.
