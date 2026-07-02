"""
MPF (Multiple Price Frames) alignment harness — the first real signal test on the Renko
line, measured honestly (every fill at a real 1m close, never at a brick grid price —
see the F2 lesson in expectancy.py / NOTES.md).

THE SIGNAL (derivative.md: "Buy white, sell black. When colors align across MPFs"):
  Two frames built from the SAME 1m closes — SPF (small bricks, the trigger) and LPF
  (large bricks, the context). Be LONG while both frames' last confirmed brick is white,
  SHORT while both are black, FLAT while they disagree.

WHY flat-on-disagreement IS the core+hedge state machine (images/hedge_core_flowchart.webp):
  core = position in the LPF trend direction; when the SPF reverses, an equal-and-opposite
  SPF hedge is opened. On a single instrument core+hedge nets to ZERO exposure while the
  frames disagree. If the LPF holds (trend suspension) the hedge closes -> back to core =
  aligned again. If the LPF flips (trend reversal) the core closes and the hedge becomes
  the new core = aligned the other way. Net exposure is identical in every state of the
  flowchart — so this harness IS the machine, implemented as the cheaper version (no extra
  hedge round-turns; the hedged span is simply flat).

EXECUTION HONESTY:
  * State at 1m bar i uses only bricks CONFIRMED at/before bar i's close (ffill of dir).
  * A state change at bar i fills at close[i] — the price that actually printed — with
    FuturesCost commission + adverse tick slippage per side.
  * R denominator: one SPF brick (the tight-stop thesis: the SPF is where risk lives).
"""
import os
import sys

import numpy as np

_r = os.path.dirname(os.path.abspath(__file__))
while _r != os.path.dirname(_r) and not os.path.isdir(os.path.join(_r, "algokit")):
    _r = os.path.dirname(_r)
sys.path.insert(0, _r)
from algokit.costs import FuturesCost
from algokit.data import load_tf
from renko import config as C
from renko.harness.expectancy import expectancy_report, print_report


def load_source():
    """The exact series the bricks were built from (same load path as build_bricks)."""
    df = load_tf(C.SOURCE_TF)[["close"]].dropna()
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    return ts, df["close"].to_numpy("float64")


def dir_on_source(bricks, n_src):
    """Last CONFIRMED brick direction as of each source bar's close (0 before any brick).

    Multiple bricks can confirm on one bar (same src_i) — the last one wins, which is
    exactly the state a live trader would see at that bar's close.
    """
    d = np.zeros(n_src, dtype=np.int8)
    d[bricks["src_i"]] = bricks["dir"]
    idx = np.where(d != 0, np.arange(n_src), 0)
    np.maximum.accumulate(idx, out=idx)
    return d[idx]


def alignment_position(spf_dir, lpf_dir):
    """+1 both white, -1 both black, 0 on disagreement (or before either frame exists)."""
    aligned = (spf_dir == lpf_dir) & (spf_dir != 0)
    return np.where(aligned, spf_dir, 0).astype(np.int8)


def bsize_on_source(bricks, n_src):
    """Brick size (points) in effect as of each source bar — for ATR-scaled frames.
    This is the per-trade 1R denominator (honest R accounting: 1R = that era's brick)."""
    b = np.zeros(n_src, dtype="float64")
    b[bricks["src_i"]] = bricks["bsize"]
    idx = np.where(b != 0, np.arange(n_src), 0)
    np.maximum.accumulate(idx, out=idx)
    out = b[idx]
    first = bricks["src_i"][0] if len(bricks["src_i"]) else 0
    out[:first] = bricks["bsize"][0] if len(bricks["bsize"]) else 1.0
    return out


def simulate_position(pos, ts, close, r_pts, cost=None):
    """Turn a per-bar target position (+1/0/-1, decided at each bar's close) into trades.

    A change at bar i fills at close[i]. One trade = one maximal run of constant nonzero
    position (a direct +1 -> -1 flip is two trades, exit and entry at the same fill).

    r_pts : scalar or per-bar array — 1R in POINTS at each bar (fixed brick size, or the
            SPF's own bsize for ATR-scaled frames). Each trade's R uses r_pts at ITS entry,
            which is exactly risk-normalized sizing (same $ risked on every trade).
    Returns trades shaped like expectancy.simulate_trades (r_net/r_gross/cost_R in R).
    """
    cost = cost or FuturesCost()
    side_usd = cost.commission_per_side + cost.slippage_ticks * cost.tick * cost.point_value
    r_arr = np.broadcast_to(np.asarray(r_pts, dtype="float64"), (len(pos),))

    bounds = np.flatnonzero(np.diff(pos) != 0) + 1
    starts = np.concatenate(([0], bounds))
    ends = np.concatenate((bounds, [len(pos) - 1]))   # last open segment closes at the end

    trades = []
    for s, e in zip(starts, ends):
        v = int(pos[s])
        if v == 0 or s == e:
            continue
        one_R_usd = r_arr[s] * C.POINT_VALUE
        gross_usd = v * (close[e] - close[s]) * C.POINT_VALUE
        cost_R = 2 * side_usd / one_R_usd
        trades.append({
            "entry_i": int(s), "exit_i": int(e),
            "ts_entry": int(ts[s]), "ts_exit": int(ts[e]),
            "dir": v, "entry_price": float(close[s]), "exit_price": float(close[e]),
            "bars_held": int(e - s), "cost_R": cost_R,
            "r_gross": gross_usd / one_R_usd, "r_net": gross_usd / one_R_usd - cost_R,
        })
    return trades


def subperiod_table(trades, spf_size):
    """Expectancy by 5-year bucket — the non-stationarity check (flag-line lesson)."""
    rows = []
    yrs = np.array([t["ts_entry"] for t in trades], dtype="datetime64[s]").astype("datetime64[Y]")
    yrs = yrs.astype(int) + 1970
    r = np.array([t["r_net"] for t in trades])
    for lo in range(2005, 2026, 5):
        m = (yrs >= lo) & (yrs < lo + 5)
        if m.sum() == 0:
            continue
        rows.append((f"{lo}-{min(lo+4, 2025)}", int(m.sum()), r[m].mean(), r[m].sum()))
    return rows


def run_pair(spf_size, lpf_size, ts, src_close, cost=None):
    zs = np.load(C.bricks_path(spf_size))
    zl = np.load(C.bricks_path(lpf_size))
    n = len(src_close)
    sd = dir_on_source({k: zs[k] for k in ("dir", "src_i")}, n)
    ld = dir_on_source({k: zl[k] for k in ("dir", "src_i")}, n)
    pos = alignment_position(sd, ld)
    trades = simulate_position(pos, ts, src_close, spf_size, cost)

    rep = expectancy_report(trades)
    print_report(rep, f"MPF align SPF={spf_size:g}pt LPF={lpf_size:g}pt (R = 1 SPF brick, honest fills)")
    span_days = (ts[-1] - ts[0]) / 86400 * (252 / 365.25)
    tim = float((pos != 0).mean())
    print(f"  time-in-market={tim*100:.1f}%  trades/trading-day={len(trades)/span_days:.2f}")
    for label, cnt, exp, tot in subperiod_table(trades, spf_size):
        print(f"    {label}: n={cnt:5d}  expectancy={exp:+.4f}R  total={tot:+8.1f}R")
    return rep


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", default=["10:25", "10:50", "25:50"],
                    help="SPF:LPF brick sizes in points, e.g. 10:50")
    a = ap.parse_args()

    ts, src_close = load_source()
    for p in a.pairs:
        s, l = (float(x) for x in p.split(":"))
        for sz in (s, l):
            if not os.path.exists(C.bricks_path(sz)):
                raise SystemExit(f"no bricks for {sz:g}pt — run engine/build_bricks.py --size {sz:g}")
        run_pair(s, l, ts, src_close)
