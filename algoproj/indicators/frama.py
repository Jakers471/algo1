"""FRAMA — Ehlers' Fractal Adaptive Moving Average.

Ported from QuantConnect LEAN's FractalAdaptiveMovingAverage (C#). Wraps the
pure math in algokit.indicators. Drawn as a single adaptive MA line over price.
"""
from algokit.indicators import frama as _frama
from .base import Line, chart_indicator


@chart_indicator(
    name="frama",
    label="FRAMA (Ehlers)",
    params={"n": 16, "long_period": 198},
    lines=[Line("frama", "FRAMA", "#f5b14c", 2, "solid")],
)
def frama(ohlc, n=16, long_period=198):
    return {"frama": _frama(ohlc["high"], ohlc["low"], int(n), int(long_period))}
