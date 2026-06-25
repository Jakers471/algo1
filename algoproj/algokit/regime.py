"""
Fan-regime score. Extracted EXACTLY from nq_mtf_signals.py's regime() (the
fixed-eps version that produces the documented +24% / 817-trip result).

A 32-MA geometric fan is collapsed into bull / consol / bear scores 0-100 that
sum to 100, longer MAs weighted more (by length -> geometric tilt). Each MA
votes up / flat / down by its L-bar slope vs +/- eps.
"""
import numpy as np
import pandas as pd


def regime_score(df, lo, hi, n_ma=32, slope_L=5, eps=0.03):
    """Return (bull, consol, bear) pandas Series (0-100, summing to 100).

    df: OHLCV DataFrame (uses df["close"]).
    lo, hi: fan length bounds (bars); n_ma geometrically-spaced MAs between.
    slope_L: slope lookback in bars.
    eps: +/- % slope band that counts as flat.
    """
    close = df["close"]
    lengths = sorted(set(int(round(v)) for v in np.geomspace(lo, hi, n_ma)))
    w = np.array(lengths, float)
    W = w.sum()
    up = np.zeros((len(lengths), len(df)))
    dn = np.zeros_like(up)
    fl = np.zeros_like(up)
    for j, n in enumerate(lengths):
        ma = close.rolling(n).mean()
        sl = ((ma / ma.shift(slope_L) - 1) * 100).to_numpy()
        u = sl > eps
        d = sl < -eps
        f = ~u & ~d & ~np.isnan(sl)
        up[j], dn[j], fl[j] = u, d, f
    bull = 100 * (w[:, None] * up).sum(0) / W
    consol = 100 * (w[:, None] * fl).sum(0) / W
    bear = 100 * (w[:, None] * dn).sum(0) / W
    return (pd.Series(bull, index=df.index),
            pd.Series(consol, index=df.index),
            pd.Series(bear, index=df.index))
