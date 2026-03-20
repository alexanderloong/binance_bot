import pandas as pd
from module.bot.utils import parse_timeframe_to_seconds
from module.bot.core_strategy import evaluate_signal
from module.backtest.metrics import MetricsCalculator
from module.bot.finance import calc_breakeven_price


class Simulator:
    """
    Backtest simulator using the shared evaluate_signal engine.

    Fee accounting model (split-leg — matches live bot):
    ─────────────────────────────────────────────────────
    • OPEN:  entry_fee  = entry_price  * qty * rate  → deducted from balance immediately
    • CLOSE: exit_fee   = exit_price   * qty * rate  → deducted inside pnl calculation
    • Total round-trip = entry_fee + exit_fee  (identical to finance.calc_round_trip_fee)

    This keeps balance tracking consistent with the live bot where the opening
    taker fee is charged the moment the order is filled.
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
        """One-leg taker fee for a closing order."""
        return abs(price) * abs(qty) * self.commission_rate

    def _close_long_pnl(
        self, exit_price: float, entry_price: float, qty: float
    ) -> float:
        """Net PnL for closing a LONG (exit fee only — entry fee already deducted)."""
        raw = (exit_price - entry_price) * qty
        return raw - self._exit_fee(exit_price, qty)

    def _close_short_pnl(
        self, exit_price: float, entry_price: float, qty: float
    ) -> float:
        """Net PnL for closing a SHORT (exit fee only — entry fee already deducted)."""
        raw = (entry_price - exit_price) * abs(qty)
        return raw - self._exit_fee(exit_price, qty)

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self, df):
        initial_balance = 1000.0
        balance = initial_balance
        position_amt = 0.0
        entry_price = 0.0
        liquidation_price = 0.0
        stop_loss_price = 0.0
        breakeven_target = 0.0
        is_breakeven_activated = False
        trades = []

        for i in range(2, len(df)):
            df_slice = df.iloc[: i + 1]
            price = df.iloc[i]["close"]
            timestamp = df.iloc[i]["timestamp"]

            if i < len(df) - 1:
                execution_time = df.iloc[i + 1]["timestamp"]
            else:
                tf_seconds = parse_timeframe_to_seconds(self.timeframe)
                execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)

            # ----------------------------------------------------------
            # 0. LIQUIDATION CHECK
            # ----------------------------------------------------------
            if position_amt != 0:
                current_candle = df.iloc[i]
                liq_hit = (
                    position_amt > 0 and current_candle["low"] <= liquidation_price
                ) or (position_amt < 0 and current_candle["high"] >= liquidation_price)

                if liq_hit:
                    # FIX: liquidation loss = raw move to liq price + exit fee
                    # (original code used -margin which ignored the fee)
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
                            "time": execution_time,
                            "type": "LIQUIDATION",
                            "price": liquidation_price,
                            "pnl": pnl,
                        }
                    )
                    position_amt = 0
                    continue

            # ----------------------------------------------------------
            # 0.5 BREAKEVEN TRIGGER
            # ----------------------------------------------------------
            if self.use_breakeven and position_amt != 0 and not is_breakeven_activated:
                if position_amt > 0 and price >= breakeven_target:
                    # FIX: exact breakeven formula (same fix as live bot)
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=True
                    )
                    is_breakeven_activated = True
                elif position_amt < 0 and price <= breakeven_target:
                    stop_loss_price = calc_breakeven_price(
                        entry_price, self.commission_rate, is_long=False
                    )
                    is_breakeven_activated = True

            # ----------------------------------------------------------
            # 1. STOP LOSS CHECK
            # ----------------------------------------------------------
            if position_amt > 0 and price <= stop_loss_price:
                pnl = self._close_long_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = (
                    "BE_STOP_LONG" if is_breakeven_activated else "STOP_LOSS_LONG"
                )
                trades.append(
                    {
                        "time": execution_time,
                        "type": type_str,
                        "price": stop_loss_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False
                continue

            elif position_amt < 0 and price >= stop_loss_price:
                pnl = self._close_short_pnl(stop_loss_price, entry_price, position_amt)
                balance += pnl
                type_str = (
                    "BE_STOP_SHORT" if is_breakeven_activated else "STOP_LOSS_SHORT"
                )
                trades.append(
                    {
                        "time": execution_time,
                        "type": type_str,
                        "price": stop_loss_price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0
                is_breakeven_activated = False
                continue

            # ----------------------------------------------------------
            # 2. SIGNAL EVALUATION
            # ----------------------------------------------------------
            signal, suggested_pos_size, _ = evaluate_signal(df_slice, position_amt)

            # ----------------------------------------------------------
            # 3. EXIT LOGIC
            # ----------------------------------------------------------
            if signal == "CLOSE_LONG" and position_amt > 0:
                pnl = self._close_long_pnl(price, entry_price, position_amt)
                balance += pnl
                trades.append(
                    {
                        "time": execution_time,
                        "type": "CLOSE_LONG",
                        "price": price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0

            elif signal == "CLOSE_SHORT" and position_amt < 0:
                pnl = self._close_short_pnl(price, entry_price, position_amt)
                balance += pnl
                trades.append(
                    {
                        "time": execution_time,
                        "type": "CLOSE_SHORT",
                        "price": price,
                        "pnl": pnl,
                    }
                )
                position_amt = 0

            # ----------------------------------------------------------
            # 4. ENTRY LOGIC
            # ----------------------------------------------------------
            elif signal in ("LONG", "SHORT") and position_amt == 0:
                effective_size = (
                    suggested_pos_size
                    if suggested_pos_size > 0
                    else self.position_size_percent
                )
                # FIX: reserve room for entry fee so balance never goes negative
                # notional_safe = balance * size * leverage / (1 + fee_rate)
                notional_safe = (balance * effective_size * self.leverage) / (
                    1 + self.commission_rate
                )
                entry_fee = notional_safe * self.commission_rate
                balance -= entry_fee

                atr_val = df.iloc[i]["ATR"]
                amount = notional_safe / price
                position_amt = amount if signal == "LONG" else -amount
                entry_price = price
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
                        "time": execution_time,
                        "type": f"OPEN_{signal}",
                        "price": price,
                        "pnl": -entry_fee,  # fee charged at open
                        "amount": abs(amount),
                    }
                )

        # Close final open position at last available price
        if position_amt != 0:
            last_price = df.iloc[-1]["close"]
            if position_amt > 0:
                pnl = self._close_long_pnl(last_price, entry_price, position_amt)
            else:
                pnl = self._close_short_pnl(last_price, entry_price, position_amt)
            balance += pnl
            trades.append(
                {
                    "time": df.iloc[-1]["timestamp"],
                    "type": "FINAL_CLOSE",
                    "price": last_price,
                    "pnl": pnl,
                }
            )

        metrics = MetricsCalculator.calculate(trades, balance, initial_balance)
        return metrics, trades
