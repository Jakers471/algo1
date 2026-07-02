"""
VWAP-band R:R backtest on the dynamic_pole breakouts.

Entry & stop use the anchored-VWAP band at the breakout bar (the cyan band on the chart):
  BEARISH: SELL-stop entry at the LOWER band; stop-loss ABOVE the UPPER band.
  BULLISH: BUY-stop  entry at the UPPER band; stop-loss BELOW the LOWER band.
Risk (1R) = band width = upper - lower. Target = entry -/+ RR x risk.

Each trade is walked forward bar-by-bar from the bar AFTER the breakout; exits on the FIRST of
stop / target (if both are inside one bar, STOP is taken first = conservative), else EXPIRES at
MAX_HOLD bars (marked to close, in R). Reports per RR: win / loss / expire %, expectancy in R,
total R.  (Costs not modelled — gross.)

Run (from algoproj/ root):
  python "strategy research/flag_pattern/analysis/vwap_rr/vwap_rr.py"
  python "strategy research/flag_pattern/analysis/vwap_rr/vwap_rr.py" --max-hold 200
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))   # algoproj/
sys.path.insert(0, os.path.join(HERE, "..", "..", "signal"))                      # signal_config
from algokit.data import load_tf
import signal_config as cfg

COLS = ["open", "high", "low", "close"]
H, L = 1, 2
RRS = [1.0, 2.0, 3.0, 4.0]


def _simulate(values, ts, brk, is_long, entry, stop, target, max_hold):
    """Walk forward from brk+1; return 'target' | 'stop' | 'expire' and the realised R."""
    risk = abs(entry - stop)
    n = len(values)
    for j in range(brk + 1, min(n, brk + 1 + max_hold)):
        hi, lo = values[j, H], values[j, L]
        if is_long:
            if lo <= stop:                       # stop-first (conservative)
                return "stop", -1.0
            if hi >= target:
                return "target", (target - entry) / risk
        else:
            if hi >= stop:
                return "stop", -1.0
            if lo <= target:
                return "target", (entry - target) / risk
    j = min(n - 1, brk + max_hold)               # expire -> mark to close
    close = values[j, 3]
    r = (close - entry) / risk if is_long else (entry - close) / risk
    return "expire", r


def main(findings, max_hold):
    d = json.load(open(findings))
    tf = d["tf"]
    df = load_tf(tf)[COLS].dropna()
    values = df.values
    ts = df.index.values.astype("datetime64[s]").astype("int64")

    trades = []          # (is_long, brk_idx, entry, stop, risk)
    skipped = 0
    for m in d["matches"]:
        if not m.get("vwap"):
            skipped += 1
            continue
        _, _center, up, dn = m["vwap"][-1]       # band at the breakout bar
        is_long = m["side"] == "long"
        entry, stop = (up, dn) if is_long else (dn, up)
        brk = int(np.searchsorted(ts, m["entry"]))
        if brk >= len(values) - 1 or ts[brk] != m["entry"] or up <= dn:
            skipped += 1
            continue
        trades.append((is_long, brk, entry, stop))

    print(f"{os.path.basename(findings)} | {tf} | {len(trades)} breakouts "
          f"(skipped {skipped}) | 1R = VWAP band width | max_hold {max_hold} bars | gross\n")
    print(f"{'RR':>4} | {'win%':>6} {'loss%':>6} {'exp%':>6} | {'expectancy(R)':>13} | {'total(R)':>9}")
    print("-" * 60)
    for rr in RRS:
        outs, rs = [], []
        for is_long, brk, entry, stop in trades:
            risk = abs(entry - stop)
            target = entry + rr * risk if is_long else entry - rr * risk
            o, r = _simulate(values, ts, brk, is_long, entry, stop, target, max_hold)
            outs.append(o)
            rs.append(r)
        n = len(outs)
        win = sum(o == "target" for o in outs) / n * 100
        loss = sum(o == "stop" for o in outs) / n * 100
        exp = sum(o == "expire" for o in outs) / n * 100
        print(f"{rr:>4.0f} | {win:>5.1f}% {loss:>5.1f}% {exp:>5.1f}% | "
              f"{np.mean(rs):>+12.3f} | {np.sum(rs):>+8.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", default=os.path.join(cfg.FINDINGS_DIR, "dynamic_pole_5m.json"))
    ap.add_argument("--max-hold", type=int, default=120)
    a = ap.parse_args()
    main(a.findings, a.max_hold)
