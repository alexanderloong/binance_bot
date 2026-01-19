import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, POSITION_SIZE_PERCENT

def run_ema_comparison():
    print(f"--- Comparing EMA Settings for {SYMBOL} ({TIMEFRAME}) ---")
    
    # 1. Load Data
    cache_file = "backtest_data.csv"
    try:
        df = pd.read_csv(cache_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        print(f"Error loading cache: {e}")
        return

    # Base Indicators
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    
    ema_lengths = [50, 100, 200]
    results = []

    for ema_len in ema_lengths:
        print(f"Testing EMA {ema_len}...")
        # Calculate specific EMA
        # Note: DataProcessor.calculate_ema adds column f'EMA_{length}' but code expects 'EMA_200' usually.
        # We need to adapt the column name check or the processor.
        # Let's see DataProcessor.calculate_ema implementation:
        # df[f'EMA_{length}'] = ...
        
        df_run = df_st.copy()
        df_final = DataProcessor.calculate_ema(df_run, length=ema_len)
        ema_col = f'EMA_{ema_len}'
        
        initial_balance = 1000
        balance = initial_balance
        position_amt = 0
        entry_price = 0
        trades = []
        
        st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
        
        for i in range(1, len(df_final)):
            current_candle = df_final.iloc[i]
            prev_candle = df_final.iloc[i-1]
            
            curr_trend = current_candle[st_dir_col]
            prev_trend = prev_candle[st_dir_col]
            ema_val = current_candle[ema_col]
            price = current_candle['close']
            timestamp = current_candle['timestamp']
            
            signal = None
            is_uptrend_long = price > ema_val
            is_downtrend_long = price < ema_val
            
            if curr_trend == 1 and prev_trend == -1:
                if is_uptrend_long:
                    signal = 'LONG'
            elif curr_trend == -1 and prev_trend == 1:
                if is_downtrend_long:
                    signal = 'SHORT'
                
            if signal:
                # Close
                if position_amt != 0:
                    pnl = 0
                    if position_amt > 0:
                        pnl = (price - entry_price) * position_amt
                    else:
                        pnl = (entry_price - price) * abs(position_amt)
                    balance += pnl
                    trades.append(pnl)
                    position_amt = 0
                    
                # Open
                trade_value = balance * POSITION_SIZE_PERCENT
                amount = trade_value / price
                if signal == 'LONG':
                    position_amt = amount
                    entry_price = price
                elif signal == 'SHORT':
                    position_amt = -amount
                    entry_price = price
                    
        # Close final
        if position_amt != 0:
            last_price = df_final.iloc[-1]['close']
            pnl = 0
            if position_amt > 0:
                pnl = (last_price - entry_price) * position_amt
            else:
                pnl = (entry_price - last_price) * abs(position_amt)
            balance += pnl

        # Stats
        pnl_abs = balance - initial_balance
        pnl_pct = (pnl_abs / initial_balance) * 100
        total_trades = len(trades)
        wins = sum(1 for p in trades if p > 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        results.append({
            'EMA': ema_len,
            'Final Balance': balance,
            'PnL %': pnl_pct,
            'Trades': total_trades,
            'Win Rate': win_rate
        })

    # Print Table
    print("\n--- RESULTS ---")
    with open("results_table.txt", "w", encoding="utf-8") as f:
        header = f"{'EMA':<10} | {'PnL %':<10} | {'Trades':<10} | {'Win Rate':<10}"
        print(header)
        print(header, file=f)
        
        sep = "-" * 50
        print(sep)
        print(sep, file=f)
        
        for r in results:
            line = f"{r['EMA']:<10} | {r['PnL %']:<10.2f} | {r['Trades']:<10} | {r['Win Rate']:<10.2f}%"
            print(line)
            print(line, file=f)

if __name__ == "__main__":
    run_ema_comparison()
