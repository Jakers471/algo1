"""
Classify every LTF swing leg by SLOPE strength: weak / medium / strong.

A pole is not a template — it's a swing leg that moves fast. Take the LTF swings (real turning
points from price), and for each leg measure slope = (price change / bars) / ATR = ATR-per-bar
(scale-free "steepness / power"). Split into WEAK / MEDIUM / STRONG by the data's own terciles.
Strong = poles; weak = chop/consolidation. Plots a real slice with legs colored by strength.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/slope_moves.py"
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))   # algoproj/
sys.path.insert(0, os.path.join(HERE, "..", "signal"))                       # structure + config
from algokit.data import load_tf
import signal_config as cfg
from structure import swings, _atr

COLS = ["open", "high", "low", "close"]
WEAK, MED = "#6b7886", "#f5b14c"          # grey, amber
STRONG_UP, STRONG_DN = "#26a69a", "#ef5350"

df = load_tf(cfg.TF)[COLS].dropna()
if cfg.HISTORY_START:
    df = df[df.index >= cfg.HISTORY_START]
values = df.values
atr = _atr(values, cfg.ATR_N)
sw = swings(values, atr, cfg.GRAINS["LTF"])

# legs between consecutive swings -> slope in ATR/bar
legs = []
for (ia, pa, _ka), (ib, pb, _kb) in zip(sw[:-1], sw[1:]):
    db = ib - ia
    if db <= 0:
        continue
    slope = abs(pb - pa) / db / atr[ib]
    legs.append((ia, pa, ib, pb, slope, pb > pa))
slopes = np.array([l[4] for l in legs])
w_cut, s_cut = np.percentile(slopes, [33, 66])          # data-driven tercile bands


def strength(s):
    return "weak" if s < w_cut else ("strong" if s > s_cut else "medium")


n = len(legs)
counts = {k: sum(1 for l in legs if strength(l[4]) == k) for k in ("weak", "medium", "strong")}
print(f"LTF grain {cfg.GRAINS['LTF']}x ATR | {n} legs")
print(f"slope (ATR/bar): p10 {np.percentile(slopes,10):.2f} | tercile cuts {w_cut:.2f} / {s_cut:.2f} "
      f"| p90 {np.percentile(slopes,90):.2f} | max {slopes.max():.2f}")
print(f"weak {counts['weak']} | medium {counts['medium']} | strong {counts['strong']}")

# center a slice on a big, strong pole so the plot shows one clearly
big = max(range(n), key=lambda i: abs(legs[i][3] - legs[i][1]))
mid = (legs[big][0] + legs[big][2]) // 2
i0, i1 = max(0, mid - 180), min(len(values), mid + 180)

fig, ax = plt.subplots(figsize=(16, 7), facecolor="#0a0e13")
ax.set_facecolor("#0a0e13")
o, h, l, c = (values[i0:i1, k] for k in range(4))
for i in range(len(o)):
    col = "#2a3742" if c[i] >= o[i] else "#3a2a2a"
    ax.plot([i, i], [l[i], h[i]], color=col, lw=0.7, zorder=2)
    lo, hi = min(o[i], c[i]), max(o[i], c[i])
    ax.add_patch(plt.Rectangle((i - 0.3, lo), 0.6, max(hi - lo, 0.01), color=col, zorder=2))

for ia, pa, ib, pb, s, up in legs:
    if ib < i0 or ia > i1:
        continue
    k = strength(s)
    col = WEAK if k == "weak" else MED if k == "medium" else (STRONG_UP if up else STRONG_DN)
    lw = 1.2 if k == "weak" else 2.2 if k == "medium" else 3.6
    ax.plot([ia - i0, ib - i0], [pa, pb], color=col, lw=lw, solid_capstyle="round", zorder=5)

ax.set_title(f"LTF swing legs by SLOPE strength — weak(grey) / medium(amber) / strong(green-up,red-down)   "
             f"[{df.index[i0].date()}]", color="#e6edf3", fontsize=12)
ax.tick_params(colors="#6b7886")
for sp in ax.spines.values():
    sp.set_color("#232e3a")
plt.tight_layout()
out = os.path.join(HERE, "output", "slope_moves.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=110, facecolor="#0a0e13")
print("saved", os.path.relpath(out, os.path.join(HERE, "..")))
