"""
The MPF research sweep on ATR-scaled bricks — four questions, honestly measured:

  1. PAIRS   : which SPF:LPF combo is best? (alignment expectancy matrix, all pairs of
               the config.ATR_KS ladder, in-sample pick / out-of-sample check)
  2. SCORE   : does deeper alignment help? (5-frame alignment score, threshold sweep)
  3. EXITS   : the asymmetry hunt — trail-k-bricks (the TSL from images/brick_params_tsl
               .webp, generalized) vs alignment-break vs ride-to-LPF-flip.
  4. VOLUME  : does per-brick volume intensity gate entries usefully? (with vs without)

MEASUREMENT RULES (inherited, non-negotiable):
  * honest fills — every fill at a real 1m close (the F2 lesson), FuturesCost per side.
  * R = the SPF brick size AT ENTRY (ATR-scaled => risk-normalized sizing by construction;
    this IS the risk management: same $ risked every trade, brick adapts to vol).
  * r_gross and r_net both reported — signal quality vs cost drag must be separable,
    because small ATR frames have brutal cost/1R in the low-vol eras.
  * every table: n, t-stat, OOS (last 30% by time), profit factor, maxDD in R.

STATE TIMING: frame state = last CONFIRMED brick as of each 1m close. The event-driven
exit sim walks SPF brick confirmations (checks LPF state there too — a coarser frame's
flip is seen at the next SPF brick, at most one small brick late).
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
from renko.harness.mpf import dir_on_source, bsize_on_source, alignment_position, simulate_position

RT_SIDE_USD = None  # filled in main from FuturesCost


# ── shared loading ──────────────────────────────────────────────────────────

def load_source_ohlcv():
    df = load_tf(C.SOURCE_TF)[["close", "volume"]].dropna(subset=["close"])
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    return ts, df["close"].to_numpy("float64"), df["volume"].fillna(0).to_numpy("float64")


def load_atr_bricks(k):
    z = np.load(C.bricks_path_atr(k))
    return {key: z[key] for key in ("ts", "open", "close", "dir", "src_i", "bsize")}


# ── stats helpers ───────────────────────────────────────────────────────────

def stats(r):
    """Compact stat block for an r_net (or r_gross) array."""
    n = len(r)
    if n == 0:
        return dict(n=0, exp=0.0, t=0.0, pf=0.0, dd=0.0, win=0.0)
    r = np.asarray(r)
    cum = np.cumsum(r)
    dd = float((cum - np.maximum.accumulate(cum)).min())
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf")
    sd = r.std(ddof=1) if n > 1 else 0.0
    t = float(r.mean() / (sd / np.sqrt(n))) if sd > 0 else 0.0
    return dict(n=n, exp=float(r.mean()), t=t, pf=pf, dd=dd, win=float((r > 0).mean()))


def row(label, trades):
    r = np.array([t["r_net"] for t in trades])
    g = np.array([t["r_gross"] for t in trades])
    s, sg = stats(r), stats(g)
    cut = int(len(r) * 0.7)
    oos = stats(r[cut:])
    print(f"  {label:24s} n={s['n']:6d}  gross={sg['exp']:+.4f}R  net={s['exp']:+.4f}R "
          f"(t={s['t']:+5.2f})  OOS={oos['exp']:+.4f}R (t={oos['t']:+5.2f})  "
          f"win%={s['win']*100:4.1f}  PF={s['pf']:4.2f}  maxDD={s['dd']:+7.0f}R")
    return {"label": label, "net": s, "gross": sg, "oos": oos}


# ── 1) pair matrix ──────────────────────────────────────────────────────────

def part_pairs(ts, close, dirs, bsizes):
    print("\n================ 1) SPF:LPF PAIR MATRIX (alignment, honest, R = SPF brick @ entry) ================")
    ks = C.ATR_KS
    out = []
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            pos = alignment_position(dirs[ks[i]], dirs[ks[j]])
            trades = simulate_position(pos, ts, close, bsizes[ks[i]])
            out.append((ks[i], ks[j], row(f"SPF={ks[i]:g} LPF={ks[j]:g}", trades)))
    # in-sample winner vs its OOS — the only honest way to "pick best frames"
    best = max(out, key=lambda x: x[2]["net"]["exp"] * (x[2]["net"]["n"] ** 0.5))
    print(f"  -> IS-favored pair: SPF={best[0]:g} LPF={best[1]:g} "
          f"(net {best[2]['net']['exp']:+.4f}R, OOS {best[2]['oos']['exp']:+.4f}R)")
    return out


# ── 2) multi-frame alignment score ──────────────────────────────────────────

def part_score(ts, close, dirs, bsizes):
    print("\n================ 2) 5-FRAME ALIGNMENT SCORE (|sum of colors| >= threshold) ================")
    ks = C.ATR_KS
    score = np.zeros(len(close), dtype=np.int8)
    for k in ks:
        score += dirs[k]
    r_pts = bsizes[ks[0]]                       # R = finest frame's brick (the tight stop)
    for thr in (3, 4, 5):
        pos = np.where(np.abs(score) >= thr, np.sign(score), 0).astype(np.int8)
        trades = simulate_position(pos, ts, close, r_pts)
        row(f"|score| >= {thr}/5", trades)


# ── 3) exit mechanics (event-driven on SPF bricks) ──────────────────────────

def sim_exits(spf, lpf_dir_src, close_src, exit_mode, trail_k=2, cost=None,
              vol_gate=None, rel_vol=None):
    """Enter at a FRESH alignment onset (not-aligned -> aligned, seen at an SPF brick
    confirmation); exit per `exit_mode`:
      "align" : first brick where frames no longer both match the position (baseline)
      "trail" : price closes trail_k SPF-bricks (at entry size) off the trade's peak —
                the generalized TSL; k=2 ~ the SPF's own 2-box flip
      "lpf"   : ride until the LPF itself flips (SPF only times the entry)
    vol_gate=(lo,hi) with rel_vol per SPF brick: entry allowed only if lo <= rv < hi.
    """
    cost = cost or FuturesCost()
    side_usd = cost.commission_per_side + cost.slippage_ticks * cost.tick * cost.point_value
    d, si, bs = spf["dir"], spf["src_i"], spf["bsize"]
    ld = lpf_dir_src[si]
    n = len(d)

    trades = []
    pos = 0
    entry_px = peak = one_R = e_ts = None
    prev_aligned = False
    for j in range(1, n):
        px = float(close_src[si[j]])
        aligned = d[j] != 0 and d[j] == ld[j]
        if pos == 0:
            if aligned and not prev_aligned:
                if vol_gate is None or (vol_gate[0] <= rel_vol[j] < vol_gate[1]):
                    pos = int(d[j])
                    entry_px, peak, one_R = px, pos * px, float(bs[j])
                    e_ts = int(spf["ts"][j])
        else:
            peak = max(peak, pos * px)
            if exit_mode == "align":
                out = not (d[j] == pos and ld[j] == pos)
            elif exit_mode == "trail":
                out = pos * px <= peak - trail_k * one_R
            elif exit_mode == "lpf":
                out = ld[j] != pos
            else:
                raise ValueError(exit_mode)
            if out:
                gross = pos * (px - entry_px) * C.POINT_VALUE
                cost_R = 2 * side_usd / (one_R * C.POINT_VALUE)
                trades.append({"ts_entry": e_ts, "ts_exit": int(spf["ts"][j]), "dir": pos,
                               "r_gross": gross / (one_R * C.POINT_VALUE),
                               "r_net": gross / (one_R * C.POINT_VALUE) - cost_R,
                               "cost_R": cost_R})
                pos = 0
        prev_aligned = aligned
    return trades


def part_exits(close_src, dirs_src, spf_bricks, pairs):
    print("\n================ 3) EXIT MECHANICS (entry fixed: fresh alignment onset) ================")
    for (ks, kl) in pairs:
        print(f"  --- pair SPF={ks:g} LPF={kl:g} ---")
        spf, ld = spf_bricks[ks], dirs_src[kl]
        row("exit: align-break", sim_exits(spf, ld, close_src, "align"))
        for k in (1, 2, 3, 4, 6):
            row(f"exit: trail {k} bricks", sim_exits(spf, ld, close_src, "trail", trail_k=k))
        row("exit: ride to LPF flip", sim_exits(spf, ld, close_src, "lpf"))


# ── 4) volume intensity gating ──────────────────────────────────────────────

def brick_rel_volume(spf, volume, med_window=200):
    """Per-brick volume INTENSITY (volume/bar over the brick's span), normalized by the
    trailing median intensity of the last `med_window` bricks (shifted — fully causal).
    Same-bar bricks inherit the bar's value. Cutoffs used downstream are a priori
    (0.8 / 1.5), not fitted."""
    import pandas as pd
    si = spf["src_i"]
    cv = np.concatenate(([0.0], np.cumsum(volume)))
    intens = np.empty(len(si))
    prev = si[0]
    intens[0] = cv[si[0] + 1] / max(si[0] + 1, 1)
    for j in range(1, len(si)):
        span = si[j] - prev
        if span == 0:
            intens[j] = intens[j - 1]
        else:
            intens[j] = (cv[si[j] + 1] - cv[prev + 1]) / span
            prev = si[j]
    med = pd.Series(intens).rolling(med_window, min_periods=20).median().shift(1)
    rv = intens / med.to_numpy()
    rv[~np.isfinite(rv)] = 1.0
    return rv


def part_volume(close_src, dirs_src, spf_bricks, volume, pairs):
    print("\n================ 4) VOLUME GATING (entry brick's relative volume intensity) ================")
    print("  gates: LOW rv<0.8 | MID 0.8-1.5 | HIGH rv>=1.5 | ungated baseline (exit=align-break)")
    for (ks, kl) in pairs:
        print(f"  --- pair SPF={ks:g} LPF={kl:g} ---")
        spf, ld = spf_bricks[ks], dirs_src[kl]
        rv = brick_rel_volume(spf, volume)
        row("ungated", sim_exits(spf, ld, close_src, "align"))
        for name, gate in (("LOW  vol entry", (0.0, 0.8)), ("MID  vol entry", (0.8, 1.5)),
                           ("HIGH vol entry", (1.5, np.inf))):
            row(name, sim_exits(spf, ld, close_src, "align", vol_gate=gate, rel_vol=rv))


# ── main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", nargs="+", default=["pairs", "score", "exits", "volume"])
    ap.add_argument("--exit-pairs", nargs="+", default=["0.08:0.32", "0.16:0.64"],
                    help="SPF:LPF ATR-k pairs for the exit/volume studies")
    a = ap.parse_args()

    ts, close, volume = load_source_ohlcv()
    n = len(close)
    bricks = {k: load_atr_bricks(k) for k in C.ATR_KS}
    dirs = {k: dir_on_source(bricks[k], n) for k in C.ATR_KS}
    bsizes = {k: bsize_on_source(bricks[k], n) for k in C.ATR_KS}
    pairs = [tuple(float(x) for x in p.split(":")) for p in a.exit_pairs]

    if "pairs" in a.parts:
        part_pairs(ts, close, dirs, bsizes)
    if "score" in a.parts:
        part_score(ts, close, dirs, bsizes)
    if "exits" in a.parts:
        part_exits(close, dirs, bricks, pairs)
    if "volume" in a.parts:
        part_volume(close, dirs, bricks, volume, pairs)
