# Optimization Files Summary

This directory contains individual optimization scripts for each parameter of the trading strategy.

## 📁 Individual Parameter Optimization Files

### Trend Indicators
- **optimize_ema.py** - Optimizes EMA length (trend baseline)
- **optimize_supertrend_length.py** - Optimizes SuperTrend ATR length
- **optimize_supertrend_factor.py** - Optimizes SuperTrend multiplier factor

### Filter Indicators
- **optimize_adx.py** - Optimizes ADX threshold (trend strength filter)
- **optimize_volume.py** - Optimizes Volume MA length (volume filter)
- **optimize_rsi_overbought.py** - Optimizes RSI overbought threshold
- **optimize_rsi_oversold.py** - Optimizes RSI oversold threshold

### Risk Management
- **optimize_atr.py** - Optimizes ATR-based stop loss
- **optimize_tp.py** - Optimizes take profit settings
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
python optimize/optimize_adx.py
```

## 📝 Notes

- Each optimizer keeps other parameters fixed from `config.py`
- Results are saved to CSV files in the format: `optimization_results_[parameter].csv`
- All optimizers use parallel processing via `BaseOptimizer`
- Recommended to run optimizations sequentially, updating `config.py` with best values after each run

## 🎯 Optimization Workflow

1. Start with trend indicators (EMA, SuperTrend)
2. Then optimize filters (ADX, Volume, RSI)
3. Finally tune risk management (ATR, TP, Leverage)
4. Update `config.py` with optimal values after each step
