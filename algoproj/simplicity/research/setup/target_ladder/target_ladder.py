"""
target_ladder — the multi-scale R:R GEOMETRY engine (NOTES F25). Geometry only, NO backtest.

Given the nested scales (base < session < HTF) it derives the concrete trade geometry:
  1R (stop)  = the BASE coil (its high<->low) -- the tight stop from the smallest scale.
  targets    = every LARGER scale's VA edges / POC / extremes, in the breakout direction, ordered
               nearest-first into a scale-out LADDER (rungs that "come down into each other").
  R:R        = (target - entry) / 1R for each rung.
Computed for BOTH directions (we don't predict which way -- direction stays unpredicted, F13); the up
and down ladders are symmetric readings of the same structure. This is the trade DEFINITION
(entry/stop/take-profit geometry) that setup_arm will later arm and a backtest will later measure
(realized R). zone_calibration is the crude single-scale version; this is the multi-scale generalization.

    from target_ladder import ladder
    ladder({"base": base_prof, "session": session_prof, "htf": htf_prof})

Run:  python research/setup/target_ladder/target_ladder.py   ->  console summary + ledger row
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # simplicity/
sys.path.insert(0, _SIM)
sys.path.insert(0, os.path.join(_SIM, "research", "runs"))
import strategy_config as cfg
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
LEVELS = [("VAH", "vah"), ("VAL", "val"), ("POC", "poc"), ("high", "high"), ("low", "low")]


def ladder(scales):
    """scales = {'base':profile, 'session':profile, 'htf':profile}. Returns the trade geometry, or None."""
    base = scales.get("base")
    if not base:
        return None
    R = base["high"] - base["low"]                       # 1R = the base coil (tight stop from smallest scale)
    if R <= 0:
        return None
    cand = []                                            # candidate target levels from the larger scales
    for name in cfg.LADDER["sources"]:
        p = scales.get(name)
        if not p:
            continue
        for lab, key in LEVELS:
            if key in p:
                cand.append((f"{name} {lab}", float(p[key])))

    def side(entry, stop, keep):
        tg = []
        for lab, lv in cand:
            if keep(lv):
                rr = round(abs(lv - entry) / R, 2)
                if rr >= cfg.LADDER["min_rr"]:
                    tg.append({"src": lab, "level": round(lv, 2), "rr": rr})
        tg.sort(key=lambda t: t["rr"])                   # nearest rung first (the scale-out order)
        return {"entry": round(entry, 2), "stop": round(stop, 2),
                "targets": tg, "best_rr": tg[-1]["rr"] if tg else 0.0}

    return {"risk_pts": round(R, 1),
            "up": side(base["high"], base["low"], lambda lv: lv > base["high"]),
            "down": side(base["low"], base["high"], lambda lv: lv < base["low"])}


def main():
    root = os.path.join(_SIM, "research")
    S = {p["sid"]: p for p in json.load(open(os.path.join(root, "structure", "volume_profile", "output", "volume_profile.json")))["profiles"]}
    B = {p["sid"]: p for p in json.load(open(os.path.join(root, "structure", "base_profile", "output", "base_profile.json")))["profiles"]}
    H = {p["sid"]: p for p in json.load(open(os.path.join(root, "structure", "htf_profile", "output", "htf_profile.json")))["profiles"]}
    rows = []
    for sid in B:
        if sid not in S:
            continue
        L = ladder({"base": B[sid], "session": S.get(sid), "htf": H.get(sid)})
        if L:
            rows.append(L)
    if not rows:
        print("no ladders (need volume_profile + base_profile + htf_profile outputs)"); return
    up = np.array([r["up"]["best_rr"] for r in rows]); dn = np.array([r["down"]["best_rr"] for r in rows])
    nrungs = np.array([len(r["up"]["targets"]) + len(r["down"]["targets"]) for r in rows])
    print(f"target ladders for {len(rows):,} sessions (base+session+htf; geometry only)")
    print(f"  best R:R  up   median {np.median(up):.2f}  (p90 {np.percentile(up,90):.2f})")
    print(f"  best R:R  down median {np.median(dn):.2f}  (p90 {np.percentile(dn,90):.2f})")
    print(f"  median rungs per session: {int(np.median(nrungs))}")
    runlog.record("target_ladder", {"stop": cfg.LADDER["stop"], "min_rr": cfg.LADDER["min_rr"], "sources": cfg.LADDER["sources"]},
                  {"n": len(rows), "median_best_rr_up": round(float(np.median(up)), 2),
                   "median_best_rr_down": round(float(np.median(dn)), 2), "median_rungs": int(np.median(nrungs))})


if __name__ == "__main__":
    main()
