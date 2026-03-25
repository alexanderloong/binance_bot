import pandas as pd
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

class BacktestReporter:
    @staticmethod
    def generate_report(initial_capital: float, final_capital: float, trades: list, equity_curve: list, silent: bool = False):
        trades_df = pd.DataFrame(trades)
        if trades_df.empty:
            if not silent:
                logger.info("No trades were executed during the backtest.")
            return

        close_trades = trades_df[trades_df["action"] == "CLOSE"]

        if len(close_trades) == 0:
            if not silent:
                logger.info("No trades were closed during the backtest.")
            return

        trades_pnl = close_trades["pnl"].tolist()
        equity_df = pd.DataFrame(equity_curve)
        equity_curve_list = equity_df["equity"].tolist()

        # Tính returns theo từng kỳ (kỳ ở đây là mỗi thay đổi trên equity curve hoặc mỗi candle)
        returns = equity_df["equity"].pct_change().fillna(0).tolist()

        # Lấy điểm số từ trading_metrics
        bot_scores = score_bot(returns, trades_pnl, equity_curve_list)

        total_pnl = close_trades["pnl"].sum()
        
        try:
            start_time = pd.to_datetime(equity_df["timestamp"].iloc[0])
            end_time = pd.to_datetime(equity_df["timestamp"].iloc[-1])
            days = (end_time - start_time).total_seconds() / 86400.0
            days = max(days, 1)
        except Exception:
            days = 1
            
        avg_trades_per_day = len(close_trades) / days

        if silent:
            return

        print("\n=== BACKTEST REPORT ===")
        print(f"Initial Capital: {initial_capital:.2f} USDT")
        print(f"Final Capital:   {final_capital:.2f} USDT")
        print(
            f"Total PnL:       {total_pnl:.2f} USDT ({(final_capital/initial_capital - 1)*100:.2f}%)"
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
        print(f"  - Avg Trades/Day:     {avg_trades_per_day:.2f}")
        print("-----------------------")
        print("[Nhóm 4] Tổng điểm (BOT SCORE):")
        print(f"  - Profitability Score: {bot_scores['profitability_score']:.4f}/100")
        print(f"  - Risk Score:          {bot_scores['risk_score']:.4f}/100")
        print(f"  - Trade Quality Score: {bot_scores['trade_quality_score']:.4f}/100")
        print(f"  => TOTAL SCORE:        {bot_scores['total_score']:.4f}/100")
        print("=======================\n")
        print("=== LAST 10 TRADES ===")
        paired_trades = []
        open_trade = None
        for t in trades:
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
