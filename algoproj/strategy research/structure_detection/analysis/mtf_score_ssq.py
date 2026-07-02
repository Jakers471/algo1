"""
Synchrosqueezed CWT of the aggregate MTF efficiency score — razor-sharp ridges (ref image 1).

Synchrosqueezing reassigns wavelet energy onto thin ridges, so a real cycle snaps into a bright
line instead of the smeared blob a plain CWT gives. Signal = the hourly aggregate MTF efficiency
score (last 4 yr), mean-subtracted; transform via ssqueezepy.ssq_cwt.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_ssq.py"
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                              # sibling: aggregate_score
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj
from algokit.data import load_tf
from mtf_score_cwt import aggregate_score
from ssqueezepy import ssq_cwt

BG, TXT = "#080b11", "#9aa7b4"
YEARS = 4


def hlabel(h):
    if h < 24:
        return f"{h:.0f}h"
    if h < 24 * 30:
        return f"{h/24:.0f}d"
    return f"{h/24/30:.0f}mo"


DT_H = 4                                          # resample step (hours): keeps days..months, cuts memory
base = load_tf("60m").dropna()
end = base.index[-1]
start = end - pd.Timedelta(days=int(365 * YEARS))
warm = start - pd.Timedelta(days=90)
idx = base[base.index >= start].index
s = pd.Series(aggregate_score(idx, warm), index=idx).resample(f"{DT_H}h").mean().dropna()
idx = s.index
sig = s.to_numpy() - s.mean()

Tx, Wx, freqs, scales = ssq_cwt(sig, fs=1.0)     # freqs in cycles/sample
mag = np.abs(Tx)
periods = DT_H / freqs                             # hours (sample step = DT_H hours)
order = np.argsort(periods)                       # ascending period for plotting
periods, mag = periods[order], mag[order]

# global (time-averaged) ridge spectrum -> dominant period
gpow = mag.mean(axis=1)
dom = periods[int(np.argmax(gpow))]

fig = plt.figure(figsize=(24, 12), facecolor=BG)
gs = GridSpec(2, 1, height_ratios=[1, 3], hspace=0.07, left=0.05, right=0.98, top=0.95, bottom=0.06)
axs, axc = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
for ax in (axs, axc):
    ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#1c2733")

axs.axhspan(-0.12, 0.12, color="#141a22"); axs.axhline(0, color="#1c2733", lw=0.6)
axs.plot(idx, sig, color="#3fd6c0", lw=0.4)
axs.set_ylim(-0.6, 0.6); axs.set_ylabel("agg score", color=TXT, fontsize=8)
axs.tick_params(labelbottom=False)
axs.set_title(f"NQ  |  aggregate MTF efficiency score — SYNCHROSQUEEZED CWT (sharp ridges)  |  "
              f"last {YEARS} yr  |  a bright thin ridge = a real cycle", color="#e6edf3", fontsize=12)

vmax = np.percentile(mag, 99.7)
vmin = vmax / 200.0
axc.pcolormesh(idx, periods, np.clip(mag, vmin, vmax), cmap="turbo",
               norm=LogNorm(vmin=vmin, vmax=vmax), shading="auto")
axc.set_yscale("log"); axc.set_ylim(periods.min(), periods.max())
axc.set_ylabel("period", color=TXT, fontsize=9)
yt = [2, 6, 24, 24 * 5, 24 * 21, 24 * 90, 24 * 250]
yt = [p for p in yt if periods.min() <= p <= periods.max()]
axc.set_yticks(yt); axc.set_yticklabels([hlabel(p) for p in yt])

out = os.path.join(HERE, "output", "mtf_score_ssq.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=150, facecolor=BG)
print(f"{start.date()} -> {end.date()} | {len(sig):,} hourly samples")
print(f"dominant synchrosqueezed ridge period ~ {hlabel(dom)}")
print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(HERE))))
