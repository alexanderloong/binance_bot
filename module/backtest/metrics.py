import pandas as pd
import math


class MetricsCalculator:
    """
    Tính toán các chỉ số thống kê từ danh sách trades.

    Trade cycle model:
        Một cycle = OPEN_* → (optional STOP_LOSS / BE_STOP / LIQUIDATION) hoặc CLOSE_* / FINAL_CLOSE
        PnL của cycle = entry_fee (âm, lưu trong OPEN) + exit pnl
    """

    @staticmethod
    def calculate(trades, final_balance, initial_balance):
        trade_cycles = []
        current_trade_pnl = 0.0
        is_open = False

        EXIT_TYPES = {"CLOSE", "FINAL_CLOSE", "LIQUIDATION", "STOP_LOSS", "BE_STOP"}

        for t in trades:
            t_type = t["type"]
            if "OPEN" in t_type:
                current_trade_pnl = t["pnl"]  # entry fee (negative)
                is_open = True
            elif any(x in t_type for x in EXIT_TYPES):
                if is_open:
                    current_trade_pnl += t["pnl"]
                    trade_cycles.append(current_trade_pnl)
                    is_open = False
                    current_trade_pnl = 0.0

        total_trades_count = len(trade_cycles)
        wins = sum(1 for pnl in trade_cycles if pnl > 0)
        win_rate = (wins / total_trades_count * 100) if total_trades_count > 0 else 0.0

        pnl_total = final_balance - initial_balance
        pnl_pct = (pnl_total / initial_balance) * 100

        # ------------------------------------------------------------------
        # Max Drawdown (peak-to-trough on running equity)
        # ------------------------------------------------------------------
        curr_equity = initial_balance
        peak = initial_balance
        mdd = 0.0
        for t in trades:
            curr_equity += t.get("pnl", 0.0)
            if curr_equity > peak:
                peak = curr_equity
            if peak > 0:
                drawdown = (peak - curr_equity) / peak
                mdd = max(mdd, drawdown)

        # ------------------------------------------------------------------
        # Profit Factor
        # ------------------------------------------------------------------
        gross_profit = sum(p for p in trade_cycles if p > 0)
        gross_loss = abs(sum(p for p in trade_cycles if p < 0))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        # ------------------------------------------------------------------
        # CAGR (Compound Annual Growth Rate)
        # FIX: guard against negative final_balance before raising to a
        # fractional power (math domain error when balance < 0).
        # ------------------------------------------------------------------
        days_elapsed = 1
        if trades:
            first_time = trades[0]["time"]
            last_time = trades[-1]["time"]
            if isinstance(first_time, pd.Timestamp) and isinstance(
                last_time, pd.Timestamp
            ):
                delta = last_time - first_time
                days_elapsed = max(delta.days, 1)

        if final_balance > 0 and initial_balance > 0:
            cagr = (final_balance / initial_balance) ** (365.0 / days_elapsed) - 1
        else:
            cagr = -1.0  # total loss
        annualized_pnl_pct = cagr * 100

        # ------------------------------------------------------------------
        # Sharpe Ratio (annualised, per-trade returns, rf=0)
        # ------------------------------------------------------------------
        sharpe = 0.0
        if len(trade_cycles) >= 2:
            import statistics

            mean_r = statistics.mean(trade_cycles)
            std_r = statistics.stdev(trade_cycles)
            if std_r > 0:
                # Scale to annual: assume ~252 trading days, trades_per_day proxy
                trades_per_year = (
                    total_trades_count / (days_elapsed / 365.0)
                    if days_elapsed > 0
                    else total_trades_count
                )
                sharpe = (mean_r / std_r) * math.sqrt(trades_per_year)

        # ------------------------------------------------------------------
        # Calmar Ratio = CAGR / Max Drawdown
        # ------------------------------------------------------------------
        mdd_pct = mdd * 100
        if mdd_pct > 0:
            calmar_ratio = annualized_pnl_pct / mdd_pct
        elif annualized_pnl_pct > 0:
            calmar_ratio = float("inf")
        else:
            calmar_ratio = 0.0

        # ------------------------------------------------------------------
        # Average Win / Loss
        # ------------------------------------------------------------------
        winning_trades = [p for p in trade_cycles if p > 0]
        losing_trades = [p for p in trade_cycles if p < 0]
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
        # Expectancy per trade
        expectancy = (
            (win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss
            if total_trades_count > 0
            else 0.0
        )

        return {
            "final_balance": final_balance,
            "pnl_pct": pnl_pct,
            "total_trades": total_trades_count,
            "win_rate": win_rate,
            "max_drawdown": mdd_pct,
            "profit_factor": profit_factor,
            "calmar_ratio": calmar_ratio,
            "annualized_pnl_pct": annualized_pnl_pct,
            "sharpe_ratio": sharpe,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
        }
