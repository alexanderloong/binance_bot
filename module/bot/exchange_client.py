import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List

import json
import pandas as pd
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from resource.config import settings

# REST API timeouts: (connect_timeout, read_timeout) in seconds
REST_TIMEOUT = (10, 30)

# --- TIME SYNC ---
# FIX: removed global monkey-patch of time.time (unsafe — affects all 3rd-party libs).
# Use synced_time() explicitly wherever server-synced time is needed.
_GLOBAL_TIME_OFFSET = 0.0
_original_time = time.time  # captured once at import; never overwritten


def synced_time() -> float:
    """Returns epoch time corrected by the measured Binance server offset."""
    return _original_time() + _GLOBAL_TIME_OFFSET


from functools import wraps


def retry_on_timestamp_error(func):
    """Decorator to retry on -1021 timestamp error after time sync."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            if "-1021" in str(e):
                self.logger.warning(
                    f"Timestamp error (-1021) in {func.__name__}. Syncing time and retrying..."
                )
                self.sync_time()
                return func(self, *args, **kwargs)
            raise

    return wrapper


class ExchangeClient:
    def __init__(self) -> None:
        self.logger = logging.getLogger("BinanceBot")

        # Determine base URL
        base_url = "https://fapi.binance.com"
        ws_base_url = "wss://fstream.binance.com/ws"
        if settings.USE_TESTNET:
            base_url = "https://testnet.binancefuture.com"
            ws_base_url = "wss://stream.binancefuture.com/ws"

        self._ws_base_url = ws_base_url
        self.client = UMFutures(
            key=settings.API_KEY,
            secret=settings.SECRET,
            base_url=base_url,
            timeout=REST_TIMEOUT,
        )

        # Prepare symbol
        self.symbol: str = settings.SYMBOL.replace("/", "").upper()

        # --- WEBSOCKET STATE ---
        self.klines_buffer: Optional[pd.DataFrame] = None
        self.last_ws_update: float = synced_time()
        self._ws_lock = threading.Lock()
        self._ws_reconnecting = False
        self.ws_client = UMFuturesWebsocketClient(
            on_message=self._on_ws_message, stream_url=ws_base_url
        )
        self._start_kline_stream()

        # Start WS health monitor thread
        self._ws_monitor_thread = threading.Thread(
            target=self._ws_health_monitor, daemon=True
        )
        self._ws_monitor_thread.start()

        # Symbol information (precision)
        self.qty_precision: int = 3  # Default for BTCUSDT safety
        self.price_precision: int = 2
        self.get_symbol_info()

        # Verify connection
        try:
            # 1. Test connectivity (Ping)
            self.client.ping()
            self.logger.info("Connection to Binance API established.")

            # Pre-populate buffer
            self.logger.info("Pre-populating klines buffer via REST...")
            self.fetch_ohlcv(limit=300)

            # 2. Try to set leverage
            try:
                self._change_leverage_with_retry(self.symbol, settings.LEVERAGE)
                self.logger.info(
                    f"Leverage set to {settings.LEVERAGE}x for {self.symbol}"
                )
            except Exception as lev_e:
                self.logger.warning(
                    f"Note: Could not set leverage (might be already set or other error): {lev_e}"
                )

            # 3. Check Balance
            balance = self.get_balance()
            self.logger.info(
                f"Successfully authenticated. Current Wallet Balance: {balance} USDT"
            )

        except Exception as e:
            self.logger.error(f"Critical connection error: {e}")

    def _start_kline_stream(self) -> None:
        """Starts the WebSocket kline stream."""
        kline_stream = f"{self.symbol.lower()}@kline_{settings.TIMEFRAME}"
        self.ws_client.subscribe(stream=kline_stream, id=1)
        self.logger.info(f"Subscribed to WebSocket stream: {kline_stream}")

    def _ws_health_monitor(self) -> None:
        """Background thread: reconnects WebSocket if silent for > 180s."""
        STALE_THRESHOLD = 180  # seconds without any WS update
        CHECK_INTERVAL = 30  # how often to check
        while True:
            time.sleep(CHECK_INTERVAL)
            try:
                age = synced_time() - self.last_ws_update
                if age > STALE_THRESHOLD and not self._ws_reconnecting:
                    with self._ws_lock:
                        if self._ws_reconnecting:
                            continue
                        self._ws_reconnecting = True
                    self.logger.warning(
                        f"WS monitor: no update for {age:.0f}s. Reconnecting WebSocket..."
                    )
                    self._reconnect_ws()
            except Exception as e:
                self.logger.error(f"WS health monitor error: {e}")

    def _reconnect_ws(self) -> None:
        """Closes existing WebSocket client and starts a fresh one."""
        try:
            try:
                self.ws_client.stop()
            except Exception:
                pass
            time.sleep(3)  # brief pause before reconnecting
            self.ws_client = UMFuturesWebsocketClient(
                on_message=self._on_ws_message,
                stream_url=self._ws_base_url,
            )
            self._start_kline_stream()
            self.last_ws_update = synced_time()
            self.logger.info("WebSocket reconnected successfully.")
        except Exception as e:
            self.logger.error(f"WebSocket reconnect failed: {e}")
        finally:
            self._ws_reconnecting = False

    def _on_ws_message(self, _, message) -> None:
        """Handles incoming WebSocket messages."""
        try:
            data = json.loads(message)

            if "e" in data and data["e"] == "kline":
                k = data["k"]

                new_row = {
                    "timestamp": pd.to_datetime(k["t"], unit="ms")
                    .tz_localize("UTC")
                    .tz_convert("Asia/Ho_Chi_Minh"),
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"]),
                }

                # FIX: guard buffer writes with _ws_lock so fetch_ohlcv
                # (main thread) never reads a partially-updated DataFrame.
                with self._ws_lock:
                    if self.klines_buffer is not None:
                        self.last_ws_update = synced_time()
                        last_ts = self.klines_buffer["timestamp"].iloc[-1]
                        if new_row["timestamp"] == last_ts:
                            for col in ["open", "high", "low", "close", "volume"]:
                                self.klines_buffer.iloc[
                                    -1, self.klines_buffer.columns.get_loc(col)
                                ] = new_row[col]
                        elif new_row["timestamp"] > last_ts:
                            self.klines_buffer = pd.concat(
                                [self.klines_buffer, pd.DataFrame([new_row])],
                                ignore_index=True,
                            )
                            if len(self.klines_buffer) > 500:
                                self.klines_buffer = self.klines_buffer.iloc[
                                    -500:
                                ].reset_index(drop=True)
        except Exception as e:
            self.logger.error(f"Error handling WS message: {e}")

    def sync_time(self) -> None:
        """Calculates the offset between local time and Binance server time."""
        global _GLOBAL_TIME_OFFSET
        try:
            # We must use the original time to calculate the true drift
            actual_local_ms = int(_original_time() * 1000)
            res = self.client.time()
            server_time = int(res["serverTime"])

            # Compensation: ServerTime - LocalTime
            diff_ms = server_time - actual_local_ms
            _GLOBAL_TIME_OFFSET = diff_ms / 1000.0

            self.logger.info(
                f"Time synced with Binance server. Offset: {diff_ms}ms (Manual Correction: {_GLOBAL_TIME_OFFSET:.3f}s)"
            )

            if diff_ms < -500:
                self.logger.warning(
                    f"Local clock is AHEAD of server by {abs(diff_ms)}ms. Fixed."
                )
        except Exception as e:
            self.logger.error(f"Failed to sync time with Binance: {e}")

    def get_symbol_info(self) -> None:
        """Fetches quantity and price precision for the current symbol."""
        try:
            info = self.client.exchange_info()
            for s in info["symbols"]:
                if s["symbol"] == self.symbol:
                    self.qty_precision = int(s["quantityPrecision"])
                    self.price_precision = int(s["pricePrecision"])
                    self.logger.info(
                        f"Symbol Info for {self.symbol}: Qty Precision: {self.qty_precision}, Price Precision: {self.price_precision}"
                    )
                    return
            self.logger.warning(
                f"Could not find symbol info for {self.symbol}. Using defaults (Qty: {self.qty_precision}, Price: {self.price_precision})"
            )
        except Exception as e:
            self.logger.error(f"Error fetching symbol info: {e}")

    def fetch_ohlcv(
        self, limit: int = 100, timeframe: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Returns kline data. Priority: WebSocket buffer.
        Fallback: REST API (only if buffer is empty or stale).
        """
        tf = timeframe or settings.TIMEFRAME
        is_default_tf = tf == settings.TIMEFRAME

        # FIX: acquire lock before reading buffer — prevents reading a
        # partially-updated DataFrame while _on_ws_message is writing.
        if is_default_tf:
            with self._ws_lock:
                if self.klines_buffer is not None and not self.klines_buffer.empty:
                    now_ts = synced_time()
                    if (now_ts - self.last_ws_update) < 120:
                        return self.klines_buffer.tail(limit).copy()
                    else:
                        self.logger.warning(
                            f"WebSocket buffer stale "
                            f"({now_ts - self.last_ws_update:.1f}s). Falling back to REST..."
                        )

        # --- REST FALLBACK / INITIAL POPULATION ---
        try:
            bars = self._klines_with_retry(self.symbol, tf, limit)

            if not bars:
                return None

            df = pd.DataFrame(
                bars,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_asset_volume",
                    "number_of_trades",
                    "taker_buy_base_asset_volume",
                    "taker_buy_quote_asset_volume",
                    "ignore",
                ],
            )

            # Convert to numeric
            cols_to_numeric = ["open", "high", "low", "close", "volume"]
            df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)

            # Convert timestamp
            df["timestamp"] = (
                pd.to_datetime(df["timestamp"], unit="ms")
                .dt.tz_localize("UTC")
                .dt.tz_convert("Asia/Ho_Chi_Minh")
            )

            # Seed buffer only if it's the default timeframe
            if is_default_tf and self.klines_buffer is None:
                self.klines_buffer = df[
                    ["timestamp", "open", "high", "low", "close", "volume"]
                ].copy()

            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            self.logger.error(
                f"Error fetching data via REST for {settings.SYMBOL}: {e}"
            )
            return None

    def fetch_history(self, limit: int = 1000) -> Optional[pd.DataFrame]:
        return self.fetch_ohlcv(limit=limit)

    def create_order(self, side: str, amount: float) -> Optional[Dict[str, Any]]:
        try:
            side = side.upper()

            order = self._new_order_with_retry(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=round(amount, self.qty_precision),
                recvWindow=10000,
            )

            if order:
                self.logger.info(
                    f"Market Order Successful: {side} {amount} {self.symbol} - ID: {order.get('orderId')}"
                )
            return order
        except Exception as e:
            self.logger.error(f"Error creating market order: {e}")
            return None

    def cancel_all_orders(self) -> bool:
        """Cancels all open orders (like old Stop Losses) for the symbol."""
        try:
            self.client.cancel_open_orders(symbol=self.symbol, recvWindow=10000)
            self.logger.info(f"Canceled all open orders for {self.symbol}")
            return True
        except Exception as e:
            self.logger.warning(f"Could not cancel open orders: {e}")
            return False

    def get_balance(self) -> Optional[float]:
        try:
            account_info = self._account_with_retry(recvWindow=10000)

            for asset in account_info["assets"]:
                if asset["asset"] == "USDT":
                    return float(asset["walletBalance"])
            return None  # Return None to indicate failure
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return None

    def get_current_position(self) -> Tuple[float, float]:
        """
        Returns:
            Tuple[float, float]: (Current Position Amount, Entry Price)
        """
        try:
            # Using get_position_risk is faster and more specific than account()
            positions = self._get_position_risk_with_retry(
                symbol=self.symbol, recvWindow=10000
            )

            for pos in positions:
                if pos["symbol"] == self.symbol:
                    return float(pos["positionAmt"]), float(pos.get("entryPrice", 0))
            return 0.0, 0.0
        except Exception as e:
            self.logger.error(f"Error fetching position: {e}")
            return 0.0, 0.0

    def close_all_positions(self) -> bool:
        """Closes all positions for the current symbol by placing an offsetting market order."""
        try:
            # Get positions using get_position_risk (more efficient)
            positions = self._get_position_risk_with_retry(
                symbol=self.symbol, recvWindow=10000
            )

            for pos in positions:
                if pos["symbol"] == self.symbol:
                    amt = float(pos["positionAmt"])
                    if amt != 0:
                        side = "SELL" if amt > 0 else "BUY"
                        # 1. Cancel any existing SL orders first
                        self.cancel_all_orders()

                        # 2. Place Market Order to close
                        order = self.client.new_order(
                            symbol=self.symbol,
                            side=side,
                            type="MARKET",
                            quantity=round(abs(amt), self.qty_precision),
                            recvWindow=10000,
                        )
                        self.logger.info(
                            f"Closed position for {self.symbol}. Amount: {amt} - Order ID: {order.get('orderId')}"
                        )
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            return False

    def get_yesterday_stats(self) -> Tuple[float, int, float]:
        """
        Fetches realized PnL, number of trades, and total commission fees
        for the previous calendar day (Vietnam timezone, UTC+7).

        Returns:
            Tuple[float, int, float]: (Total PnL, Trade Count, Total Fee)
        """
        try:
            # FIX: use explicit VN timezone — naive datetime.now() would produce
            # wrong midnight boundaries if the server runs in a different TZ.
            from datetime import timezone, timedelta as _td

            VN_TZ = timezone(_td(hours=7))

            now = datetime.now(VN_TZ)
            yesterday = now - timedelta(days=1)
            start_time = int(
                yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                * 1000
            )
            end_time = int(
                yesterday.replace(
                    hour=23, minute=59, second=59, microsecond=999000
                ).timestamp()
                * 1000
            )

            self.logger.info(
                f"Fetching stats for {yesterday.date()} VN time "
                f"({start_time} → {end_time})"
            )

            pnl_history = self._get_income_history_with_retry(
                symbol=self.symbol,
                incomeType="REALIZED_PNL",
                startTime=start_time,
                endTime=end_time,
                limit=1000,
            )

            fee_history = self._get_income_history_with_retry(
                symbol=self.symbol,
                incomeType="COMMISSION",
                startTime=start_time,
                endTime=end_time,
                limit=1000,
            )

            total_pnl = (
                sum(float(i["income"]) for i in pnl_history) if pnl_history else 0.0
            )
            trade_count = len(pnl_history) if pnl_history else 0
            total_fee = (
                sum(float(i["income"]) for i in fee_history) if fee_history else 0.0
            )

            return total_pnl, trade_count, abs(total_fee)
        except Exception as e:
            self.logger.error(f"Error fetching yesterday's stats: {e}")
            return 0.0, 0, 0.0

    # Wrapper methods to apply decorator
    @retry_on_timestamp_error
    def _get_income_history_with_retry(self, **kwargs):
        return self.client.get_income_history(**kwargs)

    @retry_on_timestamp_error
    def _change_leverage_with_retry(self, symbol, leverage):
        return self.client.change_leverage(
            symbol=symbol, leverage=leverage, recvWindow=10000
        )

    @retry_on_timestamp_error
    def _klines_with_retry(self, symbol, interval, limit):
        return self.client.klines(symbol, interval=interval, limit=limit)

    @retry_on_timestamp_error
    def _new_order_with_retry(self, **kwargs):
        return self.client.new_order(**kwargs)

    @retry_on_timestamp_error
    def _account_with_retry(self, **kwargs):
        return self.client.account(**kwargs)

    @retry_on_timestamp_error
    def _get_position_risk_with_retry(self, **kwargs):
        return self.client.get_position_risk(**kwargs)
