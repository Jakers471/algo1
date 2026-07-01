"""
Regime-alignment analysis for flag_breakout.

Wires a higher-timeframe 32-MA fan regime onto each breakout and splits the patterns into
ALIGNED (HTF regime agrees with the pole direction) vs COUNTER-trend, then re-runs the forward
return / drawdown by hold length for each group. Question: do trend-ALIGNED breakouts actually
continue, while the counter-trend ones are the drawdown-heavy noise dragging the whole set down?

HTF regime = algokit.regime.regime_score (the same 32-MA fan as strategies/fanning_mtf.py),
forward-filled onto the 5m clock with algokit.data.align (no look-ahead).

Run: python ".../analysis/regime_align/regime_align.py" [--tf 5m] [--htf 60m] [--split 50] [--hmax 60]
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
from algokit.data import load_tf, align
from algokit.regime import regime_score

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3
HTF_FAN = {"60m": (5, 200, 0.05), "15m": (5, 120, 0.03), "1d": (5, 500, 0.15)}


def _fwd_dd(values, close, entries, hmax):
    """entries: list of (idx, direction). -> mean return, mean drawdown, win% per horizon."""
    n = len(close)
    ret = np.full((len(entries), hmax), np.nan)
    dd = np.full((len(entries), hmax), np.nan)
    for i, (idx, d) in enumerate(entries):
        base, run = close[idx], 0.0
        for h in range(1, hmax + 1):
            k = idx + h
            if k >= n:
                break
            ret[i, h - 1] = d * (close[k] / base - 1) * 100
            worst = values[k, L] if d > 0 else values[k, H]
            run = min(run, d * (worst / base - 1) * 100)
            dd[i, h - 1] = run
    return np.nanmean(ret, axis=0), np.nanmean(dd, axis=0), np.nanmean(ret > 0, axis=0) * 100


def main(tf, htf, split, hmax, findings):
    ms = json.load(open(os.path.join(HERE, "..", "..", "findings", findings.format(tf=tf))))["matches"]
    df = load_tf(tf)[COLS].dropna()
    values, close = df.values, df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")

    lo, hi, eps = HTF_FAN[htf]
    hbull, _, hbear = regime_score(load_tf(htf), lo, hi, eps=eps)
    bull_a = align(hbull, df.index).to_numpy()      # HTF bull score on the 5m clock (ffill, no look-ahead)
    bear_a = align(hbear, df.index).to_numpy()

    aligned, counter = [], []
    for m in ms:
        idx = int(np.searchsorted(ts, m["entry"]))
        if idx >= len(ts) or ts[idx] != m["entry"]:
            continue
        d = 1 if m["side"] == "long" else -1
        agree = bull_a[idx] if d > 0 else bear_a[idx]     # how much HTF agrees with the pole direction
        if np.isnan(agree):
            continue
        (aligned if agree >= split else counter).append((idx, d))

    groups = {"aligned": aligned, "counter": counter,
              "all": aligned + counter}
    hs = np.arange(1, hmax + 1)
    os.makedirs(OUT, exist_ok=True)

    print(f"{tf} breakouts vs {htf} fan regime (split at bull/bear score {split})")
    print(f"aligned {len(aligned)}  |  counter {len(counter)}  |  total {len(aligned)+len(counter)}\n")
    stats = {}
    for name in ("aligned", "counter", "all"):
        if not groups[name]:
            continue
        mret, mdd, win = _fwd_dd(values, close, groups[name], hmax)
        ratio = mret / np.abs(np.where(mdd == 0, np.nan, mdd))
        best = int(hs[2:][np.nanargmax(ratio[2:])])
        stats[name] = (mret, mdd, win, ratio, best)
        print(f"[{name:>7}] n={len(groups[name]):>4}  "
              f"h24: ret {mret[23]:+.3f}% dd {mdd[23]:+.3f}% win {win[23]:.0f}%  |  "
              f"h48: ret {mret[47]:+.3f}% dd {mdd[47]:+.3f}% win {win[47]:.0f}%  |  "
              f"best h{best} ratio {ratio[best-1]:.2f}")

    # plot aligned vs counter: return (solid) + drawdown (dashed) by horizon
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("#0f0f1a")
    colors = {"aligned": "#34d399", "counter": "#f87171"}
    for name in ("aligned", "counter"):
        if name not in stats:
            continue
        mret, mdd, win, ratio, best = stats[name]
        ax.plot(hs, mret, color=colors[name], lw=2, label=f"{name} return (n={len(groups[name])})")
        ax.plot(hs, mdd, color=colors[name], lw=1.4, ls="--", alpha=0.8, label=f"{name} drawdown")
    ax.axhline(0, color="#555", lw=.8)
    ax.set_xlabel("hold length (bars after breakout)")
    ax.set_ylabel("%")
    ax.set_title(f"flag_breakout — {htf} regime-aligned vs counter-trend  ·  return (solid) / drawdown (dashed)")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    png = os.path.join(OUT, f"regime_align_{tf}_{htf}.png")
    fig.savefig(png, dpi=140)
    plt.close(fig)
    print(f"\nsaved {png}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--htf", default="60m", choices=list(HTF_FAN))
    ap.add_argument("--split", type=float, default=50.0, help="HTF agree-score cut for aligned vs counter")
    ap.add_argument("--hmax", type=int, default=60)
    ap.add_argument("--findings", default="flag_breakout_{tf}.json")
    a = ap.parse_args()
    main(a.tf, a.htf, a.split, a.hmax, a.findings)
