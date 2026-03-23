## [2.2.0] - 2026-03-23
### Fixed
- **Candle-Close Only Execution Model**: All position management decisions (liquidation, breakeven trigger, stop loss) in both the backtest simulator and the live bot now evaluate exclusively against the **close price of the last completed candle**. No intra-candle low/high triggers exist anywhere in the system, ensuring perfect parity between backtest and live behaviour.
- **`simulator.py` — Liquidation check**: Replaced `exec_low`/`exec_high` with `arr_close[i-1]`.
- **`simulator.py` — Breakeven trigger**: Replaced `arr_close[i-1]` check (already close-based but documented inconsistently) — logic confirmed correct and docstring updated.
- **`simulator.py` — Stop loss check**: Replaced `exec_low`/`exec_high` with `arr_close[i-1]`.
- **`simulator.py` — Column name lookup**: `st_dir_col`, `ema_col`, and `vol_ma_col` are now built from `self.st_length`, `self.st_factor`, `self.ema_length`, `self.volume_ma_length` instead of the global `settings` object. This fixes silent wrong-column reads when running optimization grid-searches with non-default parameters.
- **`strategy.py` — SL and breakeven check**: `_manage_open_position()` now reads `df["close"].iloc[-2]` (last closed candle) instead of `df["close"].iloc[-1]` (the forming candle), aligning live bot with the candle-close only model.
- **`simulator.py` — Removed `from resource.config import settings` inside `run()`**: No longer needed after column names are derived from `self.*`.

---

## [2.1.0] - 2026-03-21
### Fixed
- **Financial Calculations**: Extracted all PnL, fee, ROI, and position-sizing math into a dedicated `module/bot/finance.py` module — single source of truth across live bot and backtest engine.
- **Breakeven Price**: Replaced first-order approximation (`entry × (1 ± fee×2)`) with the exact algebraic formula (`entry × (1 ± rate) / (1 ∓ rate)`), eliminating systematic breakeven mispricing.
- **Position Sizing**: `open_position()` now reserves margin for the entry taker fee (`notional / (1 + fee_rate)`) to prevent insufficient-margin rejections at high position sizes.
- **ROI Calculation**: Live bot notifications now report **net ROI on margin deployed** (`net_pnl / margin × 100`) instead of gross price-move ROI, making PnL and ROI figures consistent.
- **`get_yesterday_stats` Timezone**: Fixed naive `datetime.now()` → explicit `VN_TZ (UTC+7)` so daily report boundaries are always correct regardless of server timezone.
- **WebSocket Race Condition**: `_on_ws_message` buffer writes and `fetch_ohlcv` buffer reads are now both protected by `_ws_lock`, eliminating potential partial-read of a DataFrame mid-update.
- **`time.time` Monkey-Patch Removed**: Global override of `time.time` replaced with an explicit `synced_time()` helper — third-party libraries (websocket, requests) no longer receive a patched clock.
- **`resample_to_htf` Double Computation**: Removed redundant first resample pass that was immediately overwritten.

### Fixed (Backtest)
- **Liquidation PnL**: Now computed as `raw_move_to_liq_price − exit_fee` instead of `−margin`, accurately reflecting the fee charged at forced close.
- **Breakeven in Simulator**: Aligned with live bot — uses `calc_breakeven_price()` from `finance.py`.
- **CAGR Guard**: Prevented `math domain error` when `final_balance ≤ 0` (total wipeout scenario).
- **Monthly Breakdown Timezone Warning**: Fixed `UserWarning` on timezone-aware → Period conversion by using `.dt.tz_convert(None)` before `.to_period()`.

### Added (Backtest)
- **Sharpe Ratio**: Annualised Sharpe added to `MetricsCalculator` and displayed in report summary.
- **Avg Win / Avg Loss / Expectancy**: Three new metrics surfaced in backtest report.
- **Coloured Monthly Table**: `breakdown.py` now renders ANSI-coloured output — green for positive months, red for negative, grey for missing data.

### Changed
- `close_all_positions()` in `Strategy` now correctly sends the full `TradeResult` notification (PnL + ROI) before closing — previously `pnl_str` was computed but never sent.
- `open_position()` notification now includes the exact **breakeven price** so traders know their true cost basis immediately on entry.

---

## [2.0.0] - 2026-03-19
### Changed
- **Project Structure**: Fully restructured codebase according to SOLID principles.
- **Architectural Shift**: Decoupled monolithic files into a modular system (`module/bot`, `module/backtest`, `module/optimize`).
- **Data Pipeline**: Split API fetching, simulation, and metrics calculations into separate decoupled services (`data_loader.py`, `simulator.py`, `metrics.py`, `reporter.py`).
- **Strategy Tuning**: Maintained aggressive yet robust configuration focusing on EMA + Volume Filter combo.
- **Documentation**: Incremented version to 2.0.0 framework-wide.

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
