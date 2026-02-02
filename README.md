# 🤖 Binance Futures Algorithmic Trading Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Binance](https://img.shields.io/badge/Binance-Futures-FCD535?style=for-the-badge&logo=binance)
![Strategy](https://img.shields.io/badge/Strategy-Trend%20Following-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

A **professional-grade, high-frequency** algorithmic trading bot for Bitcoin Futures (BTC/USDT). Built with a modular architecture, this bot leverages advanced technical analysis (SuperTrend, EMA, ADX, RSI) and robust risk management to capture major market moves while filtering out noise.

> **Latest Version:** 1.10.0  
> **Target:** BTC/USDT Perpetual  
> **Performance:** ~697% PnL (Backtest Data)

---

## 📈 Strategy Overview: "Trend Hunter v1.10"

This bot operates on a **Trend Following** philosophy. It aims to enter large trends early and ride them until reversal, ignoring minor price fluctuations.

### 🧠 Signal Logic
The bot executes trade entries only when **ALL** the following conditions align:

1.  **Trend Direction (EMA)**:
    *   **Long**: Price > EMA (106)
    *   **Short**: Price < EMA (106)
    *   *Rationale*: Ensures we only trade in the direction of the dominant trend.

2.  **Market Structure (SuperTrend)**:
    *   **Long**: SuperTrend (16, 1.45) is GREEN.
    *   **Short**: SuperTrend (16, 1.45) is RED.
    *   *Rationale*: Provides precise entry triggers and trailing stop levels.

3.  **Trend Strength (ADX)**:
    *   **ADX (14) > 19**
    *   *Rationale*: Filters out "choppy" sideways markets where trend following strategies usually fail.

4.  **Momentum Filter (RSI)**:
    *   **Entry Range**: 35 < RSI (14) < 65
    *   *Rationale*: Prevents "Buying the Top" (Overbought > 65) or "Selling the Bottom" (Oversold < 35).

5.  **Volume Confirmation**:
    *   **Volume > Volume MA (147)**
    *   *Rationale*: Validates that the move is backed by significant market participation.

### 🛡️ Risk Management (The "Survival" Engine)

| Parameter | Setting | Description |
| :--- | :--- | :--- |
| **Leverage** | **15x** | Optimized for aggressive growth while maintaining margin safety. |
| **Position Size** | **25%** | Allocates 25% of Total Equity per trade. |
| **Stop Loss** | **0.9x ATR** | Dynamic Volatility-Based Stop Loss. Tight Stops = Small Losses. |
| **Take Profit** | **Disabled** | "Let Profits Run". Positions are closed only on Trend Reversal. |
| **Liquidation** | **Monitoring** | Logic includes liquidation price tracking to prevent total loss. |

---

## 🚀 Performance Metrics

*Based on Backtest Data (Feb 2025 - Feb 2026)*

| Metric | Value | Verdict |
| :--- | :--- | :--- |
| **Net Profit (PnL)** | **+697.03%** | 🚀 Extremely High |
| **Profit Factor** | **1.80** | ✅ Highly Profitable |
| **Win Rate** | **39.0%** | 📉 Classic Trend Following (Small wins/losses, Massive winners) |
| **Max Drawdown** | **16.84%** | ⚠️ Managed Aggressive Risk |
| **Total Trades** | **246** | ⚡ Low Frequency (~2 trades/3 days) |

---

## 🛠️ Installation & Setup

### 1. Requirements
*   Python 3.10+
*   Binance Account (API Key & Secret)
*   Docker (Optional, for deployment)

### 2. Environment Setup
Create a `.env` file in the root directory:
```ini
API_KEY=your_binance_api_key
SECRET=your_binance_secret_key
USE_TESTNET=False
```

### 3. Installation
```bash
# Clone the repository
git clone https://github.com/alexanderloong/binance-bot.git
cd binance-bot

# Install dependencies (Best to use a virtualenv)
pip install -r requirements.txt
```

---

## 🖥️ Usage

### 📊 Backtesting
Validate strategy performance against historical data (automatically fetches live Binance data).
```bash
python backtest.py
```
> **Output**: Generates a detailed trade log and saves a performance chart to `resource/performance_summary.png`.

### 🧬 Optimization
Find the best parameters for the current market using multi-core grid search.
```bash
# Optimize EMA & SuperTrend
python optimize/optimize_ema.py

# Optimize ADX, Volume & ATR
python optimize/optimize_adx.py
```

### 🔴 Run Live
Start the bot to trade on your account.
```bash
python main.py
```

### 🐳 Run with Docker (Recommended)
Deploy as a background service with auto-restart.
```bash
# Build and Run
docker-compose up -d --build

# View Logs
docker-compose logs -f binance-bot
```

---

## 📂 Project Structure

```
binance_bot/
├── bot/
│   ├── data_processor.py   # Technical Indicator Logic (EMA, RSI, ADX...)
│   ├── exchange_client.py  # Binance API Wrapper
│   └── strategy.py         # Core Trading Decision Engine
├── optimize/               # Genetic Algorithms / Grid Search Scripts
├── resource/               # Data Cache & Performance Charts
├── backtest.py             # Backtesting Simulator
├── config.py               # Central Configuration
├── main.py                 # Application Entry Point
└── Dockerfile              # Container Definition
```

---

## 📝 Changelog
See [CHANGELOG.md](CHANGELOG.md) for detailed release history.

---

## ⚠️ Disclaimer
*This software is for educational purposes only. Cryptocurrency trading involves high risk and is not suitable for every investor. The authors are not responsible for any financial losses incurred while using this bot.*
