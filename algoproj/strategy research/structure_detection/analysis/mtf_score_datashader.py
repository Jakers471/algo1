"""
MTF score "noise soup" rendered CRISPLY with datashader — no overplot blur.

The matplotlib line plot at native resolution (millions of 1m/5m points over 4 years) was an
unreadable smear. datashader rasterizes each timeframe's score into a density image so the structure
(where a TF spends its time, how tight/wide it swings) reads sharply instead of blurring. Each TF is
shaded in its own color and composited over a dark canvas; the +/-0.12 chop band + 0 line are drawn
underneath in matplotlib.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_datashader.py" --years 4
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import datashader as ds
import datashader.transfer_functions as dtf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from mtf_score_lines import score_tf, tf_frame, THRESH  # reuse the exact score math

BG = "#080b11"
TXT = "#9aa7b4"
ORDER = ["1m", "5m", "15m", "60m", "4h"]                 # fast -> slow (slow composited on top)
COLOR = {"1m": "#4a6a8a", "5m": "#3fa7d6", "15m": "#3fd68a", "60m": "#e0b83a", "4h": "#ff5b5b"}
LABEL = {"1m": "1m", "5m": "5m", "15m": "15m", "60m": "1h", "4h": "4h"}
YR = (-0.65, 0.65)
WIDTH, HEIGHT = 2400, 900


def main(years):
    end = tf_frame("60m", pd.Timestamp("2000-01-01")).index[-1]
    start = end - pd.Timedelta(days=int(365 * years))
    warm = start - pd.Timedelta(days=60)
    xr = (int(start.value), int(end.value))              # ns

    cvs = ds.Canvas(plot_width=WIDTH, plot_height=HEIGHT, x_range=xr, y_range=YR)
    imgs, npts = [], {}
    for tf in ORDER:
        s = score_tf(tf_frame(tf, warm), tf)
        s = s[s.index >= start].dropna()
        df = pd.DataFrame({"t": s.index.astype("int64"), "y": s.to_numpy()})
        npts[tf] = len(df)
        agg = cvs.line(df, "t", "y", agg=ds.count())
        imgs.append(dtf.shade(agg, cmap=[COLOR[tf]], how="eq_hist", min_alpha=35))
    rgba = np.asarray(dtf.stack(*imgs).to_pil())          # composited RGBA, top row = max y

    fig, ax = plt.subplots(figsize=(24, 9), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axhspan(-THRESH, THRESH, color="#141a22", zorder=0)
    ax.axhline(0, color="#28323d", lw=0.8, zorder=1)
    ax.imshow(rgba, extent=[xr[0], xr[1], YR[0], YR[1]], origin="upper", aspect="auto", zorder=2,
              interpolation="nearest")
    ax.set_xlim(*xr); ax.set_ylim(*YR)
    ticks = pd.date_range(start, end, periods=9)
    ax.set_xticks(ticks.astype("int64"))
    ax.set_xticklabels([d.strftime("%Y-%m") for d in ticks])
    ax.set_ylabel("efficiency score  (bull +1 / chop 0 / bear -1)", color=TXT, fontsize=9)
    ax.tick_params(colors=TXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#1c2733")
    handles = [plt.Line2D([], [], color=COLOR[tf], lw=3, label=LABEL[tf]) for tf in ORDER]
    leg = ax.legend(handles=handles, loc="upper left", ncol=5, facecolor=BG, edgecolor="#1c2733",
                    labelcolor=TXT, fontsize=9, framealpha=1.0)
    ax.set_title(f"NQ  |  MTF efficiency score per timeframe  |  last {years} years  |  "
                 f"datashaded (density, crisp)   chop band +/-{THRESH}", color="#e6edf3", fontsize=12)
    fig.tight_layout()
    out = os.path.join(HERE, "output", "mtf_score_datashader.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=BG)
    print("points:", {k: f"{v:,}" for k, v in npts.items()})
    print("saved", os.path.relpath(out, os.path.dirname(HERE)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=4)
    a = ap.parse_args()
    main(a.years)
