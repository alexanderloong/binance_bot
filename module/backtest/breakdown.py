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

        df_trades["year_month"] = (
            df_trades["time"].dt.tz_convert(None).dt.to_period("M")
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
        pivot["Yearly"] = ((1 + pivot.fillna(0) / 100).prod(axis=1) - 1) * 100

        MONTH_ABBR = [
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

        def fmt_cell(val, width=6):
            """Format a monthly return cell with colour-coded sign indicator."""
            if pd.isna(val):
                return f"{'·':>{width}}"
            sign = "+" if val >= 0 else ""
            return f"{sign}{val:.1f}".rjust(width)

        def fmt_yearly(val):
            sign = "+" if val >= 0 else ""
            return f"{sign}{val:.1f}%".rjust(8)

        # ── Column widths ──────────────────────────────────────────────
        COL_W = 7  # month columns
        YEAR_W = 4
        SEP = " │ "
        EDGE = "│"

        # Header
        month_header = SEP.join(f"{m:>{COL_W}}" for m in MONTH_ABBR)
        header = f"  {'Year':>{YEAR_W}} {EDGE} {month_header} {EDGE} {'Yearly':>8}"
        divider_len = len(header)

        lines = []
        lines.append("╔" + "═" * (divider_len + 2) + "╗")
        lines.append(
            f"║  📅  MONTHLY & YEARLY RETURN BREAKDOWN  (% of Compounding Equity){'':>{divider_len - 63}}║"
        )
        lines.append("╠" + "═" * (divider_len + 2) + "╣")
        lines.append(f"║ {header} ║")
        lines.append("╠" + "═" * (divider_len + 2) + "╣")

        for year in pivot.index:
            cells = []
            for month in range(1, 13):
                val = pivot.loc[year, month]
                cells.append(fmt_cell(val, COL_W))
            month_row = SEP.join(cells)
            yearly_val = pivot.loc[year, "Yearly"]
            row = (
                f"  {year:>{YEAR_W}} {EDGE} {month_row} {EDGE} {fmt_yearly(yearly_val)}"
            )
            lines.append(f"║ {row} ║")

        lines.append("╚" + "═" * (divider_len + 2) + "╝")
        return "\n".join(lines)
