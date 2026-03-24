# Binance USDT-M Futures Trading Bot

A professional-grade crypto trading bot using Heikin Ashi candles and the Supertrend indicator for Binance USDT-M Futures. Built with clean architecture, SOLID principles, and full async support for live execution.

## Architecture Highlights
- **SOLID Principles:** Modules are strictly isolated (data vs strategy vs execution).
- **Extensible:** Data fetchers and Strategy modules inherit from base abstract classes. Adding new indicators is trivial.
- **Async Execution:** Utilizes Python's `asyncio` and `python-binance` WebSockets for fast reaction times in live markets.

## Installation

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
Create a `.env` file in the root directory and configure as needed:
```env
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
BINANCE_TESTNET=True
```

## Usage

### Backtesting
Run the bot against historical data to evaluate strategy performance (PnL, Max Drawdown, Winrate):
```bash
python run_backtest.py
```

### Live Trading
Start the WebSocket stream and execute live orders. Ensure your API keys are correct.
```bash
python main.py --live
```
