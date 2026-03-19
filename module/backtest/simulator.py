import pandas as pd
from module.bot.utils import parse_timeframe_to_seconds
from module.backtest.metrics import MetricsCalculator

class Simulator:
    """Mô phỏng giao dịch Backtest."""
    
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
        ema_length=97
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

    def run(self, df):
        initial_balance = 1000
        balance = initial_balance
        position_amt = 0
        entry_price = 0
        liquidation_price = 0
        stop_loss_price = 0
        trades = []

        st_dir_col = f"SUPERTd_{self.st_length}_{self.st_factor}"
        ema_col = "EMA_FILTER" if "EMA_FILTER" in df.columns else f"EMA_{self.ema_length}"

        for i in range(1, len(df)):
            current_candle = df.iloc[i]
            prev_candle = df.iloc[i - 1]

            curr_trend = current_candle[st_dir_col]
            prev_trend = prev_candle[st_dir_col]
            ema_val = current_candle[ema_col]

            price = current_candle["close"]
            timestamp = current_candle["timestamp"]

            if i < len(df) - 1:
                execution_time = df.iloc[i + 1]["timestamp"]
            else:
                tf_seconds = parse_timeframe_to_seconds(self.timeframe)
                execution_time = timestamp + pd.Timedelta(seconds=tf_seconds)

            # 0. LIQUIDATION CHECK
            if position_amt != 0:
                liq_hit = False
                if position_amt > 0:
                    if current_candle["low"] <= liquidation_price:
                        liq_hit = True
                        liq_price_trigger = liquidation_price
                else:
                    if current_candle["high"] >= liquidation_price:
                        liq_hit = True
                        liq_price_trigger = liquidation_price

                if liq_hit:
                    margin_lost = (abs(position_amt) * entry_price) / self.leverage
                    pnl = -margin_lost
                    balance += pnl
                    trades.append({
                        "time": execution_time,
                        "type": "LIQUIDATION",
                        "price": liq_price_trigger,
                        "pnl": pnl,
                    })
                    position_amt = 0
                    continue

            # 1. EXIT LOGIC
            if position_amt > 0 and curr_trend == -1:
                raw_pnl = (price - entry_price) * position_amt
                fee = (price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "CLOSE_LONG", "price": price, "pnl": pnl})
                position_amt = 0

            elif position_amt < 0 and curr_trend == 1:
                raw_pnl = (entry_price - price) * abs(position_amt)
                fee = (price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "CLOSE_SHORT", "price": price, "pnl": pnl})
                position_amt = 0

            # 1b. STOP LOSS CHECK
            if position_amt > 0 and price <= stop_loss_price:
                raw_pnl = (stop_loss_price - entry_price) * position_amt
                fee = (stop_loss_price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "STOP_LOSS_LONG", "price": stop_loss_price, "pnl": pnl})
                position_amt = 0
            elif position_amt < 0 and price >= stop_loss_price:
                raw_pnl = (entry_price - stop_loss_price) * abs(position_amt)
                fee = (stop_loss_price * abs(position_amt)) * self.commission_rate
                pnl = raw_pnl - fee
                balance += pnl
                trades.append({"time": execution_time, "type": "STOP_LOSS_SHORT", "price": stop_loss_price, "pnl": pnl})
                position_amt = 0

            # 2. ENTRY LOGIC
            is_uptrend = price > ema_val if self.use_ema_filter else True
            is_downtrend = price < ema_val if self.use_ema_filter else True

            vol_ma_col = f"VOL_MA_{self.volume_ma_length}"
            vol_ok = True
            if self.use_volume_filter and vol_ma_col in current_candle:
                vol_ok = current_candle["volume"] > current_candle[vol_ma_col]

            signal = None
            if curr_trend == 1 and prev_trend == -1 and is_uptrend and vol_ok:
                signal = "LONG"
            elif curr_trend == -1 and prev_trend == 1 and is_downtrend and vol_ok:
                signal = "SHORT"

            if signal and position_amt == 0:
                trade_value = balance * self.position_size_percent * self.leverage
                entry_fee = trade_value * self.commission_rate
                balance -= entry_fee

                amount = trade_value / price
                position_amt = amount if signal == "LONG" else -amount
                entry_price = price

                if signal == "LONG":
                    liquidation_price = entry_price * (1 - 1 / self.leverage)
                else:
                    liquidation_price = entry_price * (1 + 1 / self.leverage)

                atr_val = current_candle["ATR"]
                if signal == "LONG":
                    stop_loss_price = entry_price - (atr_val * self.sl_multiplier)
                else:
                    stop_loss_price = entry_price + (atr_val * self.sl_multiplier)

                trades.append({
                    "time": execution_time,
                    "type": f"OPEN_{signal}",
                    "price": price,
                    "pnl": -entry_fee,
                    "amount": amount,
                })

        # Close final position
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
