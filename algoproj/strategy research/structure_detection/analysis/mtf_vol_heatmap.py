"""
Multi-Timeframe VOLATILITY heatmap — the clustering tell.

Same 35-cell grid as the efficiency heatmap (5 TFs x 7 lookbacks), but each cell = realized
volatility (rolling std of returns) at that TF/lookback, percentile-ranked (0=calm .. 1=turbulent)
so scales are comparable. Sequential colormap: dark = calm, bright = turbulent.

The point (vs efficiency): efficiency FLICKERED bar-to-bar (no persistence = noise). Volatility
CLUSTERS (persistence is a settled stylized fact), so this heatmap should show SUSTAINED BLOCKS of
color — calm stretches dark, turbulent stretches bright — that your eye can read. Flicker = broken;
sustained bands = the clustering doing real work. 2D top-down (the instrument), not a 3D demo.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_vol_heatmap.py" --years 1
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mtf_score_cwt import tf_frame, hlabel
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT, GOLD = "#080b11", "#9aa7b4", "#e0b83a"
TFS = ["1m", "5m", "15m", "60m", "4h"]
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "60m": 60, "4h": 240}
TF_LABEL = {"1m": "1m", "5m": "5m", "15m": "15m", "60m": "1h", "4h": "4h"}


def main(years):
    base = load_tf("60m").dropna()
    end = base.index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=60)
    idx = base[base.index >= start].index
    close = base["close"].reindex(idx).to_numpy()

    rows, labels, weights = [], [], []
    for tf in TFS:
        ret = tf_frame(tf, warm)["close"].pct_change()
        lbs = [2 if tf == "1m" else 3, 8, 16, 32, 64, 128, 256]
        for lb in lbs:
            rv = ret.rolling(lb).std().reindex(idx, method="ffill")
            rows.append(rv.rank(pct=True).to_numpy())          # 0=calm .. 1=turbulent, per scale
            dur = lb * TF_MIN[tf]
            weights.append(np.log2(dur) + 1)
            labels.append(f"lb={lb} ({hlabel(dur)})")
    mat = np.nan_to_num(np.array(rows))
    w = np.array(weights)
    volscore = (w[:, None] * mat).sum(0) / w.sum()             # aggregate vol regime 0..1

    fig = plt.figure(figsize=(22, 13), facecolor=BG)
    gs = GridSpec(3, 1, height_ratios=[2.4, 0.8, 6.4], hspace=0.06, left=0.05, right=0.99, top=0.955, bottom=0.06)
    axp, axs, axh = (fig.add_subplot(gs[i]) for i in range(3))
    for ax in (axp, axs, axh):
        ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")
    x = np.arange(len(idx))

    axp.plot(x, close, color="#c9d4df", lw=0.6)
    axp.set_xlim(0, len(idx)); axp.set_xticks([]); axp.set_ylabel("NQ", color=TXT, fontsize=8)
    axp.set_title(f"NQ  |  Multi-Timeframe VOLATILITY heatmap  |  35 rows (5 TFs x 7 lookbacks)  |  "
                  f"last {years} yr  |  dark=calm  bright=turbulent  —  sustained blocks = vol clustering",
                  color="#e6edf3", fontsize=12)

    axs.fill_between(x, 0, volscore, color="#ff7b3a", alpha=0.5, lw=0)
    axs.plot(x, volscore, color="#ffb26b", lw=0.6)
    axs.set_xlim(0, len(idx)); axs.set_ylim(0, 1); axs.set_xticks([])
    axs.set_ylabel("vol regime", color=TXT, fontsize=8)

    nrow = mat.shape[0]
    axh.imshow(mat, aspect="auto", cmap="inferno", vmin=0, vmax=1,
               extent=[0, len(idx), nrow, 0], interpolation="nearest")
    for k in range(7, nrow, 7):
        axh.axhline(k, color="#0b0e14", lw=1.4)
    axh.set_xlim(0, len(idx)); axh.set_ylim(nrow, 0); axh.set_yticks([])
    for b, tf in enumerate(TFS):
        axh.text(-len(idx) * 0.006, b * 7 + 3.5, TF_LABEL[tf], color=GOLD, fontsize=12,
                 fontweight="bold", ha="right", va="center")
    for r, lab in enumerate(labels):
        axh.text(len(idx) * 1.003, r + 0.5, lab, color="#5a6675", fontsize=6, ha="left", va="center")
    ticks = np.linspace(0, len(idx) - 1, 10).astype(int)
    axh.set_xticks(ticks)
    axh.set_xticklabels([idx[t].strftime("%Y-%m-%d") for t in ticks], rotation=30, ha="right", fontsize=7)

    cax = fig.add_axes([0.05, 0.012, 0.28, 0.012])
    cax.imshow(np.linspace(0, 1, 256)[None, :], aspect="auto", cmap="inferno", extent=[0, 1, 0, 1])
    cax.set_yticks([]); cax.set_xticks([0, 0.5, 1]); cax.set_xticklabels(["calm", "median", "turbulent"], fontsize=7)
    cax.tick_params(colors=TXT)

    out = os.path.join(os.path.dirname(__file__), "output", "mtf_vol_heatmap.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=140, facecolor=BG)
    # persistence check: autocorrelation of the aggregate vol regime at 1 day
    vs = pd.Series(volscore)
    ac1d = vs.autocorr(24)
    print(f"{start.date()} -> {end.date()} | {len(idx):,} hourly bars")
    print(f"vol-regime autocorrelation @ 1 day: {ac1d:.2f}   (efficiency-agg ~0 = flicker; high = clustering)")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=1)
    a = ap.parse_args()
    main(a.years)
