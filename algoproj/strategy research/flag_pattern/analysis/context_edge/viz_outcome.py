"""
Show what happens AFTER the breakout — the trade itself, in context.

Left: a HIGH-context breakout (bigger trend agrees) that plays out as a WIN.
Right: a LOW-context breakout (chop / against) that plays out as a LOSS.
Each marks entry (breakout), stop (consolidation low), target (entry + 2R), and where price hit.
Illustrative examples of the two piles the R:R test separated — not proof, just what each looks like.

Run: python ".../analysis/context_edge/viz_outcome.py"
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
TARGET_R = 2.0


def composite(close, i, d):
    out = []
    for L in SCALES:
        if i - L < 0:
            continue
        seg = close[i - L:i + 1]
        path = np.abs(np.diff(seg)).sum()
        if path:
            out.append(abs(seg[-1] - seg[0]) / path * np.sign(seg[-1] - seg[0]) * d)
    return float(np.mean(out)) if out else np.nan


def trade(values, close, bi, stop, max_hold=60):
    entry = close[bi]
    risk = entry - stop                      # long: stop below entry
    target = entry + TARGET_R * risk
    n = len(close)
    for h in range(1, max_hold + 1):
        k = bi + h
        if k >= n:
            break
        if values[k, 2] <= stop:             # low hits stop
            return "stop", h, stop, entry, target
        if values[k, 1] >= target:           # high hits target
            return "target", h, target, entry, target
    return "timeout", max_hold, close[min(bi + max_hold, n - 1)], entry, target


def panel(ax, values, close, bi, ctx, kind, hit_h, hit_px, entry, stop, target, title_col):
    x0, x1 = bi - 20, bi + hit_h + 8
    xs = np.arange(x0, x1) - bi
    ax.plot(xs, close[x0:x1], color="#cfd8e3", lw=1.4, zorder=3)
    ax.axvline(0, color="#ffd700", lw=1.2, ls="--", zorder=1)
    ax.axhline(entry, color="#ffd700", lw=1, ls=":", zorder=1)
    ax.axhline(stop, color="#f87171", lw=1.2, zorder=1)
    ax.axhline(target, color="#34d399", lw=1.2, zorder=1)
    ax.scatter([0], [entry], color="#ffd700", s=45, zorder=5)
    mk = "^" if kind == "target" else "v"
    mc = "#34d399" if kind == "target" else "#f87171"
    ax.scatter([hit_h], [hit_px], color=mc, marker=mk, s=120, zorder=6)
    ax.text(xs[-1], entry, " entry", color="#ffd700", fontsize=8, va="center")
    ax.text(xs[-1], stop, " stop", color="#f87171", fontsize=8, va="center")
    ax.text(xs[-1], target, " target (2R)", color="#34d399", fontsize=8, va="center")
    verdict = "WIN  +2R" if kind == "target" else ("LOSS  -1R" if kind == "stop" else "timeout")
    ax.set_title(f"context {ctx:+.2f}  →  {verdict}", color=title_col, fontsize=13, fontweight="bold")
    ax.tick_params(colors="#9aa7b4", labelsize=8)
    ax.set_facecolor("#131a23")
    ax.set_xlabel("bars from breakout"); ax.set_ylabel("price")


def main(tf="5m"):
    ms = json.load(open(os.path.join(HERE, "..", "..", "findings", f"flag_breakout_{tf}.json")))["matches"]
    df = load_tf(tf)[["open", "high", "low", "close"]].dropna()
    values, close = df.values, df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    n = len(close)

    recs = []
    for m in ms:
        if m["side"] != "long":
            continue
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi < 160 or bi + 70 >= n or ts[bi] != m["entry"]:
            continue
        pe = int(np.searchsorted(ts, m["pole_end"]))
        stop = float(values[pe:bi, 2].min()) if bi > pe else m["pole_lo"]
        if close[bi] - stop <= 0:
            continue
        ctx = composite(close, bi, 1)
        kind, hh, hpx, entry, tgt = trade(values, close, bi, stop)
        recs.append((ctx, bi, stop, kind, hh, hpx, entry, tgt))

    wins = sorted([r for r in recs if r[3] == "target"], key=lambda r: -r[0])     # high-context wins
    losses = sorted([r for r in recs if r[3] == "stop"], key=lambda r: r[0])      # low-context losses
    hi, lo = wins[0], losses[0]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#0f0f1a")
    panel(axes[0], values, close, hi[1], hi[0], hi[3], hi[4], hi[5], hi[6], hi[2], hi[7], "#34d399")
    panel(axes[1], values, close, lo[1], lo[0], lo[3], lo[4], lo[5], lo[6], lo[2], lo[7], "#f87171")
    fig.suptitle("What happens AFTER the breakout — enter at the gold line, stop (red) or target (green) first?\n"
                 "left: high-context breakout runs to target · right: low-context breakout gets stopped",
                 color="#e0e0e0", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, "viz_outcome.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"high-context WIN: ctx {hi[0]:+.2f} | low-context LOSS: ctx {lo[0]:+.2f}")
    print(f"saved {png}")


if __name__ == "__main__":
    main()
