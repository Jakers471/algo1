"""
engine/shape_filter — profile SHAPE quality gate. Confirmed & promoted 2026-07-03.

Solidified from research/gates/profile_shape_filter. Self-contained + live-ready: a PURE
function on a profile dict (bins + POC + value area), no data / no plotting / no research deps.
All params come from strategy_config.SHAPE (read live, so config edits take effect). Scores how
much a profile looks like a clean single-peak consolidation vs a scattered/trending one (NOTES F16/F17).

    from shape_filter import score
    score(profile)   # -> {shape_score 0-100, shape_ok, va_pct, prominence, n_peaks, poc_pos, ...} or None
"""
import os
import sys

import numpy as np

# --- engine path bootstrap: flat imports work from any engine/ subfolder ---
_E = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_E) != "engine":
    _E = os.path.dirname(_E)
for _d in [_E, os.path.dirname(_E)] + [os.path.join(_E, x) for x in os.listdir(_E) if os.path.isdir(os.path.join(_E, x))]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import strategy_config as cfg

DESCRIBE = "profile shape/tightness gate: clean-vs-foggy 0-100 (shape_ok threshold)"


def score(p):
    """Shape metrics + 0-100 score for one profile dict (with 'bins'). Params from cfg.SHAPE (read live)."""
    S = cfg.SHAPE
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
    peaks = 0                                                             # local-maxima humps clearing half the POC
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

    tp, thi = S["tight_peak"], S["tight_hi"]
    tight = (va_pct / tp) if va_pct <= tp else max(0.0, 1 - (va_pct - tp) / (thi - tp))
    peakc = min(1.0, max(0.0, (prominence - 1) / S["prom_den"]))
    single = 1.0 if peaks <= 1 else (S["single_2"] if peaks == 2 else S["single_else"])
    central = max(0.0, 1 - balance / 0.5)
    w = S["weights"]
    shape = round(100 * (w["tight"] * tight + w["peak"] * peakc + w["single"] * single + w["central"] * central))
    return {"shape_score": shape, "va_pct": round(va_pct, 1), "prominence": round(prominence, 2),
            "n_peaks": int(peaks), "poc_pos": round(poc_pos, 2), "top_share_pct": round(top_share, 1),
            "shape_ok": bool(shape >= S["shape_ok"])}


def check():
    return f"clean-vs-foggy 0-100 | shape_ok >= {cfg.SHAPE['shape_ok']}"
