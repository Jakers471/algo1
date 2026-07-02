"""
MTF trend-ride test — 3-TF alignment entry, RIDE until the HTF trend ends.
Compares STOP placement (the 78%-stop-out leak): tight 1m low vs a wider 15m-structure low vs ATR.

Setup (long; mirror short), 1m base:
  HTF 1h = BULL · MTF 15m = CHOP · LTF 1m was BEAR then FLIPS BULL -> entry on the flip.
Hold until the 1h regime stops being bull (trend over) or the stop is hit. Outcome in R.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_ride.py"
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

TF_MIN = {"1m": 1, "15m": 15, "60m": 60}
THRESH = 0.12
W = 30            # pullback lookback for "was bear" + the tight 1m stop
MAXHOLD = 5000
LOOKBACKS = [3, 8, 16, 32, 64, 128, 256]


def score_tf(df, tf):
    close = df["close"]
    num, wsum = np.zeros(len(df)), 0.0
    for lb in LOOKBACKS:
        net = close - close.shift(lb)
        path = close.diff().abs().rolling(lb).sum()
        w = np.log2(lb * TF_MIN[tf]) + 1
        num += w * np.nan_to_num((net / path).clip(-1, 1).to_numpy())
        wsum += w
    return pd.Series(num / wsum, index=df.index)


def atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


print("computing 1m / 15m / 1h scores (heavy) ...")
b1 = load_tf("1m").dropna()
idx = b1.index
htf = score_tf(load_tf("60m").dropna(), "60m").reindex(idx, method="ffill").to_numpy()
mtf = score_tf(load_tf("15m").dropna(), "15m").reindex(idx, method="ffill").to_numpy()
ltf = score_tf(b1, "1m").to_numpy()
atr15 = atr(load_tf("15m").dropna()).reindex(idx, method="ffill").to_numpy()
low, high, close = b1["low"].to_numpy(), b1["high"].to_numpy(), b1["close"].to_numpy()
n = len(b1)

lp = np.roll(ltf, 1)
cross_up = (lp < THRESH) & (ltf >= THRESH)
cross_dn = (lp > -THRESH) & (ltf <= -THRESH)
minW = pd.Series(ltf).rolling(W).min().to_numpy()
maxW = pd.Series(ltf).rolling(W).max().to_numpy()
chop = np.abs(mtf) <= THRESH

lowmin30 = pd.Series(low).rolling(30).min().to_numpy()
lowmin120 = pd.Series(low).rolling(120).min().to_numpy()
highmax30 = pd.Series(high).rolling(30).max().to_numpy()
highmax120 = pd.Series(high).rolling(120).max().to_numpy()

aligned_L = np.where(cross_up & (htf > THRESH) & chop & (minW < -THRESH))[0]
aligned_S = np.where(cross_dn & (htf < -THRESH) & chop & (maxW > THRESH))[0]


def ride(idxs, side, stop_arr):
    out = []
    for t in idxs:
        if t + 1 >= n:
            continue
        entry = close[t]
        stop = stop_arr[t]
        risk = (entry - stop) if side > 0 else (stop - entry)
        if not (risk > 0):
            continue
        end = min(n, t + 1 + MAXHOLD)
        res = None
        for j in range(t + 1, end):
            if side > 0:
                if low[j] <= stop:
                    res = (-1.0, j - t, 1); break
                if htf[j] <= THRESH:
                    res = ((close[j] - entry) / risk, j - t, 0); break
            else:
                if high[j] >= stop:
                    res = (-1.0, j - t, 1); break
                if htf[j] >= -THRESH:
                    res = ((entry - close[j]) / risk, j - t, 0); break
        if res is None:
            c = close[end - 1]
            res = ((((c - entry) if side > 0 else (entry - c)) / risk), end - 1 - t, 0)
        out.append(res)
    return out


MODES = {
    "1m low  (W30, tight)": (lowmin30, highmax30),
    "15m low (W120, wide)": (lowmin120, highmax120),
    "ATR15 x1.5":            (close - 1.5 * atr15, close + 1.5 * atr15),
}

print(f"\n=== MTF trend-ride | 1h bull + 15m chop + 1m pullback-flip | hold until 1h flips | 20yr GROSS ===")
print(f"aligned events: {len(aligned_L):,} long / {len(aligned_S):,} short\n")
print(f"{'stop mode':<24}{'n':>8}{'win%':>7}{'stopout%':>10}{'expectancy':>12}{'median':>9}{'best':>7}{'hold(h)':>9}")
for name, (sl, ss) in MODES.items():
    r = ride(aligned_L, 1, sl) + ride(aligned_S, -1, ss)
    R = np.array([x[0] for x in r]); bars = np.array([x[1] for x in r]); so = np.array([x[2] for x in r])
    print(f"{name:<24}{len(R):>8,}{(R>0).mean()*100:>6.0f}%{so.mean()*100:>9.0f}%"
          f"{R.mean():>+11.2f}R{np.median(R):>+8.2f}R{R.max():>6.0f}R{np.median(bars)/60:>8.1f}")
