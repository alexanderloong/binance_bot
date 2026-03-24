import pandas as pd
import numpy as np
from execution.engine import ExecutionEngine
from execution.risk_manager import RiskManager
from core.logger import logger
from core.trading_metrics import (
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    profit_factor,
    max_drawdown,
    max_drawdown_duration,
    value_at_risk,
    win_rate,
    avg_win_loss_ratio,
    expectancy,
    consecutive_losses,
    score_bot,
)


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

        self.trades = []
        self.equity_curve = []

    def run(self, df: pd.DataFrame, silent=False):
        if not silent:
            logger.info(f"Starting backtest with {self.initial_capital} USDT")

        pending_signal = 0
        pending_atr = 0.0
        for index, row in df.iterrows():
            current_open = row["open"]
            entered_this_candle = False

            # 1. Execute pending signal from previous candle at current OPEN
            if pending_signal == 1:
                if self.position == -1:
                    self.close_position(
                        current_open, timestamp=index, reason="Close Short"
                    )
                if self.position == 0:
                    self.execute_long(
                        current_open, timestamp=index, current_atr=pending_atr
                    )
                    entered_this_candle = True
            elif pending_signal == -1:
                if self.position == 1:
                    self.close_position(
                        current_open, timestamp=index, reason="Close Long"
                    )
                if self.position == 0:
                    self.execute_short(
                        current_open, timestamp=index, current_atr=pending_atr
                    )
                    entered_this_candle = True

            # SL Evaluation for current candle
            if not entered_this_candle:
                if self.position == 1 and self.sl_atr_multiplier > 0:
                    if row["low"] <= self.sl_price:
                        self.close_position(
                            self.sl_price, timestamp=index, reason="SL Hit"
                        )
                elif self.position == -1 and self.sl_atr_multiplier > 0:
                    if row["high"] >= self.sl_price:
                        self.close_position(
                            self.sl_price, timestamp=index, reason="SL Hit"
                        )

            # 2. Record Equity MTM
            unrealized_pnl = 0
            if self.position == 1:
                unrealized_pnl = (row["close"] - self.entry_price) * self.position_size
            elif self.position == -1:
                unrealized_pnl = (self.entry_price - row["close"]) * self.position_size

            self.equity_curve.append(
                {"timestamp": index, "equity": self.capital + unrealized_pnl}
            )

            # 3. New signal generation at candle CLOSE
            # If the strategy has given a signal, it becomes pending for NEXT candle's open
            pending_signal = row.get("signal", 0)
            pending_atr = row.get("atr", 0)

        if self.position != 0:
            last_idx = df.index[-1]
            last_price = df["close"].iloc[-1]
            self.close_position(
                last_price, timestamp=last_idx, reason="End of Backtest"
            )

        self.generate_report(silent=silent)

    def execute_long(self, price: float, **kwargs):
        timestamp = kwargs.get("timestamp")
        size = self.risk_manager.calculate_position_size(self.capital, price)
        fee = price * size * self.taker_fee
        self.capital -= fee

        current_atr = kwargs.get("current_atr", 0)
        self.position = 1
        self.entry_price = price
        self.position_size = size
        if self.sl_atr_multiplier > 0 and current_atr > 0:
            self.sl_price = price - (current_atr * self.sl_atr_multiplier)
        else:
            self.sl_price = 0.0

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
        size = self.risk_manager.calculate_position_size(self.capital, price)
        fee = price * size * self.taker_fee
        self.capital -= fee

        current_atr = kwargs.get("current_atr", 0)
        self.position = -1
        self.entry_price = price
        self.position_size = size
        if self.sl_atr_multiplier > 0 and current_atr > 0:
            self.sl_price = price + (current_atr * self.sl_atr_multiplier)
        else:
            self.sl_price = 0.0

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
            pnl = (price - self.entry_price) * self.position_size - fee
        elif self.position == -1:
            pnl = (self.entry_price - price) * self.position_size - fee

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

    def generate_report(self, silent=False):
        trades_df = pd.DataFrame(self.trades)
        close_trades = trades_df[trades_df["action"] == "CLOSE"]

        if len(close_trades) == 0:
            if not silent:
                logger.info("No trades were closed during the backtest.")
            return

        trades_pnl = close_trades["pnl"].tolist()
        equity_df = pd.DataFrame(self.equity_curve)
        equity_curve_list = equity_df["equity"].tolist()

        # Tính returns theo từng kỳ (kỳ ở đây là mỗi thay đổi trên equity curve hoặc mỗi candle)
        returns = equity_df["equity"].pct_change().fillna(0).tolist()

        # Lấy điểm số từ trading_metrics
        bot_scores = score_bot(returns, trades_pnl, equity_curve_list)

        total_pnl = close_trades["pnl"].sum()

        if silent:
            return

        print("\n=== BACKTEST REPORT ===")
        print(f"Initial Capital: {self.initial_capital:.2f} USDT")
        print(f"Final Capital:   {self.capital:.2f} USDT")
        print(
            f"Total PnL:       {total_pnl:.2f} USDT ({(self.capital/self.initial_capital - 1)*100:.2f}%)"
        )
        print(f"Total Trades:    {len(close_trades)}")
        print("-----------------------")
        print("[Nhóm 1] Lợi nhuận:")
        print(f"  - Sharpe Ratio:  {sharpe_ratio(returns):.4f}")
        print(f"  - Sortino Ratio: {sortino_ratio(returns):.4f}")
        print(f"  - Calmar Ratio:  {calmar_ratio(returns):.4f}")
        print(f"  - Profit Factor: {profit_factor(trades_pnl):.4f}")
        print("-----------------------")
        print("[Nhóm 2] Rủi ro:")
        print(f"  - Max Drawdown:          {max_drawdown(equity_curve_list)*100:.2f}%")
        print(
            f"  - Max Drawdown Duration: {max_drawdown_duration(equity_curve_list)} periods"
        )
        print(f"  - VaR (95%):             {value_at_risk(returns)*100:.4f}%")
        print("-----------------------")
        print("[Nhóm 3] Chất lượng lệnh:")
        print(f"  - Win Rate:           {win_rate(trades_pnl)*100:.2f}%")
        print(f"  - Avg Win/Loss Ratio: {avg_win_loss_ratio(trades_pnl):.2f}")
        print(f"  - Expectancy:         {expectancy(trades_pnl):.2f} USDT")
        print(f"  - Consecutive Losses: {consecutive_losses(trades_pnl)}")
        print("-----------------------")
        print("[Nhóm 4] Tổng điểm (BOT SCORE):")
        print(f"  - Profitability Score: {bot_scores['profitability_score']}/100")
        print(f"  - Risk Score:          {bot_scores['risk_score']}/100")
        print(f"  - Trade Quality Score: {bot_scores['trade_quality_score']}/100")
        print(f"  => TOTAL SCORE:        {bot_scores['total_score']}/100")
        print("=======================\n")
        print("=== LAST 10 TRADES ===")
        paired_trades = []
        open_trade = None
        for t in self.trades:
            if t["action"] in ["LONG", "SHORT"]:
                open_trade = t
            elif t["action"] == "CLOSE" and open_trade:
                paired_trades.append(
                    {
                        "entry_time": open_trade["timestamp"],
                        "exit_time": t["timestamp"],
                        "direction": open_trade["action"],
                        "entry_price": open_trade["price"],
                        "exit_price": t["price"],
                        "size": t["size"],
                        "pnl": t["pnl"],
                        "reason": t.get("reason", ""),
                    }
                )
                open_trade = None

        last_10 = paired_trades[-10:] if len(paired_trades) >= 10 else paired_trades
        for pt in last_10:
            t_in = (
                pt["entry_time"].strftime("%m-%d %H:%M")
                if hasattr(pt["entry_time"], "strftime")
                else str(pt["entry_time"])[:16]
            )
            if pt["exit_time"] == "OPEN":
                print(f"[{t_in}] OPEN {pt['direction'][:1]} @ {pt['entry_price']:.1f}")
            else:
                print(
                    f"[{t_in}] {pt['direction'][:1]} {pt['entry_price']:.1f} -> {pt['exit_price']:.1f} | PnL: {pt['pnl']:.2f}U"
                )
