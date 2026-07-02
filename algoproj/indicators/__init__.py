"""
Chart-ready indicators.

Each module registers an indicator via @chart_indicator (see base.py). Importing
this package populates REGISTRY, which the tv_chart server exposes to the browser.
Add a new indicator: drop a module here, decorate its compute fn, and import it
below — it appears in the chart's indicator panel automatically.
"""
from .base import REGISTRY, ChartIndicator, Line, chart_indicator

# import each indicator module so it self-registers.
# bollinger / frama / frama_channel are kept in the package but unregistered
# (not shown on the chart); re-add the import to bring one back.
from . import vwap            # noqa: F401,E402
from . import emas            # noqa: F401,E402
from . import regime          # noqa: F401,E402

__all__ = ["REGISTRY", "ChartIndicator", "Line", "chart_indicator"]
