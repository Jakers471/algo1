"""VWAP — session-anchored Volume-Weighted Average Price with std bands.

Resets each UTC day. Single gold VWAP line; the dotted bands above/below are
colored green (upper) and red (lower). ``k`` sets the band width in
volume-weighted standard deviations (set k=0 to hide the bands). Wraps the pure
math in algokit.indicators.
"""
from algokit.indicators import vwap as _vwap
from .base import Line, chart_indicator


@chart_indicator(
    name="vwap",
    label="VWAP (session)",
    params={"k": 1.0},
    lines=[
        Line("upper", "VWAP +kσ", "#34d399", 1, "dotted"),   # upper band: green
        Line("vwap",  "VWAP",     "#e0b64c", 2, "solid"),
        Line("lower", "VWAP -kσ", "#f87171", 1, "dotted"),   # lower band: red
    ],
    # color candles by band regime: close above upper -> green, below lower -> red
    candles={"above": "upper", "below": "lower",
             "up": "#34d399", "down": "#f87171", "neutral": "#6b7886"},
)
def vwap(ohlc, k=1.0):
    mid, upper, lower = _vwap(ohlc["high"], ohlc["low"], ohlc["close"], ohlc["volume"], float(k))
    return {"vwap": mid, "upper": upper, "lower": lower}
