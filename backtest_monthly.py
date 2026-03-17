from backtest import run_backtest
from optimize.stats import calculate_monthly_performance, format_monthly_performance

if __name__ == "__main__":
    res, trades = run_backtest()
    if trades:
        monthly_stats = calculate_monthly_performance(trades)
        print(format_monthly_performance(monthly_stats))
