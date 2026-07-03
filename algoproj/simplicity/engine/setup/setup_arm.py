"""
engine/setup_arm — the confluence ARM/DISARM gate (v1, arm-once). Confirmed & promoted 2026-07-03.

Solidified from research/setup/setup_arm. Self-contained + live-ready: ANDs the promoted engine
SENSORS to decide whether to ARM a coil (place resting orders). Turns the sensors into a real gate.

    ARM  <=>  session_filter passes  AND  shape_ok  AND  rr_ok

No direction call (the OCO fill decides). Thresholds from strategy_config (control panel). v2 =
continuous DISARM + multi-scale confluence.

    from setup_arm import decide
    decide(coil_profile)   # -> (armed: bool, reasons: dict)
"""
import os
import sys

# --- engine path bootstrap (also puts engine/gates on the path for the sibling sensors) ---
_E = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_E) != "engine":
    _E = os.path.dirname(_E)
for _d in [_E, os.path.dirname(_E)] + [os.path.join(_E, x) for x in os.listdir(_E) if os.path.isdir(os.path.join(_E, x))]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import strategy_config as cfg
import shape_filter as sf          # engine/gates/shape_filter (promoted)
import zone_calibration as zc      # engine/gates/zone_calibration (promoted)

DESCRIBE = "confluence ARM gate: session AND shape_ok AND rr_min (arm-once)"


def _next_session(sess, cfg):
    """The session that OPENS after `sess` (cycle asia->london->newyork->close->asia)."""
    order = list(getattr(cfg, "SESSIONS", {}).keys())
    return order[(order.index(sess) + 1) % len(order)] if sess in order else None


def decide(base, session=None, htf=None, cfg=cfg):
    """Return (armed, reasons). ARM only if EVERY enabled gate passes. base = the coil profile dict.
    We scan a session and trade the NEXT session's OPEN -> the session gate checks the coil's next session."""
    g = {}
    nxt = _next_session(base.get("session"), cfg)
    fs = getattr(cfg, "FILTER_SESSION", {"on": False})
    if fs.get("on"):
        g["session"] = nxt in fs.get("allow", [])
    sh = sf.score(base) or {}
    g["shape"] = bool(sh.get("shape_ok"))
    zn = zc.calibrate(base) or {}
    g["rr"] = bool(zn.get("rr_ok"))
    return all(g.values()), {"gates": g, "shape_score": sh.get("shape_score"), "rr": zn.get("rr"), "trade_open": nxt}


def check():
    return "ARM when " + " AND ".join(cfg.SETUP.get("gates", [])) + (" [on]" if cfg.SETUP.get("on") else " [off]")
