"""
Chart-indicator registry.

An *indicator* here is a thin, chart-facing wrapper over the pure math in
``algokit.indicators``: it declares its params and the named line-series it
draws, and knows how to compute those lines from an OHLC DataFrame. The tv_chart
server turns them into JSON the browser overlays on the candles.

Add one by decorating a compute function with ``@chart_indicator(...)``; it lands
in ``REGISTRY`` under its name and shows up in the chart's indicator panel
automatically.
"""
from dataclasses import dataclass, field
from typing import Callable

REGISTRY: dict = {}


@dataclass
class Line:
    """One line the indicator draws, with its default styling."""
    key: str                 # identifier within the indicator (e.g. "upper")
    label: str               # shown in the chart legend / crosshair
    color: str
    width: int = 1
    style: str = "solid"     # solid | dashed | dotted


@dataclass
class ChartIndicator:
    name: str                # registry key / query name (e.g. "bollinger")
    label: str               # human label (e.g. "Bollinger Bands")
    params: dict             # default params, e.g. {"n": 20, "k": 2.0}
    lines: list              # list[Line] this indicator outputs
    fn: Callable             # (ohlc: DataFrame, **params) -> dict[key -> Series]
    overlay: bool = True     # True = drawn on the price scale (over candles)
    candles: dict = None     # optional candle-coloring rule (see chart_indicator)

    def compute(self, ohlc, params=None):
        """Resolve params (casting incoming strings to the default's type) and
        run the compute fn. Returns (resolved_params, {line_key: Series})."""
        p = dict(self.params)
        for k, v in (params or {}).items():
            if k in p and v is not None and v != "":
                p[k] = type(self.params[k])(v)
        return p, self.fn(ohlc, **p)

    def spec(self):
        """JSON-serialisable description for the chart's indicator panel."""
        return {
            "name": self.name, "label": self.label, "overlay": self.overlay,
            "params": self.params,
            "lines": [vars(l) for l in self.lines],
            "candles": self.candles,
        }


def chart_indicator(*, name, label, params, lines, overlay=True, candles=None):
    """Decorator: register ``fn`` as a chart indicator in ``REGISTRY``.

    ``candles`` (optional) enables a "color candles" toggle in the chart that
    tri-colors bars from two of the indicator's lines::

        candles={"above": "upper", "below": "lower",
                 "up": "#34d399", "down": "#f87171", "neutral": "#6b7886"}

    close > ``above`` line -> ``up`` color; close < ``below`` line -> ``down``;
    otherwise ``neutral``.
    """
    def deco(fn):
        REGISTRY[name] = ChartIndicator(name, label, params, lines, fn, overlay, candles)
        return fn
    return deco
