"""Bollinger Bands — mid SMA with upper/lower at k standard deviations.

Same definition as QuantConnect LEAN's BollingerBands (mid +/- k*stdev); wraps
the pure math already in algokit.indicators.
"""
from algokit.indicators import bollinger_bands
from .base import Line, chart_indicator


@chart_indicator(
    name="bollinger",
    label="Bollinger Bands",
    params={"n": 20, "k": 2.0},
    lines=[
        Line("upper", "BB upper", "#4c8dff", 1, "solid"),
        Line("mid",   "BB basis", "#9aa7b4", 1, "dashed"),
        Line("lower", "BB lower", "#4c8dff", 1, "solid"),
    ],
)
def bollinger(ohlc, n=20, k=2.0):
    mid, upper, lower = bollinger_bands(ohlc["close"], int(n), float(k))
    return {"upper": upper, "mid": mid, "lower": lower}
