import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH

def run_backtest():
    print(f"--- Starting Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    
    # 1. Fetch History (with Caching)
    import os
    from datetime import datetime, date
    
    cache_file = "backtest_data.csv"
    df = None
    
    # Check if cache exists and is from today
    if os.path.exists(cache_file):
        file_date = date.fromtimestamp(os.path.getmtime(cache_file))
        if file_date == date.today():
            print("Loading data from local cache...")
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            print("Cache expired. Fetching new data...")
    
    if df is None:
        client = ExchangeClient()
        # Fetch max available limit (Binance usually 1000-1500 per call)
        # We request 1500 to get maximum single-call data
        df = client.fetch_history(limit=1000)
        
        if df is not None and not df.empty:
            print(f"Saving {len(df)} candles to cache...")
            df.to_csv(cache_file, index=False)
    
    if df is None or df.empty:
        print("No data fetched.")
        return

    print(f"Data fetched: {len(df)} candles from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # 2. Process Indicators
    print("Calculating Heikin Ashi and SuperTrend...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_final = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)
    
    # 3. Simulate Trades
    # Logic:
    # - Start with 1000 USDT
    # - Buy (Long) when Trend Green AND ADX > 25 AND Price > EMA
    # - Sell (Short) when Trend Red AND ADX > 25 AND Price < EMA
    # - Position Size: 20% of CURRENT Balance
    
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 # Amount of BTC (+ for Long, - for Short)
    entry_price = 0
    
    trades = []
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    ema_col = f'EMA_{EMA_LENGTH}'
    
    from config import POSITION_SIZE_PERCENT
    
    print("\n--- Trade Log ---")

    for i in range(1, len(df_final)):
        current_candle = df_final.iloc[i]
        prev_candle = df_final.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]
        
        price = current_candle['close']
        timestamp = current_candle['timestamp']
        
        # Determine Signal
        signal = None
        
        # Trend Filter: Price relative to EMA
        is_uptrend_long = price > ema_val
        is_downtrend_long = price < ema_val
        
        if curr_trend == 1 and prev_trend == -1:
            if is_uptrend_long:
                signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1:
            if is_downtrend_long:
                signal = 'SHORT'
            
        if signal:
            # 1. Close Existing Position if any
            if position_amt != 0:
                pnl = 0
                if position_amt > 0: # Closing Long
                    pnl = (price - entry_price) * position_amt
                    print(f"[{timestamp}] CLOSE LONG | Price: {price:.2f} | Entry: {entry_price:.2f} | PnL: {pnl:.2f}")
                    trades.append({'type': 'CLOSE_LONG', 'time': timestamp, 'price': price, 'pnl': pnl})
                else: # Closing Short
                    pnl = (entry_price - price) * abs(position_amt)
                    print(f"[{timestamp}] CLOSE SHORT| Price: {price:.2f} | Entry: {entry_price:.2f} | PnL: {pnl:.2f}")
                    trades.append({'type': 'CLOSE_SHORT', 'time': timestamp, 'price': price, 'pnl': pnl})
                
                balance += pnl
                position_amt = 0
                
            # 2. Open New Position
            if True:
                # Calculate Trade Value
                trade_value = balance * POSITION_SIZE_PERCENT
                amount = trade_value / price
                
                if signal == 'LONG':
                    position_amt = amount
                    entry_price = price
                    print(f"[{timestamp}] OPEN LONG  | Price: {price:.2f} | Amt: {amount:.4f}")
                    trades.append({'type': 'OPEN_LONG', 'time': timestamp, 'price': price, 'amount': amount})
                elif signal == 'SHORT':
                    position_amt = -amount
                    entry_price = price
                    print(f"[{timestamp}] OPEN SHORT | Price: {price:.2f} | Amt: {amount:.4f}")
                    trades.append({'type': 'OPEN_SHORT', 'time': timestamp, 'price': price, 'amount': amount})

    # Final Value
    if position_amt != 0:
        # Close final position
        last_price = df_final.iloc[-1]['close']
        pnl = 0
        if position_amt > 0:
            pnl = (last_price - entry_price) * position_amt
        else:
            pnl = (entry_price - last_price) * abs(position_amt)
        balance += pnl
        
    final_balance = balance
    
    # 4. Report
    print("\n--- Backtest Results ---")
    print(f"Initial Balance: {initial_balance} USDT")
    print(f"Final Balance:   {final_balance:.2f} USDT")
    
    pnl = final_balance - initial_balance
    pnl_percent = (pnl / initial_balance) * 100
    
    print(f"PnL:             {pnl:.2f} USDT ({pnl_percent:.2f}%)")
    print(f"Total Trades:    {sum(1 for t in trades if t['type'] in ['CLOSE_LONG', 'CLOSE_SHORT'])}")
    
    # Calculate Win Rate
    # Iterate through trades to find CLOSE events
    wins = 0
    total_completed_trades = 0
    
    for t in trades:
        if t['type'] in ['CLOSE_LONG', 'CLOSE_SHORT']:
            total_completed_trades += 1
            if t['pnl'] > 0:
                wins += 1
            
    win_rate = (wins / total_completed_trades * 100) if total_completed_trades > 0 else 0
    print(f"Win Rate:        {win_rate:.2f}% ({wins}/{total_completed_trades})")
    
    # Calculate Max Drawdown
    current_equity = initial_balance
    peak_equity = initial_balance
    max_drawdown = 0
    
    for t in trades:
        if t['type'] in ['CLOSE_LONG', 'CLOSE_SHORT']:
            current_equity += t['pnl']
            
            if current_equity > peak_equity:
                peak_equity = current_equity
            
            drawdown = (peak_equity - current_equity) / peak_equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
    print(f"Max Drawdown:    {max_drawdown * 100:.2f}%")
    print("------------------------")

if __name__ == "__main__":
    run_backtest()
