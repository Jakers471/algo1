"""
Per-timeframe CWT — wavelet-decompose EACH timeframe's efficiency score separately (not the aggregate).

The aggregate blends all 5 TFs together and washes out per-TF structure. Here each TF's own score
(the 5 lines of mtf_score_lines) gets its own CWT scalogram, stacked. Shows which PERIOD BAND each
timeframe actually occupies (they act like a filter bank) and whether any single TF hides a cycle the
aggregate buried.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_cwt_perTF.py" --years 4
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mtf_score_lines import score_tf, tf_frame, LABEL
from mtf_score_cwt import cwt_morlet, W0, hlabel
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT = "#080b11", "#9aa7b4"
TFS = ["1m", "5m", "15m", "60m", "4h"]


def main(years):
    base = load_tf("60m").dropna()
    end = base.index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=90)
    idx = base[base.index >= start].index                       # common hourly timeline
    n = len(idx)
    scales = np.geomspace(2, n // 4, 150)
    fourier = 4 * np.pi / (W0 + np.sqrt(2 + W0 ** 2))
    periods = scales * fourier
    coi = fourier * np.sqrt(2) * np.minimum(np.arange(n), np.arange(n)[::-1])

    fig, axes = plt.subplots(len(TFS), 1, figsize=(20, 16), facecolor=BG, sharex=True)
    for ax, tf in zip(axes, TFS):
        sig = score_tf(tf_frame(tf, warm), tf).reindex(idx, method="ffill").to_numpy()
        power = np.abs(cwt_morlet(np.nan_to_num(sig), scales)) ** 2
        ax.set_facecolor(BG)
        ax.pcolormesh(idx, periods, np.log10(power + 1e-9), cmap="magma", shading="auto")
        ax.plot(idx, coi, color="#fff", lw=0.5, alpha=0.3)
        ax.fill_between(idx, coi, periods.max(), color=BG, alpha=0.5)
        ax.set_yscale("log"); ax.set_ylim(periods.min(), periods.max())
        yt = [p for p in [6, 24, 24 * 5, 24 * 21, 24 * 90, 24 * 250] if periods.min() <= p <= periods.max()]
        ax.set_yticks(yt); ax.set_yticklabels([hlabel(p) for p in yt], fontsize=7)
        ax.tick_params(colors=TXT, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")
        ax.text(0.006, 0.5, LABEL[tf], transform=ax.transAxes, color="#e0b83a",
                fontsize=15, fontweight="bold", ha="left", va="center")

    axes[0].set_title(f"NQ  |  per-timeframe CWT — each TF's efficiency score wavelet-decomposed "
                      f"separately  |  last {years} yr  |  where does each TF's power live?",
                      color="#e6edf3", fontsize=12)
    fig.tight_layout(h_pad=0.4)
    out = os.path.join(os.path.dirname(__file__), "output", "mtf_score_cwt_perTF.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=140, facecolor=BG)
    print(f"{start.date()} -> {end.date()} | {n:,} hourly samples")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    a = ap.parse_args()
    main(a.years)
