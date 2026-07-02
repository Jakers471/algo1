"""
Chart indicator series.

Computes a registered indicator over the FULL cached OHLC of a timeframe (so
lookback windows / warm-up are correct), caches the resulting line arrays, and
window-slices them the same O(log n) way store.py slices candles. The browser
only ever pulls the range it's showing.

Cache is keyed by (tf, indicator, params) and the source parquet mtime, so it
auto-rebuilds when the data is refreshed.
"""
import numpy as np
import pandas as pd

from algokit.data import load_tf
from indicators import REGISTRY
from tv_chart.datastore import store

_CACHE: dict = {}   # key -> {"ts": int64[], "lines": {key: float32[]}, "mtime": float}
_FRAME: dict = {}   # tf -> (DataFrame OHLCV with datetime index, ts int64[])


def specs():
    """JSON-serialisable list of every registered indicator (for the panel)."""
    return [ind.spec() for ind in REGISTRY.values()]


def _frame(tf):
    """OHLCV DataFrame (datetime index) for the same bars store.py serves as candles.

    OHLC come from the candle store (guaranteed to match the chart); volume is
    pulled from the parquet and aligned to those bars (missing -> 0)."""
    if tf in _FRAME:
        return _FRAME[tf]
    a = store._load(tf)
    idx = pd.to_datetime(a["ts"], unit="s")
    df = pd.DataFrame({"open": a["o"], "high": a["h"], "low": a["l"], "close": a["c"]}, index=idx)
    raw = load_tf(tf)
    vol = raw["volume"] if "volume" in raw.columns else None
    df["volume"] = (vol.reindex(idx).to_numpy() if vol is not None else 0.0)
    df["volume"] = df["volume"].fillna(0.0)
    _FRAME[tf] = (df, a["ts"])
    return _FRAME[tf]


def _key(tf, name, params):
    return (tf, name, tuple(sorted((k, str(v)) for k, v in params.items())))


def _series(tf, name, params):
    ind = REGISTRY.get(name)
    if ind is None:
        raise KeyError(f"unknown indicator {name!r}")
    mtime = store._parquet_mtime(tf)
    key = _key(tf, name, params)
    c = _CACHE.get(key)
    if c and c["mtime"] == mtime:
        return c
    df, _ts = _frame(tf)
    _, out = ind.compute(df, params)
    lines = {k: np.asarray(v, dtype="float32") for k, v in out.items()}
    c = {"ts": _ts, "lines": lines, "mtime": mtime}
    _CACHE[key] = c
    return c


def window(tf, name, params, t0, t1):
    """Indicator line values for bars with t0 <= time <= t1 (epoch seconds).

    Returns {line_key: [[time, value], ...]}. NaN points keep their timestamp with
    a null value (a whitespace/gap point) so colored lines break instead of drawing
    straight across a stretch that belongs to another segment.
    """
    d = _series(tf, name, params)
    ts = d["ts"]
    i = int(np.searchsorted(ts, int(t0), side="left"))
    j = int(np.searchsorted(ts, int(t1), side="right"))
    out = {}
    for key, arr in d["lines"].items():
        seg = arr[i:j]
        tseg = ts[i:j]
        out[key] = [[int(t), (None if v != v else float(v))] for t, v in zip(tseg, seg)]
    return out
