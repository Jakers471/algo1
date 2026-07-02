"""
shape_filter — turn the "clean vs foggy" volume profile into a NUMBER (VISION 8).

A QUALITY gate (not an edge hunt): score how much a session's profile looks like a clean,
single-peak consolidation vs a scattered / trending / multi-peak one. Reads the volume_profile
output (per-session bins + POC + value area). PROVISIONAL metrics/weights -- built to eyeball
against real price, then refine.

  tightness   PEAKED on va_pct (VA width / range): a clean bell coil (~TIGHT_PEAK) scores 1.0; a
              spike (va_pct->0) and a scatter/bimodal (high va_pct) both score low  (NOTES F16)
  prominence  POC vs the mean of the VALUE-AREA bins   (peaked vs flat; breakout-robust -- the
              breakout leg's thin bins fall OUTSIDE the VA so they can't dilute it; NOTES F17)
  n_peaks     significant humps                        (1 = single-peak = clean)
  balance     POC near the middle?                     (central = consolidation, edge = trend)

Run:  python research/profile_shape_filter/shape_filter.py
Out:  output/shape_scores.csv  + console distribution
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "research", "runs"))
import strategy_config as cfg  # noqa: F401 (kept for consistency)
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
VP = os.path.join(HERE, "..", "..", "structure", "volume_profile", "output", "volume_profile.json")

# --- tunable PARAMS: sourced from strategy_config.SHAPE (single source of truth; tune THERE) ---
# tightness = a PEAKED curve on va_pct (clean bell coil ~TIGHT_PEAK -> 1.0, falls to 0 at va_pct=0
# spike AND at TIGHT_HI scatter; NOTES F16). prominence = POC / mean(VA bins), breakout-robust (F17).
WEIGHTS = cfg.SHAPE["weights"]
TIGHT_PEAK, TIGHT_HI = cfg.SHAPE["tight_peak"], cfg.SHAPE["tight_hi"]
PROM_DEN = cfg.SHAPE["prom_den"]
SINGLE_2, SINGLE_ELSE = cfg.SHAPE["single_2"], cfg.SHAPE["single_else"]
SHAPE_OK = cfg.SHAPE["shape_ok"]


def score(p):
    """Shape metrics + 0-100 score for one session profile dict (with 'bins')."""
    bins = p.get("bins") or []
    if len(bins) < 3:
        return None
    v = np.array([b["v"] for b in bins], dtype=float)
    total, poc_v = v.sum(), v.max()
    if total <= 0:
        return None
    va_v = np.array([b["v"] for b in bins if b.get("va")], dtype=float)   # value-area core (breakout-robust)
    denom = va_v.mean() if va_v.size else v.mean()
    prominence = poc_v / denom if denom > 0 else 0.0
    # local-maxima peaks that clear half the POC (significant humps)
    peaks = 0
    for i in range(len(v)):
        lft = v[i - 1] if i > 0 else -1
        rgt = v[i + 1] if i < len(v) - 1 else -1
        if v[i] >= lft and v[i] >= rgt and v[i] > 0.5 * poc_v:
            peaks += 1
    va_pct = float(p["va_pct_of_range"])
    rng = p["high"] - p["low"]
    poc_pos = (p["poc"] - p["low"]) / rng if rng > 0 else 0.5
    balance = abs(poc_pos - 0.5)
    top_share = poc_v / total * 100

    tight = (va_pct / TIGHT_PEAK) if va_pct <= TIGHT_PEAK \
        else max(0.0, 1 - (va_pct - TIGHT_PEAK) / (TIGHT_HI - TIGHT_PEAK))
    peakc = min(1.0, max(0.0, (prominence - 1) / PROM_DEN))
    single = 1.0 if peaks <= 1 else (SINGLE_2 if peaks == 2 else SINGLE_ELSE)
    central = max(0.0, 1 - balance / 0.5)
    shape = round(100 * (WEIGHTS["tight"] * tight + WEIGHTS["peak"] * peakc
                         + WEIGHTS["single"] * single + WEIGHTS["central"] * central))
    return {"shape_score": shape, "va_pct": round(va_pct, 1), "prominence": round(prominence, 2),
            "n_peaks": int(peaks), "poc_pos": round(poc_pos, 2), "top_share_pct": round(top_share, 1),
            "shape_ok": bool(shape >= SHAPE_OK)}


def main():
    profiles = json.load(open(VP))["profiles"]
    rows = []
    for p in profiles:
        s = score(p)
        if s:
            rows.append({"sid": p["sid"], "session": p["session"], "date": p["date"], **s})
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "shape_scores.csv"), index=False)
    print(f"scored {len(d):,} session profiles  (PROVISIONAL shape metric)")
    print("\n  shape_score distribution:")
    for q in (10, 25, 50, 75, 90):
        print(f"    p{q:>2}: {d.shape_score.quantile(q/100):.0f}")
    print(f"  shape_ok (>={SHAPE_OK}): {d.shape_ok.mean()*100:.0f}%   median n_peaks {int(d.n_peaks.median())}"
          f"   median va% {d.va_pct.median():.0f}")
    print("wrote", os.path.join(OUT, "shape_scores.csv"))
    runlog.record("shape_filter",
                  {"weights": WEIGHTS, "tight_peak": TIGHT_PEAK, "tight_hi": TIGHT_HI, "prom_den": PROM_DEN,
                   "single_2": SINGLE_2, "single_else": SINGLE_ELSE, "shape_ok": SHAPE_OK},
                  {"n": int(len(d)), "median_score": round(float(d.shape_score.median()), 1),
                   "shape_ok_pct": round(float(d.shape_ok.mean() * 100), 1),
                   "median_va_pct": round(float(d.va_pct.median()), 1),
                   "median_n_peaks": int(d.n_peaks.median())})


if __name__ == "__main__":
    main()
