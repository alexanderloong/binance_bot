import pandas as pd

class MetricsCalculator:
    """Tính toán các chỉ số thống kê từ danh sách trades."""
    @staticmethod
    def calculate(trades, final_balance, initial_balance):
        trade_cycles = []
        current_trade_pnl = 0
        is_open = False

        for t in trades:
            if "OPEN" in t["type"]:
                current_trade_pnl = t["pnl"]  # Entry fee
                is_open = True
            elif any(x in t["type"] for x in ["CLOSE", "FINAL_CLOSE", "LIQUIDATION", "STOP_LOSS"]):
                current_trade_pnl += t["pnl"]
                if is_open:
                    trade_cycles.append(current_trade_pnl)
                    is_open = False

        total_trades_count = len(trade_cycles)
        wins = sum(1 for pnl in trade_cycles if pnl > 0)
        win_rate = (wins / total_trades_count * 100) if total_trades_count > 0 else 0
        pnl_total = final_balance - initial_balance
        pnl_pct = (pnl_total / initial_balance) * 100

        # Max Drawdown
        curr_equity = initial_balance
        peak = initial_balance
        mdd = 0
        for t in trades:
            if "pnl" in t:
                curr_equity += t["pnl"]
                peak = max(peak, curr_equity)
                drawdown = (peak - curr_equity) / peak
                mdd = max(mdd, drawdown)

        # Profit Factor
        gross_profit = sum(p for p in trade_cycles if p > 0)
        gross_loss = abs(sum(p for p in trade_cycles if p < 0))
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 0)
        )

        # Calmar Ratio = Annualized PnL / Max Drawdown
        days_elapsed = 1
        if trades:
            first_time = trades[0]["time"]
            last_time = trades[-1]["time"]
            if isinstance(first_time, pd.Timestamp) and isinstance(last_time, pd.Timestamp):
                delta = last_time - first_time
                days_elapsed = max(delta.days, 1)
        annualized_pnl_pct = pnl_pct * (365 / days_elapsed)
        calmar_ratio = (
            annualized_pnl_pct / (mdd * 100)
            if mdd > 0
            else float("inf") if annualized_pnl_pct > 0 else 0
        )

        return {
            "final_balance": final_balance,
            "pnl_pct": pnl_pct,
            "total_trades": total_trades_count,
            "win_rate": win_rate,
            "max_drawdown": mdd * 100,
            "profit_factor": profit_factor,
            "calmar_ratio": calmar_ratio,
            "annualized_pnl_pct": annualized_pnl_pct,
        }
