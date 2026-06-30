"""
Pattern/template matching engine — shared by research scripts and the chart.

A pattern is a WINDOW-bar OHLC template expressed in "% from window open" space, so
it matches on *shape* at any price level or timeframe (the fractal idea). Scanning a
timeframe scores every window by Euclidean distance to the template; the lowest
scores are the closest real occurrences.

Research scripts write the hits as findings JSON into their own strategy folder
(strategy research/<strat>/findings/) so the tv_chart viewer can overlay them —
no more exporting dozens of PNGs.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def scan(values, template, window, chunk=200_000):
    """values:(n,4) OHLC -> distance score per window start (lower = closer). Vectorized."""
    tmpl = np.asarray(template, dtype=np.float64).reshape(-1)
    ncol = values.shape[1]
    sw = sliding_window_view(values, (window, ncol))[:, 0, :, :]  # (M, window, ncol)
    m = sw.shape[0]
    out = np.empty(m, dtype=np.float64)
    for s in range(0, m, chunk):
        block = sw[s:s + chunk].astype(np.float64)
        base = block[:, 0, 0][:, None, None]              # each window's open
        flat = (block / base - 1.0).reshape(block.shape[0], -1)
        out[s:s + chunk] = np.sqrt(((flat - tmpl) ** 2).sum(axis=1))
    return out


def scan_free(values, template, window, chunk=200_000):
    """Magnitude-FREE distance: like scan(), but divide each window's %-moves (and the
    template's) by their own std first -- so SHAPE is matched regardless of move size."""
    t = np.asarray(template, dtype=np.float64).reshape(-1)
    t = t / t.std()
    ncol = values.shape[1]
    sw = sliding_window_view(values, (window, ncol))[:, 0, :, :]
    m = sw.shape[0]
    out = np.empty(m, dtype=np.float64)
    for s in range(0, m, chunk):
        b = sw[s:s + chunk].astype(np.float64)
        pct = (b / b[:, 0, 0][:, None, None] - 1.0).reshape(b.shape[0], -1)
        sd = pct.std(axis=1, keepdims=True)
        sd[sd == 0] = 1
        out[s:s + chunk] = np.sqrt(((pct / sd - t) ** 2).sum(axis=1))
    return out


def top_matches(scores, n, min_gap):
    """Best n non-overlapping window-start indices (>= min_gap bars apart)."""
    picked = []
    for idx in np.argsort(scores):
        if all(abs(int(idx) - p) >= min_gap for p in picked):
            picked.append(int(idx))
            if len(picked) == n:
                break
    return picked


def matches_under(scores, thresh, min_gap):
    """Every non-overlapping window-start with score < thresh, best (closest) first.

    No count cap — the threshold sets the sample. Uses a blocked mask so it stays fast
    even with thousands of hits.
    """
    n = len(scores)
    blocked = np.zeros(n, bool)
    picked = []
    for idx in np.argsort(scores):
        if scores[idx] >= thresh:
            break
        if blocked[idx]:
            continue
        picked.append(int(idx))
        blocked[max(0, idx - min_gap + 1):idx + min_gap] = True
    return picked
