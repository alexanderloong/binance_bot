import time
import logging
from typing import Optional, Tuple, Dict, Any, List

import json
import pandas as pd
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from config import settings

# --- GLOBAL TIME SYNC ---
_GLOBAL_TIME_OFFSET = 0.0
_original_time = time.time

def synced_time() -> float:
    return _original_time() + _GLOBAL_TIME_OFFSET

# Global monkey-patch
time.time = synced_time

from functools import wraps

def retry_on_timestamp_error(func):
    """Decorator to retry on -1021 timestamp error after time sync."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            if "-1021" in str(e):
                self.logger.warning(f"Timestamp error (-1021) in {func.__name__}. Syncing time and retrying...")
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
            
        self.client = UMFutures(key=settings.API_KEY, secret=settings.SECRET, base_url=base_url)
        
        # Prepare symbol
        self.symbol: str = settings.SYMBOL.replace("/", "").upper()
        
        # --- WEBSOCKET STATE ---
        self.klines_buffer: Optional[pd.DataFrame] = None
        self.last_ws_update: float = synced_time()
        self.ws_client = UMFuturesWebsocketClient(on_message=self._on_ws_message, stream_url=ws_base_url)
        self._start_kline_stream()
        
        # Symbol information (precision)
        self.qty_precision: int = 3 # Default for BTCUSDT safety
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
                self.logger.info(f"Leverage set to {settings.LEVERAGE}x for {self.symbol}")
            except Exception as lev_e:
                self.logger.warning(f"Note: Could not set leverage (might be already set or other error): {lev_e}")
            
            # 3. Check Balance
            balance = self.get_balance()
            self.logger.info(f"Successfully authenticated. Current Wallet Balance: {balance} USDT")
            
        except Exception as e:
            self.logger.error(f"Critical connection error: {e}")

    def _start_kline_stream(self) -> None:
        """Starts the WebSocket kline stream."""
        kline_stream = f"{self.symbol.lower()}@kline_{settings.TIMEFRAME}"
        self.ws_client.subscribe(stream=kline_stream, id=1)
        self.logger.info(f"Subscribed to WebSocket stream: {kline_stream}")

    def _on_ws_message(self, _, message) -> None:
        """Handles incoming WebSocket messages."""
        try:
            data = json.loads(message)
            
            # Handle kline event
            if 'e' in data and data['e'] == 'kline':
                k = data['k']
                is_candle_closed = k['x']
                
                # New candle data row
                new_row = {
                    'timestamp': pd.to_datetime(k['t'], unit='ms').tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh'),
                    'open': float(k['o']),
                    'high': float(k['h']),
                    'low': float(k['l']),
                    'close': float(k['c']),
                    'volume': float(k['v'])
                }

                if self.klines_buffer is not None:
                    self.last_ws_update = synced_time()
                    # Update or append
                    # If the timestamp matches the last row, update it (current unfinished candle)
                    # If it's newer, append and trim
                    last_ts = self.klines_buffer['timestamp'].iloc[-1]
                    if new_row['timestamp'] == last_ts:
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            self.klines_buffer.iloc[-1, self.klines_buffer.columns.get_loc(col)] = new_row[col]
                    elif new_row['timestamp'] > last_ts:
                        # Append new candle
                        self.klines_buffer = pd.concat([self.klines_buffer, pd.DataFrame([new_row])], ignore_index=True)
                        # Keep only last 500 to be safe
                        if len(self.klines_buffer) > 500:
                            self.klines_buffer = self.klines_buffer.iloc[-500:].reset_index(drop=True)
        except Exception as e:
            self.logger.error(f"Error handling WS message: {e}")

    def sync_time(self) -> None:
        """Calculates the offset between local time and Binance server time."""
        global _GLOBAL_TIME_OFFSET
        try:
            # We must use the original time to calculate the true drift
            actual_local_ms = int(_original_time() * 1000)
            res = self.client.time()
            server_time = int(res['serverTime'])
            
            # Compensation: ServerTime - LocalTime
            diff_ms = server_time - actual_local_ms
            _GLOBAL_TIME_OFFSET = diff_ms / 1000.0
            
            self.logger.info(f"Time synced with Binance server. Offset: {diff_ms}ms (Manual Correction: {_GLOBAL_TIME_OFFSET:.3f}s)")
            
            if diff_ms < -500:
                self.logger.warning(f"Local clock is AHEAD of server by {abs(diff_ms)}ms. Fixed.")
        except Exception as e:
            self.logger.error(f"Failed to sync time with Binance: {e}")

    def get_symbol_info(self) -> None:
        """Fetches quantity and price precision for the current symbol."""
        try:
            info = self.client.exchange_info()
            for s in info['symbols']:
                if s['symbol'] == self.symbol:
                    self.qty_precision = int(s['quantityPrecision'])
                    self.price_precision = int(s['pricePrecision'])
                    self.logger.info(f"Symbol Info for {self.symbol}: Qty Precision: {self.qty_precision}, Price Precision: {self.price_precision}")
                    return
            self.logger.warning(f"Could not find symbol info for {self.symbol}. Using defaults (Qty: {self.qty_precision}, Price: {self.price_precision})")
        except Exception as e:
            self.logger.error(f"Error fetching symbol info: {e}")

    def fetch_ohlcv(self, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Returns kline data. Priority: WebSocket buffer. 
        Fallback: REST API (only if buffer is empty or stale).
        """
        # If we have a buffer and it's somewhat fresh, return it
        if self.klines_buffer is not None and not self.klines_buffer.empty:
            # Check if the buffer is too old (e.g., > 120s silence from WS)
            now_ts = synced_time()
            
            if (now_ts - self.last_ws_update) < 120: # 120s tolerance for WS silence
                return self.klines_buffer.tail(limit).copy()
            else:
                self.logger.warning(f"WebSocket buffer stale (last update {now_ts - self.last_ws_update:.1f}s ago). Falling back to REST API...")

        # --- REST FALLBACK / INITIAL POPULATION ---
        try:
            bars = self._klines_with_retry(self.symbol, settings.TIMEFRAME, limit)
            
            if not bars:
                return None
                
            df = pd.DataFrame(bars, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            cols_to_numeric = ['open', 'high', 'low', 'close', 'volume']
            df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)
                
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Ho_Chi_Minh')
            
            # Seed buffer
            if self.klines_buffer is None:
                self.klines_buffer = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
                
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            self.logger.error(f"Error fetching data via REST for {settings.SYMBOL}: {e}")
            return None

    def fetch_history(self, limit: int = 1000) -> Optional[pd.DataFrame]:
        return self.fetch_ohlcv(limit=limit)

    def create_order(self, side: str, amount: float) -> Optional[Dict[str, Any]]:
        try:
            side = side.upper()
            
            order = self._new_order_with_retry(
                symbol=self.symbol,
                side=side,
                type='MARKET',
                quantity=round(amount, self.qty_precision),
                recvWindow=10000
            )

            if order:
                self.logger.info(f"Market Order Successful: {side} {amount} {self.symbol} - ID: {order.get('orderId')}")
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

            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            return None # Return None to indicate failure
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
            positions = self._get_position_risk_with_retry(symbol=self.symbol, recvWindow=10000)
                    
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    return float(pos['positionAmt']), float(pos.get('entryPrice', 0))
            return 0.0, 0.0
        except Exception as e:
            self.logger.error(f"Error fetching position: {e}")
            return 0.0, 0.0

    def close_all_positions(self) -> bool:
        """Closes all positions for the current symbol by placing an offsetting market order."""
        try:
            # Get positions using get_position_risk (more efficient)
            positions = self._get_position_risk_with_retry(symbol=self.symbol, recvWindow=10000)

            for pos in positions:
                if pos['symbol'] == self.symbol:
                    amt = float(pos['positionAmt'])
                    if amt != 0:
                        side = 'SELL' if amt > 0 else 'BUY'
                        # 1. Cancel any existing SL orders first
                        self.cancel_all_orders()
                        
                        # 2. Place Market Order to close
                        order = self.client.new_order(
                            symbol=self.symbol,
                            side=side,
                            type='MARKET',
                            quantity=round(abs(amt), self.qty_precision),
                            recvWindow=10000
                        )
                        self.logger.info(f"Closed position for {self.symbol}. Amount: {amt} - Order ID: {order.get('orderId')}")
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            return False
    def get_yesterday_stats(self) -> Tuple[float, int]:
        """
        Fetches realized PnL and number of trades for the previous calendar day.
        Returns:
            Tuple[float, int]: (Total PnL, Trade Count)
        """
        try:
            # Calculate yesterday's range (00:00:00 to 23:59:59)
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            start_time = int(yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
            end_time = int(yesterday.replace(hour=23, minute=59, second=59, microsecond=999).timestamp() * 1000)
            
            self.logger.info(f"Fetching stats from {yesterday.date()} ({start_time} to {end_time})")
            
            trades = self.client.get_account_trades(
                symbol=self.symbol,
                startTime=start_time,
                endTime=end_time,
                recvWindow=10000
            )
            
            total_pnl = 0.0
            unique_trades = set()
            
            if trades:
                for t in trades:
                    total_pnl += float(t.get('realizedPnl', 0))
                    # A "trade" in user context usually means a position entry. 
                    # We can approximate by looking at orders that increased position or just count unique orders.
                    # Given the request, counting unique orderIds that are not 'reduceOnly' or similar might be complex.
                    # We'll count unique orderIds for now as a proxy for "lệnh vào".
                    unique_trades.add(t['orderId'])
            
            return total_pnl, len(unique_trades)
        except Exception as e:
            self.logger.error(f"Error fetching yesterday's stats: {e}")
            return 0.0, 0

    # Wrapper methods to apply decorator
    @retry_on_timestamp_error
    def _change_leverage_with_retry(self, symbol, leverage):
        return self.client.change_leverage(symbol=symbol, leverage=leverage, recvWindow=10000)

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
