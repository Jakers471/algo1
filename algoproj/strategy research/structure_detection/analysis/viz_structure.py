"""
Static first-look at the structure detector: candles + the 3-grain swing structure.

Draws a readable slice of candles with each grain's swing zigzag overlaid (LTF faint/fine → HTF
bold/coarse), so we can eyeball whether the stair-stepping highs/lows look like real structure
before wiring the interactive tv_chart view.

Run: python "strategy research/structure_detection/analysis/viz_structure.py" [--start 20000] [--n 600]
"""
import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj/
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "signal")))          # signal_config
from algokit.data import load_tf
import signal_config as cfg
from structure import _atr, swings

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3
STYLE = {"LTF": ("#6b7886", 1.0, 3), "MTF": ("#4c8dff", 1.8, 5), "HTF": ("#ffd700", 2.6, 7)}


def candles(ax, v):
    for i, (o, h, l, c) in enumerate(v[:, :4]):
        col = "#26a69a" if c >= o else "#ef5350"
        ax.plot([i, i], [l, h], color=col, lw=0.6, zorder=2)
        ax.plot([i, i], [o, c], color=col, lw=2.4, zorder=2, solid_capstyle="butt")


def main(w0, n):
    df = load_tf(cfg.TF)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    atr = _atr(values, cfg.ATR_N)
    w1 = min(w0 + n, len(values))
    seg = values[w0:w1]

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(16, 8))
    fig.patch.set_facecolor("#0f0f1a")
    ax.set_facecolor("#0a0e13")
    candles(ax, seg)

    for name, gm in cfg.GRAINS.items():
        col, lw, ms = STYLE[name]
        sw = [(i, p, k) for i, p, k in swings(values, atr, gm) if w0 <= i < w1]
        if not sw:
            continue
        xs = [i - w0 for i, _, _ in sw]
        ps = [p for _, p, _ in sw]
        ax.plot(xs, ps, color=col, lw=lw, alpha=0.9, zorder=4, label=f"{name} ({gm}x ATR, {len(sw)} swings)")
        ax.scatter(xs, ps, color=col, s=ms * 3, zorder=5)

    ax.set_title(f"structure_detection — swing structure at 3 grains  ·  {cfg.TF}  ·  "
                 f"bars {w0}–{w1}  ({df.index[w0].date()})", color="#e0e0e0", fontsize=12)
    ax.legend(loc="upper left", fontsize=9, facecolor="#131a23", edgecolor="#232e3a", labelcolor="#cfd8e3")
    ax.tick_params(colors="#9aa7b4", labelsize=8)
    ax.set_xlabel("bar in window"); ax.set_ylabel("price")
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, f"structure_{w0}_{n}.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"saved {png}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=20000)
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args()
    main(a.start, a.n)
