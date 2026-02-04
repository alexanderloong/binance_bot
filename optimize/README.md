# Optimization Files Summary

This directory contains individual optimization scripts for each parameter of the trading strategy.

> **Version:** 1.12.0 | **Updated:** 2026-02-04

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

### Risk Management
- **optimize_atr.py** - Optimizes ATR-based stop loss multiplier
- **optimize_leverage.py** - Optimizes leverage and position sizing

## 📊 Combined Optimization Files (Legacy)
These files optimize multiple parameters together:
- **optimize_adx_volumn.py** - Combined ADX & Volume optimization
- **optimize_rsi.py** - Combined RSI overbought & oversold optimization

## 🔧 Utility Files
- **base_optimizer.py** - Base class for all optimizers
- **plot_results.py** - Visualization tools for optimization results
- **verify_precision.py** - Verification utilities

## 🚀 Usage

Each optimization file can be run independently:

```bash
# Example: Optimize EMA length
python optimize/optimize_ema.py

# Example: Optimize ADX threshold
python optimize/optimize_adx_threshold.py

# Example: Optimize ADX length
python optimize/optimize_adx_length.py

# Example: Optimize ATR Stop Loss
python optimize/optimize_atr.py
```

## 📝 Notes

- Each optimizer keeps other parameters fixed from `config.py`
- Results are saved to CSV files in the format: `optimization_results_[parameter].csv`
- All optimizers use parallel processing via `BaseOptimizer`
- Recommended to run optimizations sequentially, updating `config.py` with best values after each run

## 🎯 Optimization Workflow

1. Start with trend indicators (EMA, SuperTrend Length, SuperTrend Factor)
2. Then optimize filters (ADX, Volume, RSI Overbought, RSI Oversold)
3. Finally tune risk management (ATR Stop Loss, Leverage)
4. Update `config.py` with optimal values after each step

## 📈 Current Optimized Settings (v1.12.0)

| Parameter | Value | Description |
|-----------|-------|-------------|
| EMA_LENGTH | 102 | Trend baseline |
| SUPERTREND_LENGTH | 18 | SuperTrend ATR period |
| SUPERTREND_FACTOR | 1.5 | SuperTrend multiplier |
| ADX_THRESHOLD | 18 | Minimum trend strength |
| VOLUME_MA_LENGTH | 177 | Volume filter period |
| RSI_OVERBOUGHT | 64 | Long entry limit |
| RSI_OVERSOLD | 36 | Short entry limit |
| ATR_MULTIPLIER | 0.8 | Stop loss distance |

## ⚠️ Removed Features

- **Partial Take Profit** - Removed in v1.11.0 (not suitable for pure trend following strategy)
