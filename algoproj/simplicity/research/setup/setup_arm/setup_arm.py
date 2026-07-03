"""
setup_arm — v1 confluence gate (arm-once). The piece that turns the [SENSOR] gates into REAL gates.

Given a base coil (from base_profile), decide whether to ARM it — i.e. whether the backtest should
rest breakout orders on this coil at all. v1 is a simple AND of the built sensors, read from
strategy_config (the control-panel thresholds):

    ARM  <=>  session_filter passes  AND  shape is clean (shape_ok)  AND  geometry clears rr_min

No direction call (that's the OCO fill's job); this only decides WHETHER a coil is worth arming.
"arm-once": evaluated at the session boundary; continuous DISARM (pull orders mid-window) is v2.

Research first (backtest imports this); promote to engine/setup/setup_arm.py once it earns lift.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # simplicity/
for _p in (SIM,
           os.path.join(SIM, "research", "gates", "profile_shape_filter"),
           os.path.join(SIM, "research", "gates", "zone_calibration")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import strategy_config as _cfg          # default config; the caller can pass its own (research vs strategy)
import shape_filter as sf
import zone_calibration as zc


def _next_session(sess, cfg):
    """The session that OPENS after `sess` (chronological cycle asia->london->newyork->close->asia)."""
    order = list(getattr(cfg, "SESSIONS", {}).keys())
    if sess not in order:
        return None
    return order[(order.index(sess) + 1) % len(order)]


def decide(base, session=None, htf=None, cfg=_cfg):
    """Return (armed: bool, reasons: dict). ARM only if EVERY enabled gate passes.

    base    = the coil profile dict (base_profile). We scan a session's coil and trade the breakout at
              the NEXT session's OPEN, so the session gate checks the coil's NEXT session (the open we trade).
    cfg     = the config module in use (research_config or strategy_config) — same thresholds.
    """
    g = {}
    nxt = _next_session(base.get("session"), cfg)
    fs = getattr(cfg, "FILTER_SESSION", {"on": False})
    if fs.get("on"):
        g["session"] = nxt in fs.get("allow", [])  # trade only the OPENS in allow (asia->london, london->newyork)
    sh = sf.score(base) or {}
    g["shape"] = bool(sh.get("shape_ok"))          # shape_score >= SHAPE.shape_ok (GATE_SHAPE_OK)
    zn = zc.calibrate(base) or {}
    g["rr"] = bool(zn.get("rr_ok"))                # rr >= ZONE.rr_min (GATE_RR_MIN)
    armed = all(g.values())
    return armed, {"gates": g, "shape_score": sh.get("shape_score"), "rr": zn.get("rr"), "trade_open": nxt}


DESCRIBE = "setup_arm v1 -- ARM a coil when session AND shape_ok AND rr_min (arm-once)"
