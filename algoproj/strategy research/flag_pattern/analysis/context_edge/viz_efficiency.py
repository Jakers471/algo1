"""
Visualize ingredient 1 — what "multi-scale efficiency context" actually measures.

Picks a real HIGH-context breakout and a real LOW-context breakout and draws, on the actual price
leading into each, the "net move" (straight line, start->breakout) vs the real wiggly "path" for a
couple of lookbacks. Efficiency = net / path = how STRAIGHT price traveled to get there. High =
trending into the breakout (structure agrees); low = chopping into it. Output: a PNG.

Run: python ".../analysis/context_edge/viz_efficiency.py"
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))  # algoproj/
from algokit.data import load_tf

SCALES = [10, 20, 40, 80, 160]
DRAW = [40, 160]          # lookbacks to draw net-move lines for (keep it readable)


def eff(close, i, L):
    seg = close[i - L:i + 1]
    path = np.abs(np.diff(seg)).sum()
    if path == 0:
        return 0.0, 0.0, 0.0
    net = seg[-1] - seg[0]
    return abs(net) / path, net, path


def composite(close, i, d):
    return float(np.nanmean([eff(close, i, L)[0] * np.sign(close[i] - close[i - L]) * d for L in SCALES]))


def panel(ax, close, bi, ctx, color):
    x0, x1 = bi - 160, bi + 30
    xs = np.arange(x0, x1) - bi                      # bar index relative to breakout (0 = breakout)
    ax.plot(xs, close[x0:x1], color="#cfd8e3", lw=1.3, zorder=2)       # the real path
    ax.axvline(0, color="#ffd700", lw=1.2, ls="--", zorder=1)
    ax.scatter([0], [close[bi]], color="#ffd700", s=40, zorder=5)
    ax.text(2, close[bi], "breakout", color="#ffd700", fontsize=9, va="center")
    lines = []
    for L, col in zip(DRAW, ["#4c8dff", "#a78bfa"]):
        e, net, path = eff(close, bi, L)
        ax.plot([-L, 0], [close[bi - L], close[bi]], color=col, lw=2, ls="-", zorder=4)   # net-move line
        ax.scatter([-L], [close[bi - L]], color=col, s=25, zorder=4)
        lines.append(f"L={L:>3}:  net {net:+.0f}  /  path {path:.0f}  =  eff {e:.2f}")
    ax.set_title(f"composite context = {ctx:+.2f}", color=color, fontsize=12, fontweight="bold")
    ax.text(0.02, 0.02, "\n".join(lines), transform=ax.transAxes, color="#cfd8e3", fontsize=9,
            va="bottom", ha="left", family="monospace",
            bbox=dict(boxstyle="round", fc="#0e151d", ec="#232e3a"))
    ax.set_xlabel("bars relative to breakout")
    ax.set_ylabel("price")
    ax.tick_params(colors="#9aa7b4", labelsize=8)
    ax.set_facecolor("#131a23")


def main(tf="5m"):
    ms = json.load(open(os.path.join(HERE, "..", "..", "findings", f"flag_breakout_{tf}.json")))["matches"]
    df = load_tf(tf)[["open", "high", "low", "close"]].dropna()
    close = df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    n = len(close)

    cand = []
    for m in ms:
        if m["side"] != "long":
            continue
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi < 160 or bi + 30 >= n or ts[bi] != m["entry"]:
            continue
        cand.append((composite(close, bi, 1), bi))
    cand.sort()
    low_ctx, low_bi = cand[len(cand) // 20]          # ~5th percentile (choppy into breakout)
    high_ctx, high_bi = cand[-len(cand) // 20]        # ~95th percentile (trending into breakout)

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.patch.set_facecolor("#0f0f1a")
    panel(axes[0], close, high_bi, high_ctx, "#34d399")
    panel(axes[1], close, low_bi, low_ctx, "#f87171")
    fig.suptitle("Ingredient 1 — efficiency = how STRAIGHT price traveled into the breakout\n"
                 "colored lines = net move (start→breakout);  grey = the real path;  "
                 "straight net ≈ path → high eff (trend) · wiggly path ≫ net → low eff (chop)",
                 color="#e0e0e0", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, "viz_efficiency.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"high-context breakout: composite {high_ctx:+.2f}  |  low-context: composite {low_ctx:+.2f}")
    print(f"saved {png}")


if __name__ == "__main__":
    main()
