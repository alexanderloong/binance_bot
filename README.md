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

The bot implements a verified profitable strategy (Backtested +51% PnL over 4 years timeframe on BTC/USDT 1d):

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
This will start the scheduler to check for signals daily (aligned with 1d timeframe).
```bash
python main.py
```

### Run Backtest
Analyze historical performance, calculate Win Rate, PnL, and Max Drawdown.
```bash
python backtest.py
```

---

## 📊 Backtest Results (BTC/USDT 1d)

*Dataset: ~1500 days (approx 4 years)*

| Metric | Value |
| :--- | :--- |
| **Net PnL** | **+51.04%** |
| **Win Rate** | **75.00%** |
| **Max Drawdown** | 33.06% |
| **Total Trades** | 17 |

*Note: Past performance is not indicative of future results.*

---

## ⚙️ Configuration (`config.py`)

You can fine-tune the strategy parameters in `config.py`:

```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "1d"           # Recommended: 1d
SUPERTREND_LENGTH = 15     # Standard: 15
SUPERTREND_FACTOR = 3.0    # Smoother trend: 3.0
POSITION_SIZE_PERCENT = 1.0 # 1.0 = 100% (All-in)
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Do not risk money you cannot afford to lose. The authors are not responsible for any financial losses incurred while using this bot.
