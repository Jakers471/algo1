"""
shape_filter — turn the "clean vs foggy" volume profile into a NUMBER (VISION 8).

A QUALITY gate (not an edge hunt): score how much a session's profile looks like a clean,
single-peak consolidation vs a scattered / trending / multi-peak one. Reads the volume_profile
output (per-session bins + POC + value area). PROVISIONAL metrics/weights -- built to eyeball
against real price, then refine.

  tightness   value area narrow vs the whole range?   (low va_pct_of_range = tight)
  prominence  POC bin vs the average bin               (peaked vs flat)
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
import strategy_config as cfg  # noqa: F401 (kept for consistency)

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
VP = os.path.join(HERE, "..", "..", "structure", "volume_profile", "output", "volume_profile.json")


def score(p):
    """Shape metrics + 0-100 score for one session profile dict (with 'bins')."""
    bins = p.get("bins") or []
    if len(bins) < 3:
        return None
    v = np.array([b["v"] for b in bins], dtype=float)
    total, poc_v, mean_v = v.sum(), v.max(), v.mean()
    if total <= 0:
        return None
    prominence = poc_v / mean_v if mean_v > 0 else 0.0
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

    tight = max(0.0, 1 - va_pct / 80.0)            # va% 0->1, 80%+->0
    peakc = min(1.0, max(0.0, (prominence - 1) / 4.0))  # prom 1->0, 5->1
    single = 1.0 if peaks <= 1 else (0.5 if peaks == 2 else 0.15)
    central = max(0.0, 1 - balance / 0.5)
    shape = round(100 * (0.40 * tight + 0.30 * peakc + 0.20 * single + 0.10 * central))
    return {"shape_score": shape, "va_pct": round(va_pct, 1), "prominence": round(prominence, 2),
            "n_peaks": int(peaks), "poc_pos": round(poc_pos, 2), "top_share_pct": round(top_share, 1),
            "shape_ok": bool(shape >= 50)}


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
    print(f"  shape_ok (>=50): {d.shape_ok.mean()*100:.0f}%   median n_peaks {int(d.n_peaks.median())}"
          f"   median va% {d.va_pct.median():.0f}")
    print("wrote", os.path.join(OUT, "shape_scores.csv"))


if __name__ == "__main__":
    main()
