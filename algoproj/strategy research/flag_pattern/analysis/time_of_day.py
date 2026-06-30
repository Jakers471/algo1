"""
Time-of-day analysis for flag_pattern findings.

Buckets every discovered pattern by hour-of-day in US Eastern (NQ liquidity tracks
the US session) and compares how returns and move-size differ by WHEN the pattern
formed -- to see whether timing sharpens the edge. Reads this strategy's findings
JSON; writes a PNG + CSV into ./output next to this script.

Run (from algoproj/ root):
  python "strategy research/flag_pattern/analysis/time_of_day.py" [--tf 5m] [--h 6]
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
TZ = "America/New_York"


def hour_label(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def main(tf="5m", H=6):
    data = json.load(open(os.path.join(HERE, "..", "findings", f"flag_{tf}.json")))
    df = pd.DataFrame(data["matches"])
    df["fwd"] = df["fwd"].map(lambda d: d.get(str(H)))
    df = df.dropna(subset=["fwd"])
    # findings timestamps are UTC epochs; bucket by the pattern-START hour in ET
    df["hour"] = pd.to_datetime(df["start"], unit="s", utc=True).dt.tz_convert(TZ).dt.hour

    g = df.groupby("hour")
    tab = pd.DataFrame({
        "n": g.size(),
        "fwd_mean": g["fwd"].mean(),
        "win": g["fwd"].apply(lambda s: (s > 0).mean() * 100),
        "mfe": g["mfe"].mean(),
        "mae": g["mae"].mean(),
    }).reindex(range(24)).dropna(subset=["n"])
    hours = tab.index.tolist()
    labels = [hour_label(h) for h in hours]

    os.makedirs(OUT, exist_ok=True)
    csv = os.path.join(OUT, f"time_of_day_{tf}_h{H}.csv")
    out_tab = tab.copy()
    out_tab.insert(0, "time", labels)
    out_tab.round(4).to_csv(csv, index_label="hour_et")

    # ---- figure: 3 stacked panels ----
    plt.style.use("dark_background")
    fig, ax = plt.subplots(3, 1, figsize=(13, 12), sharex=True)
    fig.patch.set_facecolor("#0f0f1a")
    x = np.arange(len(hours))

    ax[0].bar(x, tab["n"], color="#4c8dff")
    ax[0].set_ylabel("matches")
    ax[0].set_title(f"Flag patterns by time of day (US Eastern)  ·  {tf}  ·  fwd{H} bars  ·  n={int(tab['n'].sum())}")
    for i, v in enumerate(tab["n"]):
        ax[0].text(i, v, str(int(v)), ha="center", va="bottom", fontsize=8, color="#9aa7b4")

    ax[1].bar(x, tab["fwd_mean"], color=["#34d399" if v >= 0 else "#f87171" for v in tab["fwd_mean"]])
    ax[1].axhline(0, color="#555", lw=.8)
    ax[1].set_ylabel(f"mean fwd{H}  (%)")
    axw = ax[1].twinx()
    axw.plot(x, tab["win"], color="#ffd700", marker="o", ms=3, lw=1.2)
    axw.axhline(50, color="#777", ls="--", lw=.7)
    axw.set_ylabel("win %", color="#ffd700")
    axw.set_ylim(20, 80)

    w = .4
    ax[2].bar(x - w / 2, tab["mfe"], w, color="#34d399", label="avg MFE (best)")
    ax[2].bar(x + w / 2, tab["mae"], w, color="#f87171", label="avg MAE (worst)")
    ax[2].axhline(0, color="#555", lw=.8)
    ax[2].set_ylabel("move size  (%)")
    ax[2].legend(loc="upper left", fontsize=8)
    ax[2].set_xticks(x)
    ax[2].set_xticklabels(labels, rotation=45, ha="right")

    fig.tight_layout()
    png = os.path.join(OUT, f"time_of_day_{tf}_h{H}.png")
    fig.savefig(png, dpi=140)
    plt.close(fig)

    print(tab.round(3).to_string())
    print(f"\nsaved {png}\nsaved {csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--h", type=int, default=6, help="forward horizon (bars) to score returns")
    a = ap.parse_args()
    main(a.tf, a.h)
