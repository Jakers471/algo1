"""Regime (32-MA fan) — colors each candle by its regime: bull / consol / bear.

Thin chart wrapper over algokit.regime.regime_score (the documented fan engine). Per bar it returns
bull / consol / bear scores (0-100, sum 100); the chart tints each candle by whichever is largest.
overlay=False + no lines drawn (color-only) so the 0-100 scores don't squash the price scale.
"""
from algokit.regime import regime_score
from .base import Line, chart_indicator

BULL, CONSOL, BEAR = "#26a69a", "#d9a520", "#ef5350"   # green / amber / red


@chart_indicator(
    name="regime",
    label="Regime (32-MA fan)",
    params={"lo": 5, "hi": 200, "eps": 0.05},
    lines=[Line("bull", "bull", BULL), Line("consol", "consol", CONSOL), Line("bear", "bear", BEAR)],
    overlay=False,   # color-only: no lines drawn
    candles={"mode": "state", "keys": ["bull", "consol", "bear"],
             "colors": {"bull": BULL, "consol": CONSOL, "bear": BEAR}},
)
def regime(ohlc, lo=5, hi=200, eps=0.05):
    bull, consol, bear = regime_score(ohlc, int(lo), int(hi), eps=float(eps))
    return {"bull": bull, "consol": consol, "bear": bear}
