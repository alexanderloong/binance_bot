import pandas as pd

def calculate_monthly_performance(trades):
    monthly_cycles = {}
    monthly_pnl = {}
    
    current_cycle_pnl = 0
    is_cycle_open = False
    
    for t in trades:
        time_val = t['time']
        if isinstance(time_val, pd.Timestamp):
            month_str = time_val.strftime('%Y-%m')
        else:
            month_str = pd.to_datetime(time_val).strftime('%Y-%m')
            
        if month_str not in monthly_pnl:
            monthly_pnl[month_str] = 0.0
            monthly_cycles[month_str] = []
            
        if 'pnl' in t:
            monthly_pnl[month_str] += t['pnl']
            
        if 'OPEN' in t['type']:
            current_cycle_pnl = t['pnl']
            is_cycle_open = True
        elif 'PARTIAL' in t['type']:
            if is_cycle_open:
                current_cycle_pnl += t['pnl']
        elif any(x in t['type'] for x in ['CLOSE', 'STOP_LOSS', 'FINAL_CLOSE', 'LIQUIDATION', 'TAKE_PROFIT_ROI']):
            current_cycle_pnl += t['pnl']
            if is_cycle_open:
                monthly_cycles[month_str].append(current_cycle_pnl)
                is_cycle_open = False

    monthly_stats = []
    for month in sorted(monthly_pnl.keys()):
        m_pnl = monthly_pnl[month]
        cycles = monthly_cycles[month]
        m_trades = len(cycles)
        m_win_rate = (sum(1 for p in cycles if p > 0) / m_trades * 100) if m_trades > 0 else 0.0
        
        monthly_stats.append({
            'month': month,
            'pnl': m_pnl,
            'trades': m_trades,
            'win_rate': m_win_rate
        })
        
    return monthly_stats

def format_monthly_performance(monthly_stats):
    lines = ["\n--- Monthly Performance ---"]
    for stat in monthly_stats:
        lines.append(f"[{stat['month']}] PnL: {stat['pnl']:>8.2f} USDT | Trades: {stat['trades']:>3} | Win Rate: {stat['win_rate']:>5.1f}%")
    return "\n".join(lines)
