"""
flag_pattern — signal CONTROL PANEL (single source of truth).

This module IS the definition of the strategy/signal. Every script in this strategy
(signal/nq_fractal_match.py, test/, analysis/, experiments/) imports it, so the signal is
defined in exactly one place — change it here and everything follows.

DESIGN INTENT (important): as the strategy grows — approach B (swing poles + variable-length
consolidation), more filters, indicators, multi-scale alignment — ALL of it is controlled from
HERE. The end goal is to assemble the finished strategy so it can be run as a **backtest in the
webui**. The webui expects a strategy module (see `strategies/fanning_mtf.py`) whose `DEFAULT`
dict *is the strategy* plus a `run()`. The planned bridge is a thin `strategies/flag_pattern.py`
adapter that reads THESE controls, turns signals into entries/exits, and backtests via algokit.
Keep this config the single assembly point so that bring-together is easy. (See NOTES.md §13.)

Sections: paths · data · geometry · matching · consolidation(fib) · session · templates ·
future controls (approach B / filters / execution — not wired yet).
"""
import os

import numpy as np

NAME = "flag_pattern"

# ── paths ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.abspath(os.path.join(_HERE, ".."))   # flag_pattern/
FINDINGS_DIR = os.path.join(STRATEGY_DIR, "findings")        # where findings JSON is written/read
# Price data is loaded via algokit.data.load_tf (paths live in algoproj/config.py DATA_DIR).

# ── data ─────────────────────────────────────────────────
TF = "5m"                 # timeframe scanned
HISTORY_START = None      # ISO date string (e.g. "2015-01-01") or None = full history

# ── pattern geometry ─────────────────────────────────────
WINDOW = 9                # SETUP bars matched: pole (0..3) + flag (4..8)
POLE_BARS = 4             # bars 0..3 = pole, 4..8 = flag
FWD_WINDOW = 12           # forward bars measured (MFE/MAE + chart shading)
HORIZONS = [1, 3, 6, 12, 24]   # close-to-close forward horizons (bars)

# ── matching ─────────────────────────────────────────────
MATCH_PCT = 0.1           # distance-percentile threshold (of ALL windows); smaller = tighter
MIN_GAP = WINDOW          # de-overlap matches by this many bars

# ── consolidation quality: fib retracement ───────────────
# Draw a fib 0->1 from the pole's bottom to its top. `retrace` = how far the flag pulled
# back into that range, on a CLOSING basis (0 = no pullback, 1 = full 100% retrace).
# Theory: a STRONG pattern's consolidation holds above the 0.5 fib (retrace <= 0.5); deeper
# than 0.5 means price gave back most of the move and is likelier to fully retrace / roll
# into a larger consolidation. MAX_RETRACE filters to strong ones; None = keep all + record.
MAX_RETRACE = None        # e.g. 0.5 to keep only consolidations that held above the midpoint

# ── time-of-day filter (US Eastern; NQ liquidity follows the US session) ──
# Keep only patterns whose START hour is within [START, END] inclusive. The
# time-of-day analysis showed 8 AM–2 PM ET has the bigger moves + better win rate.
SESSION_ENABLED = True
SESSION_TZ = "America/New_York"
SESSION_START_HOUR = 8    # 8 AM ET
SESSION_END_HOUR = 14     # 2 PM ET (inclusive)

# ── consolidation watch + breakout (the hybrid — NOTES §15) ──
# After a template setup is found, WATCH the flag forward (variable length) until it resolves:
# it must HOLD the FIB_HOLD level of the pole (closing basis) or it FAILS (cancel); it BREAKS OUT
# when price closes beyond the consolidation range in the pole's direction OR prints a
# >= BREAKOUT_ATR_MULT x ATR bar that way. Only breakouts are kept as valid patterns.
ATR_N = 14                # ATR period for the adaptive breakout threshold
CONSOL_MAX_WATCH = 60     # max bars to watch the flag before giving up (timeout)
FIB_HOLD = 0.5            # flag must hold this fib of the pole (closing basis) or it fails
BREAK_BUFFER = 0.0        # extra fraction of pole range beyond FIB_HOLD before a fail counts
BREAKOUT_ATR_MULT = 2.0   # a bar moving >= this x ATR in the pole direction also = a breakout
#
# (archived) swing-based pole detection (REV_ATR_MULT / POLE_ATR_MULT) — see _archive/. Standalone
# swing poles produced 32k noisy fragments (single candles as "poles"); shelved for the hybrid.

# ── templates ────────────────────────────────────────────
# Idealized 12-bar flag as "% from window open" (open, high, low, close).
# We MATCH the first WINDOW bars (pole+flag); the remaining bars are the breakout
# the setup is meant to precede (kept here for reference / future use).
BULL_FLAG = np.array([
    (0.0000,  0.0015, -0.0003,  0.0012), (0.0012,  0.0028,  0.0009,  0.0025),
    (0.0025,  0.0042,  0.0020,  0.0038), (0.0038,  0.0052,  0.0032,  0.0048),
    (0.0048,  0.0051,  0.0038,  0.0041), (0.0041,  0.0045,  0.0034,  0.0037),
    (0.0037,  0.0042,  0.0032,  0.0039), (0.0039,  0.0043,  0.0033,  0.0035),
    (0.0035,  0.0040,  0.0030,  0.0037), (0.0037,  0.0055,  0.0034,  0.0052),
    (0.0052,  0.0068,  0.0048,  0.0065), (0.0065,  0.0078,  0.0060,  0.0075),
])
BEAR_FLAG = -BULL_FLAG[:, [0, 2, 1, 3]]   # mirror: down move, high/low swapped

# pattern name -> (direction, side, SETUP template = first WINDOW bars)
SETUP = {
    "bull_flag": (+1, "long",  BULL_FLAG[:WINDOW]),
    "bear_flag": (-1, "short", BEAR_FLAG[:WINDOW]),
}

# ── FUTURE controls (planned, not wired yet) ─────────────
# Kept here so the structure invites them — everything the strategy grows into is controlled
# from this one file, and this is what the webui backtest adapter will read. See NOTES.md.
#
# Approach B — swing pole + variable-length consolidation (NOTES §7.3, §12):
#   SWING_ATR_MULT, SWING_ATR_N   # pole = a swing >= N x ATR (adaptive) — or %-based
#   BREAK_BUFFER                  # a 0.5-fib break needs a CLOSE beyond by this buffer (wicks don't count)
#   RANGE_MODE                    # consolidation equilibrium: "midpoint" | "vwap" (anchored pole->end)
#   BREAKOUT_MODE                 # how the continuation is triggered (e.g. VWAP-range break in pole dir)
#
# Multi-scale alignment (NOTES §7.2): SCALES + spatial (containment) / temporal (when) confluence.
#
# Execution / cost / sizing — for the webui backtest bridge (cf. strategies/fanning_mtf.py DEFAULT):
#   capital, sizing, risk_pct, max_contracts, commission_per_side, slippage_ticks,
#   point_value, tick, tick_value  (entry = breakout, stop = flag low, target = fib extension, ...)


def session_mask(ts):
    """Boolean mask over an epoch-second array: True where the bar's ET hour is in session."""
    if not SESSION_ENABLED:
        return np.ones(len(ts), bool)
    import pandas as pd
    h = pd.to_datetime(ts, unit="s", utc=True).tz_convert(SESSION_TZ).hour.to_numpy()
    return (h >= SESSION_START_HOUR) & (h <= SESSION_END_HOUR)


def describe():
    s = (f"{SESSION_START_HOUR%12 or 12}{'AM' if SESSION_START_HOUR<12 else 'PM'}"
         f"-{SESSION_END_HOUR%12 or 12}{'AM' if SESSION_END_HOUR<12 else 'PM'} ET") if SESSION_ENABLED else "all hours"
    return f"{NAME}: {TF} | setup {WINDOW} bars | match p{MATCH_PCT} | fwd {FWD_WINDOW} | session {s}"
