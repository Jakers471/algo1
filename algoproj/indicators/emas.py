"""EMA fan — 10 / 20 / 50 / 100 / 200 exponential moving averages on one overlay.

Thin chart wrapper over algokit.indicators.ema. The five common EMAs, drawn short->long
(fast/warm -> slow/cool), for eyeballing trend / dynamic support-resistance under the flag work.
"""
from algokit.indicators import ema
from .base import Line, chart_indicator

_LENS = [10, 20, 50, 100, 200]
_COLORS = {10: "#ffd24c", 20: "#f5b14c", 50: "#4c8dff", 100: "#9a6bff", 200: "#f87171"}


@chart_indicator(
    name="emas",
    label="EMAs 10/20/50/100/200",
    params={},   # fixed lengths (10/20/50/100/200)
    lines=[Line(f"ema{n}", f"EMA {n}", _COLORS[n], 1, "solid") for n in _LENS],
)
def emas(ohlc):
    close = ohlc["close"]
    return {f"ema{n}": ema(close, n) for n in _LENS}
