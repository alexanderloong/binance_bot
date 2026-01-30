import pandas as pd
from bot.exchange_client import ExchangeClient
from bot.data_processor import DataProcessor
from config import SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH, POSITION_SIZE_PERCENT, LEVERAGE, ADX_LENGTH, ADX_THRESHOLD, ATR_LENGTH, ATR_MULTIPLIER, PARTIAL_TP_ENABLED, PARTIAL_TP_MULTIPLIER, PARTIAL_TP_PERCENT
import os
import time
from concurrent.futures import ThreadPoolExecutor

from datetime import datetime, date, timedelta  
from binance.um_futures import UMFutures

def simulate(df, use_ema_filter=True, tp_multiplier=PARTIAL_TP_MULTIPLIER, tp_percent=PARTIAL_TP_PERCENT, sl_multiplier=ATR_MULTIPLIER, adx_threshold=ADX_THRESHOLD):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    stop_loss_price = 0
    partial_tp_hit = False
    take_profit_price = 0
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
        
        # Calculate execution time (next candle open = current candle close + 1 timeframe)
        # For 15m timeframe, add 15 minutes
        if i < len(df) - 1:
            execution_time = df.iloc[i+1]['timestamp']
        else:
            # For last candle, estimate by adding timeframe duration
            execution_time = timestamp + pd.Timedelta(minutes=15)
        
        # 1. EXIT LOGIC
        pnl = 0
        fee = 0
        if position_amt > 0 and curr_trend == -1:
            raw_pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'CLOSE_LONG', 'price': price, 'pnl': pnl})
            position_amt = 0
            
        elif position_amt < 0 and curr_trend == 1:
            raw_pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'CLOSE_SHORT', 'price': price, 'pnl': pnl})
            position_amt = 0

        # 1a. PARTIAL TAKE PROFIT CHECK
        if PARTIAL_TP_ENABLED and position_amt != 0 and not partial_tp_hit:
            is_tp_hit = (position_amt > 0 and price >= take_profit_price) or (position_amt < 0 and price <= take_profit_price)
            if is_tp_hit:
                # Close a percentage of current position
                close_amt = position_amt * tp_percent
                raw_pnl = (take_profit_price - entry_price) * close_amt if position_amt > 0 else (entry_price - take_profit_price) * abs(close_amt)
                fee = (take_profit_price * abs(close_amt)) * commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                
                # Update remaining position
                position_amt -= close_amt
                partial_tp_hit = True
                trades.append({'time': execution_time, 'type': 'PARTIAL_TP', 'price': take_profit_price, 'pnl': pnl})

        # 1b. ATR-BASED STOP LOSS CHECK
        if position_amt > 0 and price <= stop_loss_price:
            raw_pnl = (stop_loss_price - entry_price) * position_amt
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'STOP_LOSS_LONG', 'price': stop_loss_price, 'pnl': pnl})
            position_amt = 0
        elif position_amt < 0 and price >= stop_loss_price:
            raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({'time': execution_time, 'type': 'STOP_LOSS_SHORT', 'price': stop_loss_price, 'pnl': pnl})
            position_amt = 0

        # 2. ENTRY LOGIC
        is_uptrend = price > ema_val if use_ema_filter else True
        is_downtrend = price < ema_val if use_ema_filter else True
        
        # New: ADX Filter
        adx_val = current_candle['ADX']
        is_trending = adx_val > adx_threshold
        
        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend:
            if is_trending:
                signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend:
            if is_trending:
                signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * POSITION_SIZE_PERCENT * LEVERAGE
            
            # Entry Fee
            entry_fee = trade_value * commission_rate
            balance -= entry_fee
            
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            
            # Set Dynamic Stop Loss based on ATR
            atr_val = current_candle['ATR']
            if signal == 'LONG':
                stop_loss_price = entry_price - (atr_val * sl_multiplier)
                take_profit_price = entry_price + (atr_val * tp_multiplier)
            else:
                stop_loss_price = entry_price + (atr_val * sl_multiplier)
                take_profit_price = entry_price - (atr_val * tp_multiplier)
            
            partial_tp_hit = False
            
            # Record entry just for tracking
            trades.append({'time': execution_time, 'type': f'OPEN_{signal}', 'price': price, 'pnl': -entry_fee, 'amount': amount, 'sl': stop_loss_price})

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
    closed_trades = [t for t in trades if any(x in t['type'] for x in ['CLOSE', 'STOP_LOSS', 'PARTIAL_TP'])]
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

    # Profit Factor
    all_pnls = [t['pnl'] for t in trades if 'pnl' in t]
    gross_profit = sum(p for p in all_pnls if p > 0)
    gross_loss = abs(sum(p for p in all_pnls if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'total_trades': total_trades_count,
        'win_rate': win_rate,
        'max_drawdown': mdd * 100,
        'profit_factor': profit_factor
    }, trades

def get_backtest_data():
    symbol_clean = SYMBOL.replace("/", "_").replace("\\", "_")
    cache_file = f"backtest_data_{symbol_clean}_{TIMEFRAME}.csv"
    df = None
    
    # Calculate timeframe in seconds for cache expiry
    tf_seconds = 900 # Default 15m
    try:
        val = int(''.join(c for c in TIMEFRAME if c.isdigit()))
        unit = ''.join(c for c in TIMEFRAME if c.isalpha()).lower()
        if unit == 'm': tf_seconds = val * 60
        elif unit == 'h': tf_seconds = val * 3600
        elif unit == 'd': tf_seconds = val * 86400
        else: tf_seconds = val * 60
    except:
        pass

    should_fetch = True
    if os.path.exists(cache_file):
        file_mtime = os.path.getmtime(cache_file)
        file_age = time.time() - file_mtime
        
        # Log cache status
        print(f"Checking cache: {cache_file}")
        print(f"  - File age: {int(file_age)}s")
        print(f"  - Expiry threshold: {tf_seconds}s")

        if file_age < tf_seconds:
            remaining = tf_seconds - file_age
            print(f"✅ Cache is valid. Loading... (Expires in: {int(remaining)}s)")
            try:
                df = pd.read_csv(cache_file)
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    should_fetch = False
                    print(f"✅ Successfully loaded {len(df)} candles from cache.")
                else:
                    print("⚠️ Cache file is empty. Will fetch fresh data.")
            except Exception as e:
                print(f"⚠️ Error loading cache file: {e}. Will fetch fresh data.")
        else:
            print(f"🔄 Cache is stale (Age: {int(file_age)}s >= {tf_seconds}s threshold). Fetching fresh data...")
    
    if should_fetch:
        print(f"Fetching {35000} historical candles from LIVE Binance (multi-threaded)...")
        
        try:
            live_client = UMFutures(base_url="https://fapi.binance.com")
            symbol_clean = SYMBOL.replace("/", "").upper()
            
            # Multi-threaded fetcher
            def fetch_batch(end_ts):
                try:
                    return live_client.klines(symbol_clean, interval=TIMEFRAME, limit=1000, endTime=end_ts)
                except Exception as e:
                    print(f"Error fetching batch at {end_ts}: {e}")
                    return []

            # Calculate time intervals for 35,000 candles
            val = int(''.join(c for c in TIMEFRAME if c.isdigit()))
            unit = ''.join(c for c in TIMEFRAME if c.isalpha()).lower()
            ms_unit = 60 * 1000 if unit == 'm' else (3600 * 1000 if unit == 'h' else 86400 * 1000)
            ms_interval = val * ms_unit
            
            now_ms = int(time.time() * 1000)
            # We need 35 batches of 1000
            end_times = [now_ms - (i * 1000 * ms_interval) for i in range(35)]
            
            all_bars = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(fetch_batch, end_times))
            
            for batch in results:
                all_bars.extend(batch)
            
            # Sort and remove duplicates
            unique_bars = {b[0]: b for b in all_bars}
            sorted_ts = sorted(unique_bars.keys())
            bars = [unique_bars[ts] for ts in sorted_ts]
            
            # Filter to requested length if needed
            bars = bars[-35000:]
            
            print(f"Successfully fetched {len(bars)} candles.")

            df = pd.DataFrame(bars, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
                
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            if df is not None and not df.empty:
                df.to_csv(cache_file, index=False)
                print(f"✅ Live data saved to {cache_file}")
        except Exception as e:
            print(f"❌ Error fetching live data: {e}")
            df = None
            
    return df

def run_backtest():
    print(f"--- Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    tp_status = f"TP: {PARTIAL_TP_MULTIPLIER}xATR ({PARTIAL_TP_PERCENT*100}%)" if PARTIAL_TP_ENABLED else "TP: Disabled"
    print(f"Strategy: EMA {EMA_LENGTH}, SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, ADX > {ADX_THRESHOLD}, SL: {ATR_MULTIPLIER}xATR, {tp_status}")
    
    df = get_backtest_data()
    if df is None: return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_final = df_st
    
    # Run simulation with verbose output (we will modify simulate to return trades and we print them)
    # Or just print after simulation
    res, trades = simulate(df_final, use_ema_filter=True)
    
    print("\n--- Trade History ---")
    for t in trades:
        time_str = t['time']
        if isinstance(time_str, pd.Timestamp):
             time_str = time_str.strftime('%Y-%m-%d %H:%M')
        
        type_str = t['type']
        price = t['price']
        pnl = t.get('pnl', 0)
        amount = t.get('amount', 0)
        
        log_msg = f"[{time_str}] {type_str:<12} at {price:>10.2f}"
        if amount > 0:
            log_msg += f", Amt: {amount:>8.4f}"
        
        if pnl != 0:
            pnl_label = "Fee" if 'OPEN' in type_str else "PnL"
            log_msg += f", {pnl_label}: {pnl:>8.2f} USDT"
            
        print(log_msg, flush=True)
    print(f"\nFinal Balance: {res['final_balance']:.2f} USDT")
    print(f"Total PnL: {res['pnl_pct']:.2f}%")
    print(f"Win Rate: {res['win_rate']:.1f}% ({res['total_trades']} trades)")
    print(f"Profit Factor: {res['profit_factor']:.2f}")
    print(f"Max Drawdown: {res['max_drawdown']:.2f}%")

if __name__ == "__main__":
    run_backtest()
