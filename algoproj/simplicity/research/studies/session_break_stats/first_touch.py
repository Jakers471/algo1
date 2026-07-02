"""
first_touch — at NY open, which standing overnight level gets taken FIRST, and does it matter?

The liquidity-sweep question. Each day, the levels STANDING when NY opens (09:30 ET) are the
London high/low and Asia high/low. During the NY session we find which side is TOUCHED first
(wick through it), then test whether that predicts anything:
  * distribution   — high-first vs low-first (is there a side bias?)
  * sweep+reverse  — after taking one side first, how often is the OTHER side taken too?
  * direction      — given high-first (or low-first), the NY session return vs baseline
                     (does a sweep of one side lead to continuation, or reversal?)

Honest: reports the baseline NY return/up-rate so a conditional only counts if it clears it.

Run:  python research/session_break_stats/first_touch.py
Out:  console + output/first_touch.json
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
import strategy_config as cfg

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
INF = 10 ** 18


def main():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    mod = et.hour * 60 + et.minute
    sess = np.full(len(et), "asia", dtype=object)
    sess[(mod >= 180) & (mod < 570)] = "london"
    sess[(mod >= 570) & (mod < 960)] = "newyork"
    sess[(mod >= 960) & (mod < 1080)] = "close"
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)

    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
                      "open": df["open"].to_numpy(), "close": df["close"].to_numpy(),
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    lon = f[f.session == "london"].groupby("date").agg(Lh=("high", "max"), Ll=("low", "min"))
    asi = f[f.session == "asia"].groupby("date").agg(Ah=("high", "max"), Al=("low", "min"))
    close = df["close"].to_numpy(); n = len(close)
    pos = {int(t): i for i, t in enumerate(f["ts"].to_numpy())}

    rows = []
    for date, g in f[f.session == "newyork"].groupby("date"):
        if date not in lon.index:
            continue
        hi, lo, ts = g["high"].to_numpy(), g["low"].to_numpy(), g["ts"].to_numpy()
        op, cl = float(g["open"].iloc[0]), float(g["close"].iloc[-1])
        ret = (cl - op) / op * 100
        r = {"date": date, "ny_ret": ret}
        for pre, (H, L) in (("L", (lon.loc[date, "Lh"], lon.loc[date, "Ll"])),
                            ("A", (asi.loc[date, "Ah"], asi.loc[date, "Al"]) if date in asi.index else (np.nan, np.nan))):
            if np.isnan(H):
                r[pre + "_first"] = "none"; continue
            th = ts[np.argmax(hi >= H)] if (hi >= H).any() else INF
            tl = ts[np.argmax(lo <= L)] if (lo <= L).any() else INF
            r[pre + "_first"] = "high" if th < tl else ("low" if tl < th else "none")
            r[pre + "_both"] = (th < INF) and (tl < INF)
            if pre == "L" and min(th, tl) < INF:
                r["L_first_ts"] = int(min(th, tl))
        rows.append(r)
    d = pd.DataFrame(rows)
    base_ret, base_up, N = d.ny_ret.mean(), (d.ny_ret > 0).mean() * 100, len(d)
    out = {"days": N, "baseline_ny_ret": round(base_ret, 4), "baseline_up_pct": round(base_up, 1)}

    print("=" * 70)
    print(f"NY-open first touch of standing overnight levels  ({N:,} days)")
    print(f"baseline: NY session return {base_ret:+.3f}%  |  up {base_up:.1f}% of days")
    print("=" * 70)
    for pre, name in (("L", "LONDON"), ("A", "ASIA")):
        col = pre + "_first"
        vc = d[col].value_counts(normalize=True) * 100
        print(f"\n{name} levels first-touched during NY:")
        print(f"  high-first {vc.get('high',0):.1f}%   low-first {vc.get('low',0):.1f}%   none {vc.get('none',0):.1f}%")
        rec = {"high_first_pct": round(float(vc.get("high", 0)), 1),
               "low_first_pct": round(float(vc.get("low", 0)), 1)}
        for side in ("high", "low"):
            sub = d[d[col] == side]
            if len(sub) < 30:
                continue
            mret, up = sub.ny_ret.mean(), (sub.ny_ret > 0).mean() * 100
            both = sub[pre + "_both"].mean() * 100 if (pre + "_both") in sub else float("nan")
            t = (mret - base_ret) / (sub.ny_ret.std(ddof=1) / np.sqrt(len(sub)))
            print(f"  given {side}-first (n={len(sub)}): NY ret {mret:+.3f}% (base {base_ret:+.3f}, "
                  f"excess t={t:+.2f}) | up {up:.1f}% | other side also taken {both:.0f}%")
            rec[f"{side}_first_ny_ret"] = round(float(mret), 4)
            rec[f"{side}_first_up_pct"] = round(float(up), 1)
            rec[f"{side}_first_sweep_both_pct"] = round(float(both), 1)
            rec[f"{side}_first_excess_t"] = round(float(t), 2)
        out[name.lower()] = rec

    # ---- the HONEST edge test: forward return AFTER the touch, signed by touch side ----
    print("\n" + "=" * 70)
    print("FORWARD FROM the London first-touch (the tradeable test, not open->close)")
    print("  signed by side: high-first +ret = continuation up, low-first: continuation down")
    print("=" * 70)
    ft = []
    sub = d[d["L_first"].isin(["high", "low"]) & d.get("L_first_ts").notna()] if "L_first_ts" in d else d.iloc[0:0]
    for N in (12, 36):
        vals = []
        for r in sub.itertuples():
            bi = pos.get(int(r.L_first_ts))
            if bi is None or bi + N >= n:
                continue
            sgn = 1 if r.L_first == "high" else -1
            vals.append(sgn * (close[bi + N] - close[bi]) / close[bi] * 100)
        v = np.array(vals)
        if len(v) < 30:
            continue
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
        print(f"  +{N} bars (~{N*5/60:.1f}h): mean {v.mean():+.4f}%  win {(v>0).mean()*100:.1f}%  "
              f"t={t:+.2f}  (n={len(v)})" + ("   <- ~0: NO edge after the sweep" if abs(t) < 2 else ""))
        ft.append({"horizon": N, "mean_pct": round(float(v.mean()), 4),
                   "win_pct": round(float((v > 0).mean() * 100), 1), "t": round(float(t), 2), "n": len(v)})
    out["forward_from_touch"] = ft

    print("\nREAD: side-first % near 50/50 = no bias. 'excess t' near 0 = the sweep direction")
    print("doesn't predict the NY return. 'other side also taken' high = NY usually runs BOTH")
    print("overnight extremes (range expansion), regardless of which came first.")
    json.dump(out, open(os.path.join(OUT, "first_touch.json"), "w"), indent=1)
    print("wrote", os.path.join(OUT, "first_touch.json"))


if __name__ == "__main__":
    main()
