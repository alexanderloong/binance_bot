import os
import time
import math
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from binance.um_futures import UMFutures
from bot.data_processor import DataProcessor
from bot.utils import parse_timeframe_to_seconds
from config import (
    SYMBOL, TIMEFRAME, SUPERTREND_LENGTH, SUPERTREND_FACTOR, EMA_LENGTH,
    POSITION_SIZE_PERCENT, LEVERAGE, ADX_LENGTH, ADX_THRESHOLD, 
    ATR_LENGTH, ATR_MULTIPLIER,
    RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_MA_LENGTH
)

LIMIT = 70000
WORKERS = 5
SLEEP = 1.5
GEN_CHART = True

def simulate(df, use_ema_filter=True, st_length=SUPERTREND_LENGTH, st_factor=SUPERTREND_FACTOR, sl_multiplier=ATR_MULTIPLIER, adx_threshold=ADX_THRESHOLD, use_rsi_filter=True, rsi_overbought=RSI_OVERBOUGHT, rsi_oversold=RSI_OVERSOLD, use_volume_filter=True, volume_ma_length=VOLUME_MA_LENGTH, leverage=LEVERAGE, position_size_percent=POSITION_SIZE_PERCENT):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0 
    entry_price = 0
    liquidation_price = 0
    stop_loss_price = 0
    trades = []
    # Fee: 0.05% for Taker (Market Orders)
    commission_rate = 0.0005
    
    st_dir_col = f"SUPERTd_{st_length}_{st_factor}"
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
        if i < len(df) - 1:
            execution_time = df.iloc[i+1]['timestamp']
        else:
            # For last candle, estimate by adding timeframe duration
            tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)
            execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)
        

        # 0. LIQUIDATION CHECK
        if position_amt != 0:
            # Liquidation threshold: 100/Leverage % move against position
            # Simply: Check if price hits Liquidation Price
            # Used Entry Price for reference. 
            
            liq_hit = False
            if position_amt > 0: # Long
                if current_candle['low'] <= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price
            else: # Short
                if current_candle['high'] >= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price
            
            if liq_hit:
                # Liquidated!
                # Loss = Margin Collateral. 
                # Margin = Trade Value / Leverage
                # Effective PnL = -Margin
                # Actually, in cross margin, you lose more, but here we assume isolated risk per trade for simplicity 
                # or just max loss equal to initial margin assigned.
                
                margin_lost = (abs(position_amt) * entry_price) / leverage
                pnl = -margin_lost
                balance += pnl # Deduct margin
                
                trades.append({'time': execution_time, 'type': 'LIQUIDATION', 'price': liq_price_trigger, 'pnl': pnl})
                position_amt = 0
                continue # Skip other exit checks

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

        # 1a. PARTIAL TAKE PROFIT - DISABLED (Pure Trend Following)

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
        
        # New: RSI Filter
        rsi_val = current_candle['RSI']
        rsi_long_ok = rsi_val < rsi_overbought if use_rsi_filter else True
        rsi_short_ok = rsi_val > rsi_oversold if use_rsi_filter else True
        
        # New: Volume MA Filter
        vol_ma_col = f'VOL_MA_{volume_ma_length}'
        vol_ok = True
        if use_volume_filter and vol_ma_col in current_candle:
            vol_ok = current_candle['volume'] > current_candle[vol_ma_col]
        
        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend:
            if is_trending and rsi_long_ok and vol_ok:
                signal = 'LONG'
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend:
            if is_trending and rsi_short_ok and vol_ok:
                signal = 'SHORT'
            
        if signal and position_amt == 0:
            trade_value = balance * position_size_percent * leverage
            
            # Entry Fee
            entry_fee = trade_value * commission_rate
            balance -= entry_fee
            
            amount = trade_value / price
            position_amt = amount if signal == 'LONG' else -amount
            entry_price = price
            
            # Calculate Liquidation Price (Bankruptcy Price approximation)
            # Long Liq = Entry * (1 - 1/Leverage)
            # Short Liq = Entry * (1 + 1/Leverage)
            if signal == 'LONG':
                liquidation_price = entry_price * (1 - 1/leverage)
            else:
                liquidation_price = entry_price * (1 + 1/leverage)
            
            # Set Dynamic Stop Loss based on ATR
            atr_val = current_candle['ATR']
            if signal == 'LONG':
                stop_loss_price = entry_price - (atr_val * sl_multiplier)
            else:
                stop_loss_price = entry_price + (atr_val * sl_multiplier)
            
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
    # Aggregate trades into cycles to get accurate Win Rate
    trade_cycles = []
    current_trade_pnl = 0
    is_open = False
    
    for t in trades:
        if 'OPEN' in t['type']:
            current_trade_pnl = t['pnl'] # Entry fee
            is_open = True
        elif any(x in t['type'] for x in ['CLOSE', 'STOP_LOSS', 'FINAL_CLOSE', 'LIQUIDATION']):
            current_trade_pnl += t['pnl']
            if is_open:
                trade_cycles.append(current_trade_pnl)
                is_open = False
    
    total_trades_count = len(trade_cycles)
    wins = sum(1 for pnl in trade_cycles if pnl > 0)
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

    # Profit Factor based on Trade Cycles (Net PnL per trade)
    gross_profit = sum(p for p in trade_cycles if p > 0)
    gross_loss = abs(sum(p for p in trade_cycles if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

    return {
        'final_balance': balance,
        'pnl_pct': pnl_pct,
        'total_trades': total_trades_count,
        'win_rate': win_rate,
        'max_drawdown': mdd * 100,
        'profit_factor': profit_factor
    }, trades

def get_backtest_data(limit=LIMIT):
    symbol_clean = SYMBOL.replace("/", "_").replace("\\", "_")
    
    # Store data in resource folder
    cache_dir = "resource"
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, f"backtest_data_{symbol_clean}_{TIMEFRAME}.csv")
    
    df = None
    
    # Calculate timeframe in seconds for cache expiry
    tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)

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
                    if len(df) < limit:
                         print(f"⚠️ Cache has {len(df)} candles, but {limit} requested. Fetching fresh data.")
                         should_fetch = True
                    else:
                        should_fetch = False
                        df = df.iloc[-limit:].copy()
                        print(f"✅ Successfully loaded {len(df)} candles from cache.")
                else:
                    print("⚠️ Cache file is empty. Will fetch fresh data.")
            except Exception as e:
                print(f"⚠️ Error loading cache file: {e}. Will fetch fresh data.")
        else:
            print(f"🔄 Cache is stale (Age: {int(file_age)}s >= {tf_seconds}s threshold). Fetching fresh data...")
    
    if should_fetch:
        print(f"Fetching {limit} historical candles from LIVE Binance (multi-threaded)...")
        
        try:
            live_client = UMFutures(base_url="https://fapi.binance.com")
            symbol_clean = SYMBOL.replace("/", "").upper()
            
            # Optimized fetcher: Multi-threaded but safely throttled
            # 1. Increase limit per request to 1500 (max for Futures) to reduce total requests.
            # 2. Use 2 workers with 1s delay. Total ~2 req/s => ~600 weight/min (Limit is 2400).
            # This is 25% of limit, very safe even for long history.

            # Calculate time intervals (re-added)
            tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)
            ms_interval = tf_seconds * 1000
            now_ms = int(time.time() * 1000)
            
            batch_size = 1500 
            num_batches = math.ceil(limit / batch_size)
            
            print(f"Plan: Fetch {num_batches} batches (limit=1500) using {WORKERS} threads.")
            
            # Pre-check Weight Limit
            # Max Limit: 2400 weight/min
            # Weight per req: 10 (since limit=1500 > 1000)
            # Req per second = WORKERS / SLEEP
            # Weight per minute = (WORKERS / SLEEP) * 60 * 10
            
            safe_limit = 2000 # Leave buffer from 2400
            estimated_weight = (WORKERS / SLEEP) * 60 * 10
            
            print(f"Estimated Weight: {int(estimated_weight)} / {safe_limit} (Max 2400)")
            
            if estimated_weight > safe_limit:
                print(f"❌ DANGER: Configuration exceeds safe API limits!")
                print(f"   Required: < {safe_limit} weight/min")
                print(f"   Current:  ~{int(estimated_weight)} weight/min")
                print(f"   action: Increase SLEEP or Reduce WORKERS.")
                return None

            print(f"Estimated time: ~{int(num_batches/(WORKERS/SLEEP))} seconds (Safety Mode needed for large data)")
            
            # Generate end times
            end_times = [now_ms - (i * batch_size * ms_interval) for i in range(num_batches)]

            def fetch_single_batch(end_ts):
                # Rate limit: Sleep 1.0s per thread per request
                time.sleep(SLEEP) 
                
                retries = 3
                while retries > 0:
                    try:
                        return live_client.klines(symbol_clean, interval=TIMEFRAME, limit=1500, endTime=end_ts)
                    except Exception as e:
                        err_msg = str(e)
                        retry_after = 5
                        
                        if "418" in err_msg or "429" in err_msg:
                            if 'retry-after' in err_msg.lower():
                                try:
                                    retry_after = int(err_msg.split("'retry-after': '")[1].split("'")[0])
                                except:
                                    retry_after = 60
                            else:
                                retry_after = 60
                                
                            print(f"\n⚠️ Rate Limit Hit! Thread sleeping {retry_after}s...")
                            time.sleep(retry_after)
                        else:
                            # Network error or other, short sleep
                            print(f"\n⚠️ Error: {e}. Retrying...")
                            time.sleep(5)
                        
                        retries -= 1
                return []

            all_bars = []
            with ThreadPoolExecutor(max_workers=WORKERS) as executor:
                # Use list(executor.map) to preserve order or just collect and sort later
                # map preserves order of results corresponding to input iterator
                results = list(executor.map(fetch_single_batch, end_times))
            
            # Use a progress bar style print if possible, but map blocks until done.
            # To show progress with map, we'd need as_completed, but then order is lost (we sort later anyway).
            
            count_success = 0
            for batch in results:
                if batch:
                    all_bars.extend(batch)
                    count_success += 1
            
            print(f"\n✅ Fetched {count_success}/{num_batches} batches successfully.")
            
            # Sort and remove duplicates
            unique_bars = {b[0]: b for b in all_bars}
            sorted_ts = sorted(unique_bars.keys())
            bars = [unique_bars[ts] for ts in sorted_ts]
            
            # Filter to requested length if needed
            bars = bars[-limit:]
            
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

    limit = LIMIT

    print(f"Strategy: EMA {EMA_LENGTH}, SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, ADX > {ADX_THRESHOLD}, SL: {ATR_MULTIPLIER}xATR, TP: Disabled (Pure Trend Following)")
    
    df = get_backtest_data(limit=limit)
    if df is None: return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f'EMA_{EMA_LENGTH}'] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f'EMA_{EMA_LENGTH}']
    df_st['ADX'] = DataProcessor.calculate_adx(df, length=ADX_LENGTH)
    df_st['ATR'] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st['RSI'] = DataProcessor.calculate_rsi(df, length=RSI_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    df_final = df_st
    
    # Run simulation with verbose output (we will modify simulate to return trades and we print them)
    # Or just print after simulation
    res, trades = simulate(df_final, use_ema_filter=True, use_rsi_filter=True, use_volume_filter=True)
    
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
        
    # Log data range
    if not df.empty:
        start_time = df.iloc[0]['timestamp']
        end_time = df.iloc[-1]['timestamp']
        print(f"Data Range: {start_time} -> {end_time} ({(end_time - start_time).days} days) " )
    
    # Generate Performance Summary Plot
    try:
        if GEN_CHART:
            from optimize.plot_results import plot_performance
            print("\nGenerating Performance Chart...")
            plot_performance(df_final, trades, res)
    except Exception as e:
        print(f"Could not generate chart: {e}")

if __name__ == "__main__":
    run_backtest()
