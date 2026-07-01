"""
Forward-horizon analysis for the flag_breakout patterns.

For every breakout (entry), measure — at each look-forward length h — the mean forward RETURN
and the average DRAWDOWN (running max-adverse-excursion up to h). Return keeps climbing with h
(drift), but so does drawdown; the useful hold is where **return / |drawdown|** (efficiency)
peaks, not just where return is biggest.

Reads findings/flag_breakout_<tf>.json (recomputes forward stats from raw bars, so it's not
limited to the horizons stored in the file). Writes PNG + CSV to ./output.

Run:  python "strategy research/flag_pattern/analysis/forward_horizon/forward_horizon.py" [--tf 5m] [--hmax 60]
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

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3


def main(tf, hmax, findings):
    fp = os.path.join(HERE, "..", "..", "findings", findings.format(tf=tf))
    ms = json.load(open(fp))["matches"]
    df = load_tf(tf)[COLS].dropna()
    values, close = df.values, df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    n = len(close)

    ret = np.full((len(ms), hmax), np.nan)   # forward return at each horizon (directional %)
    dd = np.full((len(ms), hmax), np.nan)     # running drawdown (max adverse excursion) up to h
    for i, m in enumerate(ms):
        idx = int(np.searchsorted(ts, m["entry"]))
        if idx >= n or ts[idx] != m["entry"]:
            continue
        d = 1 if m["side"] == "long" else -1
        base, run = close[idx], 0.0
        for h in range(1, hmax + 1):
            k = idx + h
            if k >= n:
                break
            ret[i, h - 1] = d * (close[k] / base - 1) * 100
            worst = values[k, L] if d > 0 else values[k, H]      # worst intrabar price
            run = min(run, d * (worst / base - 1) * 100)          # adverse excursion (<= 0)
            dd[i, h - 1] = run

    hs = np.arange(1, hmax + 1)
    mret = np.nanmean(ret, axis=0)
    mdd = np.nanmean(dd, axis=0)
    win = np.nanmean(ret > 0, axis=0) * 100
    ratio = mret / np.abs(np.where(mdd == 0, np.nan, mdd))         # return per unit drawdown
    valid = hs >= 3                                                # skip unstable tiny-h ratios
    best = int(hs[valid][np.nanargmax(ratio[valid])])

    os.makedirs(OUT, exist_ok=True)
    np.savetxt(os.path.join(OUT, f"forward_horizon_{tf}.csv"),
               np.column_stack([hs, mret, mdd, win, ratio]), delimiter=",",
               header="horizon_bars,mean_return_pct,mean_drawdown_pct,win_pct,ret_over_dd", comments="")

    plt.style.use("dark_background")
    fig, ax = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    fig.patch.set_facecolor("#0f0f1a")
    ax[0].plot(hs, mret, color="#34d399", lw=2, label="mean forward return")
    ax[0].plot(hs, mdd, color="#f87171", lw=2, label="avg drawdown (MAE)")
    ax[0].axhline(0, color="#555", lw=.8)
    ax[0].axvline(best, color="#ffd700", ls="--", lw=1)
    ax[0].set_ylabel("%")
    ax[0].set_title(f"flag_breakout forward return vs drawdown by hold length  ·  {tf}  ·  n={len(ms)}  "
                    f"·  best hold = {best} bars")
    ax[0].legend(loc="upper left", fontsize=9)

    ax[1].plot(hs, ratio, color="#ffd700", lw=2, label="return / |drawdown|")
    ax[1].axvline(best, color="#ffd700", ls="--", lw=1)
    ax[1].axhline(1, color="#555", ls="--", lw=.7)
    ax[1].set_ylabel("return / |drawdown|")
    axw = ax[1].twinx()
    axw.plot(hs, win, color="#4c8dff", lw=1.2, label="win %")
    axw.axhline(50, color="#777", ls="--", lw=.6)
    axw.set_ylabel("win %", color="#4c8dff")
    axw.set_ylim(30, 70)
    ax[1].set_xlabel("hold length (bars after breakout)")
    ax[1].legend(loc="upper left", fontsize=9)

    fig.tight_layout()
    png = os.path.join(OUT, f"forward_horizon_{tf}.png")
    fig.savefig(png, dpi=140)
    plt.close(fig)

    print(f"{tf}: {len(ms)} breakouts")
    print(f"{'h':>4} {'return%':>9} {'drawdown%':>10} {'win%':>6} {'ret/dd':>7}")
    for h in (1, 3, 6, 12, 18, 24, 36, 48, min(60, hmax)):
        if h <= hmax:
            j = h - 1
            print(f"{h:>4} {mret[j]:>+9.3f} {mdd[j]:>+10.3f} {win[j]:>6.0f} {ratio[j]:>7.2f}")
    print(f"\nbest hold by return/|drawdown|: {best} bars  (return {mret[best-1]:+.3f}%, "
          f"drawdown {mdd[best-1]:+.3f}%, win {win[best-1]:.0f}%)")
    print(f"saved {png}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--hmax", type=int, default=60)
    ap.add_argument("--findings", default="flag_breakout_{tf}.json")
    main(ap.parse_args().tf, ap.parse_args().hmax, ap.parse_args().findings)
