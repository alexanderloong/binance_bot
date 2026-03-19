# Optimization Files Summary

This directory contains individual optimization scripts for each parameter of the trading strategy.

> **Version:** 2.0.0 | **Updated:** 2026-03-19

## 📁 Individual Parameter Optimization Files

### Trend Indicators
- **optimize_ema.py** - Optimizes EMA length (trend baseline)
- **optimize_supertrend_length.py** - Optimizes SuperTrend ATR length
- **optimize_supertrend_factor.py** - Optimizes SuperTrend multiplier factor

### Filter Indicators
- **optimize_volume.py** - Optimizes Volume MA length (volume filter)

### Risk Management
- **optimize_leverage.py** - Optimizes leverage and position sizing (Legacy/Grid)

## 🔧 Utility Files
- **base_optimizer.py** - Base class for all optimizers (Multi-threaded & Robust)
- **plot_results.py** - Visualization tools for performance charts
- **verify_precision.py** - Verification utilities
- **stats.py** - Statistical tools

## 🚀 Usage

Each optimization file can be run independently:

```bash
# Example: Optimize EMA
python module/optimize/optimize_ema.py

# Example: Optimize Volume MA
python module/optimize/optimize_volume.py
```

## 📝 Notes
- All optimizers utilize the `BaseOptimizer` class for parallel execution and robust data fetching.
- Results are saved to CSV files: `optimization_results_[parameter].csv`.
- Performance metrics tracked: PnL%, Win Rate, Profit Factor, and Max Drawdown.

## 📈 Current Production Settings (v2.0.0)

| Parameter | Value | Description |
|-----------|-------|-------------|
| EMA_LENGTH | 97 | Trend baseline |
| SUPERTREND_LENGTH | 18 | SuperTrend ATR period |
| SUPERTREND_FACTOR | 1.45 | SuperTrend multiplier |
| VOLUME_MA_LENGTH | 177 | Minimum volume moving average |
| ATR_MULTIPLIER | 0.74 | dynamic Stop Loss distance |
| LEVERAGE | 10 | Production leverage |
| POSITION_SIZE_PERCENT | 0.20 | 20% of account balance |

---
*Maintained for Production Stability 2026*
