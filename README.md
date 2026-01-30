# Binance SuperTrend & EMA Trading Bot 🚀 (v1.6.0)

A robust, automated cryptocurrency trading bot for Binance Futures, built with Python. This bot utilizes a trend-following strategy combining **SuperTrend** and **EMA 99** (default) to capture major market moves while filtering out noise.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🌟 Key Features

*   **Automated Trading**: Executes Long and Short positions 24/7 using the **Official Binance SDK** (`binance-connector`).
*   **Trend Following Strategy**: Uses SuperTrend for signals, EMA for trend confirmation, and **ADX** for strength filtering.
*   **High-Fidelity Backtesting**: Pre-flight your strategy with a simulator that uses **Live Binance Market Data** and accurately models candle-close execution timing.
*   **Profit Optimization**: **Partial Take Profit (Partial TP)** allows locking in gains at 5.0x ATR while riding the remainder of the trend.
*   **Risk Management**: Configurable position sizing, leverage, and **Dynamic ATR Stop Loss**.
*   **Resilient**: Handles API connection errors and gracefully manages Binance Testnet quirks.
*   **Testnet Support**: Safely test strategies on Binance Testnet before going live.

---

## 📈 Trading Strategy

The bot implements an optimized trend-following strategy designed for the **15m timeframe**.

### 1. Indicators
*   **Heikin Ashi Candles**: Smoothens price action for better trend identification.
*   **SuperTrend (15, 1.5)**: Used to detect short-term price momentum shifts.
*   **EMA 99**: Long-term trend filter. Trades are only opened in the direction of the EMA.
*   **ADX (14)**: Trend Strength filter. Bot only enters when ADX > 19 (Optimized for 15m).
*   **ATR (14)**: Measures market volatility.

### 2. Execution Logic (Capital Protection & Profit Optimization)

The execution logic is split into hai independent steps: **Exit (Priority)** and **Entry (Filtered)**.

| Current State | Event (SuperTrend) | EMA Filter | ADX Filter | Action | Resulting State |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Empty** | Red $\rightarrow$ **Green** | Price > EMA 99 | **ADX > 22** | **Open LONG** | LONG |
| **Empty** | Red $\rightarrow$ **Green** | Price > EMA 99 | ADX < 22 | Wait (Weak Trend) | Empty |
| **Empty** | Green $\rightarrow$ **Red** | Price < EMA 99 | **ADX > 22** | **Open SHORT** | SHORT |
| **LONG** | Green $\rightarrow$ **Red** | Any | Any | **Close LONG** | Empty |
| **SHORT** | Red $\rightarrow$ **Green** | Any | Any | **Close SHORT** | Empty |
| **ANY** | Price hits **5.0x ATR** | Any | Any | **Partial TP (10%)** | Holding (Reduced) |
| **ANY** | Any | Any | Any | **ATR Stop Loss (0.9x)** | Empty |

**Key Principles:**
*   **Active Profit/Loss Protection**: Positions are closed immediately when the SuperTrend flips, ensuring the bot doesn't hold against the trend.
*   **Disciplined Entry**: New positions are only opened when the short-term trend (SuperTrend) aligns with the long-term trend (EMA).
*   **Partial Take Profit**: Automatically takes partial profits to reduce risk and smooth the equity curve.

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
EMA_LENGTH = 99
LEVERAGE = 9
POSITION_SIZE_PERCENT = 0.25
ADX_THRESHOLD = 19
ATR_MULTIPLIER = 0.9
PARTIAL_TP_ENABLED = True
PARTIAL_TP_MULTIPLIER = 5.0
PARTIAL_TP_PERCENT = 0.1
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Cryptocurrency trading involves significant risk. The authors are not responsible for any financial losses. Always test thoroughly on **Testnet**.
