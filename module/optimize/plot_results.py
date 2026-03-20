import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path to import modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from module.backtest.orchestrator import get_backtest_data, simulate
from module.bot.data_processor import DataProcessor
from resource.config import EMA_LENGTH, VOLUME_MA_LENGTH


def plot_performance(df=None, trades=None, res=None):
    # 1. Get Data and Run Simulation (if not provided)
    if df is None or trades is None or res is None:
        print("🔄 Loading data and running simulation...")
        df = get_backtest_data()
        if df is None:
            print("❌ No data found.")
            return

        # Calculate indicators needed for simulation
        df_ha = DataProcessor.calculate_heikin_ashi(df)
        df_st = DataProcessor.calculate_supertrend(df_ha)
        df_st[f"EMA_{EMA_LENGTH}"] = DataProcessor.calculate_ema(
            df_st, length=EMA_LENGTH
        )[f"EMA_{EMA_LENGTH}"]
        df_st = DataProcessor.calculate_volume_ma(df_st, length=VOLUME_MA_LENGTH)

        # Run simulation
        res, trades = simulate(df_st, use_ema_filter=True, use_volume_filter=True)

    else:
        # If passed in, 'df' IS the final dataframe (already processed)
        df_st = df

    if not trades:
        print("❌ No trades executed.")
        return

    # 2. Prepare Data for Plotting

    # We need to reconstruct the equity curve over time
    running_balance = 1000
    equity_data = [{"time": df["timestamp"].iloc[0], "balance": 1000}]

    for t in trades:
        if "pnl" in t:
            running_balance += t["pnl"]
            equity_data.append({"time": t["time"], "balance": running_balance})

    equity_df = pd.DataFrame(equity_data)
    equity_df["time"] = pd.to_datetime(equity_df["time"])
    equity_df = equity_df.sort_values("time")

    # 3. Create Plots
    sns.set_theme(style="darkgrid")
    fig, (ax1, ax2, ax3) = plt.subplots(
        3,
        1,
        figsize=(14, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1.5, 0.8]},
    )

    # Plot 1: Price Chart
    ax1.plot(
        df_st["timestamp"],
        df_st["close"],
        color="#1f77b4",
        linewidth=1,
        label="BTC/USDT Price",
    )
    ax1.set_title("BTC/USDT Price Chart", fontsize=14, fontweight="bold", pad=15)
    ax1.set_ylabel("Price (USDT)", fontsize=12)
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Equity Curve
    ax2.plot(
        equity_df["time"],
        equity_df["balance"],
        color="#00ff88",
        linewidth=1.5,
        label="Equity (USDT)",
    )
    ax2.axhline(
        y=1000, color="gray", linestyle="--", alpha=0.5, label="Initial Balance"
    )

    # Add peak annotation
    max_bal = equity_df["balance"].max()
    max_idx = equity_df["balance"].idxmax()
    max_date = equity_df.loc[max_idx, "time"]
    ax2.scatter(max_date, max_bal, color="white", s=30, zorder=5)
    ax2.annotate(
        f"Peak: ${max_bal:.2f}",
        xy=(max_date, max_bal),
        xytext=(10, 10),
        textcoords="offset points",
        color="white",
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="#00aa55", ec="none", alpha=0.8),
    )

    ax2.set_title(
        "Strategy Performance: Equity Curve", fontsize=14, fontweight="bold", pad=15
    )
    ax2.set_ylabel("Balance (USDT)", fontsize=12)
    ax2.legend(loc="upper left")

    # Color area under curve
    ax2.fill_between(
        equity_df["time"],
        equity_df["balance"],
        1000,
        where=(equity_df["balance"] >= 1000),
        color="#00ff88",
        alpha=0.1,
        interpolate=True,
    )
    ax2.fill_between(
        equity_df["time"],
        equity_df["balance"],
        1000,
        where=(equity_df["balance"] < 1000),
        color="#ff4444",
        alpha=0.1,
        interpolate=True,
    )

    # Plot 3: Drawdown
    # Calculate rolling max
    equity_df["peak"] = equity_df["balance"].cummax()
    equity_df["drawdown"] = (
        (equity_df["balance"] - equity_df["peak"]) / equity_df["peak"] * 100
    )

    ax3.plot(equity_df["time"], equity_df["drawdown"], color="#ff4444", linewidth=1)
    ax3.fill_between(
        equity_df["time"], equity_df["drawdown"], 0, color="#ff4444", alpha=0.2
    )
    ax3.set_title("Drawdown (%)", fontsize=12)
    ax3.set_ylabel("Drawdown %", fontsize=12)
    ax3.set_xlabel("Date", fontsize=12)

    # Stats Text Box
    stats_text = (
        f"Final Balance: ${res['final_balance']:.2f}\n"
        f"Total Return: {res['pnl_pct']:.2f}%\n"
        f"Win Rate: {res['win_rate']:.1f}%\n"
        f"Profit Factor: {res['profit_factor']:.2f}\n"
        f"Max Drawdown: {res['max_drawdown']:.2f}%"
    )
    plt.figtext(
        0.15,
        0.12,
        stats_text,
        fontsize=10,
        bbox=dict(facecolor="white", alpha=0.8, boxstyle="round"),
    )

    plt.tight_layout()

    # Ensure resource directory exists
    resource_dir = "resource"
    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir)

    output_file = os.path.join(resource_dir, "performance_summary.png")
    plt.savefig(output_file, dpi=300)
    print(f"✅ Performance chart saved to {output_file}")
    # plt.show() # Cannot show in headless env


if __name__ == "__main__":
    plot_performance()
