"""
R:R test for flag_breakout — the deciding experiment.

Every prior measurement was close-to-close held through the full drawdown, which can't see a
breakout trade's real edge. This one trades each breakout properly:
  entry = the breakout bar close
  stop  = the consolidation (flag) low  (long)  / flag high (short)
  target = entry + targetR x risk, swept over several R multiples
  exit  = whichever of stop/target is hit first (stop assumed first within a bar = conservative),
          else exit at close after MAX_HOLD bars.

Reports, per target multiple: win% / stopped% / timeout% and — the number that matters —
EXPECTANCY in R (avg R per trade; > 0 = the flag pays). Also the natural MFE/MAE in R.
Runs on ALL breakouts and on the regime-ALIGNED subset.

Run: python ".../analysis/rr_test/rr_test.py" [--tf 5m] [--max-hold 60]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))  # algoproj/
from algokit.data import load_tf

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3
TARGETS = [1.0, 1.5, 2.0, 3.0]


def simulate(values, close, entry_idx, direction, stop, max_hold):
    """Return (outcome_R per target, mfe_R, mae_R). Stop checked before target within a bar."""
    entry = close[entry_idx]
    risk = abs(entry - stop)
    n = len(close)
    if risk <= 0:
        return None
    hit = {t: None for t in TARGETS}
    stop_h, final_R, mfe, mae = None, 0.0, 0.0, 0.0
    for h in range(1, max_hold + 1):
        k = entry_idx + h
        if k >= n:
            break
        if direction > 0:
            adverse = (values[k, L] - entry) / risk
            favor = (values[k, H] - entry) / risk
        else:
            adverse = (entry - values[k, H]) / risk
            favor = (entry - values[k, L]) / risk
        final_R = direction * (close[k] / entry - 1) * entry / risk
        mfe, mae = max(mfe, favor), min(mae, adverse)
        if adverse <= -1.0:                          # stop first (conservative)
            stop_h = h
            break
        for t in TARGETS:
            if hit[t] is None and favor >= t:
                hit[t] = h
    out = {}
    for t in TARGETS:
        if hit[t] is not None:
            out[t] = t                               # target reached before any stop
        elif stop_h is not None:
            out[t] = -1.0
        else:
            out[t] = final_R                         # timed out -> exit at close
    return out, mfe, mae


def stop_level(values, ts, m, direction):
    pe = int(np.searchsorted(ts, m["pole_end"]))
    bi = int(np.searchsorted(ts, m["entry"]))
    if bi <= pe:
        return m["pole_lo"] if direction > 0 else m["pole_hi"]
    seg = values[pe:bi]
    return float(seg[:, L].min()) if direction > 0 else float(seg[:, H].max())


def run_group(values, close, ts, matches, max_hold):
    rows, mfes, maes = {t: [] for t in TARGETS}, [], []
    for m in matches:
        d = 1 if m["side"] == "long" else -1
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi >= len(close) or ts[bi] != m["entry"]:
            continue
        res = simulate(values, close, bi, d, stop_level(values, ts, m, d), max_hold)
        if res is None:
            continue
        out, mfe, mae = res
        for t in TARGETS:
            rows[t].append(out[t])
        mfes.append(mfe); maes.append(mae)
    n = len(mfes)
    print(f"  n={n}  |  natural excursion (R): median MFE {np.median(mfes):.2f}  median MAE {np.median(maes):.2f}")
    print(f"  {'targetR':>7} {'win%':>6} {'stop%':>6} {'time%':>6} {'expectancy(R)':>14}")
    stats = []
    for t in TARGETS:
        a = np.array(rows[t])
        win = np.mean(a == t) * 100
        stop = np.mean(a == -1.0) * 100
        timeout = 100 - win - stop
        exp = a.mean()
        stats.append((t, win, stop, timeout, exp))
        print(f"  {t:>7.1f} {win:>6.0f} {stop:>6.0f} {timeout:>6.0f} {exp:>+14.3f}")
    return stats, n


def main(tf, max_hold, findings):
    data = json.load(open(os.path.join(HERE, "..", "..", "findings", findings.format(tf=tf))))
    ms = data["matches"]
    df = load_tf(tf)[COLS].dropna()
    values, close = df.values, df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    aligned = [m for m in ms if m.get("aligned")]

    print(f"{tf}: {len(ms)} breakouts | entry=breakout, stop=consolidation low, hold<={max_hold} bars\n")
    print("ALL breakouts:")
    all_stats, _ = run_group(values, close, ts, ms, max_hold)
    print("\nregime-ALIGNED only:")
    run_group(values, close, ts, aligned, max_hold)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"rr_test_{tf}.csv"), "w") as f:
        f.write("targetR,win_pct,stop_pct,timeout_pct,expectancy_R\n")
        for t, w, s, to, e in all_stats:
            f.write(f"{t},{w:.1f},{s:.1f},{to:.1f},{e:.4f}\n")
    best = max(all_stats, key=lambda r: r[4])
    print(f"\nbest target {best[0]}R -> expectancy {best[4]:+.3f} R/trade "
          f"({'POSITIVE — flags pay' if best[4] > 0 else 'negative — no edge with a stop/target'})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--max-hold", type=int, default=60)
    ap.add_argument("--findings", default="flag_breakout_{tf}.json")
    a = ap.parse_args()
    main(a.tf, a.max_hold, a.findings)
