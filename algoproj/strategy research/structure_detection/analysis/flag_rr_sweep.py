"""
Flag survivor — R:R robustness. Is the asymmetry a PLATEAU (real geometry) or a knife-edge at 1:2?

The survivor: entry = VWAP band edge (breakout dir), stop = opposite band edge -> 1R = band width.
Target = entry +/- RR x 1R. Sweep RR; check it OOS (post-2015), net of cost, and whether it holds in
BOTH OOS sub-periods and across a range of cost assumptions. A single positive RR = luck; a plateau
across RR that survives cost + both sub-periods = a real geometric edge.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/flag_rr_sweep.py"
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

MAXHOLD = 500
OOS_START = pd.Timestamp("2015-01-01")
RRS = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
H, L, C = 1, 2, 3

fj = json.load(open("strategy research/flag_pattern/findings/dynamic_pole_5m.json"))
df5 = load_tf("5m")[["open", "high", "low", "close"]].dropna()
V = df5.values
ts = df5.index.values.astype("datetime64[s]").astype("int64")
n = len(V)


def sim(brk, is_long, entry, stop, rr):
    risk = abs(entry - stop)
    tgt = entry + rr * risk if is_long else entry - rr * risk
    for j in range(brk + 1, min(n, brk + 1 + MAXHOLD)):
        hi, lo = V[j, H], V[j, L]
        if is_long:
            if lo <= stop: return -1.0
            if hi >= tgt: return rr
        else:
            if hi >= stop: return -1.0
            if lo <= tgt: return rr
    j = min(n - 1, brk + MAXHOLD)
    return ((V[j, C] - entry) if is_long else (entry - V[j, C])) / risk


# collect trades: (date, is_long, entry, stop, risk_pts)
trades = []
for m in fj["matches"]:
    if not m.get("vwap"):
        continue
    _, _c, up, dn = m["vwap"][-1]
    if up <= dn:
        continue
    is_long = m["side"] == "long"
    entry, stop = (up, dn) if is_long else (dn, up)
    brk = int(np.searchsorted(ts, m["entry"]))
    if brk >= n - 1 or ts[brk] != m["entry"]:
        continue
    trades.append((pd.Timestamp(m["entry"], unit="s"), is_long, entry, stop, abs(entry - stop)))

dates = np.array([t[0] for t in trades])
oos = dates >= OOS_START
mid = OOS_START + (dates[oos].max() - OOS_START) / 2


def expectancy(mask, rr, cost):
    tot = 0.0
    cnt = 0
    wins = 0
    for (dt, is_long, entry, stop, risk), keep in zip(trades, mask):
        if not keep:
            continue
        r = sim_cache[(id(dt), rr)] if (id(dt), rr) in sim_cache else None
        if r is None:
            r = sim(int(np.searchsorted(ts, int(dt.timestamp()))), is_long, entry, stop, rr)
            sim_cache[(id(dt), rr)] = r
        rn = r - cost / risk
        tot += rn; cnt += 1; wins += rn > 0
    return cnt, (tot / cnt if cnt else np.nan), (wins / cnt * 100 if cnt else np.nan)


sim_cache = {}
print(f"flag survivor R:R sweep | 1R = VWAP band width | net of cost | OOS >= {OOS_START.date()}\n")
print(f"{'RR':>4} | {'FULL n/exp/win':>24} | {'OOS n/exp/win':>24}")
print("-" * 62)
for rr in RRS:
    fn, fe, fw = expectancy(np.ones(len(trades), bool), rr, 0.75)
    on, oe, ow = expectancy(oos, rr, 0.75)
    print(f"{rr:>4} | {f'{fn}  {fe:+.3f}R  {fw:.0f}%':>24} | {f'{on}  {oe:+.3f}R  {ow:.0f}%':>24}")

print("\ncost sensitivity (OOS, net expectancy R):")
print(f"{'RR':>4} | " + " | ".join(f"{c}pt" for c in (0.0, 0.5, 0.75, 1.0, 1.5)))
for rr in RRS:
    row = f"{rr:>4} | "
    row += " | ".join(f"{expectancy(oos, rr, c)[1]:+.3f}" for c in (0.0, 0.5, 0.75, 1.0, 1.5))
    print(row)

print("\nsub-period plateau (OOS net exp @ 0.75pt): does it hold in BOTH halves?")
print(f"{'RR':>4} | {'OOS 1st half':>14} | {'OOS 2nd half':>14}")
for rr in RRS:
    _, e1, _ = expectancy(oos & (dates < mid), rr, 0.75)
    _, e2, _ = expectancy(oos & (dates >= mid), rr, 0.75)
    print(f"{rr:>4} | {e1:>+13.3f}R | {e2:>+13.3f}R")
