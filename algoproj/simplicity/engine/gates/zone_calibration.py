"""
engine/zone_calibration — zone -> TRADE GEOMETRY (R:R) gate. Confirmed & promoted 2026-07-03.

Solidified from research/gates/zone_calibration. Self-contained + live-ready: a PURE function on a
profile dict. From the zone (range hi/lo + value area) it derives risk (VA edge = 1R), room (range),
R:R, and the entry timeframe. Params from strategy_config.ZONE (read live).

    from zone_calibration import calibrate
    calibrate(profile)   # -> {risk_pts, room_pts, rr, rr_ok, entry_tf, height_pct, bars} or None
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

DESCRIBE = "zone -> risk/room/R:R + entry timeframe (rr_min gate)"


def _entry_tf(height_pct):
    for b in cfg.ZONE["tf_bands"]:
        hi = float("inf") if b[0] is None else b[0]
        if height_pct < hi:
            return b[1]
    return "15m"


def calibrate(p):
    """Zone geometry for one profile dict. Params from cfg.ZONE (read live)."""
    rng = p["high"] - p["low"]
    va = p["vah"] - p["val"]
    if rng <= 0 or va <= 0:
        return None
    rr = round(rng / va, 2)                     # room (range) / risk (VA edge)
    return {"height_pct": round(p["height_pct"], 3), "bars": int(p["bars"]),
            "risk_pts": round(va, 1), "room_pts": round(rng, 1), "rr": rr,
            "entry_tf": _entry_tf(p["height_pct"]), "rr_ok": bool(rr >= cfg.ZONE["rr_min"])}


def check():
    return f"risk=VA edge, room=range | rr_min >= {cfg.ZONE['rr_min']}"
