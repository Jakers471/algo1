"""
Pole nesting — how many 1m regime-poles sit inside each 5m regime-pole (MTF frequency multiplier).

Same regime-fan pole detector on both timeframes; count 1m poles fully contained in each 5m pole's
time span. Reports totals, avg 1m-per-5m, same-direction share, and per-week rates.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/pole_nesting.py"
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf
from algokit.regime import regime_score

THRESH, MIN_BARS, LO, HI, EPS = 50, 3, 5, 200, 0.05


def poles(tf):
    df = load_tf(tf).dropna()
    bull, _, bear = regime_score(df, LO, HI, eps=EPS)
    ts = df.index.values.astype("datetime64[s]").astype("int64")

    def runs(s, side):
        a = s >= THRESH
        out, i, n = [], 0, len(a)
        while i < n:
            if a[i]:
                j = i
                while j < n and a[j]:
                    j += 1
                if j - i >= MIN_BARS:
                    out.append((int(ts[i]), int(ts[j - 1]), side))
                i = j
            else:
                i += 1
        return out

    return runs(bull.to_numpy(), 1) + runs(bear.to_numpy(), -1), int(ts[0]), int(ts[-1])


print("running regime poles on 5m ...")
p5, t0, t1 = poles("5m")
print("running regime poles on 1m (heavier) ...")
p1, _, _ = poles("1m")

p1 = sorted(p1)
s1 = np.array([s for s, e, d in p1])
e1 = np.array([e for s, e, d in p1])
d1 = np.array([d for s, e, d in p1])

nested, same_dir, counts = 0, 0, []
for S, E, D in p5:
    m = (s1 >= S) & (e1 <= E)
    c = int(m.sum())
    counts.append(c)
    nested += c
    same_dir += int((m & (d1 == D)).sum())

weeks = (t1 - t0) / (7 * 86400)
counts = np.array(counts)
print(f"\nspan {weeks:.0f} weeks ({weeks/52:.1f} yr)")
print(f"5m poles: {len(p5):,}   |   1m poles: {len(p1):,}")
print(f"1m poles nested inside 5m poles: {nested:,}  ({same_dir:,} same-direction, "
      f"{same_dir/max(nested,1)*100:.0f}%)")
print(f"avg 1m poles per 5m pole: {counts.mean():.1f}  (median {np.median(counts):.0f}, "
      f"max {counts.max()}, empty {int((counts==0).sum())})")
print(f"\nPER WEEK:  5m poles {len(p5)/weeks:.1f}/wk   |   1m poles {len(p1)/weeks:.0f}/wk   "
      f"|   nested 1m {nested/weeks:.0f}/wk")
