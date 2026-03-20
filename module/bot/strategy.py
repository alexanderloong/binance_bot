import time
import os
import json
from datetime import datetime, timedelta
import logging
from typing import Optional, Any, List
import pandas as pd

from config import settings
from module.bot.notifier import Notifier
from .data_processor import DataProcessor
from .utils import parse_timeframe_to_seconds
from .core_strategy import evaluate_signal

class Strategy:
    def __init__(self, exchange_client: Any, logger: Any, notifier: Optional[Notifier] = None):
        self.client = exchange_client
        self.logger = logger
        self.notifier = notifier
        self.in_position: bool = False 
        self.last_candle_time: Optional[int] = None
        self.trade_history: List[float] = [] # For rate limiting
        self.stop_loss_price: Optional[float] = None
        
        self.entry_price: Optional[float] = None
        self.breakeven_activated: bool = False
        
        # Parse timeframe for stale candle checking
        self.tf_seconds: int = parse_timeframe_to_seconds(settings.TIMEFRAME)
        self._load_state()

    def _state_file(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

    def _load_state(self):
        try:
            if os.path.exists(self._state_file()):
                with open(self._state_file(), 'r') as f:
                    data = json.load(f)
                    self.stop_loss_price = data.get("stop_loss_price")
                    self.entry_price = data.get("entry_price")
                    self.breakeven_activated = data.get("breakeven_activated", False)
                    self.logger.info(f"Loaded persistent state: SL={self.stop_loss_price}, Entry={self.entry_price}, BE={self.breakeven_activated}")
        except Exception as e:
            self.logger.error(f"Error loading state: {e}")

    def _save_state(self):
        try:
            data = {
                "stop_loss_price": self.stop_loss_price,
                "entry_price": self.entry_price,
                "breakeven_activated": self.breakeven_activated
            }
            with open(self._state_file(), 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

    def check_rate_limit(self) -> bool:
        current_time = time.time()
        # Keep only trades within last hour (3600 seconds)
        self.trade_history = [t for t in self.trade_history if current_time - t < 3600]
        
        if len(self.trade_history) >= settings.MAX_TRADES_PER_HOUR:
            self.logger.warning(f"RATE LIMIT REACHED: {len(self.trade_history)} trades in last hour. Max is {settings.MAX_TRADES_PER_HOUR}. Skipping trade.")
            return False
        return True

    def run_analysis(self) -> bool:
        """
        Main analysis loop called every cycle.
        Returns False if no action was taken or data was valid but no trade.
        """
        df = self.client.fetch_ohlcv(limit=300)
        
        if df is None or df.empty:
            self.logger.error("No data received from exchange.")
            return False
            
        current_pos_amt, entry_price_api = self.client.get_current_position()
        if current_pos_amt == 0:
            self.entry_price = None
            self.stop_loss_price = None
            self.breakeven_activated = False
        elif self.entry_price is None:
            self.entry_price = entry_price_api
            
        if current_pos_amt != 0:
             self._manage_open_position(df, current_pos_amt, self.entry_price)
             if self.stop_loss_price is None and current_pos_amt != 0: 
                 pass

        delay_seconds = self._check_new_candle(df)
        if delay_seconds is None:
            return False

        df_final = DataProcessor.prepare_all_indicators(df)
        
        # HTF Data
        df_htf = self.client.fetch_ohlcv(limit=100, timeframe=settings.HTF_TIMEFRAME)
        if df_htf is not None and not df_htf.empty:
            df_htf_ha = DataProcessor.calculate_heikin_ashi(df_htf)
            df_htf_st = DataProcessor.calculate_supertrend(df_htf_ha)
            st_col = f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
            htf_trend_val = df_htf_st[st_col].iloc[-2]
            df_final.loc[df_final.index[-2], 'HTF_TREND'] = htf_trend_val
            
        self._analyze_market_and_trade(df_final, current_pos_amt, self.entry_price, delay_seconds)
        return True

    def _manage_open_position(self, df: pd.DataFrame, current_pos_amt: float, entry_price: float) -> None:
        """
        Handles Stop Loss, Breakeven, and basic position logic.
        """
        current_price = df['close'].iloc[-1]
        
        if self.stop_loss_price is None:
            df_ha = DataProcessor.calculate_heikin_ashi(df)
            atr_val = DataProcessor.calculate_atr(df_ha, settings.ATR_LENGTH).iloc[-2]
            
            if current_pos_amt > 0:
                self.stop_loss_price = entry_price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                self.stop_loss_price = entry_price + (atr_val * settings.ATR_MULTIPLIER)
            self.logger.info(f"Reconstructed SOFTWARE STOP LOSS at {self.stop_loss_price:.2f} (Entry: {entry_price:.2f})")
            self._save_state()

        # Breakeven Check
        if not self.breakeven_activated and entry_price is not None:
            breakeven_multiplier = getattr(settings, 'BREAKEVEN_MULTIPLIER', 2.0)
            if current_pos_amt > 0:
                breakeven_target = entry_price + (entry_price - self.stop_loss_price) * breakeven_multiplier
                if current_price >= breakeven_target:
                    self.stop_loss_price = entry_price * (1 + settings.TAKER_FEE_RATE * 2)
                    self.breakeven_activated = True
                    self.logger.info(f"LONG BREAKEVEN HIT at {current_price}. SL moved to {self.stop_loss_price}")
                    self._save_state()
            else:
                breakeven_target = entry_price - (self.stop_loss_price - entry_price) * breakeven_multiplier
                if current_price <= breakeven_target:
                    self.stop_loss_price = entry_price * (1 - settings.TAKER_FEE_RATE * 2)
                    self.breakeven_activated = True
                    self.logger.info(f"SHORT BREAKEVEN HIT at {current_price}. SL moved to {self.stop_loss_price}")
                    self._save_state()

        is_sl_hit = (current_pos_amt > 0 and current_price <= self.stop_loss_price) or \
                    (current_pos_amt < 0 and current_price >= self.stop_loss_price)
        
        if is_sl_hit:
            self.logger.warning(f"SOFTWARE STOP LOSS/BREAKEVEN HIT at {current_price:.2f} (Target: {self.stop_loss_price:.2f}). Closing position.")
            
            if self.notifier:
                est_fee = (entry_price + current_price) * abs(current_pos_amt) * settings.TAKER_FEE_RATE
                pnl = 0.0
                roi = 0.0
                if current_pos_amt > 0:
                    raw_pnl = (current_price - entry_price) * abs(current_pos_amt)
                    pnl = raw_pnl - est_fee
                    roi = (current_price - entry_price) / entry_price * settings.LEVERAGE * 100
                else:
                    raw_pnl = (entry_price - current_price) * abs(current_pos_amt)
                    pnl = raw_pnl - est_fee
                    roi = (entry_price - current_price) / entry_price * settings.LEVERAGE * 100

                self.notifier.send_lark_message(
                    f"⚠️ **SL/BREAKEVEN HIT**\n"
                    f"Current Price: {current_price:.2f}\n"
                    f"Target SL: {self.stop_loss_price:.2f}\n"
                    f"PNL: {pnl:.2f} USDT\n"
                    f"ROI: {roi:.2f}%\n"
                    f"Closing position."
                )
            self.close_all_positions()
            self.stop_loss_price = None
            self.entry_price = None
            self.breakeven_activated = False
            self._save_state()
            return



    def _check_new_candle(self, df: pd.DataFrame) -> Optional[float]:
        """
        Checks if the latest data represents a new, valid candle to process.
        Returns:
            Optional[float]: Delay in seconds if valid new candle, None if should skip.
        """
        try:
            # Get timestamp of the last CLOSED candle (second to last row)
            last_closed_candle = df.iloc[-2]
            last_closed_time = last_closed_candle['timestamp'] 
            last_closed_ts_val = int(last_closed_time.timestamp()) 
            
            # 1. If we already processed this EXACT candle, skip
            if self.last_candle_time is not None and self.last_candle_time == last_closed_ts_val:
                return None
                
            # 2. If we see a candle that is OLDER than our last processed one (API Flicker), skip
            if self.last_candle_time is not None and last_closed_ts_val < self.last_candle_time:
                return None

            # Calculate Latency/Delay
            candle_close_time = last_closed_time + timedelta(seconds=self.tf_seconds)
            now = datetime.now(last_closed_time.tzinfo)
            delay_seconds = (now - candle_close_time).total_seconds()
            
            # 3. SUCCESS: It's a fresh, new candle.
            self.last_candle_time = last_closed_ts_val
            self.logger.info(f"Processing new candle: {last_closed_time} (Latency: {delay_seconds:.1f}s)")
            return delay_seconds
            
        except Exception as e:
            self.logger.error(f"Error checking candle timestamp: {e}")
            return None

    def _analyze_market_and_trade(self, df_final: pd.DataFrame, current_pos_amt: float, entry_price: float, delay_seconds: float) -> None:
        last_candle = df_final.iloc[-2]
        candle_time = last_candle['timestamp'].strftime('%d-%m-%Y %H:%M:%S')
        atr_val = last_candle.get('ATR', 0)
        close_price = last_candle['close']

        # Log market state for debugging
        adx_val = last_candle.get('ADX', 0)
        atr_val = last_candle.get('ATR', 0)
        rsi_val = last_candle.get('RSI', 50)
        ema_val = last_candle.get(f'EMA_{settings.EMA_LENGTH}', 0)
        vol_ma_col = f'VOL_MA_{settings.VOLUME_MA_LENGTH}'
        vol_ma_val = last_candle.get(vol_ma_col, 0)
        current_volume = last_candle.get('volume', 0)
        st_dir_col = f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
        current_trend = last_candle[st_dir_col]
        ema_slope_length = getattr(settings, 'EMA_SLOPE_EMA_LENGTH', settings.EMA_LENGTH)
        ema_slope_lookback = getattr(settings, 'EMA_SLOPE_LOOKBACK', 3)
        ema_slope_threshold = getattr(settings, 'EMA_SLOPE_THRESHOLD', 0.001)
        ema_slope_val = last_candle.get(f'EMA_{ema_slope_length}', ema_val)
        ema_slope_prev = df_final.iloc[-(ema_slope_lookback + 2)].get(f'EMA_{ema_slope_length}', ema_val)
        ema_slope_pct = (ema_slope_val - ema_slope_prev) / ema_slope_prev if ema_slope_prev != 0 else 0

        self.logger.info(
            f"Market Data: {candle_time} | Close: {close_price} | Trend: {current_trend} | "
            f"EMA{settings.EMA_LENGTH}: {ema_val:.2f} | ADX: {adx_val:.2f} | ATR: {atr_val:.2f} | "
            f"RSI: {rsi_val:.2f} | Vol: {current_volume:.0f} (MA: {vol_ma_val:.0f}) | "
            f"EMA{ema_slope_length} Slope: {ema_slope_pct*100:.3f}% ({'FLAT' if abs(ema_slope_pct) < ema_slope_threshold else 'STEEP'})"
        )

        # --- STALENESS CHECK ---
        STALE_TOLERANCE = 120
        if delay_seconds > STALE_TOLERANCE:
            self.logger.warning(f"Candle {candle_time} is STALE (Closed {int(delay_seconds)}s ago). Skipping trade logic.")
            return

        # --- UNIFIED SIGNAL EVALUATION ---
        signal, actual_pos_size, reason = evaluate_signal(df_final, current_pos_amt)
        self.logger.info(f"Signal evaluation: {reason}")

        if signal in ('CLOSE_LONG', 'CLOSE_SHORT'):
            direction = "LONG" if signal == 'CLOSE_LONG' else "SHORT"
            self.logger.info(f"Trend flip signal. Closing {direction} position ({current_pos_amt}).")
            self.close_all_positions()

        elif signal in ('LONG', 'SHORT'):
            self.logger.info(f"SIGNAL DETECTED: {signal} | Pos size: {actual_pos_size*100:.1f}%")
            if actual_pos_size < settings.POSITION_SIZE_PERCENT:
                self.logger.info(f"⚠️ EMA slope FLAT. Reducing size to {actual_pos_size*100:.1f}%.")
            self.open_position(signal, close_price, atr_val, pos_size_pct=actual_pos_size)

        else:
            self.logger.info(f"No actionable signal for {candle_time}. Position: {current_pos_amt}")

    def close_all_positions(self) -> None:
        self.logger.info("Closing all positions... fetching PnL/ROI for notification.")
        
        # Try to get position details before closing for the notification
        pnl_str = ""
        try:
            amt, entry = self.client.get_current_position()
            if amt != 0:
                 # Fetch current price for estimate
                 df = self.client.fetch_ohlcv(limit=1)
                 if df is not None and not df.empty:
                    curr_price = df['close'].iloc[-1]
                    est_fee = (entry + curr_price) * abs(amt) * settings.TAKER_FEE_RATE
                    if amt > 0:
                        roi = (curr_price - entry) / entry * settings.LEVERAGE * 100
                        raw_pnl = (curr_price - entry) * abs(amt)
                    else:
                        roi = (entry - curr_price) / entry * settings.LEVERAGE * 100
                        raw_pnl = (entry - curr_price) * abs(amt)
                    pnl = raw_pnl - est_fee
                    pnl_str = f"\nPNL: {pnl:.2f} USDT\nROI: {roi:.2f}%"
        except:
            pass

        if self.client.close_all_positions():
            self.in_position = False
            self.stop_loss_price = None
            self.entry_price = None
            self.breakeven_activated = False
            self._save_state()

    def partial_close_position(self, quantity: float, side: str) -> None:
        self.logger.info(f"Partially closing {quantity:.4f} ({side})...")
        try:
             order = self.client.create_order(side, quantity)
             if order:
                 self.logger.info("Partial close successful.")
                 if self.notifier:
                     self.notifier.send_lark_message(f"✂️ **Partial Close Successful**\nSide: {side}\nQuantity: {quantity:.4f}")
        except Exception as e:
             self.logger.error(f"Failed to partial close: {e}")

    def open_position(self, side: str, price: float, atr_val: float, pos_size_pct: float = settings.POSITION_SIZE_PERCENT) -> None:
        
        # Safety Check: Rate Limit
        if not self.check_rate_limit():
            return

        # Calculate amount based on % balance
        try:
            balance = self.client.get_balance()
            if balance is None:
                self.logger.error("Could not fetch balance. Aborting position opening.")
                return

            # Calculate trade amount using leverage
            amount_usdt = balance * pos_size_pct * settings.LEVERAGE
            trade_amount = amount_usdt / price
            
            self.logger.info(f"Opening {side} position at {price} (Size: {pos_size_pct*100}% of Balance: {balance} USDT, Leverage: {settings.LEVERAGE}x -> {trade_amount:.4f} BTC)")
            
            if side == 'LONG':
                 self.stop_loss_price = price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                 self.stop_loss_price = price + (atr_val * settings.ATR_MULTIPLIER)
            
            self.logger.info(f"Setting SOFTWARE SL: {self.stop_loss_price:.2f} (ATR: {atr_val:.2f})")
            # -------------------------------------

            # Open Market Order (Long or Short)
            order_resp = self.client.create_order('buy' if side == 'LONG' else 'sell', trade_amount)
            
            if order_resp:
                self.in_position = True
                self.entry_price = price
                self.breakeven_activated = False
                self.trade_history.append(time.time())
                self._save_state()
                if self.notifier:
                    self.notifier.send_lark_message(
                        f"✅ **Position Opened ({side})**\n"
                        f"Entry Price: {price:.2f}\n"
                        f"Amount: {trade_amount:.4f} BTC ({amount_usdt:.2f} USDT)\n"
                        f"Stop Loss: {self.stop_loss_price:.2f}\n"
                        f"Leverage: {settings.LEVERAGE}x"
                    )
            
        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")

    def send_daily_report(self) -> None:
        """Sends a summary report of yesterday's performance."""
        try:
            total_pnl, trade_count, total_fee = self.client.get_yesterday_stats()
            balance = self.client.get_balance()
            
            net_pnl = total_pnl - total_fee
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%d-%m-%Y')
            
            pnl_emoji = "🟢" if net_pnl >= 0 else "🔴"
            pnl_sign = "+" if net_pnl >= 0 else ""
            gross_sign = "+" if total_pnl >= 0 else ""
            roi_pct = (net_pnl / balance * 100) if balance else 0
            roi_sign = "+" if roi_pct >= 0 else ""

            message = (
                f"📊 **DAILY PERFORMANCE REPORT ({yesterday})**\n"
                f"--------------------------------\n"
                f"{pnl_emoji} Net PNL: {pnl_sign}{net_pnl:.2f} USDT ({roi_sign}{roi_pct:.2f}%)\n"
                f"   (Gross: {gross_sign}{total_pnl:.2f} USDT | Fee: -{total_fee:.2f} USDT)\n"
                f"📈 Positions Closed: {trade_count}\n"
                f"🏦 Current Balance: {balance:.2f} USDT\n"
            )
            
            self.logger.info(f"Sending daily report: Net PNL {net_pnl:.2f}, Trades {trade_count}")
            if self.notifier:
                self.notifier.send_lark_message(message)
                
        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
