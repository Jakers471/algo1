"""
MTF alignment + timing test — do the timeframes agree, and does LTF re-joining the HTF time a move?

For each TF (1m/5m/15m/1h/4h) compute an independent regime SCORE = weighted mean of signed
directional efficiency over 7 lookbacks (same as the heatmap), aligned onto a 5m base timeline.
Then:
  (A) AGREEMENT — how often do the 5 TFs share a state (bull/chop/bear) vs diverge?
  (B) TIMING    — when the 5m score RE-JOINS a direction (crosses +/-thresh), split by the 1h (HTF)
      context: does 'rejoin WITH the HTF' beat 'rejoin AGAINST the HTF' on forward return?

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_alignment.py"
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

TFS = ["1m", "5m", "15m", "60m", "4h"]
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "60m": 60, "4h": 240}
BASE = "5m"
THRESH = 0.12
LOOKBACKS = [3, 8, 16, 32, 64, 128, 256]


def score_tf(df, tf):
    close = df["close"]
    num = np.zeros(len(df))
    wsum = 0.0
    for lb in LOOKBACKS:
        net = close - close.shift(lb)
        path = close.diff().abs().rolling(lb).sum()
        eff = (net / path).clip(-1, 1).to_numpy()
        w = np.log2(lb * TF_MIN[tf]) + 1
        num += w * np.nan_to_num(eff)
        wsum += w
    return pd.Series(num / wsum, index=df.index)


def tf_frame(tf):
    if tf == "4h":
        h1 = load_tf("60m").dropna()
        return h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return load_tf(tf).dropna()


print("computing per-TF scores (1m is heavy) ...")
base = tf_frame(BASE)
idx = base.index
scores = {}
for tf in TFS:
    scores[tf] = score_tf(tf_frame(tf), tf).reindex(idx, method="ffill")
S = pd.DataFrame(scores).dropna()
idx = S.index
state = np.sign(np.where(np.abs(S) < THRESH, 0, S)).astype(int)   # bull=1 chop=0 bear=-1
state = pd.DataFrame(state, index=idx, columns=TFS)

# ── (A) agreement ──
st = state.to_numpy()
n = len(st)
nbull = (st == 1).sum(1); nbear = (st == -1).sum(1); nchop = (st == 0).sum(1)
all_same = (nbull == 5) | (nbear == 5) | (nchop == 5)
nz = st != 0
dir_aligned = np.array([len(set(row[m])) <= 1 and m.any() for row, m in zip(st, nz)])  # all non-chop agree
print(f"\n=== (A) AGREEMENT  ({n:,} 5m bars, {n/78/252:.1f}yr, thresh +/-{THRESH}) ===")
print(f"all 5 TFs SAME state: {all_same.mean()*100:.1f}%  "
      f"(all-bull {(nbull==5).mean()*100:.1f} / all-bear {(nbear==5).mean()*100:.1f} / all-chop {(nchop==5).mean()*100:.1f})")
print(f"all non-chop TFs agree on direction: {dir_aligned.mean()*100:.1f}%")
print(f"avg TFs per bar: bull {nbull.mean():.1f} / chop {nchop.mean():.1f} / bear {nbear.mean():.1f}")
for a, b in [("5m", "60m"), ("5m", "15m"), ("15m", "60m"), ("60m", "4h")]:
    same = (state[a] == state[b]).mean() * 100
    print(f"  {a:>3} vs {b:>3} same state: {same:.0f}%")

# ── (B) timing: 5m rejoins a direction, split by 1h context ──
close = base["close"].reindex(idx).to_numpy()
s5 = S["5m"].to_numpy(); prev = np.roll(s5, 1)
htf = S["60m"].to_numpy()
rejoin_long = (prev < THRESH) & (s5 >= THRESH)
rejoin_short = (prev > -THRESH) & (s5 <= -THRESH)


def fwd(entry_mask, side, h):
    e = np.where(entry_mask)[0]
    e = e[e + h < n]
    r = (close[e + h] / close[e] - 1.0) * side * 100
    return r


print(f"\n=== (B) TIMING — 5m score re-joins a direction, by 1h context (fwd % on 5m bars) ===")
print(f"{'condition':<34}{'n':>7}{'fwd6 win/mean':>18}{'fwd24 win/mean':>18}")
conds = [
    ("LONG  rejoin + 1h BULL (aligned)", rejoin_long & (htf > THRESH), 1),
    ("LONG  rejoin + 1h chop", rejoin_long & (np.abs(htf) <= THRESH), 1),
    ("LONG  rejoin + 1h BEAR (counter)", rejoin_long & (htf < -THRESH), 1),
    ("SHORT rejoin + 1h BEAR (aligned)", rejoin_short & (htf < -THRESH), -1),
    ("SHORT rejoin + 1h chop", rejoin_short & (np.abs(htf) <= THRESH), -1),
    ("SHORT rejoin + 1h BULL (counter)", rejoin_short & (htf > THRESH), -1),
]
for name, mask, side in conds:
    r6, r24 = fwd(mask, side, 6), fwd(mask, side, 24)
    if len(r6) == 0:
        continue
    print(f"{name:<34}{len(r6):>7}{f'{(r6>0).mean()*100:.0f}% / {r6.mean():+.3f}':>18}"
          f"{f'{(r24>0).mean()*100:.0f}% / {r24.mean():+.3f}':>18}")
