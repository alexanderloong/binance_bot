import os
import time
import math
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from binance.um_futures import UMFutures
from bot.utils import parse_timeframe_to_seconds

class BacktestDataLoader:
    """Tải và Cache dữ liệu Kline từ Binance cho Backtest."""
    def __init__(self, symbol, timeframe, workers=5, sleep=1.5):
        self.symbol = symbol
        self.timeframe = timeframe
        self.workers = workers
        self.sleep = sleep

    def _fetch_binance_history(self, symbol_clean, limit, ms_interval, now_ms):
        print(f"Fetching {limit} historical candles from LIVE Binance (multi-threaded)...")
        live_client = UMFutures(base_url="https://fapi.binance.com")

        batch_size = 1500
        num_batches = math.ceil(limit / batch_size)

        print(f"Plan: Fetch {num_batches} batches (limit=1500) using {self.workers} threads.")
        safe_limit = 2000
        estimated_weight = (self.workers / self.sleep) * 60 * 10
        print(f"Estimated Weight: {int(estimated_weight)} / {safe_limit} (Max 2400)")

        if estimated_weight > safe_limit:
            print(f"❌ DANGER: Configuration exceeds safe API limits!")
            return None

        print(f"Estimated time: ~{int(num_batches/(self.workers/self.sleep))} seconds")

        BINANCE_FUTURES_LAUNCH_MS = 1569888000000
        end_times = [
            now_ms - (i * batch_size * ms_interval)
            for i in range(num_batches)
            if (now_ms - (i * batch_size * ms_interval)) > BINANCE_FUTURES_LAUNCH_MS
        ]
        if len(end_times) < num_batches:
            print(f"ℹ️  Trimmed to {len(end_times)} batches (history limit reached before 2019-10-01).")

        def fetch_single_batch(end_ts):
            time.sleep(self.sleep)
            retries = 3
            while retries > 0:
                try:
                    return live_client.klines(symbol_clean, interval=self.timeframe, limit=1500, endTime=end_ts)
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
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
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

    def get_data(self, limit):
        symbol_file_name = self.symbol.replace("/", "_").replace("\\", "_")
        symbol_api_name = self.symbol.replace("/", "").upper()

        cache_dir = "resource"
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        cache_file = os.path.join(cache_dir, f"backtest_data_{symbol_file_name}_{self.timeframe}.csv")

        tf_seconds = parse_timeframe_to_seconds(self.timeframe)
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
            df = self._fetch_binance_history(symbol_api_name, limit, ms_interval, now_ms)
            
            if df is not None and not df.empty:
                df.to_csv(cache_file, index=False)
                print(f"✅ Live data saved to {cache_file}")
            else:
                print(f"❌ Error fetching live data.")

        return df
