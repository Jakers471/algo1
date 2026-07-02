"""
Aggregate overlay — the original flag_overlay sanity check, on 20 years.

Recreates Figure_1: stack the closest matches in normalized space and draw the mean shape + the
25-75 percentile band + the template. Repeats it at several SELECTION LEVELS (top-50 like the
original demo, then percentile thresholds 0.1 / 0.5 / 1.0%) so we can SEE whether loosening the
match keeps a coherent flag or smears into noise — the check to run BEFORE loosening MATCH_PCT
(NOTES §19, step 1). Uses the config's full 12-bar template (pole+flag+breakout) so the classic
pole/flag/breakout shape is visible, session-filtered like the live signal.

Run: python ".../analysis/aggregate_overlay/aggregate_overlay.py" [--tf 5m] [--norm level|free]
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
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))  # algoproj/
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "signal")))    # signal_config
from algokit.data import load_tf
from algokit import patterns
import signal_config as cfg

COLS = ["open", "high", "low", "close"]
LEVELS = [("top 50", "top", 50), ("p0.1%", "pct", 0.1), ("p0.5%", "pct", 0.5), ("p1.0%", "pct", 1.0)]


def select(scores, ts, kind, val, window):
    s = scores.copy()
    s[~cfg.session_mask(ts[:len(scores)])] = np.inf          # session filter, like the live signal
    if kind == "top":
        return patterns.top_matches(s, val, window)
    return patterns.matches_under(s, float(np.percentile(scores, val)), window)


def close_paths(values, idxs, window):
    out = []
    for i in idxs:
        w = values[i:i + window]
        out.append((w[:, 3] / w[0, 0] - 1.0) * 100)          # normalized close path, %
    return np.array(out)


def panel(ax, paths, tmpl_close, color, title):
    bars = np.arange(paths.shape[1])
    for p in paths[:200]:                                     # subsample thin lines for readability
        ax.plot(bars, p, color=color, lw=0.5, alpha=0.06)
    ax.fill_between(bars, np.percentile(paths, 25, 0), np.percentile(paths, 75, 0), color=color, alpha=0.18)
    ax.plot(bars, paths.mean(0), color=color, lw=2.6)
    ax.plot(bars, tmpl_close, color="#ffd700", lw=1.8, ls="--")
    ax.axvline(cfg.POLE_BARS - 0.5, color="#555", lw=.8, ls=":")
    ax.axvline(8.5, color="#555", lw=.8, ls=":")
    ax.axhline(0, color="#555", lw=.6, ls="--")
    ax.set_title(f"{title}  (n={len(paths)})", color="#e0e0e0", fontsize=10)
    ax.tick_params(colors="#9aa7b4", labelsize=8)
    ax.set_facecolor("#1a1a2e")


def main(tf, norm):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    scorer = patterns.scan_free if norm == "free" else patterns.scan
    templates = [("BULL FLAG", cfg.BULL_FLAG, "#00e676"), ("BEAR FLAG", cfg.BEAR_FLAG, "#ff1744")]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(len(templates), len(LEVELS), figsize=(4.2 * len(LEVELS), 4.2 * len(templates)))
    fig.patch.set_facecolor("#0f0f1a")
    print(f"{tf}: {len(df):,} bars | norm={norm} | template {len(cfg.BULL_FLAG)} bars | session 8-2 ET")
    for r, (name, tmpl, color) in enumerate(templates):
        window = len(tmpl)
        scores = scorer(values, tmpl, window)
        tmpl_close = tmpl[:, 3] * 100
        for cix, (lab, kind, val) in enumerate(LEVELS):
            idxs = select(scores, ts, kind, val, window)
            paths = close_paths(values, idxs, window)
            panel(axes[r][cix], paths, tmpl_close, color, f"{name} · {lab}")
            print(f"  {name:>10} {lab:>6}: {len(idxs)} matches")
    fig.suptitle(f"Aggregate overlay — mean shape vs template as selection loosens  ·  {tf}  ·  norm={norm}"
                 f"\nthin=matches  solid=mean  band=25-75%  gold=template  ·  dotted: pole|flag , flag|breakout",
                 color="#e0e0e0", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, f"aggregate_overlay_{tf}_{norm}.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"saved {png}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--norm", default="level", choices=["level", "free"])
    a = ap.parse_args()
    main(a.tf, a.norm)
