import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR

def run_debug_backtest():
    print(f"--- DEBUG Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    
    # Load Data
    cache_file = "backtest_data.csv"
    try:
        df = pd.read_csv(cache_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        print(f"Error loading cache: {e}")
        return

    # Monkeypatch DataProcessor to test 10, 2
    import bot.data_processor
    bot.data_processor.SUPERTREND_LENGTH = 10
    bot.data_processor.SUPERTREND_FACTOR = 2.0
    
    # Update local vars for column names
    SUPERTREND_LENGTH = 10
    SUPERTREND_FACTOR = 2.0
    
    # Process
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_final = DataProcessor.calculate_ema(df_st, length=200)
    
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0
    entry_price = 0
    
    trades = []
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    from config import POSITION_SIZE_PERCENT
    
    with open("debug_log.txt", "w", encoding="utf-8") as f:
        print(f"--- DEBUG Backtest for {SYMBOL} ({TIMEFRAME}) ---", file=f)
        print(f"Starting balance: {initial_balance}", file=f)
        
        for i in range(1, len(df_final)):
            current_candle = df_final.iloc[i]
            prev_candle = df_final.iloc[i-1]
            
            curr_trend = current_candle[st_dir_col]
            prev_trend = prev_candle[st_dir_col]
            ema200 = current_candle['EMA_200']
            price = current_candle['close']
            timestamp = current_candle['timestamp']
            
            signal = None
            is_uptrend_long = price > ema200
            is_downtrend_long = price < ema200
            
            if curr_trend == 1 and prev_trend == -1:
                if is_uptrend_long:
                    signal = 'LONG'
            elif curr_trend == -1 and prev_trend == 1:
                if is_downtrend_long:
                    signal = 'SHORT'
                
            if signal:
                # 1. Close Existing
                if position_amt != 0:
                    pnl = 0
                    if position_amt > 0: # Closing Long
                        pnl = (price - entry_price) * position_amt
                        print(f"[{timestamp}] CLOSE LONG | Price: {price:.2f} | Entry: {entry_price:.2f} | PnL: {pnl:.2f}", file=f)
                    else: # Closing Short
                        pnl = (entry_price - price) * abs(position_amt)
                        print(f"[{timestamp}] CLOSE SHORT | Price: {price:.2f} | Entry: {entry_price:.2f} | PnL: {pnl:.2f}", file=f)
                    
                    balance += pnl
                    trades.append(pnl)
                    position_amt = 0
                    
                # 2. Open New
                if True:
                    trade_value = balance * POSITION_SIZE_PERCENT
                    amount = trade_value / price
                    if signal == 'LONG':
                        position_amt = amount
                        entry_price = price
                        print(f"[{timestamp}] OPEN LONG  | Price: {price:.2f} | Amt: {amount:.4f}", file=f)
                    elif signal == 'SHORT':
                        position_amt = -amount
                        entry_price = price
                        print(f"[{timestamp}] OPEN SHORT | Price: {price:.2f} | Amt: {amount:.4f}", file=f)

        print(f"Final Balance: {balance:.2f}", file=f)
        if len(trades) > 0:
            wins = sum(1 for p in trades if p > 0)
            print(f"Win Rate: {wins}/{len(trades)} ({wins/len(trades)*100:.2f}%)", file=f)

if __name__ == "__main__":
    run_debug_backtest()
