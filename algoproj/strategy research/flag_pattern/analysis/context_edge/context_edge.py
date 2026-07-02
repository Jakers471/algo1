"""
Multi-scale context features + conditional-edge check for flag_breakout.

The honest, ML-free first cut of the "scan price many ways" idea. At each breakout we compute a
CONTEXT vector — directional efficiency (Kaufman: net move / path length, 0..1) at several
lookbacks, signed so + means the bigger move agrees with the pole direction — then ask: does the
breakout's forward outcome VARY with that context? The flag has no NAKED edge; this tests for a
CONDITIONAL one. It generalizes the 1h-regime test (one feature) to several scales, on efficiency
(the right, dimensionless axis) instead of a single MA fan.

Outputs the per-breakout feature matrix (the reusable "puzzle-piece" data) as CSV + a quintile PNG
(mean forward outcome by context quintile — a rising staircase = a real conditional edge).

Run: python ".../analysis/context_edge/context_edge.py" [--tf 5m] [--h 12]
"""
import argparse
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

SCALES = [10, 20, 40, 80, 160]      # lookbacks (bars) for the multi-scale efficiency context


def eff_signed(close, i, L, d):
    """Directional efficiency over the L bars ending at i, signed + when it agrees with pole dir d."""
    if i - L < 0:
        return np.nan
    seg = close[i - L:i + 1]
    path = np.abs(np.diff(seg)).sum()
    if path == 0:
        return np.nan
    net = seg[-1] - seg[0]
    return (abs(net) / path) * np.sign(net) * d


def quintiles(x, y):
    """Mean(y), win%(y>0), n per quintile of x (NaNs dropped)."""
    ok = ~np.isnan(x)
    x, y = x[ok], y[ok]
    order = np.argsort(x)
    out = []
    for q in np.array_split(order, 5):
        out.append((y[q].mean(), (y[q] > 0).mean() * 100, len(q)))
    return out


def main(tf, h, findings):
    ms = json.load(open(os.path.join(HERE, "..", "..", "findings", findings.format(tf=tf))))["matches"]
    df = load_tf(tf)[["open", "high", "low", "close"]].dropna()
    close = df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    n = len(close)

    feats = {f"eff{L}": [] for L in SCALES}
    fwd = []
    for m in ms:
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi >= n or ts[bi] != m["entry"] or bi + h >= n:
            continue
        d = 1 if m["side"] == "long" else -1
        for L in SCALES:
            feats[f"eff{L}"].append(eff_signed(close, bi, L, d))
        fwd.append(d * (close[bi + h] / close[bi] - 1) * 100)
    fwd = np.array(fwd)
    F = {k: np.array(v) for k, v in feats.items()}
    F["eff_composite"] = np.nanmean(np.vstack([F[f"eff{L}"] for L in SCALES]), axis=0)
    cols = [f"eff{L}" for L in SCALES] + ["eff_composite"]

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"context_matrix_{tf}.csv"), "w") as fcsv:
        fcsv.write(",".join(cols + ["fwd"]) + "\n")
        for r in range(len(fwd)):
            fcsv.write(",".join(f"{F[c][r]:.4f}" if not np.isnan(F[c][r]) else "" for c in cols)
                       + f",{fwd[r]:.4f}\n")

    print(f"{tf}: {len(fwd)} breakouts | outcome = fwd{h}% (directional) | context = signed efficiency\n")
    print(f"{'feature':>13} | " + " ".join(f"{'Q' + str(i+1):>13}" for i in range(5)))
    print(f"{'':>13} | " + " ".join(f"{'mean%(win%)':>13}" for _ in range(5)))
    print("-" * (16 + 14 * 5))
    for c in cols:
        qs = quintiles(F[c], fwd)
        cells = " ".join(f"{m:+6.3f}({w:4.0f})" for m, w, _ in qs)
        print(f"{c:>13} | {cells}")

    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.patch.set_facecolor("#0f0f1a")
    for ax, c in zip(axes.ravel(), cols):
        qs = quintiles(F[c], fwd)
        means = [m for m, _, _ in qs]
        ax.bar(range(1, 6), means, color=["#34d399" if m >= 0 else "#f87171" for m in means])
        ax.axhline(0, color="#555", lw=.8)
        ax.set_title(f"{c}  (outcome by context quintile)", color="#e0e0e0", fontsize=10)
        ax.set_xlabel("context quintile (Q1 low → Q5 high, aligned)")
        ax.set_ylabel(f"mean fwd{h}%")
        ax.tick_params(colors="#9aa7b4", labelsize=8)
    fig.suptitle(f"flag_breakout — does forward outcome depend on multi-scale context?  ·  {tf}  ·  fwd{h}\n"
                 "rising Q1→Q5 = conditional edge (breakout pays more when bigger structure agrees)",
                 color="#e0e0e0", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    png = os.path.join(OUT, f"context_edge_{tf}_h{h}.png")
    fig.savefig(png, dpi=140, facecolor="#0f0f1a")
    plt.close(fig)
    print(f"\nsaved {png}\nsaved context_matrix_{tf}.csv (feature matrix for future ML)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--h", type=int, default=12)
    ap.add_argument("--findings", default="flag_breakout_{tf}.json")
    a = ap.parse_args()
    main(a.tf, a.h, a.findings)
