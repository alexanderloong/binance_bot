import pandas as pd


class BacktestBreakdown:
    """
    Bảng thống kê PnL theo tháng và năm từ lịch sử giao dịch.
    Dùng True Compounding Equity để tính % Return.
    """

    @staticmethod
    def generate_breakdown(trades, initial_balance=1000.0):
        if not trades:
            return "No trades to breakdown."

        df_trades = pd.DataFrame(trades)

        if "time" not in df_trades.columns or "pnl" not in df_trades.columns:
            return "Invalid trade format for breakdown."

        df_trades["time"] = pd.to_datetime(df_trades["time"])
        df_trades["pnl"] = df_trades["pnl"].fillna(0.0)
        df_trades = df_trades.sort_values("time").reset_index(drop=True)

        # FIX: timezone-aware timestamps cannot be converted to Period directly
        # in newer pandas without a UserWarning. Remove tz info first.
        df_trades["year_month"] = (
            df_trades["time"]
            .dt.tz_convert(
                None
            )  # strip tz cleanly (vs tz_localize(None) which errors on aware)
            .dt.to_period("M")
        )

        monthly_grouped = df_trades.groupby("year_month").agg(pnl_sum=("pnl", "sum"))

        res_records = []
        current_equity = initial_balance
        for ym, row in monthly_grouped.iterrows():
            pnl = row["pnl_sum"]
            ret_pct = (pnl / current_equity) * 100 if current_equity != 0 else 0.0
            current_equity += pnl
            res_records.append({"year": ym.year, "month": ym.month, "ret_pct": ret_pct})

        if not res_records:
            return "No monthly data to display."

        res_df = pd.DataFrame(res_records)
        pivot = res_df.pivot(index="year", columns="month", values="ret_pct")
        pivot = pivot.reindex(columns=range(1, 13))

        # Yearly compound return: (1+r1)(1+r2)... - 1
        pivot["Yearly"] = ((1 + pivot.fillna(0) / 100).prod(axis=1) - 1) * 100

        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        lines = []
        lines.append("=" * 110)
        lines.append("📅 MONTHLY & YEARLY RETURN BREAKDOWN (% Compounding Equity)")
        lines.append("=" * 110)

        header = (
            f"{'Year':<5} | "
            + " | ".join([f"{m:>5}" for m in month_names])
            + f" | {'Yearly':>7}"
        )
        lines.append(header)
        lines.append("-" * len(header))

        for year in pivot.index:
            row_str = f"{year:<5} | "
            month_strs = []
            for month in range(1, 13):
                val = pivot.loc[year, month]
                if pd.isna(val):
                    month_strs.append(f"{'—':>5}")
                else:
                    sign = "+" if val > 0 else ""
                    month_strs.append(f"{sign}{val:>4.1f}")
            yearly_val = pivot.loc[year, "Yearly"]
            yearly_sign = "+" if yearly_val > 0 else ""
            row_str += " | ".join(month_strs) + f" | {yearly_sign}{yearly_val:>6.1f}%"
            lines.append(row_str)

        lines.append("=" * 110)
        return "\n".join(lines)
