import pandas as pd
from module.bot.utils import parse_timeframe_to_seconds
from module.bot.core_strategy import evaluate_signal
from module.backtest.metrics import MetricsCalculator

class Simulator:
    """Backtest simulator using the shared evaluate_signal engine."""
    
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

    def run(self, df):
        initial_balance = 1000
        balance = initial_balance
        position_amt = 0
        entry_price = 0
        liquidation_price = 0
        stop_loss_price = 0
        breakeven_target = 0
        is_breakeven_activated = False
        trades = []

        for i in range(2, len(df)):
            # Build a slice up to (and including) current candle for evaluate_signal
            # evaluate_signal looks at df.iloc[-2] (last closed) and df.iloc[-3] (prev closed)
            df_slice = df.iloc[:i + 1]

            price = df.iloc[i]["close"]
            timestamp = df.iloc[i]["timestamp"]

            if i < len(df) - 1:
                execution_time = df.iloc[i + 1]["timestamp"]
            else:
                tf_seconds = parse_timeframe_to_seconds(self.timeframe)
                execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)

            # 0. LIQUIDATION CHECK
            if position_amt != 0:
                current_candle = df.iloc[i]
                liq_hit = False
                if position_amt > 0 and current_candle["low"] <= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price
                elif position_amt < 0 and current_candle["high"] >= liquidation_price:
                    liq_hit = True
                    liq_price_trigger = liquidation_price

                if liq_hit:
                    margin_lost = (abs(position_amt) * entry_price) / self.leverage
                    pnl = -margin_lost
                    balance += pnl
                    trades.append({"time": execution_time, "type": "LIQUIDATION", "price": liq_price_trigger, "pnl": pnl})
                    position_amt = 0
                    continue

            # 0.5 BREAKEVEN TRIGGER
            if self.use_breakeven and position_amt != 0 and not is_breakeven_activated:
                if position_amt > 0 and price >= breakeven_target:
                    stop_loss_price = entry_price * (1 + self.commission_rate * 2)
                    is_breakeven_activated = True
                elif position_amt < 0 and price <= breakeven_target:
                    stop_loss_price = entry_price * (1 - self.commission_rate * 2)
                    is_breakeven_activated = True

            # 1. STOP LOSS CHECK (before exit signal, to catch intra-candle moves)
            if position_amt > 0 and price <= stop_loss_price:
                raw_pnl = (stop_loss_price - entry_price) * position_amt
                fee = (stop_loss_price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                type_str = "BE_STOP_LONG" if is_breakeven_activated else "STOP_LOSS_LONG"
                trades.append({"time": execution_time, "type": type_str, "price": stop_loss_price, "pnl": pnl})
                position_amt = 0
                continue
            elif position_amt < 0 and price >= stop_loss_price:
                raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
                fee = (stop_loss_price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                type_str = "BE_STOP_SHORT" if is_breakeven_activated else "STOP_LOSS_SHORT"
                trades.append({"time": execution_time, "type": type_str, "price": stop_loss_price, "pnl": pnl})
                position_amt = 0
                continue

            # 2. UNIFIED SIGNAL EVALUATION (same rules as live bot)
            signal, suggested_pos_size, _ = evaluate_signal(df_slice, position_amt)

            # 3. EXIT LOGIC
            if signal == 'CLOSE_LONG' and position_amt > 0:
                raw_pnl = (price - entry_price) * position_amt
                fee = (price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "CLOSE_LONG", "price": price, "pnl": pnl})
                position_amt = 0

            elif signal == 'CLOSE_SHORT' and position_amt < 0:
                raw_pnl = (entry_price - price) * abs(position_amt)
                fee = (price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "CLOSE_SHORT", "price": price, "pnl": pnl})
                position_amt = 0

            # 4. ENTRY LOGIC (only if flat/no position after exit)
            elif signal in ('LONG', 'SHORT') and position_amt == 0:
                # Apply dynamic position sizing (from EMA slope logic in evaluate_signal)
                effective_size = suggested_pos_size if suggested_pos_size > 0 else self.position_size_percent
                trade_value = balance * effective_size * self.leverage
                entry_fee = trade_value * self.commission_rate
                balance -= entry_fee

                atr_val = df.iloc[i]["ATR"]
                amount = trade_value / price
                position_amt = amount if signal == "LONG" else -amount
                entry_price = price

                if signal == "LONG":
                    liquidation_price = entry_price * (1 - 1 / self.leverage)
                    stop_loss_price = entry_price - (atr_val * self.sl_multiplier)
                    breakeven_target = entry_price + (entry_price - stop_loss_price) * self.breakeven_multiplier
                else:
                    liquidation_price = entry_price * (1 + 1 / self.leverage)
                    stop_loss_price = entry_price + (atr_val * self.sl_multiplier)
                    breakeven_target = entry_price - (stop_loss_price - entry_price) * self.breakeven_multiplier

                is_breakeven_activated = False
                trades.append({
                    "time": execution_time,
                    "type": f"OPEN_{signal}",
                    "price": price,
                    "pnl": -entry_fee,
                    "amount": amount,
                })

        # Close final open position at last price
        if position_amt != 0:
            last_price = df.iloc[-1]["close"]
            raw_pnl = (
                (last_price - entry_price) * position_amt
                if position_amt > 0
                else (entry_price - last_price) * abs(position_amt)
            )
            fee = (last_price * abs(position_amt)) * self.commission_rate
            pnl = raw_pnl - fee
            balance += pnl
            trades.append({
                "time": df.iloc[-1]["timestamp"],
                "type": "FINAL_CLOSE",
                "price": last_price,
                "pnl": pnl,
            })

        metrics = MetricsCalculator.calculate(trades, balance, initial_balance)
        return metrics, trades

