"""
Candle cache/datastore for the standalone chart.

Why this exists: the parquets go back to 2005 (1m = 6.2M bars / 157 MB). We can't
ship that to the browser, and we don't want to re-decode parquet every time you
flip timeframes. So:

  * each timeframe is loaded ONCE into contiguous numpy arrays (ts/o/h/l/c)
  * those arrays are persisted to a compact .npz in datastore/cache/ so a server
    restart is near-instant (np.load >> parquet decode). The cache is keyed to the
    source parquet's mtime, so it auto-rebuilds if you refresh the data.
  * queries are O(log n) slices (searchsorted), never a full scan.

The browser only ever pulls small windows (latest N, or N-before-a-cursor), so
panning back through 20 years stays smooth. See serve.py for the routes.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # reach algoproj/
from config import DATA_DIR
from algokit.data import TF, load_tf

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

_MEM: dict = {}   # tf -> {ts:int64[], o/h/l/c:float32[]}  (process-lifetime cache)


def _parquet_mtime(tf):
    return os.path.getmtime(os.path.join(DATA_DIR, TF[tf]))


def _build_from_parquet(tf):
    df = load_tf(tf)[["open", "high", "low", "close", "volume"]].dropna()
    # tz-naive UTC index -> epoch seconds (project-wide convention treats naive as UTC)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    return {
        "ts": ts,
        "o": df["open"].to_numpy("float32"),
        "h": df["high"].to_numpy("float32"),
        "l": df["low"].to_numpy("float32"),
        "c": df["close"].to_numpy("float32"),
        "v": df["volume"].to_numpy("float32"),
    }


def _load(tf):
    """Return the cached arrays for a timeframe, building/reading the .npz as needed."""
    if tf not in TF:
        raise KeyError(f"unknown timeframe {tf!r}")
    if tf in _MEM:
        return _MEM[tf]

    src_mtime = _parquet_mtime(tf)
    path = os.path.join(CACHE_DIR, f"{tf}.npz")
    if os.path.exists(path):
        z = np.load(path, allow_pickle=False)
        # require "v" so caches built before volume was added get rebuilt automatically
        if float(z["mtime"][0]) == src_mtime and "v" in z.files:
            _MEM[tf] = {k: z[k] for k in ("ts", "o", "h", "l", "c", "v")}
            return _MEM[tf]

    arr = _build_from_parquet(tf)
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(path, mtime=np.array([src_mtime], dtype="float64"), **arr)
    _MEM[tf] = arr
    return arr


def _rows(a, i, j):
    ts, o, h, l, c, v = a["ts"], a["o"], a["h"], a["l"], a["c"], a["v"]
    return [[int(ts[k]), float(o[k]), float(h[k]), float(l[k]), float(c[k]), float(v[k])] for k in range(i, j)]


# ── public API ───────────────────────────────────────────
def meta(tf):
    a = _load(tf)
    n = len(a["ts"])
    return {"tf": tf, "count": int(n),
            "first": int(a["ts"][0]) if n else None,
            "last": int(a["ts"][-1]) if n else None}


def latest(tf, count):
    """The most recent `count` bars."""
    a = _load(tf)
    n = len(a["ts"])
    return _rows(a, max(0, n - count), n)


def before(tf, ts, count):
    """The `count` bars immediately older than epoch-second cursor `ts` (for left-paging)."""
    a = _load(tf)
    j = int(np.searchsorted(a["ts"], int(ts), side="left"))  # first bar with time >= ts
    return _rows(a, max(0, j - count), j)


def after(tf, ts, count):
    """The `count` bars immediately newer than epoch-second cursor `ts` (right-paging)."""
    a = _load(tf)
    n = len(a["ts"])
    i = int(np.searchsorted(a["ts"], int(ts), side="right"))  # first bar with time > ts
    return _rows(a, i, min(n, i + count))


def around(tf, ts, count):
    """`count` bars centered on epoch-second `ts` (for snapping to a finding)."""
    a = _load(tf)
    n = len(a["ts"])
    j = int(np.searchsorted(a["ts"], int(ts), side="left"))
    half = count // 2
    return _rows(a, max(0, j - half), min(n, j + half))


def warm(tfs=None):
    """Optionally pre-build caches (e.g. on server start) so the first view is instant."""
    for tf in (tfs or [t for t in ("1d", "60m", "15m", "5m", "1m") if t in TF]):
        _load(tf)
