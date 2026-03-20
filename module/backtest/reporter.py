import os
import time
import pandas as pd
from config import CONSOLE_TRADE_LIMIT
from module.backtest.breakdown import BacktestBreakdown


class BacktestReporter:
    """Xử lý output, in kết quả và lưu log ra file."""

    @staticmethod
    def log_results(res, trades, df):
        log_dir = "resource/backtest_logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"backtest_{timestamp}.txt")
        log_lines = []

        def app_log(msg):
            print(msg)
            log_lines.append(str(msg))

        total_trades_count = len(trades)
        print(
            f"--- Trade History (Showing last {CONSOLE_TRADE_LIMIT}, full log saved to file) ---"
        )
        log_lines.append("--- Trade History ---")

        for i, t in enumerate(trades):
            time_str = t["time"]
            if isinstance(time_str, pd.Timestamp):
                time_str = time_str.strftime("%Y-%m-%d %H:%M")

            type_str = t["type"]
            price = t["price"]
            pnl = t.get("pnl", 0)
            amount = t.get("amount", 0)

            log_msg = f"[{time_str}] {type_str:<16} at {price:>10.2f}"
            if amount > 0:
                log_msg += f", Amt: {amount:>8.4f}"
            if pnl != 0:
                pnl_label = "Fee" if "OPEN" in type_str else "PnL"
                sign = "+" if pnl > 0 else ""
                log_msg += f", {pnl_label}: {sign}{pnl:>8.2f} USDT"

            log_lines.append(log_msg)
            if (
                CONSOLE_TRADE_LIMIT <= 0
                or (total_trades_count - i) <= CONSOLE_TRADE_LIMIT
            ):
                print(log_msg)

        app_log("")
        app_log("=" * 50)
        app_log("📊 BACKTEST RESULTS SUMMARY")
        app_log("=" * 50)

        # FIX: reconstruct initial_balance properly and display it
        pnl_pct = res.get("pnl_pct", 0)
        if pnl_pct != -100:
            initial_balance = res["final_balance"] / (1 + pnl_pct / 100)
        else:
            initial_balance = 1000.0

        app_log(f"Initial Balance:   {initial_balance:.2f} USDT")
        app_log(f"Final Balance:     {res['final_balance']:.2f} USDT")

        pnl_sign = "+" if pnl_pct >= 0 else ""
        app_log(f"Total PnL:         {pnl_sign}{pnl_pct:.2f}%")
        app_log(f"Annualized (CAGR): {pnl_sign}{res['annualized_pnl_pct']:.2f}%")
        app_log(f"")
        app_log(
            f"Win Rate:          {res['win_rate']:.1f}%  ({res['total_trades']} closed trades)"
        )
        app_log(f"Avg Win:           +{res['avg_win']:.2f} USDT")
        app_log(f"Avg Loss:           {res['avg_loss']:.2f} USDT")
        app_log(f"Expectancy:        {res['expectancy']:+.2f} USDT / trade")
        app_log(f"")
        app_log(f"Profit Factor:     {res['profit_factor']:.2f}")
        app_log(f"Max Drawdown:     -{res['max_drawdown']:.2f}%")
        app_log(f"Calmar Ratio:      {res['calmar_ratio']:.2f}")
        app_log(f"Sharpe Ratio:      {res['sharpe_ratio']:.2f}")

        if not df.empty:
            start_time = df.iloc[0]["timestamp"]
            end_time = df.iloc[-1]["timestamp"]
            total_days = max((end_time - start_time).days, 1)
            avg_per_day = res["total_trades"] / total_days
            app_log(f"")
            app_log(
                f"Data Range:        {start_time.strftime('%Y-%m-%d')} → {end_time.strftime('%Y-%m-%d')} ({total_days} days)"
            )
            app_log(f"Avg Trades/Day:    {avg_per_day:.2f}")

        app_log("=" * 50)
        app_log("")

        breakdown_str = BacktestBreakdown.generate_breakdown(
            trades, initial_balance=initial_balance
        )
        for line in breakdown_str.split("\n"):
            app_log(line)
        app_log("")

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
            print(f"\n✅ Backtest log saved to: {log_file}")
        except Exception as e:
            print(f"\n❌ Failed to save log: {e}")
