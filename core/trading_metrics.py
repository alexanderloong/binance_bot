import numpy as np
import pandas as pd

# ==============================================================================
# NHÓM 1: LỢI NHUẬN
# ==============================================================================

def sharpe_ratio(returns, risk_free=0.02):
    """Tính Sharpe Ratio. Giả định biến returns và risk_free đã cùng khung thời gian."""
    if len(returns) == 0:
        return 0.0
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    if std_return == 0:
        return 0.0
    return (mean_return - risk_free) / std_return

def sortino_ratio(returns, risk_free=0.02):
    """Tính Sortino Ratio."""
    if len(returns) == 0:
        return 0.0
    mean_return = np.mean(returns)
    negative_returns = [r for r in returns if r < 0]
    downside_std = np.std(negative_returns) if len(negative_returns) > 0 else 0.0
    if downside_std == 0:
        return 0.0
    return (mean_return - risk_free) / downside_std

def calmar_ratio(returns):
    """Tính Calmar Ratio = Tỷ suất sinh lời / Max Drawdown."""
    if len(returns) == 0:
        return 0.0
    
    cumulative_returns = np.cumsum(returns)
    # Tạo equity curve ảo xuất phát từ 1 để tính Max Drawdown
    equity_curve = 1 + cumulative_returns
    total_return = cumulative_returns[-1] if len(cumulative_returns) > 0 else 0
    
    md = max_drawdown(equity_curve)
    if md == 0:
        return 0.0
    return total_return / md

def profit_factor(trades_pnl):
    """Tính Profit Factor = Tổng lãi / Tổng lỗ."""
    gross_profit = sum(p for p in trades_pnl if p > 0)
    gross_loss = abs(sum(p for p in trades_pnl if p < 0))
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss

# ==============================================================================
# NHÓM 2: RỦI RO
# ==============================================================================

def max_drawdown(equity_curve):
    """Tính Max Drawdown từ đường cong vốn."""
    if len(equity_curve) < 2:
        return 0.0
    
    peak = equity_curve[0]
    md = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        # Drawdown được tính bằng định mức phần trăm giảm từ đỉnh
        drawdown = (peak - equity) / peak if peak > 0 else 0
        if drawdown > md:
            md = drawdown
    return md

def max_drawdown_duration(equity_curve):
    """Tính thời gian Drawdown dài nhất (số kỳ/nến/lệnh)."""
    if len(equity_curve) < 2:
        return 0
    
    peak = equity_curve[0]
    max_duration = 0
    current_duration = 0
    
    for equity in equity_curve:
        if equity >= peak:
            peak = equity
            if current_duration > max_duration:
                max_duration = current_duration
            current_duration = 0
        else:
            current_duration += 1
            
    if current_duration > max_duration:
        max_duration = current_duration
        
    return max_duration

def value_at_risk(returns, confidence=0.95):
    """Tính Value at Risk (VaR) dựa trên lịch sử lợi nhuận."""
    if len(returns) == 0:
        return 0.0
    # Lấy phân vị thứ (100 - confidence*100)
    return abs(np.percentile(returns, 100 - (confidence * 100)))

# ==============================================================================
# NHÓM 3: CHẤT LƯỢNG LỆNH
# ==============================================================================

def win_rate(trades_pnl):
    """Tính Tỷ lệ Thắng (Win Rate)."""
    if len(trades_pnl) == 0:
        return 0.0
    wins = len([p for p in trades_pnl if p > 0])
    return wins / len(trades_pnl)

def avg_win_loss_ratio(trades_pnl):
    """Tính Tỷ lệ Lãi/Lỗ trung bình (Reward/Risk Ratio)."""
    wins = [p for p in trades_pnl if p > 0]
    losses = [p for p in trades_pnl if p < 0]
    
    avg_win = np.mean(wins) if len(wins) > 0 else 0
    avg_loss = abs(np.mean(losses)) if len(losses) > 0 else 0
    
    if avg_loss == 0:
        return float('inf') if avg_win > 0 else 0.0
    return avg_win / avg_loss

def expectancy(trades_pnl):
    """Tính Kỳ vọng toán học (Expectancy) của trung bình một lệnh."""
    if len(trades_pnl) == 0:
        return 0.0
    return np.mean(trades_pnl)

def consecutive_losses(trades_pnl):
    """Tính số lệnh thua lỗ liên tiếp tối đa."""
    max_consecutive = 0
    current = 0
    for p in trades_pnl:
        if p < 0:
            current += 1
            if current > max_consecutive:
                max_consecutive = current
        else:
            current = 0
    return max_consecutive

# ==============================================================================
# NHÓM 4: TỔNG ĐIỂM
# ==============================================================================

def score_bot(returns, trades_pnl, equity_curve):
    """
    Trả về dictionary điểm 0-100 cho từng nhóm và tổng điểm (Total Score).
    Điểm số được heuristic (nội suy 0-100) dựa trên các chỉ số tài chính thông dụng.
    """
    if not isinstance(returns, (list, np.ndarray, pd.Series)):
        returns = np.array(returns)
    if not isinstance(trades_pnl, (list, np.ndarray, pd.Series)):
        trades_pnl = np.array(trades_pnl)
    if not isinstance(equity_curve, (list, np.ndarray, pd.Series)):
        equity_curve = np.array(equity_curve)
        
    # Lấy các chỉ số đại diện
    sr = sharpe_ratio(returns, risk_free=0.0)
    pf = profit_factor(trades_pnl)
    md = max_drawdown(equity_curve)
    wr = win_rate(trades_pnl)
    awlr = avg_win_loss_ratio(trades_pnl)
    
    # 1. Điểm Lợi nhuận (Tối đa 100)
    # Sharpe = 2.0 -> 50 điểm, Profit Factor = 2.5 -> 50 điểm
    score_profit = 0.0
    if sr > 0:
        score_profit += min((sr / 2.0) * 50, 50)
    if pf != float('inf') and pf > 1.0:
        score_profit += min(((pf - 1.0) / 1.5) * 50, 50)
    elif pf == float('inf'):
        score_profit += 50
    score_profit = max(0.0, min(100.0, score_profit))

    # 2. Điểm Rủi ro (Tối đa 100) 
    # MD < 5% -> 100, MD > 30% -> 0
    if md <= 0.05:
        score_risk = 100.0
    elif md >= 0.30:
        score_risk = 0.0
    else:
        score_risk = 100.0 - ((md - 0.05) / 0.25) * 100.0
    score_risk = max(0.0, min(100.0, score_risk))
    
    # 3. Điểm Chất lượng lệnh (Tối đa 100)
    # Win rate 60% -> 50 điểm, RL 2.0 -> 50 điểm
    score_tq = 0.0
    score_tq += min((wr / 0.6) * 50, 50)
    if awlr != float('inf') and awlr > 0:
        score_tq += min((awlr / 2.0) * 50, 50)
    elif awlr == float('inf'):
        score_tq += 50
    score_tq = max(0.0, min(100.0, score_tq))
    
    # 4. Tổng điểm (Trọng số: Lợi nhuận 40%, Rủi ro 40%, CL Lệnh 20%)
    total_score = 0.4 * score_profit + 0.4 * score_risk + 0.2 * score_tq
    
    return {
        "profitability_score": score_profit,
        "risk_score": score_risk,
        "trade_quality_score": score_tq,
        "total_score": total_score
    }
