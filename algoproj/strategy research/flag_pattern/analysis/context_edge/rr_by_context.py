"""
R:R expectancy by multi-scale context quintile — the decisive conditional-edge test.

Combines the context feature (signed multi-scale efficiency at the breakout) with the proper R:R
trade sim (entry = breakout close, stop = consolidation low, target = R multiple, stop-first
within a bar). Splits breakouts into context quintiles and measures EXPECTANCY in R per bucket.
If the top-context quintile (bigger structure agrees with the pole) shows POSITIVE expectancy while
the whole set was ~zero, that's a genuine conditional edge. If it's still ~zero, the context effect
doesn't survive proper execution.

Run: python ".../analysis/context_edge/rr_by_context.py" [--tf 5m] [--max-hold 60]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))  # algoproj/
from algokit.data import load_tf

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3
SCALES = [10, 20, 40, 80, 160]
TARGETS = [1.0, 2.0, 3.0]


def eff_signed(close, i, L, d):
    if i - L < 0:
        return np.nan
    seg = close[i - L:i + 1]
    path = np.abs(np.diff(seg)).sum()
    if path == 0:
        return np.nan
    return (abs(seg[-1] - seg[0]) / path) * np.sign(seg[-1] - seg[0]) * d


def stop_level(values, ts, m, d):
    pe = int(np.searchsorted(ts, m["pole_end"]))
    bi = int(np.searchsorted(ts, m["entry"]))
    if bi <= pe:
        return m["pole_lo"] if d > 0 else m["pole_hi"]
    seg = values[pe:bi]
    return float(seg[:, L].min()) if d > 0 else float(seg[:, H].max())


def simulate(values, close, entry_idx, d, stop, max_hold):
    entry = close[entry_idx]
    risk = abs(entry - stop)
    n = len(close)
    if risk <= 0:
        return None
    hit = {t: None for t in TARGETS}
    stop_h, final_R = None, 0.0
    for h in range(1, max_hold + 1):
        k = entry_idx + h
        if k >= n:
            break
        adverse = (values[k, L] - entry) / risk if d > 0 else (entry - values[k, H]) / risk
        favor = (values[k, H] - entry) / risk if d > 0 else (entry - values[k, L]) / risk
        final_R = d * (close[k] / entry - 1) * entry / risk
        if adverse <= -1.0:
            stop_h = h
            break
        for t in TARGETS:
            if hit[t] is None and favor >= t:
                hit[t] = h
    return {t: (t if hit[t] is not None else (-1.0 if stop_h is not None else final_R)) for t in TARGETS}


def rr(values, close, ts, matches, max_hold):
    rows = {t: [] for t in TARGETS}
    for m in matches:
        d = 1 if m["side"] == "long" else -1
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi >= len(close) or ts[bi] != m["entry"]:
            continue
        out = simulate(values, close, bi, d, stop_level(values, ts, m, d), max_hold)
        if out is None:
            continue
        for t in TARGETS:
            rows[t].append(out[t])
    return {t: np.array(v) for t, v in rows.items()}, len(rows[TARGETS[0]])


def main(tf, max_hold, findings):
    ms = json.load(open(os.path.join(HERE, "..", "..", "findings", findings.format(tf=tf))))["matches"]
    df = load_tf(tf)[COLS].dropna()
    values, close = df.values, df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")

    # composite multi-scale context per breakout
    ctx = []
    for m in ms:
        bi = int(np.searchsorted(ts, m["entry"]))
        if bi >= len(close) or ts[bi] != m["entry"]:
            ctx.append(np.nan)
            continue
        d = 1 if m["side"] == "long" else -1
        vals = [eff_signed(close, bi, s, d) for s in SCALES]
        ctx.append(np.nanmean(vals))
    ctx = np.array(ctx)
    valid = [i for i in range(len(ms)) if not np.isnan(ctx[i])]
    order = sorted(valid, key=lambda i: ctx[i])
    quints = np.array_split(order, 5)

    print(f"{tf}: {len(ms)} breakouts | R:R by multi-scale context quintile | stop=consolidation low\n")
    print(f"{'bucket':>10} {'n':>5} {'ctx':>7} | " + " ".join(f"{'exp@' + str(t) + 'R':>10}" for t in TARGETS))
    print("-" * (26 + 11 * len(TARGETS)))
    for name, idxs in [("all", valid)] + [(f"Q{i+1}", list(q)) for i, q in enumerate(quints)]:
        grp = [ms[i] for i in idxs]
        rows, n = rr(values, close, ts, grp, max_hold)
        cmean = np.nanmean([ctx[i] for i in idxs])
        exps = " ".join(f"{rows[t].mean():>+10.3f}" for t in TARGETS)
        print(f"{name:>10} {n:>5} {cmean:>7.2f} | {exps}")
    print("\n(Q5 = bigger structure most AGREES with the pole. Positive exp there while 'all' ~0 = conditional edge.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--max-hold", type=int, default=60)
    ap.add_argument("--findings", default="flag_breakout_{tf}.json")
    a = ap.parse_args()
    main(a.tf, a.max_hold, a.findings)
