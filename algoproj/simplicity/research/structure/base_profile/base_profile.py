"""
base_profile — profile the detected CONSOLIDATION BASE, not the whole session (VISION / NOTES F6).

The parallel version of volume_profile. Instead of profiling every bar of a session, it detects the
current tight base (a causal contraction scan back from the last bar) and profiles ONLY that window.
The impulse leg and any breakout fall OUTSIDE the base, so the range-normalization distortions we keep
patching in the whole-session profile (POC placement, tightness, prominence -- NOTES F5/F16/F17) can't
arise here. It emits the SAME profile-dict shape as volume_profile, so shape_filter + zone_calibration
score it with ZERO changes -- the whole point of the seam.

Detector (causal): band = BAND_MULT x median bar-range of the session; walk back from the last bar,
growing the window while its (high-low) stays <= band; stop when a bar would blow it open. That gives
the consolidation price is in AT the end of the session (what the live strategy reads before the next open).

    from base_profile import compute, detect, check
    compute()            # base profiles over the 5m history (same shape as volume_profile output)
    check()              # readiness summary

Run:  python research/structure/base_profile/base_profile.py   ->  output/base_profile.json + ledger row
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # simplicity/
sys.path.insert(0, _SIM)
sys.path.insert(0, os.path.join(HERE, "..", "volume_profile"))         # reuse the profiler helpers
sys.path.insert(0, os.path.join(_SIM, "research", "runs"))
import strategy_config as cfg
import volume_profile as vp
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)

# --- tunable PARAMS: sourced from strategy_config.BASE (single source of truth; tune THERE) ---
BAND_MULT = cfg.BASE["band_mult"]   # base window range <= BAND_MULT x the session's median bar-range
MIN_BARS = cfg.BASE["min_bars"]     # need >= this many bars to call it a base


def detect(hi, lo):
    """Causal contraction scan: grow a window back from the last bar while its range stays tight.
    Returns (start_idx, end_idx) of the base, or None if no base of >= MIN_BARS forms."""
    n = len(hi)
    if n < MIN_BARS:
        return None
    band = BAND_MULT * float(np.median(hi - lo))
    end = n - 1
    wl, wh, start = lo[end], hi[end], end
    for i in range(end - 1, -1, -1):
        nwl, nwh = min(wl, lo[i]), max(wh, hi[i])
        if (nwh - nwl) > band:
            break
        wl, wh, start = nwl, nwh, i
    return (start, end) if (end - start + 1) >= MIN_BARS else None


def _profile(g):
    """Profile-dict (same shape as volume_profile) over the given bar slice g (high/low/vol)."""
    sl, sh = float(g["low"].min()), float(g["high"].max())
    if sh <= sl:
        return None
    nb = max(3, int(round((sh - sl) / vp.ROW_SIZE)))
    edges = np.linspace(sl, sh, nb + 1)
    vbin = vp._spread_volume(g["low"].to_numpy(), g["high"].to_numpy(), g["vol"].to_numpy(), edges)
    va = vp._value_area(vbin, edges)
    if va is None:
        return None
    poc, val, vah = va
    centers = (edges[:-1] + edges[1:]) / 2
    bins = [{"p": round(float(centers[i]), 2), "v": round(float(vbin[i]), 1),
             "va": bool(val <= centers[i] <= vah)} for i in range(nb) if vbin[i] > 0]
    return {"high": round(sh, 2), "low": round(sl, 2), "poc": poc, "val": val, "vah": vah,
            "height_pct": round((sh - sl) / sl * 100, 3),
            "va_pct_of_range": round((vah - val) / (sh - sl) * 100, 1), "bins": bins}


def compute(tail=None):
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    if tail:
        df = df.tail(tail)
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
                      "vol": df["volume"].to_numpy(dtype="float64"),
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    f = f[f["session"] != "close"]

    out, n_sessions = [], 0
    for (date, s), g in f.groupby(["date", "session"], sort=False):
        n_sessions += 1
        det = detect(g["high"].to_numpy(), g["low"].to_numpy())
        if not det:
            continue
        st, en = det
        gb = g.iloc[st:en + 1]
        pr = _profile(gb)
        if pr is None:
            continue
        pr.update(date=date, session=s, sid=f"{date} {s}",
                  start=int(gb["ts"].min()), end=int(gb["ts"].max()),
                  session_start=int(g["ts"].min()), session_end=int(g["ts"].max()),
                  bars=int(en - st + 1), session_bars=int(len(g)))
        out.append(pr)
    return out, n_sessions


def check():
    o, n = compute(tail=20000)
    if not o:
        return "no bases detected"
    va = np.median([x["va_pct_of_range"] for x in o])
    cov = np.median([x["bars"] / x["session_bars"] for x in o]) * 100
    return f"{len(o)}/{n} sessions have a base ({len(o)/n*100:.0f}%); base = {cov:.0f}% of the session; median VA {va:.0f}% of base range"


def main():
    o, n = compute()
    json.dump({"band_mult": BAND_MULT, "min_bars": MIN_BARS, "row_size": vp.ROW_SIZE,
               "profiles": o}, open(os.path.join(OUT, "base_profile.json"), "w"))
    cov = np.median([x["bars"] / x["session_bars"] for x in o]) * 100
    va = np.median([x["va_pct_of_range"] for x in o])
    print(f"detected a base in {len(o):,}/{n:,} sessions ({len(o)/n*100:.0f}%)  "
          f"[band={BAND_MULT}x median bar-range, min {MIN_BARS} bars]")
    print(f"  base spans a median {cov:.0f}% of its session; median VA {va:.0f}% of base range "
          f"(vs ~54% whole-session)")
    print("wrote", os.path.join(OUT, "base_profile.json"))
    runlog.record("base_profile",
                  {"band_mult": BAND_MULT, "min_bars": MIN_BARS, "row_size": vp.ROW_SIZE},
                  {"n_sessions": int(n), "n_bases": len(o), "detect_pct": round(len(o) / n * 100, 1),
                   "median_base_coverage_pct": round(float(cov), 1),
                   "median_base_va_pct": round(float(va), 1)})


if __name__ == "__main__":
    main()
