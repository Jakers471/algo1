"""
Multi-Timeframe Efficiency Heatmap (rebuild of the lost quanted-era favorite).

35 rows = 5 timeframes (1m / 5m / 15m / 1h / 4h) x 7 lookbacks each. Color = signed directional
EFFICIENCY over each lookback = net displacement / total path length (Kaufman ratio, in [-1,1]):
  teal = efficient UP (bull) · red = efficient DOWN (bear) · black = chop (|eff| small).
Each TF's efficiency is aligned onto a common 1m timeline (forward-fill). Coarser scales weighted
heavier (w) and collapsed into the top price-regime coloring + the score line. Threshold +/-0.12.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_efficiency_heatmap.py"
  python "strategy research/structure_detection/analysis/mtf_efficiency_heatmap.py" --bars 3000
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG = "#080b11"
TEAL, RED, GREY, GOLD, TXT = "#14e0c0", "#ff3b3b", "#c9d2dc", "#e0b83a", "#9aa7b4"
TFS = ["1m", "5m", "15m", "60m", "4h"]
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "60m": 60, "4h": 240}
TF_LABEL = {"1m": "1m", "5m": "5m", "15m": "15m", "60m": "1h", "4h": "4h"}
THRESH = 0.12

CMAP = LinearSegmentedColormap.from_list("eff", [
    (0.00, "#ff2f2f"), (0.34, "#2a0202"), (0.47, "#000000"),
    (0.53, "#000000"), (0.66, "#02241f"), (1.00, "#10f0d2")])


def human(m):
    if m < 60:
        return f"{int(m)}m"
    if m < 1440:
        return f"{m/60:.0f}h"
    return f"{m/1440:.0f}d"


def efficiency(close, lb):
    net = close - close.shift(lb)
    path = close.diff().abs().rolling(lb).sum()
    return (net / path).clip(-1, 1)


def tf_frame(tf, since):
    if tf == "4h":
        h1 = load_tf("60m").dropna()
        df = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    else:
        df = load_tf(tf).dropna()
    return df[df.index >= since]


def main(bars):
    base = load_tf("1m").dropna()
    win = base.iloc[-bars:]
    idx = win.index
    since = idx[0] - pd.Timedelta(days=60)          # warm-up for the longest 4h lookback (256*4h)

    rows, labels, weights = [], [], []
    for tf in TFS:
        df = tf_frame(tf, since)
        lbs = [2 if tf == "1m" else 3, 8, 16, 32, 64, 128, 256]
        for lb in lbs:
            e = efficiency(df["close"], lb).reindex(idx, method="ffill").to_numpy()
            rows.append(np.nan_to_num(e))
            dur = lb * TF_MIN[tf]
            w = np.log2(dur) + 1
            weights.append(w)
            labels.append(f"lb={lb} ({human(dur)}) w={w:.1f}")
    mat = np.array(rows)                              # (35, bars)
    w = np.array(weights)
    score = (w[:, None] * mat).sum(0) / w.sum()       # weighted mean efficiency per column, [-1,1]
    reg = np.where(score > THRESH, 1, np.where(score < -THRESH, -1, 0))

    # ── figure ──
    fig = plt.figure(figsize=(20, 14), facecolor=BG)
    gs = GridSpec(3, 1, height_ratios=[3.0, 0.8, 6.2], hspace=0.05, left=0.055, right=0.93, top=0.955, bottom=0.06)
    axp, axs, axh = (fig.add_subplot(gs[i]) for i in range(3))
    x = np.arange(bars)
    for ax in (axp, axs, axh):
        ax.set_facecolor(BG)
        ax.tick_params(colors=TXT, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")

    def runs(a):
        out, i, n = [], 0, len(a)
        while i < n:
            j = i
            while j < n and a[j] == a[i]:
                j += 1
            out.append((i, j - 1, a[i]))
            i = j
        return out

    # price panel: regime background + regime-colored price
    c = win["close"].to_numpy()
    col = {1: TEAL, -1: RED, 0: GREY}
    for a, b, r in runs(reg):
        if r != 0:
            axp.axvspan(a, b + 1, color=col[r], alpha=0.06, zorder=0)
    axp.plot(x, c, color=GREY, lw=0.7, zorder=2)
    for a, b, r in runs(reg):
        if r != 0:
            axp.plot(x[a:b + 2], c[a:b + 2], color=col[r], lw=0.8, zorder=3)
    axp.set_xlim(0, bars)
    axp.set_ylabel("Price", color=TXT, fontsize=8)
    axp.yaxis.set_label_position("right"); axp.yaxis.tick_right()
    axp.set_xticks([])
    for lab, cc in [("Bull regime", TEAL), ("Bear regime", RED), ("Chop regime", GREY)]:
        axp.plot([], [], color=cc, lw=3, label=lab)
    axp.legend(loc="upper left", facecolor=BG, edgecolor="#1c2733", labelcolor=TXT, fontsize=7)

    # score panel
    axs.axhline(THRESH, color="#2a3742", lw=0.6, ls="--")
    axs.axhline(-THRESH, color="#2a3742", lw=0.6, ls="--")
    axs.axhline(0, color="#1c2733", lw=0.5)
    axs.plot(x, score, color=GREY, lw=0.6)
    axs.fill_between(x, 0, score, where=score > 0, color=TEAL, alpha=0.5, lw=0)
    axs.fill_between(x, 0, score, where=score < 0, color=RED, alpha=0.5, lw=0)
    axs.set_xlim(0, bars); axs.set_ylim(-1, 1)
    axs.set_ylabel("Score", color=TXT, fontsize=8)
    axs.yaxis.set_label_position("right"); axs.yaxis.tick_right()
    axs.set_yticks([-THRESH, 0, THRESH]); axs.set_yticklabels(["-0.12", "0.00", "+0.12"])
    axs.set_xticks([])

    # heatmap
    nrow = mat.shape[0]
    axh.imshow(mat, aspect="auto", cmap=CMAP, vmin=-1, vmax=1,
               extent=[0, bars, nrow, 0], interpolation="nearest")
    for k in range(7, nrow, 7):
        axh.axhline(k, color="#0b0e14", lw=1.4)
    axh.set_xlim(0, bars); axh.set_ylim(nrow, 0)
    axh.set_yticks([])
    # TF labels (left) + lookback labels (right)
    for b, tf in enumerate(TFS):
        axh.text(-bars * 0.006, b * 7 + 3.5, TF_LABEL[tf], color=GOLD, fontsize=11, fontweight="bold",
                 ha="right", va="center")
    for r, lab in enumerate(labels):
        axh.text(bars * 1.004, r + 0.5, lab, color="#5a6675", fontsize=5.5, ha="left", va="center")
    # date ticks
    ticks = np.linspace(0, bars - 1, 11).astype(int)
    axh.set_xticks(ticks)
    axh.set_xticklabels([idx[t].strftime("%Y-%m-%d %H:%M") for t in ticks], rotation=30, ha="right", fontsize=6)

    # colorbar
    cax = fig.add_axes([0.055, 0.015, 0.30, 0.012])
    grad = np.linspace(-1, 1, 256)[None, :]
    cax.imshow(grad, aspect="auto", cmap=CMAP, extent=[-1, 1, 0, 1])
    cax.set_yticks([]); cax.set_xticks([-1, -THRESH, 0, THRESH, 1])
    cax.set_xticklabels(["-1 (pure bear)", "-0.12", "0 (chop)", "+0.12", "+1 (pure bull)"], fontsize=6)
    cax.tick_params(colors=TXT)
    for sp in cax.spines.values():
        sp.set_color("#1c2733")

    fig.suptitle(f"NQ  |  Multi-Timeframe Efficiency Heatmap  |  {nrow} rows (5 TFs x 7 lookbacks)  |  "
                 f"{bars:,} bars  |  {idx[0].date()} to {idx[-1].date()}  |  threshold +/-{THRESH}",
                 color=TXT, fontsize=11, y=0.985)
    out = os.path.join(os.path.dirname(__file__), "output", "mtf_efficiency_heatmap.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=BG)
    print(f"{bars:,} bars {idx[0]} -> {idx[-1]}")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=10000)
    a = ap.parse_args()
    main(a.bars)
