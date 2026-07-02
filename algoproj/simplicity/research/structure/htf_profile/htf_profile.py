"""
htf_profile — the HIGHER-TIMEFRAME composite profile (the third scale; NOTES F15/F19).

The largest of the three nested profilers (base < session < HTF). For each session it composites the
trailing HTF_DAYS calendar days of 5m volume into ONE profile ending at the session OPEN (causal -- it's
the multi-day context you walk INTO the session with, it does not peek at the session itself). Gives the
"where has the market balanced over the week" reference: composite POC / value area / naked levels, and
"are we at value or extended" once you place current price against it.

Kept SEPARATE from volume_profile / base_profile on purpose: three independent modules, tuned side by
side, each gathering its own data. Emits the SAME profile-dict shape, so shape_filter + zone_calibration
score it unchanged (the seam). Role in a trade: HTF supplies the RUNWAY (big target) + regime context;
base supplies the tight stop; session is the zone between. Direction stays unpredicted (F13).

    from htf_profile import compute, check
Run:  python research/structure/htf_profile/htf_profile.py   ->  output/htf_profile.json + ledger row
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, _SIM)
sys.path.insert(0, os.path.join(HERE, "..", "volume_profile"))
sys.path.insert(0, os.path.join(_SIM, "research", "runs"))
import strategy_config as cfg
import volume_profile as vp
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)

# --- tunable PARAMS: sourced from strategy_config.HTF (single source of truth; tune THERE) ---
HTF_DAYS = cfg.HTF["days"]        # trailing calendar days composited into the HTF profile (~one week)
HTF_BINS = cfg.HTF["bins"]        # fixed bin count for the composite (a week needs coarser rows than a session)
MIN_HTF_BARS = cfg.HTF["min_bars"]


def _profile(hi, lo, vol):
    sl, sh = float(lo.min()), float(hi.max())
    if sh <= sl:
        return None
    edges = np.linspace(sl, sh, HTF_BINS + 1)
    vbin = vp._spread_volume(lo, hi, vol, edges)
    va = vp._value_area(vbin, edges)
    if va is None:
        return None
    poc, val, vah = va
    centers = (edges[:-1] + edges[1:]) / 2
    bins = [{"p": round(float(centers[i]), 2), "v": round(float(vbin[i]), 1),
             "va": bool(val <= centers[i] <= vah)} for i in range(HTF_BINS) if vbin[i] > 0]
    return {"high": round(sh, 2), "low": round(sl, 2), "poc": poc, "val": val, "vah": vah,
            "height_pct": round((sh - sl) / sl * 100, 3),
            "va_pct_of_range": round((vah - val) / (sh - sl) * 100, 1), "bins": bins}


def compute(since_ts=None):
    """HTF composite per session (trailing HTF_DAYS ending at session open). since_ts skips older sessions
    but the trailing window is still drawn from the full history."""
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
    ts = (et.view("int64") // 1_000_000_000).astype("int64")
    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
                      "vol": df["volume"].to_numpy(dtype="float64"), "ts": np.asarray(ts)})
    f = f[f["session"] != "close"]
    ts_all = f["ts"].to_numpy(); hi_all = f["high"].to_numpy(); lo_all = f["low"].to_numpy(); vol_all = f["vol"].to_numpy()

    out = []
    for (date, s), gg in f.groupby(["date", "session"], sort=False):
        start = int(gg["ts"].min())
        if since_ts and start < since_ts:
            continue
        a = start - HTF_DAYS * 86400
        i0 = int(np.searchsorted(ts_all, a, "left")); i1 = int(np.searchsorted(ts_all, start, "left"))
        if i1 - i0 < MIN_HTF_BARS:
            continue
        pr = _profile(hi_all[i0:i1], lo_all[i0:i1], vol_all[i0:i1])
        if pr is None:
            continue
        pr.update(date=date, session=s, sid=f"{date} {s}", start=int(ts_all[i0]), end=start,
                  htf_days=HTF_DAYS, htf_bars=int(i1 - i0), bars=int(i1 - i0))
        out.append(pr)
    return out


def check():
    o = compute(since_ts=int(pd.Timestamp.now(tz="UTC").timestamp()) - 400 * 86400)
    if not o:
        return "no HTF composites"
    va = np.median([x["va_pct_of_range"] for x in o])
    h = np.median([x["height_pct"] for x in o])
    return f"{len(o)} recent HTF composites ({HTF_DAYS}d, {HTF_BINS} rows); median week height {h:.1f}%, VA {va:.0f}% of range"


def main():
    since = int(pd.Timestamp("2023-01-01", tz="UTC").timestamp())   # recent window keeps the run quick
    o = compute(since_ts=since)
    json.dump({"htf_days": HTF_DAYS, "htf_bins": HTF_BINS, "profiles": o},
              open(os.path.join(OUT, "htf_profile.json"), "w"))
    va = np.median([x["va_pct_of_range"] for x in o]); h = np.median([x["height_pct"] for x in o])
    print(f"built {len(o):,} HTF composites since 2023 ({HTF_DAYS}d week, {HTF_BINS} rows)")
    print(f"  median week height {h:.2f}% of price; median VA {va:.0f}% of the week's range")
    print("wrote", os.path.join(OUT, "htf_profile.json"))
    runlog.record("htf_profile", {"htf_days": HTF_DAYS, "htf_bins": HTF_BINS, "min_htf_bars": MIN_HTF_BARS},
                  {"n": len(o), "median_week_height_pct": round(float(h), 3),
                   "median_va_pct": round(float(va), 1)})


if __name__ == "__main__":
    main()
