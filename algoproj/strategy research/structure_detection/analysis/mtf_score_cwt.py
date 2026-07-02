"""
CWT + Fourier of the aggregate MTF efficiency score — pull hidden scale-structure out of the noise soup.

Builds the single aggregate regime score (weighted mean of all 5 TFs x 7 lookbacks of signed
efficiency, hourly base), then decomposes it:
  • CWT scalogram (Morlet, FFT method, pure numpy) — power at each PERIOD over TIME (what cycle, when).
  • Global power spectrum (time-averaged scalogram = the Fourier-equivalent) — which periods dominate.
If real cyclic structure hides under the noise, it shows up as bright horizontal ridges.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_cwt.py" --years 4
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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT = "#080b11", "#9aa7b4"
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "60m": 60, "4h": 240}
LOOKBACKS = [3, 8, 16, 32, 64, 128, 256]
W0 = 6.0


def tf_frame(tf, since):
    if tf == "4h":
        h1 = load_tf("60m").dropna()
        df = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    else:
        df = load_tf(tf).dropna()
    return df[df.index >= since]


def aggregate_score(idx, warm):
    num, wsum = np.zeros(len(idx)), 0.0
    for tf in TF_MIN:
        close = tf_frame(tf, warm)["close"]
        for lb in LOOKBACKS:
            net = close - close.shift(lb)
            path = close.diff().abs().rolling(lb).sum()
            eff = (net / path).clip(-1, 1).reindex(idx, method="ffill").to_numpy()
            w = np.log2(lb * TF_MIN[tf]) + 1
            num += w * np.nan_to_num(eff)
            wsum += w
    return num / wsum


def cwt_morlet(sig, scales, dt=1.0, w0=W0):
    sig = np.asarray(sig, float) - np.mean(sig)
    n = len(sig)
    sf = np.fft.fft(sig)
    k = np.fft.fftfreq(n, d=dt) * 2 * np.pi
    coef = np.empty((len(scales), n), complex)
    for i, a in enumerate(scales):
        norm = np.sqrt(2 * np.pi * a / dt) * np.pi ** -0.25
        coef[i] = np.fft.ifft(sf * (norm * np.exp(-0.5 * (a * k - w0) ** 2) * (k > 0)))
    return coef


def hlabel(h):
    if h < 24:
        return f"{h:.0f}h"
    if h < 24 * 30:
        return f"{h/24:.0f}d"
    return f"{h/24/30:.0f}mo"


def main(years):
    base = load_tf("60m").dropna()
    end = base.index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=90)
    idx = base[base.index >= start].index                 # hourly timeline
    sig = aggregate_score(idx, warm)

    n = len(sig)
    scales = np.geomspace(2, n // 4, 180)                  # 2h .. ~n/4 hours
    fourier = 4 * np.pi / (W0 + np.sqrt(2 + W0 ** 2))      # period = fourier * scale (~1.03)
    periods = scales * fourier                              # in hours
    power = np.abs(cwt_morlet(sig, scales)) ** 2
    gpow = power.mean(axis=1)                               # global (time-avg) spectrum
    coi = fourier * np.sqrt(2) * np.minimum(np.arange(n), np.arange(n)[::-1])  # cone of influence (h)

    fig = plt.figure(figsize=(22, 11), facecolor=BG)
    gs = GridSpec(2, 2, height_ratios=[1, 3], width_ratios=[5, 1], hspace=0.08, wspace=0.03,
                  left=0.05, right=0.97, top=0.95, bottom=0.07)
    axs = fig.add_subplot(gs[0, 0]); axc = fig.add_subplot(gs[1, 0], sharex=axs)
    axg = fig.add_subplot(gs[1, 1], sharey=axc)
    for ax in (axs, axc, axg):
        ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")

    axs.axhspan(-0.12, 0.12, color="#141a22"); axs.axhline(0, color="#1c2733", lw=0.6)
    axs.plot(idx, sig, color="#3fd6c0", lw=0.4)
    axs.set_ylim(-0.6, 0.6); axs.set_ylabel("agg score", color=TXT, fontsize=8)
    axs.tick_params(labelbottom=False)
    axs.set_title(f"NQ  |  aggregate MTF efficiency score — CWT scalogram + global spectrum  |  "
                  f"last {years} yr  |  bright ridge = a real cycle", color="#e6edf3", fontsize=12)

    lp = np.log10(power + 1e-9)
    axc.pcolormesh(idx, periods, lp, cmap="magma", shading="auto")
    axc.plot(idx, coi, color="#ffffff", lw=0.6, alpha=0.35)
    axc.fill_between(idx, coi, periods.max(), color=BG, alpha=0.5)
    axc.set_yscale("log"); axc.set_ylim(periods.min(), periods.max())
    axc.set_ylabel("period", color=TXT, fontsize=9)
    yt = [2, 6, 24, 24 * 5, 24 * 21, 24 * 90, 24 * 250]
    yt = [p for p in yt if periods.min() <= p <= periods.max()]
    axc.set_yticks(yt); axc.set_yticklabels([hlabel(p) for p in yt])

    axg.plot(gpow, periods, color="#e0b83a", lw=1.2)
    axg.set_yscale("log"); axg.set_ylim(periods.min(), periods.max())
    axg.tick_params(labelleft=False); axg.set_xlabel("avg power", color=TXT, fontsize=8)
    axg.set_xticks([])

    out = os.path.join(os.path.dirname(__file__), "output", "mtf_score_cwt.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=BG)
    peak = periods[int(np.argmax(gpow))]
    print(f"{start.date()} -> {end.date()} | {n:,} hourly samples")
    print(f"dominant global period ~ {hlabel(peak)}")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    a = ap.parse_args()
    main(a.years)
