import os
import time
import math
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from binance.um_futures import UMFutures
from bot.data_processor import DataProcessor
from bot.utils import parse_timeframe_to_seconds
from config import (
    SYMBOL,
    TIMEFRAME,
    SUPERTREND_LENGTH,
    SUPERTREND_FACTOR,
    EMA_LENGTH,
    POSITION_SIZE_PERCENT,
    LEVERAGE,
    VOLUME_MA_LENGTH,
    ATR_LENGTH,
    ATR_MULTIPLIER,
    TAKER_FEE_RATE,
)

LIMIT = 150000
WORKERS = 5
SLEEP = 1.5
GEN_CHART = True


def calculate_metrics(trades, final_balance, initial_balance):
    """Tính các thông số hiệu suất từ danh sách trade lịch sử."""
    trade_cycles = []
    current_trade_pnl = 0
    is_open = False

    for t in trades:
        if "OPEN" in t["type"]:
            current_trade_pnl = t["pnl"]  # Entry fee
            is_open = True
        elif any(x in t["type"] for x in ["CLOSE", "FINAL_CLOSE", "LIQUIDATION", "STOP_LOSS"]):
            current_trade_pnl += t["pnl"]
            if is_open:
                trade_cycles.append(current_trade_pnl)
                is_open = False

    total_trades_count = len(trade_cycles)
    wins = sum(1 for pnl in trade_cycles if pnl > 0)
    win_rate = (wins / total_trades_count * 100) if total_trades_count > 0 else 0
    pnl_total = final_balance - initial_balance
    pnl_pct = (pnl_total / initial_balance) * 100

    # Max Drawdown
    curr_equity = initial_balance
    peak = initial_balance
    mdd = 0
    for t in trades:
        if "pnl" in t:
            curr_equity += t["pnl"]
            peak = max(peak, curr_equity)
            drawdown = (peak - curr_equity) / peak
            mdd = max(mdd, drawdown)

    # Profit Factor
    gross_profit = sum(p for p in trade_cycles if p > 0)
    gross_loss = abs(sum(p for p in trade_cycles if p < 0))
    profit_factor = (
        (gross_profit / gross_loss)
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0)
    )

    # Calmar Ratio = Annualized PnL / Max Drawdown
    days_elapsed = 1
    if trades:
        first_time = trades[0]["time"]
        last_time = trades[-1]["time"]
        if isinstance(first_time, pd.Timestamp) and isinstance(last_time, pd.Timestamp):
            delta = last_time - first_time
            days_elapsed = max(delta.days, 1)
    annualized_pnl_pct = pnl_pct * (365 / days_elapsed)
    calmar_ratio = (
        annualized_pnl_pct / (mdd * 100)
        if mdd > 0
        else float("inf") if annualized_pnl_pct > 0 else 0
    )

    return {
        "final_balance": final_balance,
        "pnl_pct": pnl_pct,
        "total_trades": total_trades_count,
        "win_rate": win_rate,
        "max_drawdown": mdd * 100,
        "profit_factor": profit_factor,
        "calmar_ratio": calmar_ratio,
        "annualized_pnl_pct": annualized_pnl_pct,
    }


def simulate(
    df,
    use_ema_filter=True,
    st_length=SUPERTREND_LENGTH,
    st_factor=SUPERTREND_FACTOR,
    use_volume_filter=True,
    volume_ma_length=VOLUME_MA_LENGTH,
    sl_multiplier=ATR_MULTIPLIER,
    leverage=LEVERAGE,
    position_size_percent=POSITION_SIZE_PERCENT,
):
    initial_balance = 1000
    balance = initial_balance
    position_amt = 0
    entry_price = 0
    liquidation_price = 0
    stop_loss_price = 0
    trades = []
    commission_rate = TAKER_FEE_RATE

    st_dir_col = f"SUPERTd_{st_length}_{st_factor}"
    ema_col = "EMA_FILTER" if "EMA_FILTER" in df.columns else f"EMA_{EMA_LENGTH}"

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i - 1]

        curr_trend = current_candle[st_dir_col]
        prev_trend = prev_candle[st_dir_col]
        ema_val = current_candle[ema_col]

        price = current_candle["close"]
        timestamp = current_candle["timestamp"]

        # Calculate execution time (next candle open)
        if i < len(df) - 1:
            execution_time = df.iloc[i + 1]["timestamp"]
        else:
            tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)
            execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)

        # 0. LIQUIDATION CHECK
        if position_amt != 0:
            liq_hit = False
            if position_amt > 0:  # Long
                if current_candle["low"] <= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price
            else:  # Short
                if current_candle["high"] >= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price

            if liq_hit:
                margin_lost = (abs(position_amt) * entry_price) / leverage
                pnl = -margin_lost
                balance += pnl
                trades.append({
                    "time": execution_time,
                    "type": "LIQUIDATION",
                    "price": liq_price_trigger,
                    "pnl": pnl,
                })
                position_amt = 0
                continue

        # 1. EXIT LOGIC — SuperTrend flip
        if position_amt > 0 and curr_trend == -1:
            raw_pnl = (price - entry_price) * position_amt
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({"time": execution_time, "type": "CLOSE_LONG", "price": price, "pnl": pnl})
            position_amt = 0

        elif position_amt < 0 and curr_trend == 1:
            raw_pnl = (entry_price - price) * abs(position_amt)
            fee = (price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({"time": execution_time, "type": "CLOSE_SHORT", "price": price, "pnl": pnl})
            position_amt = 0

        # 1b. ATR-BASED STOP LOSS CHECK
        if position_amt > 0 and price <= stop_loss_price:
            raw_pnl = (stop_loss_price - entry_price) * position_amt
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({"time": execution_time, "type": "STOP_LOSS_LONG", "price": stop_loss_price, "pnl": pnl})
            position_amt = 0
        elif position_amt < 0 and price >= stop_loss_price:
            raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
            fee = (stop_loss_price * abs(position_amt)) * commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({"time": execution_time, "type": "STOP_LOSS_SHORT", "price": stop_loss_price, "pnl": pnl})
            position_amt = 0

        # 2. ENTRY LOGIC
        is_uptrend = price > ema_val if use_ema_filter else True
        is_downtrend = price < ema_val if use_ema_filter else True

        vol_ma_col = f"VOL_MA_{volume_ma_length}"
        vol_ok = True
        if use_volume_filter and vol_ma_col in current_candle:
            vol_ok = current_candle["volume"] > current_candle[vol_ma_col]

        signal = None
        if curr_trend == 1 and prev_trend == -1 and is_uptrend and vol_ok:
            signal = "LONG"
        elif curr_trend == -1 and prev_trend == 1 and is_downtrend and vol_ok:
            signal = "SHORT"

        if signal and position_amt == 0:
            trade_value = balance * position_size_percent * leverage
            entry_fee = trade_value * commission_rate
            balance -= entry_fee

            amount = trade_value / price
            position_amt = amount if signal == "LONG" else -amount
            entry_price = price

            # Liquidation price
            if signal == "LONG":
                liquidation_price = entry_price * (1 - 1 / leverage)
            else:
                liquidation_price = entry_price * (1 + 1 / leverage)

            # ATR-based Stop Loss
            atr_val = current_candle["ATR"]
            if signal == "LONG":
                stop_loss_price = entry_price - (atr_val * sl_multiplier)
            else:
                stop_loss_price = entry_price + (atr_val * sl_multiplier)

            trades.append({
                "time": execution_time,
                "type": f"OPEN_{signal}",
                "price": price,
                "pnl": -entry_fee,
                "amount": amount,
            })

    # Close final position
    if position_amt != 0:
        last_price = df.iloc[-1]["close"]
        raw_pnl = (
            (last_price - entry_price) * position_amt
            if position_amt > 0
            else (entry_price - last_price) * abs(position_amt)
        )
        fee = (last_price * abs(position_amt)) * commission_rate
        pnl = raw_pnl - fee
        balance += pnl
        trades.append({
            "time": df.iloc[-1]["timestamp"],
            "type": "FINAL_CLOSE",
            "price": last_price,
            "pnl": pnl,
        })

    metrics = calculate_metrics(trades, balance, initial_balance)
    return metrics, trades


def fetch_binance_history(symbol_clean, limit, ms_interval, now_ms):
    """Fetch history request từ Binance."""
    print(f"Fetching {limit} historical candles from LIVE Binance (multi-threaded)...")
    live_client = UMFutures(base_url="https://fapi.binance.com")

    batch_size = 1500
    num_batches = math.ceil(limit / batch_size)

    print(f"Plan: Fetch {num_batches} batches (limit=1500) using {WORKERS} threads.")
    safe_limit = 2000
    estimated_weight = (WORKERS / SLEEP) * 60 * 10
    print(f"Estimated Weight: {int(estimated_weight)} / {safe_limit} (Max 2400)")

    if estimated_weight > safe_limit:
        print(f"❌ DANGER: Configuration exceeds safe API limits!")
        return None

    print(f"Estimated time: ~{int(num_batches/(WORKERS/SLEEP))} seconds")

    BINANCE_FUTURES_LAUNCH_MS = 1569888000000
    end_times = [
        now_ms - (i * batch_size * ms_interval)
        for i in range(num_batches)
        if (now_ms - (i * batch_size * ms_interval)) > BINANCE_FUTURES_LAUNCH_MS
    ]
    if len(end_times) < num_batches:
        print(f"ℹ️  Trimmed to {len(end_times)} batches (history limit reached before 2019-10-01).")

    def fetch_single_batch(end_ts):
        time.sleep(SLEEP)
        retries = 3
        while retries > 0:
            try:
                return live_client.klines(symbol_clean, interval=TIMEFRAME, limit=1500, endTime=end_ts)
            except Exception as e:
                err_msg = str(e)
                retry_after = 5
                if "418" in err_msg or "429" in err_msg:
                    try:
                        retry_after = int(err_msg.split("'retry-after': '")[1].split("'")[0])
                    except:
                        retry_after = 60
                    print(f"\n⚠️ Rate Limit Hit! Thread sleeping {retry_after}s...")
                    time.sleep(retry_after)
                else:
                    print(f"\n⚠️ Error: {e}. Retrying...")
                    time.sleep(5)
                retries -= 1
        return []

    all_bars = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        results = list(executor.map(fetch_single_batch, end_times))

    count_success = 0
    for batch in results:
        if batch:
            all_bars.extend(batch)
            count_success += 1

    print(f"\n✅ Fetched {count_success}/{num_batches} batches successfully.")

    unique_bars = {b[0]: b for b in all_bars}
    sorted_ts = sorted(unique_bars.keys())
    bars = [unique_bars[ts] for ts in sorted_ts]
    bars = bars[-limit:]
    print(f"Successfully fetched {len(bars)} candles.")

    df = pd.DataFrame(
        bars,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore",
        ],
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    df["timestamp"] = (
        pd.to_datetime(df["timestamp"], unit="ms")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Ho_Chi_Minh")
    )
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    return df


def get_backtest_data(limit=LIMIT):
    symbol_file_name = SYMBOL.replace("/", "_").replace("\\", "_")
    symbol_api_name = SYMBOL.replace("/", "").upper()

    cache_dir = "resource"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, f"backtest_data_{symbol_file_name}_{TIMEFRAME}.csv")

    tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)
    should_fetch = True
    df = None

    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        print(f"Checking cache: {cache_file} (Age: {int(file_age)}s, Expiry: {tf_seconds}s)")

        if file_age < tf_seconds:
            print(f"✅ Cache is valid. Loading... (Expires in: {int(tf_seconds - file_age)}s)")
            try:
                df = pd.read_csv(cache_file)
                if not df.empty:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
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
            print(f"🔄 Cache is stale. Fetching fresh data...")

    if should_fetch:
        ms_interval = tf_seconds * 1000
        now_ms = int(time.time() * 1000)
        df = fetch_binance_history(symbol_api_name, limit, ms_interval, now_ms)
        
        if df is not None and not df.empty:
            df.to_csv(cache_file, index=False)
            print(f"✅ Live data saved to {cache_file}")
        else:
            print(f"❌ Error fetching live data.")

    return df


def log_results(res, trades, df):
    """Log performance và ghi ra tệp txt."""
    log_dir = "resource/backtest_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"backtest_{timestamp}.txt")
    log_lines = []

    def app_log(msg):
        print(msg)
        log_lines.append(str(msg))

    app_log("--- Trade History ---")
    for t in trades:
        time_str = t["time"]
        if isinstance(time_str, pd.Timestamp):
            time_str = time_str.strftime("%Y-%m-%d %H:%M")

        type_str = t["type"]
        price = t["price"]
        pnl = t.get("pnl", 0)
        amount = t.get("amount", 0)

        log_msg = f"[{time_str}] {type_str:<12} at {price:>10.2f}"
        if amount > 0:
            log_msg += f", Amt: {amount:>8.4f}"
        if pnl != 0:
            pnl_label = "Fee" if "OPEN" in type_str else "PnL"
            log_msg += f", {pnl_label}: {pnl:>8.2f} USDT"

        app_log(log_msg)

    app_log(f"\nFinal Balance: {res['final_balance']:.2f} USDT")
    app_log(f"Total PnL: {res['pnl_pct']:.2f}%")
    app_log(f"Annualized PnL: {res['annualized_pnl_pct']:.2f}%")
    app_log(f"Win Rate: {res['win_rate']:.1f}% ({res['total_trades']} trades)")
    app_log(f"Profit Factor: {res['profit_factor']:.2f}")
    app_log(f"Max Drawdown: {res['max_drawdown']:.2f}%")
    app_log(f"Calmar Ratio: {res['calmar_ratio']:.2f}")

    if not df.empty:
        start_time = df.iloc[0]["timestamp"]
        end_time = df.iloc[-1]["timestamp"]
        total_days = (end_time - start_time).days
        avg_trades_per_day = res["total_trades"] / total_days if total_days > 0 else 0
        app_log(f"Data Range: {start_time} -> {end_time} ({total_days} days)")
        app_log(f"Avg Trades/Day: {avg_trades_per_day:.2f}")

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
        print(f"\n✅ Backtest logs saved to: {log_file}")
    except Exception as e:
        print(f"\n❌ Failed to save log file: {e}")


def run_backtest():
    print(f"--- Backtest for {SYMBOL} ({TIMEFRAME}) ---")
    print(f"Strategy: SuperTrend {SUPERTREND_LENGTH}/{SUPERTREND_FACTOR}, EMA {EMA_LENGTH}, Vol MA {VOLUME_MA_LENGTH}")

    df = get_backtest_data(limit=LIMIT)
    if df is None:
        return

    print(f"Processing {len(df)} candles...")
    df_ha = DataProcessor.calculate_heikin_ashi(df)
    df_st = DataProcessor.calculate_supertrend(df_ha)
    df_st[f"EMA_{EMA_LENGTH}"] = DataProcessor.calculate_ema(df_st, length=EMA_LENGTH)[f"EMA_{EMA_LENGTH}"]
    df_st["ATR"] = DataProcessor.calculate_atr(df, length=ATR_LENGTH)
    df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)
    df_final = df_st

    # Run simulation
    res, trades = simulate(df_final, use_ema_filter=True, use_volume_filter=True)

    # Log results
    log_results(res, trades, df)

    try:
        if GEN_CHART:
            from optimize.plot_results import plot_performance
            print("\nGenerating Performance Chart...")
            plot_performance(df_final, trades, res)
    except Exception as e:
        print(f"Could not generate chart: {e}")

    return res, trades


if __name__ == "__main__":
    run_backtest()
