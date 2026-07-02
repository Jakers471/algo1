"""FRAMA Channel — BigBeluga.

Ported from BigBeluga's TradingView Pine v5 "FRAMA Channel [BigBeluga]".
A smoothed FRAMA (on hl2) wrapped in a volatility channel. Wraps the pure math
in algokit.indicators. The momentum candle-coloring and breakout labels from the
original are omitted (this chart's overlay renderer draws lines, not per-bar
candle recoloring).

Attribution: © BigBeluga, CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/).
"""
from algokit.indicators import frama_channel as _frama_channel
from .base import Line, chart_indicator


@chart_indicator(
    name="frama_channel",
    label="FRAMA Channel (BigBeluga)",
    params={"n": 26, "distance": 1.5},
    lines=[
        Line("upper", "FC upper", "#27e27b", 1, "solid"),
        Line("mid",   "FRAMA",    "#a2b5ca", 1, "dashed"),
        Line("lower", "FC lower", "#2772e2", 1, "solid"),
    ],
)
def frama_channel(ohlc, n=26, distance=1.5):
    mid, upper, lower = _frama_channel(ohlc["high"], ohlc["low"], int(n), float(distance))
    return {"upper": upper, "mid": mid, "lower": lower}
