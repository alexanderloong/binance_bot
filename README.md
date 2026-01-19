# Binance SuperTrend & EMA Trading Bot 🚀

A robust, automated cryptocurrency trading bot for Binance Futures, built with Python. This bot utilizes a trend-following strategy combining **SuperTrend** and **EMA 200** to capture major market moves while filtering out noise.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🌟 Key Features

*   **Automated Trading**: Executes Long and Short positions 24/7.
*   **Trend Following Strategy**: Uses SuperTrend for entry/exit signals and EMA 200 for long-term trend filtering.
*   **Robuszt Backtesting**: Includes a built-in backtester with historical data caching, PnL calculation, and Max Drawdown analysis.
*   **Risk Management**: Configurable position sizing (default 100% equity).
*   **Resilient**: Handles API connection errors and auto-reconnects.
*   **Testnet Support**: Safely test strategies on Binance Testnet before going live.

---

## 📈 Trading Strategy

The bot implements a high-frequency trend-following strategy (Backtested on **15m timeframe**):

1.  **Indicators**:
    *   **Heikin Ashi Candles**: Smoothens price action.
    *   **SuperTrend**: Length 15, Factor 3.0.
    *   **EMA 200**: Exponential Moving Average (Period 200).

2.  **Entry Logic**:
    *   **LONG**: SuperTrend flips to GREEN (Uptrend) **AND** Price > EMA 200.
    *   **SHORT**: SuperTrend flips to RED (Downtrend) **AND** Price < EMA 200.

3.  **Exit Logic**:
    *   Closes position when the SuperTrend flips direction.

---

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/binance-bot.git
    cd binance-bot
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Open `.env` and add your Binance API keys (and set `USE_TESTNET=False` for real trading):
        ```env
        BINANCE_API_KEY=your_api_key
        BINANCE_SECRET=your_secret_key
        USE_TESTNET=True
        ```

---

## 🚀 Usage

### Run the Live Bot
This will start the scheduler to check for signals every 1 minute.
```bash
python main.py
```

### Run Backtest
Analyze historical performance for the 15m timeframe.
```bash
python backtest.py
```

---

## 📊 Backtest Results (BTC/USDT 15m)

*Dataset: ~1500 candles (~16 days)*

| Metric | Value |
| :--- | :--- |
| **Net PnL** | **+3.43%** (approx 6-7%/month) |
| **Win Rate** | **30.00%** |
| **Max Drawdown** | 6.16% |
| **Total Trades** | 21 |

*Note: 15m timeframe trades more frequently with lower win rate but captures quick moves.*

---

## ⚙️ Configuration (`config.py`)

You can fine-tune the strategy parameters in `config.py`:

```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"          # Aggressive: 15m | Safe: 1d
SUPERTREND_LENGTH = 15     # Standard: 15
SUPERTREND_FACTOR = 3.0    # Smoother trend: 3.0
POSITION_SIZE_PERCENT = 1.0 # 1.0 = 100% (All-in)
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Do not risk money you cannot afford to lose. The authors are not responsible for any financial losses incurred while using this bot.
