# Binance SuperTrend & EMA Trading Bot 🚀

A robust, automated cryptocurrency trading bot for Binance Futures, built with Python. This bot utilizes a trend-following strategy combining **SuperTrend** and **EMA 100** (default) to capture major market moves while filtering out noise.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🌟 Key Features

*   **Automated Trading**: Executes Long and Short positions 24/7.
*   **Trend Following Strategy**: Uses SuperTrend for entry/exit signals and EMA filter for trend confirmation.
*   **Robust Backtesting**: Includes a built-in backtester with historical data caching, PnL calculation, and Max Drawdown analysis.
*   **Risk Management**: Configurable position sizing (default 100% equity).
*   **Resilient**: Handles API connection errors and auto-reconnects.
*   **Testnet Support**: Safely test strategies on Binance Testnet before going live.

---

## 📈 Trading Strategy

The bot implements a trend-following strategy (Optimized for **15m timeframe**):

1.  **Indicators**:
    *   **Heikin Ashi Candles**: Smoothens price action for better trend identification.
    *   **SuperTrend**: Length 15, Factor 1.5.
    *   **EMA 100**: Exponential Moving Average (Period 100).

2.  **Entry Logic**:
    *   **LONG**: SuperTrend direction flips to 1 (Green) **AND** Price > EMA 100.
    *   **SHORT**: SuperTrend direction flips to -1 (Red) **AND** Price < EMA 100.

3.  **Exit Logic**:
    *   Closes existing position when a new opposite signal is detected.

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
        API_KEY=your_api_key
        SECRET=your_secret_key
        USE_TESTNET=True
        ```
        *(Note: The bot automatically detects `API_KEY` and `SECRET` from `.env` as per the latest `config.py`)*

---

## 🚀 Deployment (Stable & Auto-Restart)

To ensure the bot runs stably 24/7 and automatically restarts if it encounters errors or the system reboots, you should use Docker:

### Running with Docker (Recommended)
This is the most professional method, providing an isolated and extremely stable environment.

1.  Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for Windows.
2.  Open a terminal in the project directory and run:
    ```bash
    docker-compose up -d --build
    ```
3.  To view logs:
    ```bash
    docker-compose logs -f
    ```
4.  To stop the bot:
    ```bash
    docker-compose down
    ```

---

## 🚀 Usage

### Run Manually (Testing)
This will start the scheduler to check for signals every 1 minute.
```bash
python main.py
```

### Run Backtest
Analyze historical performance for the configured timeframe.
```bash
python backtest.py
```

---

## 📊 Monitoring Performance

You can monitor the bot's performance through the following channels:

1.  **Bot Logs**: Check the `bot.log` file to track transaction logs, balance checks, and order status in real-time.
2.  **Binance Testnet Dashboard**: Access [testnet.binancefuture.com](https://testnet.binancefuture.com/) to visually see open positions and asset fluctuations.
3.  **Backtest Report**: Run `python backtest.py` to get a summary report on PnL, Win Rate, and Max Drawdown based on historical data (last 1000 candles).

---

## ⚙️ Configuration (`config.py`)

You can fine-tune the strategy parameters in `config.py`:

```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"          # Period for candles (e.g., 15m, 1h, 1d)
SUPERTREND_LENGTH = 15     # Standard: 15
SUPERTREND_FACTOR = 1.5    # Aggressiveness of SuperTrend
EMA_LENGTH = 100           # Trend filter period
LEVERAGE = 9               # Leverage multiplier (x9)
POSITION_SIZE_PERCENT = 1  # 1.0 = 100% of balance used per trade
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Do not risk money you cannot afford to lose. The authors are not responsible for any financial losses incurred while using this bot.
