"""
fib_bias — EDGE TEST: does a session's Fibonacci position predict the NEXT session's direction?

VISION 9 flagged Fib (off the session high/low) as a directional-bias tool — but UNTESTED. This
tests it honestly (same spirit as session_break_stats): for each completed session take where its
CLOSE sits within the range as a fib retracement `fpos = (close-low)/(high-low)`, bucket into fib
zones, and measure the NEXT tradeable session's direction (open->close). If a zone's P(next up)
lifts meaningfully off the base rate (beyond binomial noise), Fib carries a directional edge; if
lifts hug 1.0, it does not — and Fib is not a direction gate (drop it, or keep only as geometry).

Run:  python research/gates/fib_bias/fib_bias.py
Out:  output/fib_bias.json  + console table
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "research", "runs"))
import strategy_config as cfg
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
TRADING = ("asia", "london", "newyork")
# fib retracement bands (where the close sits in the range); labelled by the zone they fall in
EDGES = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0001]
LABELS = ["0-23.6 (deep low)", "23.6-38.2", "38.2-50", "50-61.8", "61.8-78.6", "78.6-100 (deep high)"]


def _sessions(et):
    mod = et.hour * 60 + et.minute
    lab = np.full(len(et), "asia", dtype=object)
    lab[(mod >= 180) & (mod < 570)] = "london"
    lab[(mod >= 570) & (mod < 960)] = "newyork"
    lab[(mod >= 960) & (mod < 1080)] = "close"
    return lab, mod


def build():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    df = df[et.year >= cfg.ERA_START_YEAR]
    et = et[et.year >= cfg.ERA_START_YEAR]
    sess, mod = _sessions(et)
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)
    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "open": df["open"].to_numpy(), "high": df["high"].to_numpy(),
                      "low": df["low"].to_numpy(), "close": df["close"].to_numpy(),
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    f = f[np.isin(f["session"], TRADING)]
    # one row per session instance (ordered)
    g = f.groupby(["date", "session"], sort=False)
    rows = []
    for (date, s), gg in g:
        lo, hi = float(gg["low"].min()), float(gg["high"].max())
        if hi <= lo:
            continue
        o, c = float(gg["open"].iloc[0]), float(gg["close"].iloc[-1])
        rows.append({"sid": f"{date} {s}", "session": s, "ts": int(gg["ts"].min()),
                     "open": o, "close": c, "fpos": (c - lo) / (hi - lo),
                     "dir": 1 if c >= o else 0})
    d = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    # NEXT session's direction (open->close) = the thing you'd trade after this reading
    d["next_dir"] = d["dir"].shift(-1)
    d["next_ret"] = (d["close"].shift(-1) / d["open"].shift(-1) - 1) * 100  # next session open->close %
    return d.dropna(subset=["next_dir"])


def main():
    d = build()
    base = d["next_dir"].mean()
    d["zone"] = pd.cut(d["fpos"], EDGES, labels=LABELS, right=False)
    print(f"fib_bias EDGE TEST -- {len(d):,} sessions (era >= {cfg.ERA_START_YEAR})")
    print(f"base rate  P(next session up) = {base*100:.1f}%\n")
    print(f"  {'fib zone (close in range)':<22}{'n':>7}{'P(next up)':>12}{'lift':>7}{'next ret%':>11}")
    print("  " + "-" * 60)
    report = {"base_rate": round(base, 4), "n": int(len(d)), "zones": []}
    for lab in LABELS:
        z = d[d["zone"] == lab]
        if len(z) == 0:
            continue
        p = z["next_dir"].mean(); lift = p / base if base else 0
        se = (base * (1 - base) / len(z)) ** 0.5           # binomial noise band on the rate
        sig = "" if abs(p - base) < 2 * se else "  *"       # * = >2sigma from base
        print(f"  {lab:<22}{len(z):>7}{p*100:>11.1f}%{lift:>7.2f}{z['next_ret'].mean():>10.3f}%{sig}")
        report["zones"].append({"zone": lab, "n": int(len(z)), "p_next_up": round(p, 4),
                                "lift": round(lift, 3), "next_ret_pct": round(float(z["next_ret"].mean()), 4),
                                "sig_2sigma": bool(abs(p - base) >= 2 * se)})
    spread = d.groupby("zone", observed=True)["next_dir"].mean()
    edge = spread.max() - spread.min()
    verdict = ("DIRECTIONAL EDGE worth a gate" if edge >= 0.06 else
               "NO usable directional edge (lifts ~1, within noise) -- Fib is not a direction gate")
    report["max_minus_min_p"] = round(float(edge), 4); report["verdict"] = verdict
    print(f"\n  spread across zones (max-min P up) = {edge*100:.1f} pts  ->  {verdict}")
    print("  (* = zone rate >2-sigma from base; geometry-only Fib overlay stays on the chart regardless)")
    json.dump(report, open(os.path.join(OUT, "fib_bias.json"), "w"), indent=1)
    print("wrote", os.path.join(OUT, "fib_bias.json"))
    runlog.record("fib_bias",
                  {"edges": EDGES, "era_start": cfg.ERA_START_YEAR, "next_target": "next-session open->close dir"},
                  {"n": report["n"], "base_rate_pct": round(report["base_rate"] * 100, 1),
                   "max_minus_min_p_pts": round(report["max_minus_min_p"] * 100, 1),
                   "verdict": report["verdict"]})


if __name__ == "__main__":
    main()
