"""
engine/target_ladder — multi-scale R:R GEOMETRY. Confirmed & promoted 2026-07-03.

Solidified from research/setup/target_ladder. Self-contained + live-ready: a PURE function on the
nested scale dicts. 1R = the base coil; targets = the larger scales' VA edges / POC / extremes in the
breakout direction, ordered into a scale-out ladder with R:R per rung, both directions. Geometry only.
Sources + min_rr from strategy_config.LADDER (read live).

    from target_ladder import ladder
    ladder({"base": base_prof, "session": session_prof, "htf": htf_prof})   # -> {risk_pts, up, down} or None
"""
import os
import sys

# --- engine path bootstrap ---
_E = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_E) != "engine":
    _E = os.path.dirname(_E)
for _d in [_E, os.path.dirname(_E)] + [os.path.join(_E, x) for x in os.listdir(_E) if os.path.isdir(os.path.join(_E, x))]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import strategy_config as cfg

DESCRIBE = "multi-scale target ladder: 1R = base coil, targets = larger scales' VA/POC/extremes"
LEVELS = [("VAH", "vah"), ("VAL", "val"), ("POC", "poc"), ("high", "high"), ("low", "low")]


def ladder(scales):
    """scales = {'base':profile, 'session':profile, 'htf':profile}. Returns the trade geometry, or None.

    A disabled scale should be passed as None by the caller (HTF toggle etc.) -> it simply drops out.
    """
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


def check():
    return f"sources={cfg.LADDER['sources']} | 1R=base coil | min_rr {cfg.LADDER['min_rr']}"
