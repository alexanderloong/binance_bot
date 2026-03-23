import time
import os
import json
from datetime import datetime, timedelta
import logging
from typing import Optional, Any, List
import pandas as pd

from resource.config import settings
from module.bot.notifier import Notifier
from .data_processor import DataProcessor
from .utils import parse_timeframe_to_seconds
from .core_strategy import evaluate_signal
from .finance import (
    TradeResult,
    calc_breakeven_price,
    calc_trade_quantity,
)


class Strategy:
    def __init__(
        self, exchange_client: Any, logger: Any, notifier: Optional[Notifier] = None
    ):
        self.client = exchange_client
        self.logger = logger
        self.notifier = notifier
        self.in_position: bool = False
        self.last_candle_time: Optional[int] = None
        self.trade_history: List[float] = []
        self.stop_loss_price: Optional[float] = None
        self.entry_price: Optional[float] = None
        self.breakeven_activated: bool = False
        self.tf_seconds: int = parse_timeframe_to_seconds(settings.TIMEFRAME)
        self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _state_file(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "bot_state.json"
        )

    def _load_state(self):
        try:
            if os.path.exists(self._state_file()):
                with open(self._state_file(), "r") as f:
                    data = json.load(f)
                    self.stop_loss_price = data.get("stop_loss_price")
                    self.entry_price = data.get("entry_price")
                    self.breakeven_activated = data.get("breakeven_activated", False)
                    self.logger.info(
                        f"Loaded persistent state: SL={self.stop_loss_price}, "
                        f"Entry={self.entry_price}, BE={self.breakeven_activated}"
                    )
        except Exception as e:
            self.logger.error(f"Error loading state: {e}")

    def _save_state(self):
        try:
            data = {
                "stop_loss_price": self.stop_loss_price,
                "entry_price": self.entry_price,
                "breakeven_activated": self.breakeven_activated,
            }
            with open(self._state_file(), "w") as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def check_rate_limit(self) -> bool:
        current_time = time.time()
        self.trade_history = [t for t in self.trade_history if current_time - t < 3600]
        if len(self.trade_history) >= settings.MAX_TRADES_PER_HOUR:
            self.logger.warning(
                f"RATE LIMIT REACHED: {len(self.trade_history)} trades in last hour. "
                f"Max is {settings.MAX_TRADES_PER_HOUR}. Skipping trade."
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run_analysis(self) -> bool:
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

        delay_seconds = self._check_new_candle(df)
        if delay_seconds is None:
            return False

        df_final = DataProcessor.prepare_all_indicators(df)

        # HTF Data
        df_htf = self.client.fetch_ohlcv(limit=100, timeframe=settings.HTF_TIMEFRAME)
        if df_htf is not None and not df_htf.empty:
            df_htf_ha = DataProcessor.calculate_heikin_ashi(df_htf)
            df_htf_st = DataProcessor.calculate_supertrend(df_htf_ha)
            st_col = (
                f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
            )
            htf_trend_val = df_htf_st[st_col].iloc[-2]
            df_final.loc[df_final.index[-2], "HTF_TREND"] = htf_trend_val

        self._analyze_market_and_trade(
            df_final, current_pos_amt, self.entry_price, delay_seconds
        )
        return True

    # ------------------------------------------------------------------
    # Open position management
    # ------------------------------------------------------------------

    def _manage_open_position(
        self, df: pd.DataFrame, current_pos_amt: float, entry_price: float
    ) -> None:
        # Candle-close only: evaluate all position management decisions
        # against the close of the last COMPLETED candle (iloc[-2]).
        # iloc[-1] is the candle currently forming and must not be used.
        current_price = df["close"].iloc[-2]
        is_long = current_pos_amt > 0

        # Reconstruct SL if missing after bot restart
        if self.stop_loss_price is None:
            df_ha = DataProcessor.calculate_heikin_ashi(df)
            atr_val = DataProcessor.calculate_atr(df_ha, settings.ATR_LENGTH).iloc[-2]
            if is_long:
                self.stop_loss_price = entry_price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                self.stop_loss_price = entry_price + (atr_val * settings.ATR_MULTIPLIER)
            self.logger.info(
                f"Reconstructed SOFTWARE STOP LOSS at {self.stop_loss_price:.2f} "
                f"(Entry: {entry_price:.2f})"
            )
            self._save_state()

        # Breakeven check
        if not self.breakeven_activated and entry_price is not None:
            risk = abs(entry_price - self.stop_loss_price)
            if is_long:
                if current_price >= entry_price + risk * settings.BREAKEVEN_MULTIPLIER:
                    self.stop_loss_price = calc_breakeven_price(
                        entry_price, settings.TAKER_FEE_RATE, is_long=True
                    )
                    self.breakeven_activated = True
                    self.logger.info(
                        f"LONG BREAKEVEN HIT at {current_price}. "
                        f"SL → exact BE: {self.stop_loss_price:.4f}"
                    )
                    self._save_state()
            else:
                if current_price <= entry_price - risk * settings.BREAKEVEN_MULTIPLIER:
                    self.stop_loss_price = calc_breakeven_price(
                        entry_price, settings.TAKER_FEE_RATE, is_long=False
                    )
                    self.breakeven_activated = True
                    self.logger.info(
                        f"SHORT BREAKEVEN HIT at {current_price}. "
                        f"SL → exact BE: {self.stop_loss_price:.4f}"
                    )
                    self._save_state()

        # SL hit check
        sl_hit = (is_long and current_price <= self.stop_loss_price) or (
            not is_long and current_price >= self.stop_loss_price
        )
        if sl_hit:
            self.logger.warning(
                f"SL/BREAKEVEN HIT at {current_price:.2f} "
                f"(Target: {self.stop_loss_price:.2f}). Closing."
            )
            if self.notifier and entry_price is not None:
                result = TradeResult(
                    side="LONG" if is_long else "SHORT",
                    entry_price=entry_price,
                    exit_price=current_price,
                    quantity=abs(current_pos_amt),
                    leverage=settings.LEVERAGE,
                    fee_rate=settings.TAKER_FEE_RATE,
                )
                label = (
                    "BREAKEVEN EXIT" if self.breakeven_activated else "STOP LOSS HIT"
                )
                self.notifier.send_lark_message(
                    f"⚠️ **{label}**\nSL Target: {self.stop_loss_price:.2f}\n"
                    + result.format_summary()
                )
            self.close_all_positions()
            self.stop_loss_price = None
            self.entry_price = None
            self.breakeven_activated = False
            self._save_state()

    # ------------------------------------------------------------------
    # Candle deduplication
    # ------------------------------------------------------------------

    def _check_new_candle(self, df: pd.DataFrame) -> Optional[float]:
        try:
            last_closed_candle = df.iloc[-2]
            last_closed_time = last_closed_candle["timestamp"]
            last_closed_ts_val = int(last_closed_time.timestamp())

            if (
                self.last_candle_time is not None
                and self.last_candle_time == last_closed_ts_val
            ):
                return None
            if (
                self.last_candle_time is not None
                and last_closed_ts_val < self.last_candle_time
            ):
                return None

            candle_close_time = last_closed_time + timedelta(seconds=self.tf_seconds)
            now = datetime.now(last_closed_time.tzinfo)
            delay_seconds = (now - candle_close_time).total_seconds()

            self.last_candle_time = last_closed_ts_val
            self.logger.info(
                f"Processing new candle: {last_closed_time} (Latency: {delay_seconds:.1f}s)"
            )
            return delay_seconds
        except Exception as e:
            self.logger.error(f"Error checking candle timestamp: {e}")
            return None

    # ------------------------------------------------------------------
    # Market analysis + trade execution
    # ------------------------------------------------------------------

    def _analyze_market_and_trade(
        self,
        df_final: pd.DataFrame,
        current_pos_amt: float,
        entry_price: float,
        delay_seconds: float,
    ) -> None:
        last_candle = df_final.iloc[-2]
        candle_time = last_candle["timestamp"].strftime("%d-%m-%Y %H:%M:%S")
        atr_val = last_candle.get("ATR", 0)
        close_price = last_candle["close"]

        adx_val = last_candle.get("ADX", 0)
        rsi_val = last_candle.get("RSI", 50)
        ema_val = last_candle.get(f"EMA_{settings.EMA_LENGTH}", 0)
        vol_ma_val = last_candle.get(f"VOL_MA_{settings.VOLUME_MA_LENGTH}", 0)
        current_volume = last_candle.get("volume", 0)
        st_dir_col = (
            f"SUPERTd_{settings.SUPERTREND_LENGTH}_{settings.SUPERTREND_FACTOR}"
        )
        current_trend = last_candle[st_dir_col]
        ema_slope_length = getattr(
            settings, "EMA_SLOPE_EMA_LENGTH", settings.EMA_LENGTH
        )
        ema_slope_lookback = getattr(settings, "EMA_SLOPE_LOOKBACK", 3)
        ema_slope_threshold = getattr(settings, "EMA_SLOPE_THRESHOLD", 0.001)
        ema_slope_val = last_candle.get(f"EMA_{ema_slope_length}", ema_val)
        ema_slope_prev = df_final.iloc[-(ema_slope_lookback + 2)].get(
            f"EMA_{ema_slope_length}", ema_val
        )
        ema_slope_pct = (
            (ema_slope_val - ema_slope_prev) / ema_slope_prev
            if ema_slope_prev != 0
            else 0
        )

        self.logger.info(
            f"Market Data: {candle_time} | Close: {close_price} | Trend: {current_trend} | "
            f"EMA{settings.EMA_LENGTH}: {ema_val:.2f} | ADX: {adx_val:.2f} | ATR: {atr_val:.2f} | "
            f"RSI: {rsi_val:.2f} | Vol: {current_volume:.0f} (MA: {vol_ma_val:.0f}) | "
            f"EMA{ema_slope_length} Slope: {ema_slope_pct*100:.3f}% "
            f"({'FLAT' if abs(ema_slope_pct) < ema_slope_threshold else 'STEEP'})"
        )

        STALE_TOLERANCE = 120
        if delay_seconds > STALE_TOLERANCE:
            self.logger.warning(
                f"Candle {candle_time} is STALE ({int(delay_seconds)}s ago). Skipping."
            )
            return

        signal, actual_pos_size, reason = evaluate_signal(df_final, current_pos_amt)
        self.logger.info(f"Signal evaluation: {reason}")

        if signal in ("CLOSE_LONG", "CLOSE_SHORT"):
            direction = "LONG" if signal == "CLOSE_LONG" else "SHORT"
            self.logger.info(f"Trend flip. Closing {direction} ({current_pos_amt}).")
            self.close_all_positions()

        elif signal in ("LONG", "SHORT"):
            self.logger.info(f"SIGNAL: {signal} | Size: {actual_pos_size*100:.1f}%")
            if actual_pos_size < settings.POSITION_SIZE_PERCENT:
                self.logger.info(
                    f"⚠️ EMA slope FLAT → reduced size {actual_pos_size*100:.1f}%."
                )
            self.open_position(
                signal, close_price, atr_val, pos_size_pct=actual_pos_size
            )
        else:
            self.logger.info(
                f"No signal for {candle_time}. Position: {current_pos_amt}"
            )

    # ------------------------------------------------------------------
    # Order helpers
    # ------------------------------------------------------------------

    def close_all_positions(self) -> None:
        self.logger.info("Closing all positions...")

        # Capture trade result before closing for notification
        try:
            amt, entry = self.client.get_current_position()
            if amt != 0 and entry != 0:
                df = self.client.fetch_ohlcv(limit=1)
                if df is not None and not df.empty:
                    curr_price = df["close"].iloc[-1]
                    result = TradeResult(
                        side="LONG" if amt > 0 else "SHORT",
                        entry_price=entry,
                        exit_price=curr_price,
                        quantity=abs(amt),
                        leverage=settings.LEVERAGE,
                        fee_rate=settings.TAKER_FEE_RATE,
                    )
                    if self.notifier:
                        self.notifier.send_lark_message(
                            result.format_summary("POSITION CLOSED")
                        )
        except Exception:
            pass  # best-effort notification

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
                    self.notifier.send_lark_message(
                        f"✂️ **Partial Close Successful**\nSide: {side}\nQuantity: {quantity:.4f}"
                    )
        except Exception as e:
            self.logger.error(f"Failed to partial close: {e}")

    def open_position(
        self,
        side: str,
        price: float,
        atr_val: float,
        pos_size_pct: float = settings.POSITION_SIZE_PERCENT,
    ) -> None:
        if not self.check_rate_limit():
            return

        try:
            balance = self.client.get_balance()
            if balance is None:
                self.logger.error("Could not fetch balance. Aborting.")
                return

            trade_amount, notional_usdt = calc_trade_quantity(
                balance=balance,
                pos_size_pct=pos_size_pct,
                leverage=settings.LEVERAGE,
                price=price,
                fee_rate=settings.TAKER_FEE_RATE,
                qty_precision=self.client.qty_precision,
            )

            if trade_amount <= 0:
                self.logger.error(
                    f"Trade amount zero after rounding ({trade_amount}). Aborting."
                )
                return

            is_long = side == "LONG"
            if is_long:
                self.stop_loss_price = price - (atr_val * settings.ATR_MULTIPLIER)
            else:
                self.stop_loss_price = price + (atr_val * settings.ATR_MULTIPLIER)

            self.logger.info(
                f"Opening {side} | Price: {price} | "
                f"{pos_size_pct*100:.1f}% × {balance:.2f} USDT × {settings.LEVERAGE}x "
                f"→ {trade_amount} BTC ({notional_usdt:.2f} USDT) | "
                f"SL: {self.stop_loss_price:.2f}"
            )

            order_resp = self.client.create_order(
                "buy" if is_long else "sell", trade_amount
            )

            if order_resp:
                self.in_position = True
                self.entry_price = price
                self.breakeven_activated = False
                self.trade_history.append(time.time())
                self._save_state()

                if self.notifier:
                    be_price = calc_breakeven_price(
                        price, settings.TAKER_FEE_RATE, is_long
                    )
                    self.notifier.send_lark_message(
                        f"✅ **Position Opened ({side})**\n"
                        f"Entry Price:  {price:.2f}\n"
                        f"Amount:       {trade_amount} BTC ({notional_usdt:.2f} USDT)\n"
                        f"Stop Loss:    {self.stop_loss_price:.2f}\n"
                        f"Breakeven:    {be_price:.4f}\n"
                        f"Leverage:     {settings.LEVERAGE}x"
                    )

        except Exception as e:
            self.logger.error(f"Failed to open position: {e}")

    # ------------------------------------------------------------------
    # Daily report
    # ------------------------------------------------------------------

    def send_daily_report(self) -> None:
        try:
            total_pnl, trade_count, total_fee = self.client.get_yesterday_stats()
            balance = self.client.get_balance()
            net_pnl = total_pnl - total_fee
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")

            pnl_emoji = "🟢" if net_pnl >= 0 else "🔴"
            pnl_sign = "+" if net_pnl >= 0 else ""
            gross_sign = "+" if total_pnl >= 0 else ""
            roi_pct = (net_pnl / balance * 100) if balance else 0
            roi_sign = "+" if roi_pct >= 0 else ""

            message = (
                f"📊 **DAILY PERFORMANCE REPORT ({yesterday})**\n"
                f"--------------------------------\n"
                f"{pnl_emoji} Net PNL:  {pnl_sign}{net_pnl:.2f} USDT\n"
                f"   Gross:   {gross_sign}{total_pnl:.2f} USDT\n"
                f"   Fee:    -{total_fee:.4f} USDT\n"
                f"📈 Trades Closed: {trade_count}\n"
                f"📉 Daily ROI*:    {roi_sign}{roi_pct:.2f}%\n"
                f"🏦 Current Balance: {balance:.2f} USDT\n"
                f"   (*vs current balance)\n"
            )

            self.logger.info(
                f"Daily report: Net PNL {net_pnl:.2f}, Trades {trade_count}"
            )
            if self.notifier:
                self.notifier.send_lark_message(message)

        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
