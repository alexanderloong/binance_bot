# Binance Futures Trading Bot (v1.16.1 - 2026 Optimized)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Binance](https://img.shields.io/badge/exchange-Binance%20Futures-yellow)
![Stability](https://img.shields.io/badge/Stability-Production--Ready-green)

A robust, trend-following trading bot strategies for Binance Futures. This bot uses a combination of **SuperTrend**, **EMA (Exponential Moving Average)**, **ADX (Average Directional Index)**, **RSI (Relative Strength Index)**, and Volume analysis to execute trades.

> **Note**: Version 1.16.1 is the **Optimized EMA Release**. It features a specialized filter configuration (EMA + Volume) that achieved **+756% PnL** during a 2-year backtest on BTC/USDT (15m).

## 🚀 Features

-   **Trend Following Strategy**: Capitalizes on major market moves using SuperTrend and EMA.
-   **Trend Strength Filtering**: Avoids chop/ranging markets using ADX.
-   **Momentum Checks**: RSI filtering to prevent buying tops or selling bottoms.
-   **Volume Confirmation**: Ensures breakouts are supported by volume.
-   **Dynamic Rate Limiting**: Intelligent throttling to respect Binance API limits.
-   **Heikin Ashi Support**: Uses Heikin Ashi candles for smoother trend detection.
-   **Advanced Risk Management**: ATR-based Stop Loss, strict leverage control.
-   **Optimized Codebase**: Fully typed, modular, and optimized for performance.

## 🛠 Installation

### Prerequisites

-   Python 3.10 or higher.
-   A Binance Futures account (Testnet recommended for initial testing).

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd binance_bot
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration:**
    Create a `.env` file in the root directory:
    ```env
    API_KEY=your_binance_api_key
    SECRET=your_binance_secret_key
    USE_TESTNET=True  # Set to False for real trading
    ```

## 🏃 Usage

### Running the Bot
To start the bot in live trading mode (or Testnet):
```bash
python main.py
```
The bot will initialize, sync time with Binance, and start polling for candle data.

### Backtesting
To run the simulation on historical data:
```bash
python backtest.py
```
This will fetch historical data, run the strategy, and display a performance summary including PnL, Win Rate, and Max Drawdown.

### Optimization
To find the best parameters:
```bash
python optimize/optimize_rsi_long_threshold.py
```

## ⚙️ Configuration

Global settings are managed in `config.py` (and the `TradingConfig` class). Key parameters include:

-   **Symbol**: `BTC/USDT` (Default)
-   **Timeframe**: `15m`
-   **Leverage**: `10x`
-   **Position Size**: `20%` of Balance per trade
-   **Indicators**:
    -   SuperTrend (Length 18, Factor 1.45)
    -   EMA (Length 97) - *Optimized for 15m BTC*
    -   RSI (14, OB 64, OS 36)

## 📊 Strategy Overview

1.  **Entry Conditions**:
    -   **Long**:
        -   Price > EMA
        -   SuperTrend flips GREEN (or persists Green after pullback)
        -   ADX > 18 (Strong Trend)
        -   RSI is healthy (53 < RSI < 64)
    -   **Short**:
        -   Price < EMA
        -   SuperTrend flips RED
        -   ADX > 18
        -   RSI is healthy (> 36)

2.  **Exit Conditions**:
    -   **Stop Loss**: Dynamic ATR-based Stop Loss (0.7x ATR).
    -   **Trend Reversal**: Close immediately if SuperTrend flips against position.
    -   **RSI Divergence**: Bearish divergence detection to partial close and tighten Stop Loss.

3.  **Risk Management**:
    -   **EMA Slope Sizing**: Reduces position size if the trend slope is flat.

## 📜 License
This project is licensed under the MIT License.
