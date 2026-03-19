# Optimization Files Summary

This directory contains individual optimization scripts for each parameter of the trading strategy.

> **Version:** 1.15.0 | **Updated:** 2026-02-06

## 📁 Individual Parameter Optimization Files

### Trend Indicators
- **optimize_ema.py** - Optimizes EMA length (trend baseline)
- **optimize_supertrend_length.py** - Optimizes SuperTrend ATR length
- **optimize_supertrend_factor.py** - Optimizes SuperTrend multiplier factor

### Filter Indicators
- **optimize_adx_threshold.py** - Optimizes ADX threshold filter
- **optimize_adx_length.py** - Optimizes ADX lookback period
- **optimize_volume.py** - Optimizes Volume MA length (volume filter)
- **optimize_rsi_overbought.py** - Optimizes RSI overbought threshold
- **optimize_rsi_oversold.py** - Optimizes RSI oversold threshold
- **optimize_rsi_long_threshold.py** - (New) Optimizes RSI lower threshold for Long entries

### Rule-Specific Optimizations (v1.13+)
- **optimize_rsi_divergence.py** - Optimizes lookback and min RSI for bearish divergence detection.
- **optimize_ema_slope.py** - Optimizes slope threshold and reduced sizing for flat markets.

### Risk Management
- **optimize_atr.py** - Optimizes ATR-based stop loss multiplier
- **optimize_leverage.py** - Optimizes leverage and position sizing (Legacy/Grid)

## 🔧 Utility Files
- **base_optimizer.py** - Base class for all optimizers (Multi-threaded & Robust)
- **plot_results.py** - Visualization tools for performance charts
- **verify_precision.py** - Verification utilities

## 🚀 Usage

Each optimization file can be run independently:

```bash
# Example: Optimize Bearish Divergence parameters
python optimize/optimize_rsi_divergence.py

# Example: Optimize EMA Slope sizing
python optimize/optimize_ema_slope.py
```

## 📝 Notes
- All optimizers utilize the `BaseOptimizer` class for parallel execution and robust data fetching.
- Results are saved to CSV files: `optimization_results_[parameter].csv`.
- Performance metrics tracked: PnL%, Win Rate, Profit Factor, and Max Drawdown.

## 📈 Current Production Settings (v1.16.0)

| Parameter | Value | Description |
|-----------|-------|-------------|
| EMA_LENGTH | 102 | Trend baseline |
| SUPERTREND_LENGTH | 18 | SuperTrend ATR period |
| SUPERTREND_FACTOR | 1.45 | SuperTrend multiplier |
| ADX_THRESHOLD | 18 | Minimum trend strength |
| RSI_LONG_THRESHOLD | 53 | Minimum RSI for Long entry |
| RSI_OVERBOUGHT | 64 | Maximum RSI for Long entry |
| ATR_MULTIPLIER | 0.7 | dynamic Stop Loss distance |
| LEVERAGE | 10 | Production leverage |
| POSITION_SIZE_PERCENT | 0.20 | 20% of account balance |

---
*Maintained for Production Stability 2026*
