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
        *(Lưu ý: Nếu file `.env` của bạn dùng `API_KEY` và `SECRET`, bot sẽ tự động nhận diện đúng theo `config.py` mới nhất)*

---

## 🚀 Usage

### Run the Live Bot
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

## 📊 Xem Hiệu Suất (Monitoring Performance)

Bạn có thể theo dõi hiệu suất của bot qua các kênh sau:

1.  **Bot Logs**: Xem tệp `bot.log` để theo dõi nhật ký giao dịch, kiểm tra số dư và trạng thái lệnh theo thời gian thực.
2.  **Binance Testnet Dashboard**: Truy cập [testnet.binancefuture.com](https://testnet.binancefuture.com/) để xem trực quan các vị thế đang mở và biến động tài sản.
3.  **Backtest Report**: Chạy `python backtest.py` để nhận báo cáo tổng kết về PnL, Win Rate và Max Drawdown dựa trên dữ liệu lịch sử (1000 nến gần nhất).

---

## ⚙️ Configuration (`config.py`)

You can fine-tune the strategy parameters in `config.py`:

```python
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"          # Period for candles (e.g., 15m, 1h, 1d)
SUPERTREND_LENGTH = 15     # Standard: 15
SUPERTREND_FACTOR = 1.5    # Aggressiveness of SuperTrend
EMA_LENGTH = 100           # Trend filter period
POSITION_SIZE_PERCENT = 1  # 1.0 = 100% of balance used per trade
```

---

## ⚠️ Disclaimer

This software is for educational purposes only. Do not risk money you cannot afford to lose. The authors are not responsible for any financial losses incurred while using this bot.
