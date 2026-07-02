"""
zone_calibration — turn a session's zone into TRADE GEOMETRY before entry (VISION 7).

The R:R engine. From the zone (session range hi/lo + value area) it derives, PER SESSION:
  risk_pts   the stop = beyond the value-area edge   (VAH - VAL)  -> 1R
  room_pts   the room / measured move = the range     (high - low)
  rr         room / risk                              (tighter VA vs range = better R:R)
  entry_tf   tight+short zone -> smaller entry TF for a snug entry; wide -> higher TF
  rr_ok      geometry worth risking on?               (rr >= RR_MIN)

A GATE: most zones become no-trade (rr below threshold) -- correct. PROVISIONAL rules
(stop = VA edge, target = full range); built to eyeball against real price, then refine.

Run:  python research/zone_calibration/zone_calibration.py
Out:  output/zone_calibration.csv  + console distribution
"""
import os
import sys
import json

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as cfg  # noqa: F401

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
VP = os.path.join(HERE, "..", "volume_profile", "output", "volume_profile.json")

RR_MIN = 2.0
# height_pct thresholds -> which lower timeframe supplies the entry/stop
TF_BANDS = [(0.25, "1m"), (0.60, "5m"), (float("inf"), "15m")]


def _entry_tf(height_pct):
    for hi, tf in TF_BANDS:
        if height_pct < hi:
            return tf
    return "15m"


def calibrate(p):
    """Zone geometry for one session profile dict."""
    rng = p["high"] - p["low"]
    va = p["vah"] - p["val"]
    if rng <= 0 or va <= 0:
        return None
    rr = round(rng / va, 2)                     # room (range) / risk (VA edge)
    return {"height_pct": round(p["height_pct"], 3), "bars": int(p["bars"]),
            "risk_pts": round(va, 1), "room_pts": round(rng, 1), "rr": rr,
            "entry_tf": _entry_tf(p["height_pct"]), "rr_ok": bool(rr >= RR_MIN)}


def main():
    profiles = json.load(open(VP))["profiles"]
    rows = []
    for p in profiles:
        c = calibrate(p)
        if c:
            rows.append({"sid": p["sid"], "session": p["session"], "date": p["date"], **c})
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "zone_calibration.csv"), index=False)
    print(f"calibrated {len(d):,} session zones  (PROVISIONAL geometry: stop=VA edge, target=range)")
    print("\n  R:R distribution:")
    for q in (10, 25, 50, 75, 90):
        print(f"    p{q:>2}: {d.rr.quantile(q/100):.2f}")
    print(f"  rr_ok (>= {RR_MIN}): {d.rr_ok.mean()*100:.0f}%")
    print("  entry_tf split:", d.entry_tf.value_counts().to_dict())
    print("wrote", os.path.join(OUT, "zone_calibration.csv"))


if __name__ == "__main__":
    main()
