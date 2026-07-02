"""
Regime poles — find & count poles straight from the 32-MA fan (algokit.regime.regime_score).

No template. A POLE = a contiguous run of bars where the fan is strongly directional:
  bull pole  = bull score >= THRESH for >= MIN_BARS bars,
  bear pole  = bear score >= THRESH for >= MIN_BARS bars.
Each run = one pole instance. Counts them over full history (vs the template's ~1,500) and emits
findings so tv_chart flags each pole span. Also plots a slice so you can see them immediately.

Run (from algoproj/ root):
  python "strategy research/structure_detection/signal/regime_poles.py" --save
  python "strategy research/structure_detection/signal/regime_poles.py" --save --thresh 60 --min-bars 3
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))   # algoproj/
from algokit.data import load_tf
from algokit.regime import regime_score

FINDINGS_DIR = os.path.join(HERE, "..", "findings")
OUT_DIR = os.path.join(HERE, "..", "analysis", "output")


def runs(score, thresh, min_bars):
    """Contiguous [start, end] index runs where score >= thresh, at least min_bars long."""
    above = score >= thresh
    out, i, n = [], 0, len(above)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            if j - i >= min_bars:
                out.append((i, j - 1))
            i = j
        else:
            i += 1
    return out


def main(tf, start, lo, hi, eps, thresh, min_bars, save):
    df = load_tf(tf).dropna()
    if start:
        df = df[df.index >= start]
    bull, consol, bear = regime_score(df, lo, hi, eps=eps)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()

    bull_runs = runs(bull.to_numpy(), thresh, min_bars)
    bear_runs = runs(bear.to_numpy(), thresh, min_bars)

    matches = []
    for (a, b), side, name, sc in (
            [(r, "long", "bull_pole", bull) for r in bull_runs] +
            [(r, "short", "bear_pole", bear) for r in bear_runs]):
        matches.append({
            "pattern": name, "side": side,
            "start": int(ts[a]), "pole_end": int(ts[b]), "end": int(ts[b]), "entry": int(ts[b]),
            "pole_lo": round(float(low[a:b + 1].min()), 2), "pole_hi": round(float(high[a:b + 1].max()), 2),
            "bars": int(b - a + 1), "regime": round(float(sc.to_numpy()[a:b + 1].mean()), 0),
            "fwd": {}, "mfe": None, "mae": None, "retrace": None})
    matches.sort(key=lambda m: m["start"])
    for r, m in enumerate(matches, 1):
        m["rank"] = r

    span_yr = (ts[-1] - ts[0]) / (365.25 * 86400)
    lens = np.array([m["bars"] for m in matches])
    print(f"{tf}: {len(df):,} bars ({df.index[0].date()} -> {df.index[-1].date()}, {span_yr:.1f} yr)")
    print(f"fan lo{lo}/hi{hi}/eps{eps} | pole = score >= {thresh} for >= {min_bars} bars")
    print(f"POLES: {len(matches)}  (bull {len(bull_runs)} / bear {len(bear_runs)})  "
          f"= {len(matches)/max(span_yr,1e-9):.0f}/yr | median {np.median(lens):.0f} bars "
          f"(p90 {np.percentile(lens,90):.0f}, max {lens.max()})")
    print(f"vs template ~1,500 poles over 20 yr")

    # static slice plot so you can SEE the flagged poles
    i0, i1 = 0, min(len(df), 1200)
    c = df["close"].to_numpy()[i0:i1]
    fig, ax = plt.subplots(figsize=(16, 6), facecolor="#0a0e13")
    ax.set_facecolor("#0a0e13")
    ax.plot(range(i1 - i0), c, color="#c9d4df", lw=0.8, zorder=3)
    for a, b in bull_runs:
        if b >= i0 and a <= i1:
            ax.axvspan(max(a, i0) - i0, min(b, i1) - i0, color="#26a69a", alpha=0.28, zorder=1)
    for a, b in bear_runs:
        if b >= i0 and a <= i1:
            ax.axvspan(max(a, i0) - i0, min(b, i1) - i0, color="#ef5350", alpha=0.28, zorder=1)
    ax.set_title(f"Regime POLES flagged (green=bull / red=bear) — {tf}, first {i1-i0} bars "
                 f"[{df.index[i0].date()}]  |  {len(matches)} poles total", color="#e6edf3", fontsize=12)
    ax.tick_params(colors="#6b7886")
    for s in ax.spines.values():
        s.set_color("#232e3a")
    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(OUT_DIR, "regime_poles.png"), dpi=110, facecolor="#0a0e13")
    print("saved analysis/output/regime_poles.png")

    if save:
        out = {"tf": tf, "source": "regime_poles", "pole_bars": None,
               "fwd_window": 12, "horizons": [1, 3, 6, 12, 24],
               "fan": {"lo": lo, "hi": hi, "eps": eps, "thresh": thresh, "min_bars": min_bars},
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "matches": matches}
        os.makedirs(FINDINGS_DIR, exist_ok=True)
        path = os.path.join(FINDINGS_DIR, f"regime_poles_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> findings/{os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--start", default=None)
    ap.add_argument("--lo", type=int, default=5)
    ap.add_argument("--hi", type=int, default=200)
    ap.add_argument("--eps", type=float, default=0.05)
    ap.add_argument("--thresh", type=float, default=70)
    ap.add_argument("--min-bars", type=int, default=5)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.start, a.lo, a.hi, a.eps, a.thresh, a.min_bars, a.save)
