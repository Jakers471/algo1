"""
Build Renko bricks from the NQ 1m store and write findings — with the expectancy-lens
diagnostics printed up front (brick count, frequency, and cost as a % of 1R).

Run:  python renko/build_bricks.py                 # default size from config
      python renko/build_bricks.py --size 10 25 50 # sweep several brick sizes
      python renko/build_bricks.py --reversal 1    # pure Renko instead of 2-box
"""
import os
import sys
import argparse

import numpy as np

# reach the algoproj root (the dir containing algokit/) regardless of this file's depth
_r = os.path.dirname(os.path.abspath(__file__))
while _r != os.path.dirname(_r) and not os.path.isdir(os.path.join(_r, "algokit")):
    _r = os.path.dirname(_r)
sys.path.insert(0, _r)
from algokit.data import load_tf
from algokit.costs import FuturesCost
from renko import config as C
from renko.engine.bricks import build_bricks, build_bricks_adaptive


def _load_source(tf):
    df = load_tf(tf)[["close"]].dropna()
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    return ts, df["close"].to_numpy("float64")


def _atr_sizes(k, tf):
    """Per-source-bar brick size = k * daily ATR(20), monthly re-set, no look-ahead.

    The size for every bar in month M is k * ATR20 as of the LAST COMPLETED DAY BEFORE
    month M (shift(1) then first value of the month), rounded to the tick, floor 1 tick.
    Returns sizes aligned to the same rows _load_source keeps.
    """
    import pandas as pd
    df = load_tf(tf)
    keep = df["close"].notna()
    d = df.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([d["high"] - d["low"],
                    (d["high"] - d["close"].shift()).abs(),
                    (d["low"] - d["close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(C.ATR_LOOKBACK_D).mean().shift(1)          # only completed, prior days
    monthly = atr.resample("MS").first()                        # value known at month start
    sz = (k * monthly).reindex(df.index, method="ffill")
    sz = sz.bfill()                                             # first month: earliest known ATR
    sz = (sz / C.TICK).round() * C.TICK
    return np.maximum(sz.to_numpy("float64")[keep.to_numpy()], C.TICK)


def _cost_report(brick_size, cost: FuturesCost):
    """The headline number: round-turn cost as a fraction of 1R (= one brick of stop)."""
    rt_commission = 2 * cost.commission_per_side                       # entry + exit, 1 contract
    rt_slippage_pts = 2 * cost.slippage_ticks * cost.tick              # adverse fill both sides
    rt_cost_usd = rt_commission + rt_slippage_pts * cost.point_value
    one_R_usd = brick_size * cost.point_value                          # stop = 1 brick
    return rt_cost_usd, one_R_usd, rt_cost_usd / one_R_usd


def run(brick_size, reversal, tf):
    ts, close = _load_source(tf)
    span_years = (ts[-1] - ts[0]) / (365.25 * 24 * 3600)

    bk = build_bricks(ts, close, brick_size, reversal)
    nb = len(bk["dir"])
    flips = int((np.diff(bk["dir"]) != 0).sum()) if nb > 1 else 0

    os.makedirs(C.FINDINGS_DIR, exist_ok=True)
    out = C.bricks_path(brick_size, tf)
    np.savez(out, **bk, meta=np.array([brick_size, reversal], dtype="float64"))

    cost = FuturesCost()
    rt_usd, one_R, frac = _cost_report(brick_size, cost)

    print(f"\n=== brick {brick_size:g}pt  reversal={reversal}  tf={tf} ===")
    print(f"  source bars      : {len(close):,}  spanning {span_years:.1f} yr")
    print(f"  bricks           : {nb:,}  ({nb/span_years:,.0f}/yr, {nb/span_years/252:.1f}/trading-day)")
    print(f"  color flips      : {flips:,}  (reversals -- the raw signal count)")
    print(f"  1R (1-brick stop): ${one_R:,.0f}   ({C.brick_ticks(brick_size):.0f} ticks)")
    print(f"  round-turn cost  : ${rt_usd:,.2f}  ({cost.describe()})")
    print(f"  >> COST / 1R     : {frac*100:.1f}%   <-- the expectancy tax, before we're even right")
    print(f"  wrote {os.path.relpath(out)}")
    return {"brick_size": brick_size, "bricks": nb, "flips": flips, "cost_frac": frac}


def run_atr(k, reversal, tf):
    """Adaptive build: brick = k * daily ATR20 (monthly re-set, causal). See config.ATR_KS."""
    ts, close = _load_source(tf)
    sizes = _atr_sizes(k, tf)
    assert len(sizes) == len(close), "size/close alignment broke"
    span_years = (ts[-1] - ts[0]) / (365.25 * 24 * 3600)

    bk = build_bricks_adaptive(ts, close, sizes, reversal)
    nb = len(bk["dir"])
    flips = int((np.diff(bk["dir"]) != 0).sum()) if nb > 1 else 0

    os.makedirs(C.FINDINGS_DIR, exist_ok=True)
    out = C.bricks_path_atr(k, tf)
    np.savez(out, **bk, meta=np.array([k, reversal], dtype="float64"))

    bs = bk["bsize"]
    print(f"\n=== ATR brick k={k:g}  reversal={reversal}  tf={tf} ===")
    print(f"  bricks           : {nb:,}  ({nb/span_years/252:.1f}/trading-day)   flips: {flips:,}")
    print(f"  brick size (pts) : min={bs.min():g}  median={np.median(bs):g}  max={bs.max():g}")
    print(f"  wrote {os.path.relpath(out)}")
    return {"k": k, "bricks": nb, "flips": flips}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, nargs="+", default=[C.BRICK_SIZE])
    ap.add_argument("--atr", type=float, nargs="+", default=None,
                    help="build ATR-scaled bricks with these k multiples (e.g. --atr 0.04 0.08)")
    ap.add_argument("--reversal", type=int, default=C.REVERSAL_BRICKS)
    ap.add_argument("--tf", default=C.SOURCE_TF)
    a = ap.parse_args()

    if a.atr:
        for k in a.atr:
            run_atr(k, a.reversal, a.tf)
        raise SystemExit(0)

    rows = [run(s, a.reversal, a.tf) for s in a.size]
    if len(rows) > 1:
        print("\n=== sweep summary (cost/1R is the lens) ===")
        print(f"  {'size':>6} {'bricks':>10} {'flips':>9} {'cost/1R':>9}")
        for r in rows:
            print(f"  {r['brick_size']:>6g} {r['bricks']:>10,} {r['flips']:>9,} {r['cost_frac']*100:>8.1f}%")
