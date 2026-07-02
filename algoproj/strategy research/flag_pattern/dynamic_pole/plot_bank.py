"""Plot the parametric template bank as candles, so you can SEE every variation before scanning."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "signal"))
sys.path.insert(0, HERE)
import signal_config as cfg
import template_bank as tb

bank = tb.make_bank(cfg.WINDOW, cfg.BANK_POLE_BARS, cfg.BANK_POLE_CURVE, cfg.BANK_FLAG_SLOPE)
n = len(bank)
cols = 6
rows = (n + cols - 1) // cols
fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 2.5 * rows), facecolor="#0a0e13")
axes = axes.flatten()

for ax, item in zip(axes, bank):
    t = item["bull"]
    o, h, l, c = (t[:, k] * 100 for k in range(4))
    pb = item["pole_bars"]
    for i in range(len(t)):
        col = "#26a69a" if c[i] >= o[i] else "#ef5350"
        ax.plot([i, i], [l[i], h[i]], color=col, lw=0.7, zorder=3)
        lo, hi = min(o[i], c[i]), max(o[i], c[i])
        ax.add_patch(plt.Rectangle((i - 0.32, lo), 0.64, max(hi - lo, 0.004), color=col, zorder=4))
    ax.axvspan(-0.5, pb - 0.5, color="#4c8dff", alpha=0.12, zorder=1)
    ax.axvspan(pb - 0.5, len(t) - 0.5, color="#f5b14c", alpha=0.12, zorder=1)
    ax.set_title(item["name"], fontsize=8, color="#e6edf3")
    ax.set_facecolor("#0a0e13")
    ax.tick_params(colors="#6b7886", labelsize=6)
    for s in ax.spines.values():
        s.set_color("#232e3a")

for ax in axes[n:]:
    ax.axis("off")

fig.suptitle(f"Template BANK — {n} bull-flag variations  (blue=pole  amber=flag; "
             "pole:flag ratio x pole curve x flag drift)", color="#e6edf3", fontsize=12)
plt.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(HERE, "..", "images", "template_bank.png")
plt.savefig(out, dpi=100, facecolor="#0a0e13")
print("saved", os.path.relpath(out))
