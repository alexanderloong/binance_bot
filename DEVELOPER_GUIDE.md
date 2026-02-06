# Developer Guide

## Codebase Structure
The project follows a modular architecture designed for readability and maintainability.

```
binance_bot/
├── bot/
│   ├── exchange_client.py  # Wrapper for Binance API interactions
│   ├── strategy.py         # Core trading logic and decision making
│   ├── data_processor.py   # Technical indicators (pandas/numpy optimized)
│   └── utils.py            # Helpers (Logging, Time conversion)
├── optimize/               # Scripts for parameter optimization
├── backtest.py             # Backtesting engine
├── config.py               # Centralized configuration (Typed)
├── main.py                 # Entry point
└── requirements.txt        # Dependencies
```

## Coding Conventions

-   **Type Hinting**: All functions and methods must use Python type hints (PEP 484).
-   **Configuration**: Do not hardcode magic numbers. Use `config.settings`.
-   **Logging**: Use `self.logger` within classes or `setup_logger()` from `utils.py`. Avoid `print()`.
-   **Dataframes**: Use Vectorized operations (pandas/numpy) wherever possible. Avoid iterating over rows in DataFrames.

## Extending the Strategy

### Adding a New Indicator
1.  Add the calculation logic to `bot/data_processor.py` as a `@staticmethod`.
2.  Update `config.py` with necessary parameters.
3.  Call the new method in `bot/strategy.py` -> `_prepare_indicators`.

### Modifying Entry Logic
Edit `bot/strategy.py` method `_analyze_market_and_trade`.
-   Signals are determined in the `signal` variable logic block.
-   Ensure you check `current_pos_amt == 0` before creating an entry signal.

## Backtesting
The backtest engine (`backtest.py`) mimics the live strategy loop.
**Important**: When you change logic in `bot/strategy.py`, you **must** replicate relevant logic in `backtest.py`'s `simulate` Loop to ensure backtest results reflect reality.

## Dependency Management
-   Use `pip install -r requirements.txt`.
-   When adding libraries, update `requirements.txt` with pinned versions.
