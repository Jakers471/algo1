"""
MTF convergence — collapse the 5 timeframe scores into ONE readable "agreement" line, then a quick
edge read: does full agreement across timeframes actually predict a forward move, or is it noise?

At each hourly bar:
  agree  = |sum of the 5 score-signs| / 5   -> 0.2 (3-2 split) .. 1.0 (all 5 same side)   [direction consensus]
  spread = std of the 5 scores               -> low = converged, high = diverged
Both smoothed for readability. Then bucket bars by agreement and measure forward directional return
(1d / 3d / 5d ahead) — if all-5-aligned beats the split buckets, there's signal; if flat, it's noise.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_convergence.py" --years 4
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
from mtf_score_lines import score_tf, tf_frame
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT = "#080b11", "#9aa7b4"
TFS = ["1m", "5m", "15m", "60m", "4h"]
SMOOTH = 24   # hourly bars to smooth the convergence line (1 day)


def main(years):
    base = load_tf("60m").dropna()
    end = base.index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=90)
    idx = base[base.index >= start].index
    close = base["close"].reindex(idx).to_numpy()

    S = pd.DataFrame({tf: score_tf(tf_frame(tf, warm), tf).reindex(idx, method="ffill") for tf in TFS}).fillna(0)
    sgn = np.sign(S.to_numpy())
    agree = np.abs(sgn.sum(1)) / 5.0                       # 0.2 / 0.6 / 1.0
    spread = S.to_numpy().std(1)
    mean_score = S.to_numpy().mean(1)
    direction = np.sign(mean_score)
    agree_s = pd.Series(agree, idx).rolling(SMOOTH).mean().to_numpy()

    # ── edge read: forward directional close return by agreement bucket ──
    n = len(idx)
    print(f"{start.date()} -> {end.date()} | {n:,} hourly bars\n")
    print("does timeframe agreement predict? forward directional return (dir = sign of mean score)")
    print(f"{'bucket':<22}{'n':>8}{'1d win/mean':>16}{'3d win/mean':>16}{'5d win/mean':>16}")
    for name, mask in [("all-5 aligned (1.0)", agree == 1.0),
                       ("4-1 split (0.6)", np.isclose(agree, 0.6)),
                       ("3-2 split (0.2)", np.isclose(agree, 0.2))]:
        row = f"{name:<22}{int(mask.sum()):>8}"
        for h in (24, 72, 120):
            e = np.where(mask)[0]; e = e[e + h < n]
            r = (close[e + h] / close[e] - 1.0) * direction[e] * 100
            row += f"{f'{(r>0).mean()*100:.0f}% / {r.mean():+.3f}':>16}" if len(r) else f"{'-':>16}"
        print(row)

    # ── the convergence line ──
    fig = plt.figure(figsize=(22, 10), facecolor=BG)
    gs = GridSpec(2, 1, height_ratios=[1.4, 1], hspace=0.06, left=0.05, right=0.97, top=0.94, bottom=0.07)
    axp = fig.add_subplot(gs[0])
    axc = fig.add_subplot(gs[1], sharex=axp)
    for ax in (axp, axc):
        ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")
    axp.plot(idx, close, color="#c9d4df", lw=0.5)
    axp.set_ylabel("NQ", color=TXT, fontsize=8); axp.tick_params(labelbottom=False)
    axp.set_title(f"NQ  |  MTF convergence — one line: how tightly the 5 timeframes agree  "
                  f"(1.0 = all same side)  |  last {years} yr", color="#e6edf3", fontsize=12)
    axc.axhline(1.0, color="#1c2733", lw=0.5); axc.axhline(0.2, color="#1c2733", lw=0.5)
    axc.fill_between(idx, 0.85, 1.0, color="#14e0c0", alpha=0.08)      # high-convergence zone
    axc.plot(idx, agree_s, color="#e0b83a", lw=0.8)
    axc.set_ylim(0.15, 1.02); axc.set_ylabel("agreement (smoothed)", color=TXT, fontsize=8)
    out = os.path.join(os.path.dirname(__file__), "output", "mtf_convergence.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=BG)
    print("\nsaved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    a = ap.parse_args()
    main(a.years)
