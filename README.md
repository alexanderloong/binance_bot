# Binance SuperTrend & EMA Trading Bot 🚀

A robust, automated cryptocurrency trading bot for Binance Futures, built with Python. This bot utilizes a trend-following strategy combining **SuperTrend** and **EMA 100** (default) to capture major market moves while filtering out noise.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🌟 Key Features

*   **Automated Trading**: Executes Long and Short positions 24/7 using the **Official Binance SDK** (`binance-connector`).
*   **Trend Following Strategy**: Uses SuperTrend for signals, EMA for trend confirmation, and **ADX** for strength filtering.
*   **Robust Backtesting**: Includes a built-in backtester with historical data caching, PnL calculation, and Max Drawdown analysis.
*   **Risk Management**: Configurable position sizing and leverage.
*   **Resilient**: Handles API connection errors and gracefully manages Binance Testnet quirks.
*   **Testnet Support**: Safely test strategies on Binance Testnet before going live.

---

## 📈 Trading Strategy

The bot implements an optimized trend-following strategy designed for the **15m timeframe**.

### 1. Indicators
*   **Heikin Ashi Candles**: Smoothens price action for better trend identification.
*   **SuperTrend (15, 1.5)**: Used to detect short-term price momentum shifts.
*   **EMA 99**: Long-term trend filter. Trades are only opened in the direction of the EMA.
*   **ADX (14)**: Trend Strength filter. Bot only enters when ADX > 25 (Trend is strong).
*   **ATR (14)**: Measures market volatility.

### 2. Execution Logic (Capital Protection & Profit Optimization)

The execution logic is split into two independent steps: **Exit (Priority)** and **Entry (Filtered)**.

| Current State | Event (SuperTrend) | EMA Filter | ADX Filter | Action | Resulting State |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Empty** | Red $\rightarrow$ **Green** | Price > EMA 99 | **ADX > 25** | **Open LONG** | LONG |
| **Empty** | Red $\rightarrow$ **Green** | Price > EMA 99 | ADX < 25 | Wait (Weak Trend) | Empty |
| **Empty** | Green $\rightarrow$ **Red** | Price < EMA 99 | **ADX > 25** | **Open SHORT** | SHORT |
| **LONG** | Green $\rightarrow$ **Red** | Any | Any | **Close LONG** | Empty |
| **SHORT** | Red $\rightarrow$ **Green** | Any | Any | **Close SHORT** | Empty |

**Key Principles:**
*   **Active Profit/Loss Protection**: Positions are closed immediately when the SuperTrend flips, ensuring the bot doesn't hold against the trend.
*   **Disciplined Entry**: New positions are only opened when the short-term trend (SuperTrend) aligns with the long-term trend (EMA).

---

## 🛠️ Installation & Setup

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
    *   Create a `.env` file in the root directory:
        ```env
        API_KEY=your_binance_api_key
        SECRET=your_binance_secret_key
        USE_TESTNET=True
        ```

---

## 🚀 Deployment (Stable & Auto-Restart)

To ensure the bot runs 24/7 with automatic recovery, Docker is highly recommended.

### Running with Docker
1.  Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed.
2.  Start the bot:
    ```bash
    docker-compose up -d --build
    ```
3.  Check logs:
    ```bash
    docker-compose logs -f
    ```

---

## 🚀 Usage

### Manual Start
Starts the scheduler to monitor market signals every minute.
```bash
python main.py
```

### Run Backtest
Analyze historical performance. The results include PnL, Win Rate, and Max Drawdown.
```bash
python backtest.py
```

---

## ⚙️ Configuration (`config.py`)

Fine-tune the strategy in `config.py`:
```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"
SUPERTREND_LENGTH = 15
SUPERTREND_FACTOR = 1.5
EMA_LENGTH = 100
LEVERAGE = 20
POSITION_SIZE_PERCENT = 1  # 1.0 = 100% of balance
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Cryptocurrency trading involves significant risk. The authors are not responsible for any financial losses. Always test thoroughly on **Testnet**.
