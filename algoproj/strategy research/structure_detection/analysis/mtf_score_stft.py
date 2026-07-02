"""
STFT (windowed-Fourier) spectrogram of the aggregate MTF efficiency score — the Fourier counterpart
to the CWT scalogram. Fixed time-frequency resolution (vs the wavelet's scale-adaptive one), so it's
a useful cross-check: a real cycle shows as a persistent horizontal band in BOTH.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_stft.py" --years 4
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
from scipy.signal import spectrogram

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mtf_score_cwt import aggregate_score  # reuse the exact aggregate-score builder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT = "#080b11", "#9aa7b4"


def hlabel(h):
    return f"{h:.0f}h" if h < 24 else (f"{h/24:.0f}d" if h < 24 * 30 else f"{h/24/30:.0f}mo")


def main(years):
    base = load_tf("60m").dropna()
    end = base.index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=90)
    idx = base[base.index >= start].index
    sig = aggregate_score(idx, warm)
    sig = sig - np.mean(sig)

    nper = 24 * 30                                  # ~1-month window (fs = 1 sample/hour)
    f, t, Sxx = spectrogram(sig, fs=1.0, nperseg=nper, noverlap=int(nper * 0.9), scaling="density")
    f = f[1:]; Sxx = Sxx[1:]                        # drop DC
    periods = 1.0 / f                               # hours
    times = start + pd.to_timedelta(t, unit="h")

    fig = plt.figure(figsize=(22, 10), facecolor=BG)
    gs = GridSpec(2, 1, height_ratios=[1, 3], hspace=0.08, left=0.05, right=0.98, top=0.94, bottom=0.07)
    axs, axp = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    for ax in (axs, axp):
        ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")

    axs.axhspan(-0.12, 0.12, color="#141a22"); axs.axhline(0, color="#1c2733", lw=0.6)
    axs.plot(idx, sig, color="#3fd6c0", lw=0.4); axs.set_ylim(-0.6, 0.6)
    axs.set_ylabel("agg score", color=TXT, fontsize=8); axs.tick_params(labelbottom=False)
    axs.set_title(f"NQ  |  aggregate MTF efficiency score — STFT (windowed-Fourier) spectrogram  |  "
                  f"last {years} yr  |  persistent band = a real cycle", color="#e6edf3", fontsize=12)

    axp.pcolormesh(times, periods, np.log10(Sxx + 1e-12), cmap="magma", shading="auto")
    axp.set_yscale("log"); axp.set_ylim(periods.min(), periods.max())
    axp.set_ylabel("period", color=TXT, fontsize=9)
    yt = [p for p in [4, 12, 24, 24 * 5, 24 * 21, 24 * 90, 24 * 250] if periods.min() <= p <= periods.max()]
    axp.set_yticks(yt); axp.set_yticklabels([hlabel(p) for p in yt])

    out = os.path.join(os.path.dirname(__file__), "output", "mtf_score_stft.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=BG)
    gmean = Sxx.mean(axis=1)
    print(f"{start.date()} -> {end.date()} | dominant STFT period ~ {hlabel(periods[int(np.argmax(gmean))])}")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    a = ap.parse_args()
    main(a.years)
