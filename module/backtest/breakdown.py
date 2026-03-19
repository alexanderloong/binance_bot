import pandas as pd

class BacktestBreakdown:
    """Tạo bảng thống kê PnL theo từng tháng và năm từ lịch sử giao dịch.
    Sử dụng True Compounding Equity để tính % Return."""
    
    @staticmethod
    def generate_breakdown(trades, initial_balance=1000.0):
        if not trades:
            return "No trades to breakdown."

        df_trades = pd.DataFrame(trades)
        
        if "time" not in df_trades.columns or "pnl" not in df_trades.columns:
            return "Invalid trade format for breakdown."

        df_trades['time'] = pd.to_datetime(df_trades['time'])
        df_trades['pnl'] = df_trades.get('pnl', 0.0).fillna(0.0)
        df_trades = df_trades.sort_values("time")
        
        # Get start-of-month equity by grouping
        df_trades['year_month'] = df_trades['time'].dt.to_period('M')
        
        monthly_grouped = df_trades.groupby('year_month').agg(
            pnl_sum=('pnl', 'sum')
        )
        
        res_records = []
        current_equity = initial_balance
        for ym, row in monthly_grouped.iterrows():
            pnl = row['pnl_sum']
            # Return is pnl / current equity at start of month
            ret_pct = (pnl / current_equity) * 100
            current_equity += pnl # update for next month
            
            res_records.append({
                "year": ym.year,
                "month": ym.month,
                "ret_pct": ret_pct
            })
            
        res_df = pd.DataFrame(res_records)
        
        # Pivot table: Dòng = Năm, Cột = Tháng
        pivot = res_df.pivot(index='year', columns='month', values='ret_pct')
        pivot = pivot.reindex(columns=range(1, 13))
        
        # Tính tổng năm (Compounding: (1+r1)*(1+r2)... - 1)
        pivot['Yearly'] = ((1 + pivot.fillna(0) / 100).prod(axis=1) - 1) * 100
        
        # Vẽ bảng Text
        lines = []
        lines.append("="*105)
        lines.append("📅 MONTHLY & YEARLY RETURN BREAKDOWN (% Compounding Equity)")
        lines.append("="*105)
        
        # Dựng Header
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        header = f"{'Year':<5} | " + " | ".join([f"{m:>5}" for m in month_names]) + f" | {'Total':>7}"
        lines.append(header)
        lines.append("-" * len(header))
        
        # Dựng từng dòng Năm
        for year in pivot.index:
            row_str = f"{year:<5} | "
            month_strs = []
            for month in range(1, 13):
                val = pivot.loc[year, month]
                if pd.isna(val):
                    month_strs.append(f"{'-':>5}")
                else:
                    month_strs.append(f"{val:>5.1f}")
            
            yearly_val = pivot.loc[year, 'Yearly']
            row_str += " | ".join(month_strs) + f" | {yearly_val:>7.1f}%"
            lines.append(row_str)
            
        lines.append("="*105)
        return "\n".join(lines)
