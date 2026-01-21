import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, POSITION_SIZE_PERCENT, LEVERAGE
import os
from datetime import datetime, date

def simulate(df, use_ema_filter=True):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    trades = []
    # Fee: 0.05% for Taker (Market Orders)
    commission_rate = 0.0005 
    
    st_dir_col = f"SUPERTd_{SUPERTREND_LENGTH}_{SUPERTREND_FACTOR}"
    # Use the custom EMA column if provided (for comparison), otherwise default to config EMA
    ema_col = 'EMA_FILTER' if 'EMA_FILTER' in df.columns else f'EMA_{EMA_LENGTH}'

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]
        
        price = current_candle['close']
        timestamp = current_candle['timestamp']
        
        # 1. EXIT LOGIC
        pnl = 0
        fee = 0
        if position_amt > 0 and curr_trend == -1:
            raw_pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': timestamp, 'type': 'CLOSE_LONG', 'price': price, 'pnl': pnl})
            position_amt = 0
            
        elif position_amt < 0 and curr_trend == 1:
            raw_pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': timestamp, 'type': 'CLOSE_SHORT', 'price': price, 'pnl': pnl})
            position_amt = 0

        # 2. ENTRY LOGIC
        is_uptrend = price > ema_val if use_ema_filter else True
        is_downtrend = price < ema_val if use_ema_filter else True
        
        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend:
            signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend:
            signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * POSITION_SIZE_PERCENT * LEVERAGE
            
            # Entry Fee
            entry_fee = trade_value * commission_rate
            balance -= entry_fee
            
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            
            # Record entry just for tracking, PnL is usually realized on close (or you can account for fee here)
            # To match balance tracking: we already deducted entry_fee from balance.
            # We can record a small negative PnL for the entry fee to track drawdown accurately
            trades.append({'time': timestamp, 'type': f'OPEN_{signal}', 'price': price, 'pnl': -entry_fee, 'amount': amount})

    # Close final position
    if position_amt != 0:
        last_price = df.iloc[-1]['close']
        raw_pnl = (last_price - entry_price) * position_amt if position_amt > 0 else (entry_price - last_price) * abs(position_amt)
        fee = (last_price * abs(position_amt)) * commission_rate
        pnl = raw_pnl - fee
        balance += pnl
        trades.append({'time': df.iloc[-1]['timestamp'], 'type': 'FINAL_CLOSE', 'price': last_price, 'pnl': pnl})

    # Stats calculation
    # Count only closed trades for win rate
    closed_trades = [t for t in trades if 'CLOSE' in t['type']]
    total_trades_count = len(closed_trades)
    
    # Win = PnL > 0 (Fee is already included in PnL)
    wins = sum(1 for t in closed_trades if t['pnl'] > 0)
    win_rate = (wins / total_trades_count * 100) if total_trades_count > 0 else 0
    pnl_total = balance - initial_balance
    pnl_pct = (pnl_total / initial_balance) * 100
    
    # Max Drawdown
    curr_equity = initial_balance
    peak = initial_balance
    mdd = 0
    # Replay all PnL events (entries have fees, exits have pnl - fees)
    for t in trades:
        if 'pnl' in t:
            curr_equity += t['pnl']
            peak = max(peak, curr_equity)
            drawdown = (peak - curr_equity) / peak
            mdd = max(mdd, drawdown)

    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'total_trades': total_trades_count,
        'win_rate': win_rate,
        'max_drawdown': mdd * 100
    }, trades

def run_backtest():
    print(f"--- Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    print(f"Strategy: EMA {EMA_LENGTH}, SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}")
    
    cache_file = "backtest_data.csv"
    df = None
    
    if os.path.exists(cache_file):
        print("Loading data from local cache...")
        try:
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # handling tz if needed, usually just kept as is for backtest display
        except:
            pass
    
    if df is None or df.empty:
        client = ExchangeClient()
        df = client.fetch_history(limit=1000)
        if df is not None:
            df.to_csv(cache_file, index=False)
    
    if df is None or df.empty:
        print("No data.")
        return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_final = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)
    
    # Run simulation with verbose output (we will modify simulate to return trades and we print them)
    # Or just print after simulation
    res, trades = simulate(df_final, use_ema_filter=True)
    
    print("\n" + "="*80)
    print(f"{'Time':<25} | {'Type':<15} | {'Price':<12} | {'Amount':<15} | {'PnL (USDT)':<12}")
    print("-" * 80)
    
    previous_pnl_acc = 0
    for t in trades:
        time_str = t['time']
        if isinstance(time_str, pd.Timestamp):
             time_str = time_str.strftime('%Y-%m-%d %H:%M')
        
        type_str = t['type']
        price = t['price']
        pnl = t.get('pnl', 0)
        amount = t.get('amount', 0)
        amount_str = f"{amount:.4f}" if amount > 0 else "-"
        
        # Determine nice formatting
        if 'OPEN' in type_str:
             print(f"{time_str:<25} | {type_str:<15} | {price:<12.4f} | {amount_str:<15} | {pnl:>12.4f} (Fee)")
        elif 'CLOSE' in type_str:
             print(f"{time_str:<25} | {type_str:<15} | {price:<12.4f} | {amount_str:<15} | {pnl:>12.4f}")
        else:
             print(f"{time_str:<25} | {type_str:<15} | {price:<12.4f} | {amount_str:<15} | {pnl:>12.4f}")

    print("="*80)
    print(f"\nFinal Balance: {res['final_balance']:.2f} USDT")
    print(f"Total PnL: {res['pnl_pct']:.2f}%")
    print(f"Win Rate: {res['win_rate']:.1f}% ({res['total_trades']} trades)")
    print(f"Max Drawdown: {res['max_drawdown']:.2f}%")

if __name__ == "__main__":
    run_backtest()
