# Binance Futures Trading Bot (v2.1.0)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Binance](https://img.shields.io/badge/exchange-Binance%20Futures-yellow)
![Stability](https://img.shields.io/badge/Stability-Production--Ready-green)
![Version](https://img.shields.io/badge/version-2.1.0-brightgreen)

A robust, trend-following trading bot for Binance Futures. Uses a combination of **SuperTrend**, **EMA**, **Heikin Ashi**, and **Volume** analysis to execute trades — with a fully audited financial calculation layer and a high-fidelity backtest engine.

> **v2.1.0** introduces a centralized `finance.py` module that fixes all fee, PnL, ROI, and breakeven calculations across both the live bot and backtest engine, along with a race-condition fix in the WebSocket layer and enriched backtest metrics (Sharpe Ratio, Expectancy, coloured monthly table).

---

## 🚀 Features

- **Trend Following Strategy** — SuperTrend + EMA + Volume confirmation on Heikin Ashi candles
- **HTF Filter** — 4H SuperTrend acts as a higher-timeframe trend gate
- **Dynamic ATR Stop Loss** — `0.74 × ATR` risk per trade
- **Breakeven Management** — SL automatically moves to exact breakeven once profit target is reached
- **Audited Financial Layer** — All PnL, fee, ROI and position-sizing math in `module/bot/finance.py`
- **WebSocket + REST Fallback** — Real-time kline buffer with auto-reconnect on silence > 180s
- **Time Sync** — Auto-corrects local clock drift vs Binance server time (no more `-1021` errors)
- **Rate Limiting** — Hard cap of `MAX_TRADES_PER_HOUR` to prevent runaway trading
- **Lark Notifications** — Entry, exit, SL, breakeven, daily report and error alerts
- **Persistent State** — `bot_state.json` survives restarts without losing SL/entry/breakeven state
- **Full Backtest Engine** — Historical simulation with Sharpe, Calmar, Expectancy, CAGR, and coloured monthly breakdown table

---

## 🛠 Installation

### Prerequisites
- Python 3.10 or higher
- A Binance Futures account (Testnet recommended for initial testing)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd binance_bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration** — create a `.env` file in the root directory:
   ```env
   API_KEY=your_binance_api_key
   SECRET=your_binance_secret_key
   USE_TESTNET=True          # Set to False for live trading
   LARK_WEBHOOK_URL=https://open.larksuite.com/open-apis/bot/v2/hook/...
   ```

---

## 🏃 Usage

### Running the Bot
```bash
python main.py
```
The bot initialises, syncs time with Binance, pre-populates the kline buffer, and starts polling for candle close events.

### Backtesting
```bash
python -m module.backtest.orchestrator
```
Fetches historical data (cached to `resource/`), runs the full strategy simulation, and prints a summary including PnL, Win Rate, Sharpe Ratio, Max Drawdown, and a coloured monthly return table.

### Optimization
```bash
python module/optimize/optimize_ema.py
python module/optimize/optimize_leverage.py
# ... see module/optimize/ for all available scripts
```

---

## ⚙️ Configuration

All settings live in `config.py` via the `TradingConfig` dataclass.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SYMBOL` | `BTC/USDT` | Trading pair |
| `TIMEFRAME` | `15m` | Entry timeframe |
| `HTF_TIMEFRAME` | `4h` | Higher timeframe filter |
| `LEVERAGE` | `1` | Futures leverage |
| `POSITION_SIZE_PERCENT` | `1.0` | Fraction of balance per trade |
| `SUPERTREND_LENGTH` | `18` | SuperTrend ATR period |
| `SUPERTREND_FACTOR` | `1.45` | SuperTrend multiplier |
| `EMA_LENGTH` | `97` | EMA trend filter (optimised for BTC 15m) |
| `VOLUME_MA_LENGTH` | `166` | Volume MA filter period |
| `ATR_LENGTH` | `14` | ATR period for stop loss |
| `ATR_MULTIPLIER` | `0.74` | SL distance = ATR × this value |
| `BREAKEVEN_MULTIPLIER` | `2.0` | Move SL to BE after `risk × 2.0` profit |
| `TAKER_FEE_RATE` | `0.0005` | Binance Futures taker fee (0.05%) |
| `MAX_TRADES_PER_HOUR` | `5` | Rate limit guard |

---

## 📊 Strategy Overview

### Entry Conditions
| Direction | Conditions |
|-----------|-----------|
| **Long** | SuperTrend flips GREEN + Price > EMA + Volume > Volume MA + HTF trend = UP |
| **Short** | SuperTrend flips RED + Price < EMA + Volume > Volume MA + HTF trend = DOWN |

### Exit Conditions
| Trigger | Action |
|---------|--------|
| SuperTrend reversal | Market close in opposite direction |
| ATR Stop Loss hit | Market close at SL price |
| Breakeven activation | SL moves to exact breakeven price (fee-inclusive) |

---

## 🗂 Project Structure

```
binance_bot/
├── main.py                        # Entry point
├── config.py                      # Centralised typed configuration
├── requirements.txt
├── module/
│   ├── bot/
│   │   ├── exchange_client.py     # Binance API + WebSocket wrapper
│   │   ├── strategy.py            # Trading logic & order management
│   │   ├── core_strategy.py       # Signal evaluation (shared with backtest)
│   │   ├── data_processor.py      # Technical indicators (HA, SuperTrend, EMA, ATR…)
│   │   ├── finance.py             # ✨ Fee, PnL, ROI, breakeven & sizing math
│   │   ├── notifier.py            # Lark webhook notifications
│   │   └── utils.py               # Logger, timeframe parser, IP helper
│   ├── backtest/
│   │   ├── orchestrator.py        # Backtest entry point
│   │   ├── simulator.py           # Candle-by-candle simulation loop
│   │   ├── data_loader.py         # Historical data fetch + cache
│   │   ├── metrics.py             # Sharpe, Calmar, CAGR, Expectancy…
│   │   ├── breakdown.py           # Coloured monthly/yearly return table
│   │   └── reporter.py            # Console + file output
│   └── optimize/                  # Parameter grid-search scripts
└── resource/
    ├── .env.example
    └── backtest_logs/             # Auto-generated backtest reports
```

---

## 📜 License
This project is licensed under the MIT License.