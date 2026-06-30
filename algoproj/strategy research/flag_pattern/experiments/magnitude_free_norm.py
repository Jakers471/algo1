"""
EXPERIMENT: magnitude-free normalization vs the current (magnitude-sensitive) match.

Current detector normalizes a window to "% from its open" and compares to the template.
That is blind to price LEVEL but NOT to move SIZE -- it only finds flags about as big as
the template (~0.5%). This experiment additionally divides each window's %-moves by their
own spread (std), so SHAPE is matched regardless of magnitude. If price is fractal, the
same flag should then be found at any size.

Compares, per pattern, current vs mag-free on: match count, fwd6 mean / win%, and the
spread of matched-window range% (p10/p50/p90) -- the magnitude spread is the whole point.

Run: python "strategy research/flag_pattern/experiments/magnitude_free_norm.py" [--tf 5m]
"""
import argparse
import os
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj/
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "signal")))    # signal_config
from algokit.data import load_tf
from algokit import patterns
import signal_config as cfg

COLS = ["open", "high", "low", "close"]


def scan_free(values, tmpl, window, chunk=200_000):
    """Magnitude-free distance: divide each window's %-moves (and the template's) by their std."""
    t = tmpl.flatten().astype(float)
    t = t / t.std()
    sw = sliding_window_view(values, (window, values.shape[1]))[:, 0, :, :]
    m = sw.shape[0]
    out = np.empty(m)
    for s in range(0, m, chunk):
        b = sw[s:s + chunk].astype(float)
        pct = (b / b[:, 0, 0][:, None, None] - 1.0).reshape(b.shape[0], -1)
        sd = pct.std(axis=1, keepdims=True)
        sd[sd == 0] = 1
        out[s:s + chunk] = np.sqrt(((pct / sd - t) ** 2).sum(axis=1))
    return out


def select(scores, ts):
    thr = np.percentile(scores, cfg.MATCH_PCT)
    s = scores.copy()
    s[~cfg.session_mask(ts[:len(scores)])] = np.inf
    return patterns.matches_under(s, thr, cfg.MIN_GAP)


def stats(values, close, idxs, direction, window):
    e = np.array([i + window - 1 for i in idxs])
    f6 = np.array([direction * (close[k + 6] / close[k] - 1) * 100 for k in e if k + 6 < len(close)])
    rng = np.array([(values[i:i + window, 1].max() - values[i:i + window, 2].min()) / values[i, 0] * 100
                    for i in idxs])
    p = np.percentile(rng, [10, 50, 90])
    return len(idxs), f6.mean(), (f6 > 0).mean() * 100, p


def main(tf):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    close = values[:, 3]
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    print(cfg.describe())
    print(f"{tf}: {len(df):,} bars  {df.index[0].date()} -> {df.index[-1].date()}\n")
    print(f"{'method':>9} {'pattern':>10} {'n':>5} {'fwd6':>8} {'win%':>6}   range% p10/p50/p90")
    print("-" * 62)
    for name, (direction, side, tmpl) in cfg.SETUP.items():
        for label, scores in (("current", patterns.scan(values, tmpl, cfg.WINDOW)),
                              ("mag-free", scan_free(values, tmpl, cfg.WINDOW))):
            n, m, w, p = stats(values, close, select(scores, ts), direction, cfg.WINDOW)
            print(f"{label:>9} {name:>10} {n:>5} {m:+8.3f} {w:6.1f}   {p[0]:.2f}/{p[1]:.2f}/{p[2]:.2f}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    main(ap.parse_args().tf)
