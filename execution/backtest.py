import pandas as pd
import numpy as np
from execution.engine import ExecutionEngine
from execution.risk_manager import RiskManager
from core.logger import logger
from execution.reporter import BacktestReporter


class BacktestEngine(ExecutionEngine):
    def __init__(
        self,
        initial_capital: float = 1000.0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        sl_atr_multiplier: float = 0.0,
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_manager = RiskManager(initial_capital)
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.sl_atr_multiplier = sl_atr_multiplier

        self.position = 0  # 1 for Long, -1 for Short, 0 for flat
        self.entry_price = 0.0
        self.position_size = 0.0
        self.sl_price = 0.0
        self.initial_sl_price = 0.0
        self.entry_fee = 0.0
        
        self.trades = []
        self.equity_curve = []

    def run(self, df: pd.DataFrame, silent=False):
        if not silent:
            logger.info(f"Starting backtest with {self.initial_capital} USDT")

        pending_signal = 0
        pending_atr = 0.0
        for index, row in df.iterrows():
            current_open = row["open"]
            current_atr = row.get("atr", 0.0)

            self._process_pending_signal(pending_signal, current_open, index, pending_atr)
            self._evaluate_stop_loss(row, index)
            self._record_equity(row, index)

            pending_signal = row.get("signal", 0)
            pending_atr = row.get("atr", 0)

        if self.position != 0:
            last_idx = df.index[-1]
            last_price = df["close"].iloc[-1]
            self.close_position(
                last_price, timestamp=last_idx, reason="End of Backtest"
            )

        self.generate_report(silent=silent)

    def _process_pending_signal(self, pending_signal, current_open, index, pending_atr):
        if pending_signal == 1:
            if self.position == -1:
                self.close_position(current_open, timestamp=index, reason="Close Short")
            if self.position == 0:
                self.execute_long(current_open, timestamp=index, current_atr=pending_atr)
        elif pending_signal == -1:
            if self.position == 1:
                self.close_position(current_open, timestamp=index, reason="Close Long")
            if self.position == 0:
                self.execute_short(current_open, timestamp=index, current_atr=pending_atr)
        elif pending_signal == 2:
            if self.position == -1:
                self.close_position(current_open, timestamp=index, reason="Close Short (EMA block)")
        elif pending_signal == -2:
            if self.position == 1:
                self.close_position(current_open, timestamp=index, reason="Close Long (EMA block)")



    def _evaluate_stop_loss(self, row, index):
        if self.position == 1 and self.sl_atr_multiplier > 0:
            if row["close"] <= self.sl_price:
                self.close_position(row["close"], timestamp=index, reason="SL Hit (Close)")
                
        elif self.position == -1 and self.sl_atr_multiplier > 0:
            if row["close"] >= self.sl_price:
                self.close_position(row["close"], timestamp=index, reason="SL Hit (Close)")

    def _record_equity(self, row, index):
        unrealized_pnl = 0
        if self.position == 1:
            unrealized_pnl = (row["close"] - self.entry_price) * self.position_size - self.entry_fee
        elif self.position == -1:
            unrealized_pnl = (self.entry_price - row["close"]) * self.position_size - self.entry_fee

        self.equity_curve.append(
            {"timestamp": index, "equity": self.capital + unrealized_pnl}
        )

    def execute_long(self, price: float, **kwargs):
        timestamp = kwargs.get("timestamp")
        current_atr = kwargs.get("current_atr", 0)

        sl_price = 0.0
        if self.sl_atr_multiplier > 0 and current_atr > 0:
            sl_price = price - (current_atr * self.sl_atr_multiplier)

        size = self.risk_manager.calculate_position_size(
            self.capital, price, stop_loss=sl_price if sl_price > 0 else None
        )
        fee = price * size * self.taker_fee

        self.position = 1
        self.entry_price = price
        self.position_size = size
        self.entry_fee = fee
        self.sl_price = sl_price
        self.initial_sl_price = sl_price

        self.trades.append(
            {
                "timestamp": timestamp,
                "action": "LONG",
                "price": price,
                "size": size,
                "fee": fee,
                "pnl": 0,
            }
        )

    def execute_short(self, price: float, **kwargs):
        timestamp = kwargs.get("timestamp")
        current_atr = kwargs.get("current_atr", 0)

        sl_price = 0.0
        if self.sl_atr_multiplier > 0 and current_atr > 0:
            sl_price = price + (current_atr * self.sl_atr_multiplier)

        size = self.risk_manager.calculate_position_size(
            self.capital, price, stop_loss=sl_price if sl_price > 0 else None
        )
        fee = price * size * self.taker_fee

        self.position = -1
        self.entry_price = price
        self.position_size = size
        self.entry_fee = fee
        self.sl_price = sl_price
        self.initial_sl_price = sl_price

        self.trades.append(
            {
                "timestamp": timestamp,
                "action": "SHORT",
                "price": price,
                "size": size,
                "fee": fee,
                "pnl": 0,
            }
        )

    def close_position(self, price: float, **kwargs):
        timestamp = kwargs.get("timestamp")
        reason = kwargs.get("reason", "")

        fee = price * self.position_size * self.taker_fee
        pnl = 0
        if self.position == 1:
            pnl = (price - self.entry_price) * self.position_size - fee - self.entry_fee
        elif self.position == -1:
            pnl = (self.entry_price - price) * self.position_size - fee - self.entry_fee

        self.capital += pnl

        self.trades.append(
            {
                "timestamp": timestamp,
                "action": "CLOSE",
                "price": price,
                "size": self.position_size,
                "fee": fee,
                "pnl": pnl,
                "reason": reason,
            }
        )

        self.position = 0
        self.entry_price = 0
        self.position_size = 0
        self.entry_fee = 0.0
        self.sl_price = 0.0
        self.initial_sl_price = 0.0

    def generate_report(self, silent=False):
        BacktestReporter.generate_report(
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            trades=self.trades,
            equity_curve=self.equity_curve,
            silent=silent
        )
