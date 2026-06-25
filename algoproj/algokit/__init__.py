"""
algokit — shared quant-research library for the NQ fan-regime project.

Extracted (refactored, not changed) from the scripts under research/ and viz/.
Public surface:
    data       : load_tf, align, load_vix, TF
    indicators : sma, fan, slope_pct, geom_lengths, rsi, bollinger_bandwidth,
                 bollinger_bands, adx, atr, ma_spread, compression, INDICATORS
    regime     : regime_score
    costs      : FlatCost, FuturesCost
    backtest   : run_long_only
    metrics    : total_return, cagr, sharpe, max_drawdown, win_rate, expectancy, summary
    charts     : lightweight_chart, fan_plot, regime_ribbon
"""
from . import data, indicators, regime, costs, backtest, metrics, charts

__all__ = ["data", "indicators", "regime", "costs", "backtest", "metrics", "charts"]
