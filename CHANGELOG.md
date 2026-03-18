## [1.16.1] - 2026-03-18
### Added
- **PnL Milestone**: Achieved **+756% PnL** in a 2-year backtest for BTC/USDT 15m using the EMA + Volume Filter combo.
### Optimized
- **EMA Length**: Fine-tuned EMA from 102 down to **97** after thorough optimization.
### Changed
- **Default Strategy**: Revised default trading filters to **EMA + Volume** only, as it yielded the highest Profit Factor (1.25) and Net Profit compared to ADX-based filters.
- **Documentation**: Incremented version to 1.16.1 across all files.

## [1.16.0] - 2026-03-07
### Changed
- **Optimization**: Updated `ATR_MULTIPLIER` and other strategy parameters based on performance analysis.
- **Documentation**: Incremented version to 1.16.0.

## [1.15.2] - 2026-03-04
### Changed
- **Cleanup**: Removed redundant "All Positions Closed" Lark notification.
- **Documentation Update**: Updated version to 1.15.2.

## [1.15.1] - 2026-03-04
### Changed
- **Documentation Update**: Updated documentation and tagged release as v1.15.1.
- **Lark Notifications**: Enhanced notifications with PnL, ROI, and USDT amounts.
- **Reporting**: Implemented daily performance report at 9:00 AM.

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
-   **Refactored Strategy**: `Strategy` class broken down into modular methods for better readability.
-   **Optimized Indicators**: `DataProcessor` methods updated for clarity and strict typing.
-   **Logging**: Improved logging format and timezone handling in `utils.py`.
### Fixed
-   **Rate Limiting**: Enhanced `check_rate_limit` logic and API weight handling in backtest data fetching.

## [1.13.0] - 2026-02-04
-   Initial Trend Following Strategy Implementation.
-   Added RSI Divergence Rule.
-   Added EMA Slope Position Sizing Rule.

## [1.9.2] - 2026-01-31
### Added
- **Performance Visualization:** Integrated `matplotlib` and `seaborn` for generating equity curve and drawdown charts.
- **Dependencies:** Updated `requirements.txt` with plotting libraries.

### Changed
- **Strategy Tuning (Aggressive):** Shifted to an aggressive growth configuration.
- **Code Optimization:** Refactored `backtest.py` and `optimize/plot_results.py`.

## [1.9.1] - 2026-01-31
### Changed
- **Config Update:** Refined trading parameters (Leverage 7x, Position Size 75%).

## [1.9.0] - 2026-01-31
### Added
- **Leverage & Position Size Optimizer:** New optimization script.
- **Target-Based Optimization:** Set risk tolerance (Max DD) and consistency requirements (Min PF).

## [1.8.1] - 2026-01-31
### Optimized
- **EMA Length:** Fine-tuned EMA parameter from 99 -> 106.

## [1.8.0] - 2026-01-31
### Added
- **Volume MA Filter:** Implemented Volume Moving Average filter (Length 55).

## [1.7.1] - 2026-01-31
### Optimized
- **RSI Thresholds:** Fine-tuned RSI (OB 66, OS 35).

## [1.7.0] - 2026-01-31
### Added
- **RSI Overbought/Oversold Filter:** New entry filter to avoid extremes.

## [1.6.1] - 2026-01-31
### Refactored
- **Code Optimization:** Cleaned up unused imports and centralized shared utility functions.

## [1.6.0] - 2026-01-30
### Added
- **Global Strategy Optimization:** Comprehensive grid search for all core parameters.

## [1.5.0] - 2026-01-27
### Added
- **Partial Take Profit (ATR-based):** Sophisticated partial exit strategy using ATR targets.

## [1.4.0] - 2026-01-26
### Added
- **Synchronized Timestamp Logic:** Backtest mirrors live bot behavior with next-candle execution.
- **Live Data Backtesting:** Enhanced `backtest.py` to fetch from Live Binance API even in Testnet.

## [1.3.0] - 2026-01-26
### Added
- **Dynamic ATR Stop Loss:** replacement of fixed % Stop Loss with 1.5x ATR.

## [1.2.0] - 2026-01-25
### Added
- **Trend Strength Filter (ADX):** entries only when ADX > 25.
- **Volatility Tracking (ATR):** integrated ATR awareness.

## [1.1.2] - 2026-01-22
### Fixed
- **Prevented "Spam" Trading:** Added `last_candle_time` tracking.
- **Real-time State Verification:** Position fetching replaced internal state tracking.

## [1.0.0] - 2026-01-20
### Added
- Initial project setup for the Binance Trading Bot.
- Strategy Implementation: Heikin Ashi candles + SuperTrend + EMA filter.
