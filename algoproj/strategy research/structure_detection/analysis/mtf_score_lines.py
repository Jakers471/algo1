"""
MTF efficiency scores as 5 lines — watch the timeframes diverge and re-converge over years.

One line per timeframe (1m/5m/15m/1h/4h). Each line = that TF's aggregate regime score = the
weighted mean of its 7 lookbacks' signed directional efficiency (same math as the heatmap), in
[-1,+1]. Fast TFs drawn faint/thin, slow TFs bolder, so the slow structure reads on top of the fast
noise. The +/-0.12 chop band is shaded. Sharp, thin, dark.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_lines.py"
  python "strategy research/structure_detection/analysis/mtf_score_lines.py" --years 2
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG = "#080b11"
TXT = "#9aa7b4"
THRESH = 0.12
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "60m": 60, "4h": 240}
LOOKBACKS = [3, 8, 16, 32, 64, 128, 256]
# fast -> slow : (color, linewidth, alpha)
STYLE = {
    "1m":  ("#4a6a8a", 0.35, 0.35),
    "5m":  ("#3fa7d6", 0.40, 0.50),
    "15m": ("#3fd68a", 0.50, 0.75),
    "60m": ("#e0b83a", 0.70, 0.95),
    "4h":  ("#ff5b5b", 0.90, 1.00),
}
LABEL = {"1m": "1m", "5m": "5m", "15m": "15m", "60m": "1h", "4h": "4h"}


def score_tf(df, tf):
    close = df["close"]
    num, wsum = np.zeros(len(df)), 0.0
    for lb in LOOKBACKS:
        net = close - close.shift(lb)
        path = close.diff().abs().rolling(lb).sum()
        w = np.log2(lb * TF_MIN[tf]) + 1
        num += w * np.nan_to_num((net / path).clip(-1, 1).to_numpy())
        wsum += w
    return pd.Series(num / wsum, index=df.index)


def tf_frame(tf, since):
    if tf == "4h":
        h1 = load_tf("60m").dropna()
        df = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    else:
        df = load_tf(tf).dropna()
    return df[df.index >= since]


def main(years, smooth):
    end = load_tf("60m").dropna().index[-1]
    plot_start = end - pd.Timedelta(days=int(365 * years))
    warm = plot_start - pd.Timedelta(days=60)

    fig, ax = plt.subplots(figsize=(24, 9), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axhspan(-THRESH, THRESH, color="#141a22", zorder=0)          # chop band
    ax.axhline(0, color="#1c2733", lw=0.6, zorder=1)
    for tf in ["1m", "5m", "15m", "60m", "4h"]:
        s = score_tf(tf_frame(tf, warm), tf)
        if smooth:
            s = s.resample(smooth).mean()                          # daily-average out the tick noise
        s = s[s.index >= plot_start]
        col, lw, al = STYLE[tf]
        ax.plot(s.index, s.to_numpy(), color=col, lw=lw + 0.4, alpha=min(al + 0.15, 1.0),
                antialiased=True, solid_capstyle="round", label=LABEL[tf],
                zorder=2 + list(STYLE).index(tf))

    ax.set_xlim(plot_start, end)
    ax.set_ylim(-1, 1)
    ax.set_ylabel("efficiency score  (bull +1 / chop 0 / bear -1)", color=TXT, fontsize=9)
    ax.tick_params(colors=TXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#1c2733")
    ax.grid(True, color="#0f151d", lw=0.4, zorder=0)
    leg = ax.legend(loc="upper left", ncol=5, facecolor=BG, edgecolor="#1c2733",
                    labelcolor=TXT, fontsize=9, framealpha=1.0)
    for line in leg.get_lines():
        line.set_linewidth(2.0)
    ax.set_title(f"NQ  |  MTF efficiency score per timeframe  |  last {years} years  |  "
                 f"watch them diverge & re-converge   (chop band +/-{THRESH})",
                 color="#e6edf3", fontsize=12)
    fig.tight_layout()
    out = os.path.join(os.path.dirname(__file__), "output", "mtf_score_lines.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=170, facecolor=BG)
    print(f"{plot_start.date()} -> {end.date()}")
    print("saved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    ap.add_argument("--smooth", default="1D", help="resample rule to smooth each line (e.g. 1D, 4H, 1H); '' = raw")
    a = ap.parse_args()
    main(a.years, a.smooth or None)
