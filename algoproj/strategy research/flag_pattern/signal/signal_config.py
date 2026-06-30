"""
flag_pattern — signal definition (single source of truth).

Everything needed to reproduce this signal lives here:
  • data        — which timeframe / how much history
  • geometry    — the setup window, pole/flag split, forward window, horizons
  • templates   — the idealized OHLC shapes (in "% from window open" space)
  • matching    — distance threshold (no top-N cap) + de-overlap gap
  • session     — the time-of-day filter (US Eastern)

nq_fractal_match.py (chart findings), test/, and analysis/ all import THIS module,
so the signal is defined in exactly one place. Change it here and everything follows.
"""
import numpy as np

NAME = "flag_pattern"

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
