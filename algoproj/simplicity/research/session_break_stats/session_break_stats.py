"""
session_break_stats — is there any predictability / edge in the session-level breach data?

Interrogates research/session_anchors output three ways, HONESTLY (baselines, not raw rates):

  1. BASE RATES        — how often each session high/low gets breached, how fast.
  2. CONDITIONAL BREAK — does one session's break predict another's? P(Y|X) vs P(Y) = lift.
  3. FOLLOW-THROUGH    — THE edge test: after a level breaks (close through), does price
                         CONTINUE in the breakout direction over the next N bars, beyond the
                         market's own drift? mean move, win%, t-stat, and EXCESS vs drift,
                         plus a first-half/second-half stability check.

Prints a verdict per test (edge only if it clears the baseline AND is stable AND t is real).

Run:  python research/session_break_stats/session_break_stats.py
Out:  console report + output/session_break_stats.json
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as cfg

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
ANC = os.path.join(HERE, "..", "session_anchors", "output", "session_anchors.json")
NS = [12, 36]  # forward bars on 5m: 1h, 3h


def main():
    if not os.path.exists(ANC):
        print("run session_anchors.py first"); return
    levels = json.load(open(ANC))["levels"]
    L = pd.DataFrame(levels)
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    ts = (df.index.view("int64") // 1_000_000_000).astype("int64")
    close = df["close"].to_numpy(); n = len(close)
    pos = {int(t): i for i, t in enumerate(ts)}
    out = {}

    # ---- 1. BASE RATES ----
    print("=" * 66 + "\n1) BASE RATES  (per session x level)\n" + "=" * 66)
    print(f"  {'session':<9}{'type':<6}{'n':>7}{'hit%':>8}{'median bars->breach':>22}")
    base = {}
    for (s, t), g in L.groupby(["session", "type"]):
        hitpct = g["hit"].mean() * 100
        med = int(g.loc[g["hit"], "duration_bars"].median()) if g["hit"].any() else 0
        base[f"{s}_{t}"] = round(hitpct, 1)
        print(f"  {s:<9}{t:<6}{len(g):>7}{hitpct:>7.1f}%{med:>18} (~{med*5/60:.1f}h)")
    out["base_hit_pct"] = base

    # ---- 2. CONDITIONAL BREAK (same-day eventual-hit lift) ----
    print("\n" + "=" * 66 + "\n2) CONDITIONAL BREAK  same day: P(Y hit | X hit) vs P(Y hit)\n" + "=" * 66)
    piv = L.pivot_table(index="date", columns=["session", "type"], values="hit", aggfunc="max")
    pairs = [(("london", "high"), ("newyork", "high")),
             (("asia", "high"), ("london", "high")),
             (("london", "low"), ("newyork", "low")),
             (("newyork", "high"), ("newyork", "low"))]
    conds = []
    for x, y in pairs:
        if x not in piv or y not in piv:
            continue
        d = piv[[x, y]].dropna()
        base_y = d[y].mean()
        cond_y = d[d[x]][y].mean()
        lift = cond_y / base_y if base_y else float("nan")
        conds.append({"given": f"{x[0]} {x[1]}", "predict": f"{y[0]} {y[1]}",
                      "P_Y": round(base_y, 3), "P_Y_given_X": round(cond_y, 3), "lift": round(lift, 3)})
        print(f"  given {x[0]:>7} {x[1]:<4} -> {y[0]:>7} {y[1]:<4}   "
              f"P(Y)={base_y:.2f}  P(Y|X)={cond_y:.2f}  lift={lift:.2f}"
              + ("   <- lift~1: no info" if 0.9 <= lift <= 1.1 else ""))
    out["conditional"] = conds

    # ---- 3. FOLLOW-THROUGH (the edge test) ----
    print("\n" + "=" * 66 + "\n3) FOLLOW-THROUGH after a level breaks  (continuation vs fade)\n" + "=" * 66)
    ft_out = []
    for N in NS:
        fret = (close[N:] - close[:-N]) / close[:-N] * 100      # N-bar fwd return per bar
        drift = float(np.mean(fret))                             # market drift, long-sense
        print(f"\n  horizon {N} bars (~{N*5/60:.1f}h)   market drift {drift:+.3f}%")
        print(f"  {'break':<12}{'n':>7}{'mean move%':>12}{'win%':>7}{'t':>7}{'excess vs drift':>17}{'  1st/2nd half'}")
        for typ, d in (("high", 1), ("low", -1)):
            rows = L[(L["type"] == typ) & (L["hit"])]
            vals, dates = [], []
            for r in rows.itertuples():
                bi = pos.get(int(r.breach_ts)) if r.breach_ts else None
                if bi is None or bi + N >= n:
                    continue
                vals.append(d * (close[bi + N] - close[bi]) / close[bi] * 100)
                dates.append(r.date)
            v = np.array(vals)
            if len(v) < 30:
                continue
            mean, win = float(v.mean()), float((v > 0).mean() * 100)
            t = mean / (v.std(ddof=1) / np.sqrt(len(v))) if v.std() else 0
            excess = mean - d * drift
            half = len(v) // 2
            h1, h2 = float(v[:half].mean()), float(v[half:].mean())
            edge = abs(t) >= 2 and abs(excess) >= 0.03 and np.sign(h1) == np.sign(h2)
            print(f"  {typ+' breakout':<12}{len(v):>7}{mean:>+11.3f}%{win:>6.1f}%{t:>+7.2f}"
                  f"{excess:>+16.3f}%   {h1:+.3f}/{h2:+.3f}{'   *EDGE?' if edge else ''}")
            ft_out.append({"horizon": N, "break": typ, "n": len(v), "mean_pct": round(mean, 3),
                           "win_pct": round(win, 1), "t": round(t, 2), "excess_pct": round(excess, 3),
                           "half1": round(h1, 3), "half2": round(h2, 3), "edge_flag": bool(edge)})
    out["follow_through"] = ft_out

    print("\n" + "=" * 66)
    print("READ: lift~1 and excess~0 with |t|<2 = NO predictability (breaches are ~base-rate,")
    print("breakouts don't continue beyond drift). An '*EDGE?' needs |t|>=2, excess>=0.03%,")
    print("AND same sign in both halves -- then it's worth a real OOS/cost test, not before.")
    json.dump(out, open(os.path.join(OUT, "session_break_stats.json"), "w"), indent=1)
    print("wrote", os.path.join(OUT, "session_break_stats.json"))


if __name__ == "__main__":
    main()
