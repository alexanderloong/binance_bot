import time
import logging
from typing import Optional, Tuple, Dict, Any, List

import pandas as pd
from binance.um_futures import UMFutures
from config import settings

# --- GLOBAL TIME SYNC ---
_GLOBAL_TIME_OFFSET = 0.0
_original_time = time.time

def synced_time() -> float:
    return _original_time() + _GLOBAL_TIME_OFFSET

# Global monkey-patch
time.time = synced_time

class ExchangeClient:
    def __init__(self) -> None:
        self.logger = logging.getLogger("BinanceBot")
        
        # Determine base URL
        base_url = "https://fapi.binance.com"
        if settings.USE_TESTNET:
            base_url = "https://testnet.binancefuture.com"
            
        self.client = UMFutures(key=settings.API_KEY, secret=settings.SECRET, base_url=base_url)
        
        # Prepare symbol
        self.symbol: str = settings.SYMBOL.replace("/", "").upper()
        
        # Symbol information (precision)
        self.qty_precision: int = 3 # Default for BTCUSDT safety
        self.price_precision: int = 2
        self.get_symbol_info()
        
        # Verify connection
        try:
            # 1. Test connectivity (Ping)
            self.client.ping()
            self.logger.info("Connection to Binance API established.")
            
            # 2. Try to set leverage
            # 2. Try to set leverage
            try:
                self.client.change_leverage(
                    symbol=self.symbol, 
                    leverage=settings.LEVERAGE, 
                    recvWindow=10000
                )
                self.logger.info(f"Leverage set to {settings.LEVERAGE}x for {self.symbol}")
            except Exception as lev_e:
                if "-1021" in str(lev_e):
                    self.logger.warning("Timestamp error (-1021) on leverage set. Syncing time and retrying...")
                    self.sync_time()
                    try:
                        self.client.change_leverage(
                            symbol=self.symbol, 
                            leverage=settings.LEVERAGE, 
                            recvWindow=10000
                        )
                        self.logger.info(f"Leverage set to {settings.LEVERAGE}x for {self.symbol}")
                    except Exception as lev_e_retry:
                         self.logger.warning(f"Note: Could not set leverage after sync (might be already set or other error): {lev_e_retry}")
                else:
                    self.logger.warning(f"Note: Could not set leverage (might be already set): {lev_e}")
            
            # 3. Check Balance
            balance = self.get_balance()
            self.logger.info(f"Successfully authenticated. Current Wallet Balance: {balance} USDT")
            
        except Exception as e:
            self.logger.error(f"Critical connection error: {e}")

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
        try:
            try:
                bars = self.client.klines(self.symbol, interval=settings.TIMEFRAME, limit=limit)
            except Exception as e:
                # -1021 is "Timestamp for this request is outside of the recvWindow"
                if "-1021" in str(e):
                    self.sync_time()
                    bars = self.client.klines(self.symbol, interval=settings.TIMEFRAME, limit=limit)
                else: raise e
            
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
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            self.logger.error(f"Error fetching data for {settings.SYMBOL}: {e}")
            return None

    def fetch_history(self, limit: int = 1000) -> Optional[pd.DataFrame]:
        return self.fetch_ohlcv(limit=limit)

    def create_order(self, side: str, amount: float) -> Optional[Dict[str, Any]]:
        try:
            side = side.upper()
            
            try:
                order = self.client.new_order(
                    symbol=self.symbol,
                    side=side,
                    type='MARKET',
                    quantity=round(amount, self.qty_precision),
                    recvWindow=10000
                )
            except Exception as e:
                if "-1021" in str(e):
                    self.logger.warning("Timestamp error (-1021) on order. Retrying with re-sync...")
                    self.sync_time()
                    order = self.client.new_order(
                        symbol=self.symbol,
                        side=side,
                        type='MARKET',
                        quantity=round(amount, self.qty_precision),
                        recvWindow=10000
                    )
                else:
                    raise e

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
            try:
                account_info = self.client.account(recvWindow=10000)
            except Exception as e:
                if "-1021" in str(e):
                    self.logger.warning("Timestamp error (-1021) on balance. Retrying with re-sync...")
                    self.sync_time()
                    account_info = self.client.account(recvWindow=10000)
                else:
                    raise e

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
            try:
                positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
            except Exception as e:
                if "-1021" in str(e):
                    self.logger.warning("Timestamp error (-1021). Retrying with re-sync...")
                    self.sync_time()
                    positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
                else:
                    raise e
                    
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
            try:
                positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
            except Exception as e:
                 # Auto retry once on timestamp error
                 if "-1021" in str(e):
                     self.sync_time()
                     positions = self.client.get_position_risk(symbol=self.symbol, recvWindow=10000)
                 else:
                     raise e

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
