import pandas as pd
from module.bot.utils import parse_timeframe_to_seconds
from module.bot.core_strategy import evaluate_signal
from module.backtest.metrics import MetricsCalculator
from module.bot.finance import calc_breakeven_price


class Simulator:
    """
    Backtest simulator — mirrors live bot behaviour as closely as possible.

    Execution model (matches live bot):
    ─────────────────────────────────────────────────────────────────────
    Signal candle  : df.iloc[i-1]  (last CLOSED candle = df_slice.iloc[-2])
    Entry price    : df.iloc[i]['open']  (next candle open — same as live market order)
    ATR for SL     : df_final.iloc[i-1]['ATR']  (ATR on HA-processed data, same as live)
    SL check       : uses candle low/high (intra-candle) — matches live per-second polling

    Fee accounting (split-leg, matches live bot):
    ─────────────────────────────────────────────────────────────────────
    OPEN  : entry_fee = entry_price * qty * rate  → deducted from balance immediately
    CLOSE : exit_fee  = exit_price  * qty * rate  → deducted inside pnl calc
    Total = entry_fee + exit_fee  == finance.calc_round_trip_fee()
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
            df_final: DataFrame already processed by DataProcessor.prepare_all_indicators()
                      (contains ATR on HA candles, EMA, SuperTrend, HTF_TREND, etc.)
                      Same object that live bot's run_analysis() works with.
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

        # We need at least 3 rows for evaluate_signal (uses iloc[-2] and iloc[-3])
        # and 1 row lookahead for the next-candle open price → start at i=3
        for i in range(3, len(df_final)):
            # ----------------------------------------------------------
            # Signal candle  = df_final.iloc[i-1]  (last closed)
            # Execution candle = df_final.iloc[i]  (candle where order fills)
            # FIX [2]: entry price = open of NEXT candle, not close of signal candle
            # ----------------------------------------------------------
            signal_candle = df_final.iloc[i - 1]
            exec_candle = df_final.iloc[i]

            exec_price = exec_candle["open"]  # realistic fill price
            exec_time = exec_candle["timestamp"]

            # df_slice ends at signal candle (iloc[i-1] is the last row)
            # → evaluate_signal will see df_slice.iloc[-2] == df_final.iloc[i-1] ✓
            df_slice = df_final.iloc[:i]

            # ----------------------------------------------------------
            # 0. LIQUIDATION CHECK (intra-candle, same as live)
            # ----------------------------------------------------------
            if position_amt != 0:
                liq_hit = (
                    position_amt > 0 and exec_candle["low"] <= liquidation_price
                ) or (position_amt < 0 and exec_candle["high"] >= liquidation_price)
                if liq_hit:
                    if position_amt > 0:
                        pnl = self._close_long_pnl(
                            liquidation_price, entry_price, position_amt
                        )
                    else:
                        pnl = self._close_short_pnl(
                            liquidation_price, entry_price, position_amt
                        )
                    balance += pnl
                    trades.append(
                        {
                            "time": exec_time,
                            "type": "LIQUIDATION",
                            "price": liquidation_price,
                            "pnl": pnl,
                        }
                    )
                    position_amt = 0
                    is_breakeven_activated = False
                    continue

            # ----------------------------------------------------------
            # 0.5 BREAKEVEN TRIGGER (uses close of signal candle, same as live)
            # ----------------------------------------------------------
            if self.use_breakeven and position_amt != 0 and not is_breakeven_activated:
                signal_price = signal_candle["close"]
                if position_amt > 0 and signal_price >= breakeven_target:
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=True
                    )
                    is_breakeven_activated = True
                elif position_amt < 0 and signal_price <= breakeven_target:
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=False
                    )
                    is_breakeven_activated = True

            # ----------------------------------------------------------
            # 1. STOP LOSS CHECK (intra-candle low/high, matches live polling)
            # FIX [7]: use candle low/high instead of close-only
            # ----------------------------------------------------------
            if position_amt > 0 and exec_candle["low"] <= stop_loss_price:
                pnl = self._close_long_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = (
                    "BE_STOP_LONG" if is_breakeven_activated else "STOP_LOSS_LONG"
                )
                trades.append(
                    {
                        "time": exec_time,
                        "type": type_str,
                        "price": stop_loss_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False
                continue

            elif position_amt < 0 and exec_candle["high"] >= stop_loss_price:
                pnl = self._close_short_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = (
                    "BE_STOP_SHORT" if is_breakeven_activated else "STOP_LOSS_SHORT"
                )
                trades.append(
                    {
                        "time": exec_time,
                        "type": type_str,
                        "price": stop_loss_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False
                continue

            # ----------------------------------------------------------
            # 2. SIGNAL EVALUATION (same df_slice live bot uses)
            # ----------------------------------------------------------
            signal, suggested_pos_size, _ = evaluate_signal(df_slice, position_amt)

            # ----------------------------------------------------------
            # 3. EXIT LOGIC
            # ----------------------------------------------------------
            if signal == "CLOSE_LONG" and position_amt > 0:
                pnl = self._close_long_pnl(exec_price, entry_price, position_amt)
                balance += pnl
                trades.append(
                    {
                        "time": exec_time,
                        "type": "CLOSE_LONG",
                        "price": exec_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False

            elif signal == "CLOSE_SHORT" and position_amt < 0:
                pnl = self._close_short_pnl(exec_price, entry_price, position_amt)
                balance += pnl
                trades.append(
                    {
                        "time": exec_time,
                        "type": "CLOSE_SHORT",
                        "price": exec_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False

            # ----------------------------------------------------------
            # 4. ENTRY LOGIC
            # ----------------------------------------------------------
            elif signal in ("LONG", "SHORT") and position_amt == 0:
                effective_size = (
                    suggested_pos_size
                    if suggested_pos_size > 0
                    else self.position_size_percent
                )

                # FIX [position sizing]: reserve margin for entry fee
                notional_safe = (balance * effective_size * self.leverage) / (
                    1 + self.commission_rate
                )
                entry_fee = notional_safe * self.commission_rate
                balance -= entry_fee

                # FIX [3]: ATR from df_final (HA-processed) at signal candle — matches live bot
                atr_val = signal_candle["ATR"]

                # FIX [2]: fill at next candle open
                amount = notional_safe / exec_price
                position_amt = amount if signal == "LONG" else -amount
                entry_price = exec_price
                is_breakeven_activated = False

                if signal == "LONG":
                    liquidation_price = entry_price * (1 - 1 / self.leverage)
                    stop_loss_price = entry_price - (atr_val * self.sl_multiplier)
                    breakeven_target = (
                        entry_price
                        + (entry_price - stop_loss_price) * self.breakeven_multiplier
                    )
                else:
                    liquidation_price = entry_price * (1 + 1 / self.leverage)
                    stop_loss_price = entry_price + (atr_val * self.sl_multiplier)
                    breakeven_target = (
                        entry_price
                        - (stop_loss_price - entry_price) * self.breakeven_multiplier
                    )

                trades.append(
                    {
                        "time": exec_time,
                        "type": f"OPEN_{signal}",
                        "price": exec_price,
                        "pnl": -entry_fee,
                        "amount": abs(amount),
                    }
                )

        # Close any still-open position at last available price
        if position_amt != 0:
            last_price = df_final.iloc[-1]["close"]
            if position_amt > 0:
                pnl = self._close_long_pnl(last_price, entry_price, position_amt)
            else:
                pnl = self._close_short_pnl(last_price, entry_price, position_amt)
            balance += pnl
            trades.append(
                {
                    "time": df_final.iloc[-1]["timestamp"],
                    "type": "FINAL_CLOSE",
                    "price": last_price,
                    "pnl": pnl,
                }
            )

        metrics = MetricsCalculator.calculate(trades, balance, initial_balance)
        return metrics, trades
