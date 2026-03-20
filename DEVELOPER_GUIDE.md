# Developer Guide — v2.1.0

## Project Structure

```
binance_bot/
├── main.py                        # Entry point
├── config.py                      # TradingConfig dataclass (frozen, typed)
├── requirements.txt
├── module/
│   ├── bot/
│   │   ├── exchange_client.py     # Binance REST + WebSocket client
│   │   ├── strategy.py            # Order management & position lifecycle
│   │   ├── core_strategy.py       # evaluate_signal() — shared with backtest
│   │   ├── data_processor.py      # Indicators: HA, SuperTrend, EMA, ATR, ADX, RSI, Volume
│   │   ├── finance.py             # ✨ All financial math (fee, PnL, ROI, breakeven, sizing)
│   │   ├── notifier.py            # Lark webhook
│   │   └── utils.py               # Logger, parse_timeframe_to_seconds, get_public_ip
│   ├── backtest/
│   │   ├── orchestrator.py        # CLI entry point for backtests
│   │   ├── simulator.py           # Candle-by-candle simulation (uses finance.py)
│   │   ├── data_loader.py         # Multi-threaded historical data fetch + CSV cache
│   │   ├── metrics.py             # Sharpe, Calmar, CAGR, Profit Factor, Expectancy
│   │   ├── breakdown.py           # ANSI-coloured monthly/yearly return table
│   │   └── reporter.py            # Console summary + backtest_logs/ file output
│   └── optimize/                  # Grid-search scripts for each parameter
└── resource/
    ├── .env.example
    └── backtest_logs/
```

---

## Coding Conventions

- **Type Hinting** — all functions must use PEP 484 type hints.
- **No Magic Numbers** — all constants go in `config.py` via `TradingConfig`. Access via `settings.PARAM`.
- **Financial Math** — **never** inline fee/PnL/ROI calculations. Always import from `module/bot/finance.py`.
- **Logging** — use `self.logger` in classes. Never use `print()` in production paths.
- **DataFrame Operations** — prefer vectorised pandas/numpy. Avoid row-iteration except where recursion is unavoidable (e.g. SuperTrend, Heikin Ashi).
- **Thread Safety** — any shared state accessed from both the main thread and the WebSocket thread must be guarded with `self._ws_lock`.

---

## Financial Calculations — `module/bot/finance.py`

This is the **single source of truth** for all money math. Do not duplicate formulas elsewhere.

| Function | Purpose |
|----------|---------|
| `calc_fee(price, qty, rate)` | One-leg taker fee |
| `calc_round_trip_fee(entry, exit, qty, rate)` | Full open+close fee |
| `calc_gross_pnl(entry, exit, qty, is_long)` | PnL before fees |
| `calc_net_pnl(entry, exit, qty, rate, is_long)` | PnL after fees |
| `calc_roi(net_pnl, entry, qty, leverage)` | Net ROI % on margin |
| `calc_breakeven_price(entry, rate, is_long)` | Exact breakeven exit price |
| `calc_trade_quantity(balance, size_pct, leverage, price, rate, precision)` | Fee-safe position size |
| `TradeResult` | Dataclass — snapshot of a closed trade with computed properties |

### Breakeven Formula
The exact (non-approximated) breakeven for a LONG:
```
BE = entry × (1 + fee_rate) / (1 − fee_rate)
```
The first-order approximation `entry × (1 + fee_rate × 2)` is **not used** — it understates the true breakeven by ~0.025 USD per BTC at current fee rates.

---

## Extending the Strategy

### Adding a New Indicator
1. Add a `@staticmethod` to `module/bot/data_processor.py`.
2. Add any new parameters to `config.py` → `TradingConfig`.
3. Call it inside `DataProcessor.prepare_all_indicators()`.
4. Reference the new column in `core_strategy.py` → `evaluate_signal()`.

### Modifying Entry / Exit Logic
- All signal logic lives in `module/bot/core_strategy.py` → `evaluate_signal()`.
- This function is **shared** between the live bot and the backtest simulator.
- **Never** put signal logic only in `strategy.py` — the backtest will diverge from live results.

### Adding a New Metric to Backtest
1. Add the calculation to `module/backtest/metrics.py` → `MetricsCalculator.calculate()`.
2. Surface it in `module/backtest/reporter.py` → `BacktestReporter.log_results()`.

---

## Backtesting

Run:
```bash
python -m module.backtest.orchestrator
```

**Fee accounting model (split-leg):**
- `OPEN_*` event: entry fee is deducted from balance immediately (`pnl = −entry_fee`).
- `CLOSE_*` / `STOP_LOSS_*` / `LIQUIDATION` event: `pnl = raw_move − exit_fee`.
- Total round-trip = `entry_fee + exit_fee` — identical to `finance.calc_round_trip_fee()`.

**Key rule:** when you change logic in `core_strategy.py`, the backtest automatically reflects it. When you change order-management logic in `strategy.py` (e.g. SL placement, breakeven), replicate the same logic in `simulator.py`.

---

## WebSocket & Thread Safety

`ExchangeClient` runs two threads:
1. **Main thread** — calls `fetch_ohlcv()` which reads `self.klines_buffer`.
2. **WS thread** — `_on_ws_message()` writes to `self.klines_buffer`.
3. **WS monitor thread** — `_ws_health_monitor()` triggers reconnect if silent > 180s.

Both read and write paths on `klines_buffer` are protected by `self._ws_lock`. Never access `klines_buffer` outside this lock.

---

## Dependency Management

```bash
pip install -r requirements.txt
```

When adding a new library, pin its version in `requirements.txt`.