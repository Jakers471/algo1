"""
Dead-simple illustration of EFFICIENCY (ingredient 1), no trading clutter.

Two toy price paths that end at the SAME place (+10) — one trends there, one chops there.
Efficiency = straight-line move (net) / distance actually walked (path). Same destination, very
different efficiency. That single number is what the context score measures (at 5 zoom levels).

Run: python ".../analysis/context_edge/viz_efficiency_simple.py"
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

TREND = np.array([0, 1.2, 2.0, 2.6, 3.8, 4.4, 5.5, 6.1, 7.4, 8.0, 8.9, 9.4, 10.0])
CHOP = np.array([0, 3.2, -0.8, 3.6, 0.2, 4.8, 1.0, 5.6, 2.2, 7.0, 3.4, 8.2, 10.0])


def panel(ax, y, color, label):
    x = np.arange(len(y))
    net = abs(y[-1] - y[0])
    path = np.abs(np.diff(y)).sum()
    e = net / path
    ax.plot(x, y, color="#cfd8e3", lw=1.6, marker="o", ms=4, zorder=3, label="the real path (walked)")
    ax.annotate("", xy=(x[-1], y[-1]), xytext=(x[0], y[0]),
                arrowprops=dict(arrowstyle="->", color=color, lw=2.4), zorder=2)
    ax.text(x[-1] * 0.5, (y[0] + y[-1]) / 2 + 0.6, "straight-line move (net)", color=color,
            fontsize=9, ha="center")
    ax.scatter([x[0], x[-1]], [y[0], y[-1]], color=color, s=45, zorder=4)
    ax.set_title(f"{label}\nefficiency = net {net:.0f} / path {path:.0f} = {e:.2f}",
                 color=color, fontsize=13, fontweight="bold")
    ax.tick_params(colors="#9aa7b4", labelsize=8)
    ax.set_facecolor("#131a23")
    ax.set_xlabel("time →"); ax.set_ylabel("price")
    ax.legend(loc="upper left", fontsize=8, facecolor="#0e151d", edgecolor="#232e3a", labelcolor="#cfd8e3")


def main():
    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    fig.patch.set_facecolor("#0f0f1a")
    panel(axes[0], TREND, "#34d399", "TRENDING (efficient)")
    panel(axes[1], CHOP, "#f87171", "CHOPPY (inefficient)")
    fig.suptitle('Efficiency = "as the crow flies" ÷ "distance actually walked"\n'
                 "both paths end at +10 — but one went straight there, one wandered",
                 color="#e0e0e0", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, "viz_efficiency_simple.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"saved {png}")


if __name__ == "__main__":
    main()
