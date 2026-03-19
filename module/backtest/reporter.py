import os
import time
import pandas as pd

class BacktestReporter:
    """Xử lý output, in kết quả và lưu log ra file."""
    
    @staticmethod
    def log_results(res, trades, df):
        log_dir = "resource/backtest_logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"backtest_{timestamp}.txt")
        log_lines = []

        def app_log(msg):
            print(msg)
            log_lines.append(str(msg))

        app_log("--- Trade History ---")
        for t in trades:
            time_str = t["time"]
            if isinstance(time_str, pd.Timestamp):
                time_str = time_str.strftime("%Y-%m-%d %H:%M")

            type_str = t["type"]
            price = t["price"]
            pnl = t.get("pnl", 0)
            amount = t.get("amount", 0)

            log_msg = f"[{time_str}] {type_str:<12} at {price:>10.2f}"
            if amount > 0:
                log_msg += f", Amt: {amount:>8.4f}"
            if pnl != 0:
                pnl_label = "Fee" if "OPEN" in type_str else "PnL"
                log_msg += f", {pnl_label}: {pnl:>8.2f} USDT"

            app_log(log_msg)

        app_log(f"\nFinal Balance: {res['final_balance']:.2f} USDT")
        app_log(f"Total PnL: {res['pnl_pct']:.2f}%")
        app_log(f"Annualized PnL: {res['annualized_pnl_pct']:.2f}%")
        app_log(f"Win Rate: {res['win_rate']:.1f}% ({res['total_trades']} trades)")
        app_log(f"Profit Factor: {res['profit_factor']:.2f}")
        app_log(f"Max Drawdown: {res['max_drawdown']:.2f}%")
        app_log(f"Calmar Ratio: {res['calmar_ratio']:.2f}")

        if not df.empty:
            start_time = df.iloc[0]["timestamp"]
            end_time = df.iloc[-1]["timestamp"]
            total_days = (end_time - start_time).days
            avg_trades_per_day = res["total_trades"] / total_days if total_days > 0 else 0
            app_log(f"Data Range: {start_time} -> {end_time} ({total_days} days)")
            app_log(f"Avg Trades/Day: {avg_trades_per_day:.2f}")

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines))
            print(f"\n✅ Backtest logs saved to: {log_file}")
        except Exception as e:
            print(f"\n❌ Failed to save log file: {e}")
