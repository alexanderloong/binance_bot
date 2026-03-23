import pandas as pd
import numpy as np
from module.bot.core_strategy import evaluate_signal
from module.backtest.metrics import MetricsCalculator
from module.bot.finance import calc_breakeven_price


class Simulator:
    """
    Backtest simulator — mirrors live bot behaviour as closely as possible.

    Performance notes:
    ─────────────────────────────────────────────────────────────────────
    The main loop runs 228 000+ iterations. To keep it fast:
    • All per-candle column lookups use pre-extracted numpy arrays (O(1)).
    • evaluate_signal receives a fixed 5-row window instead of a growing
      slice — it only ever reads iloc[-2] and iloc[-3].

    Execution model (matches live bot — candle-close only):
    ─────────────────────────────────────────────────────────────────────
    ALL decisions (liquidation, breakeven, SL, signal) are evaluated against
    the CLOSE price of the last completed candle (arr_close[i-1]).
    No intra-candle low/high triggers exist in either backtest or live bot.

    Signal candle  : df.iloc[i-1]  (last CLOSED candle)
    Check price    : arr_close[i-1]  (close of last CLOSED candle)
    Entry price    : df.iloc[i]['open']  (next candle open)
    ATR for SL     : signal_candle['ATR']  (HA-processed)

    Fee accounting (split-leg):
    ─────────────────────────────────────────────────────────────────────
    OPEN  : entry_fee = entry_price * qty * rate  → deducted immediately
    CLOSE : exit_fee  = exit_price  * qty * rate  → inside pnl calc
    """

    def __init__(
        self,
        timeframe,
        use_ema_filter=True,
        st_length=18,
        st_factor=1.45,
        use_volume_filter=True,
        volume_ma_length=177,
        sl_multiplier=0.74,
        leverage=10,
        position_size_percent=0.2,
        commission_rate=0.0005,
        ema_length=97,
        use_htf_filter=False,
        use_breakeven=False,
        breakeven_multiplier=1.0,
    ):
        self.timeframe = timeframe
        self.use_ema_filter = use_ema_filter
        self.st_length = st_length
        self.st_factor = st_factor
        self.use_volume_filter = use_volume_filter
        self.volume_ma_length = volume_ma_length
        self.sl_multiplier = sl_multiplier
        self.leverage = leverage
        self.position_size_percent = position_size_percent
        self.commission_rate = commission_rate
        self.ema_length = ema_length
        self.use_htf_filter = use_htf_filter
        self.use_breakeven = use_breakeven
        self.breakeven_multiplier = breakeven_multiplier

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _exit_fee(self, price: float, qty: float) -> float:
        return abs(price) * abs(qty) * self.commission_rate

    def _close_long_pnl(self, exit_price, entry_price, qty) -> float:
        return (exit_price - entry_price) * qty - self._exit_fee(exit_price, qty)

    def _close_short_pnl(self, exit_price, entry_price, qty) -> float:
        return (entry_price - exit_price) * abs(qty) - self._exit_fee(exit_price, qty)

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self, df_final):
        """
        Args:
            df_final: DataFrame processed by DataProcessor.prepare_all_indicators()
        """
        initial_balance = 1000.0
        balance = initial_balance
        position_amt = 0.0
        entry_price = 0.0
        liquidation_price = 0.0
        stop_loss_price = 0.0
        breakeven_target = 0.0
        is_breakeven_activated = False
        trades = []

        # ------------------------------------------------------------------
        # PERF: Pre-extract all columns as numpy arrays — O(1) index vs .iloc
        # Column names are built from self.* so optimization runs with
        # non-default params read the correct columns (not settings globals).
        # ------------------------------------------------------------------
        st_dir_col = f"SUPERTd_{self.st_length}_{self.st_factor}"
        ema_col    = f"EMA_{self.ema_length}"
        vol_ma_col = f"VOL_MA_{self.volume_ma_length}"

        arr_open      = df_final["open"].to_numpy()
        arr_close     = df_final["close"].to_numpy()
        arr_timestamp = df_final["timestamp"].to_numpy()
        arr_atr       = df_final["ATR"].to_numpy()
        arr_vol_ma    = df_final[vol_ma_col].to_numpy() if vol_ma_col in df_final.columns else np.zeros(len(df_final))
        arr_htf       = df_final["HTF_TREND"].to_numpy() if "HTF_TREND" in df_final.columns else df_final[st_dir_col].to_numpy()

        n = len(df_final)

        for i in range(3, n):
            exec_open  = arr_open[i]
            exec_time  = arr_timestamp[i]

            # Candle-close only: all decisions are evaluated against the
            # close price of the last fully completed candle.
            signal_close = arr_close[i - 1]

            # ----------------------------------------------------------
            # 0. LIQUIDATION CHECK (candle-close price)
            # ----------------------------------------------------------
            if position_amt != 0:
                liq_hit = (
                    (position_amt > 0 and signal_close <= liquidation_price) or
                    (position_amt < 0 and signal_close >= liquidation_price)
                )
                if liq_hit:
                    pnl = (self._close_long_pnl(liquidation_price, entry_price, position_amt)
                           if position_amt > 0 else
                           self._close_short_pnl(liquidation_price, entry_price, position_amt))
                    balance += pnl
                    trades.append({"time": exec_time, "type": "LIQUIDATION",
                                   "price": liquidation_price, "pnl": pnl})
                    position_amt = 0
                    is_breakeven_activated = False
                    continue

            # ----------------------------------------------------------
            # 0.5 BREAKEVEN TRIGGER (candle-close price)
            # ----------------------------------------------------------
            if self.use_breakeven and position_amt != 0 and not is_breakeven_activated:
                if position_amt > 0 and signal_close >= breakeven_target:
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=True)
                    is_breakeven_activated = True
                elif position_amt < 0 and signal_close <= breakeven_target:
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=False)
                    is_breakeven_activated = True

            # ----------------------------------------------------------
            # 1. STOP LOSS CHECK (candle-close price)
            # ----------------------------------------------------------
            if position_amt > 0 and signal_close <= stop_loss_price:
                pnl = self._close_long_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = "BE_STOP_LONG" if is_breakeven_activated else "STOP_LOSS_LONG"
                trades.append({"time": exec_time, "type": type_str,
                                "price": stop_loss_price, "pnl": pnl})
                position_amt = 0
                is_breakeven_activated = False
                continue

            elif position_amt < 0 and signal_close >= stop_loss_price:
                pnl = self._close_short_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = "BE_STOP_SHORT" if is_breakeven_activated else "STOP_LOSS_SHORT"
                trades.append({"time": exec_time, "type": type_str,
                                "price": stop_loss_price, "pnl": pnl})
                position_amt = 0
                is_breakeven_activated = False
                continue

            # ----------------------------------------------------------
            # 2. SIGNAL EVALUATION
            # PERF: pass fixed 5-row window instead of growing slice.
            #       evaluate_signal only reads iloc[-2] and iloc[-3].
            # ----------------------------------------------------------
            window_start = max(0, i - 5)
            df_window = df_final.iloc[window_start:i]

            signal, suggested_pos_size, _ = evaluate_signal(
                df_window,
                position_amt,
                use_ema_filter=self.use_ema_filter,
                use_volume_filter=self.use_volume_filter,
                use_htf_filter=self.use_htf_filter,
            )

            # ----------------------------------------------------------
            # 3. EXIT LOGIC
            # ----------------------------------------------------------
            if signal == "CLOSE_LONG" and position_amt > 0:
                pnl = self._close_long_pnl(exec_open, entry_price, position_amt)
                balance += pnl
                trades.append({"time": exec_time, "type": "CLOSE_LONG",
                                "price": exec_open, "pnl": pnl})
                position_amt = 0
                is_breakeven_activated = False

            elif signal == "CLOSE_SHORT" and position_amt < 0:
                pnl = self._close_short_pnl(exec_open, entry_price, position_amt)
                balance += pnl
                trades.append({"time": exec_time, "type": "CLOSE_SHORT",
                                "price": exec_open, "pnl": pnl})
                position_amt = 0
                is_breakeven_activated = False

            # ----------------------------------------------------------
            # 4. ENTRY LOGIC
            # ----------------------------------------------------------
            elif signal in ("LONG", "SHORT") and position_amt == 0:
                effective_size = (suggested_pos_size if suggested_pos_size > 0
                                  else self.position_size_percent)
                notional_safe = (balance * effective_size * self.leverage) / (1 + self.commission_rate)
                entry_fee = notional_safe * self.commission_rate
                balance -= entry_fee

                # ATR from signal candle (numpy array — no .iloc overhead)
                atr_val = arr_atr[i - 1]
                amount = notional_safe / exec_open
                position_amt = amount if signal == "LONG" else -amount
                entry_price = exec_open
                is_breakeven_activated = False

                if signal == "LONG":
                    liquidation_price = entry_price * (1 - 1 / self.leverage)
                    stop_loss_price   = entry_price - (atr_val * self.sl_multiplier)
                    breakeven_target  = entry_price + (entry_price - stop_loss_price) * self.breakeven_multiplier
                else:
                    liquidation_price = entry_price * (1 + 1 / self.leverage)
                    stop_loss_price   = entry_price + (atr_val * self.sl_multiplier)
                    breakeven_target  = entry_price - (stop_loss_price - entry_price) * self.breakeven_multiplier

                trades.append({
                    "time":   exec_time,
                    "type":   f"OPEN_{signal}",
                    "price":  exec_open,
                    "pnl":    -entry_fee,
                    "amount": abs(amount),
                })

        # Close any still-open position at last close price
        if position_amt != 0:
            last_price = arr_close[-1]
            pnl = (self._close_long_pnl(last_price, entry_price, position_amt)
                   if position_amt > 0 else
                   self._close_short_pnl(last_price, entry_price, position_amt))
            balance += pnl
            trades.append({
                "time":  arr_timestamp[-1],
                "type":  "FINAL_CLOSE",
                "price": last_price,
                "pnl":   pnl,
            })

        metrics = MetricsCalculator.calculate(trades, balance, initial_balance)
        return metrics, trades
