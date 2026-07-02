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
# Frozen (fixed-length) pole + flag. The drawn template (12-bar hand shape, 4-bar pole /
# 5-bar flag) is interpolated to THESE lengths, pole-segment and flag-segment separately, so
# the frozen SHAPE is kept but rescaled to whatever pole:flag bar counts we set here.
WINDOW = 40               # SETUP bars matched: pole (0..9) + flag (10..39)
POLE_BARS = 10            # bars 0..9 = pole, 10..39 = flag  (10 pole / 30 flag)
FWD_WINDOW = 12           # forward bars measured (MFE/MAE + chart shading)
HORIZONS = [1, 3, 6, 12, 24]   # close-to-close forward horizons (bars)

# ── matching ─────────────────────────────────────────────
MATCH_PCT = 0.5           # distance-percentile threshold (of ALL windows); smaller = tighter
                          # (0.1 -> 0.5 on 2026-06-30 §19 step 1: aggregate overlay stays a clean flag
                          #  through 1%, so widen the net + let fib-hold/breakout filters gate quality)
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
SESSION_START_HOUR = 8    # 8:00 AM ET (inclusive)
SESSION_END_HOUR = 14     # 2:00 PM ET HARD STOP (minute-precise; nothing after 2:00 PM kept)

# ── consolidation watch + breakout (the hybrid — NOTES §15) ──
# After a template setup is found, WATCH the flag forward (variable length) until it resolves:
# it must HOLD the FIB_HOLD level of the pole (closing basis) or it FAILS (cancel); it BREAKS OUT
# when price closes beyond the consolidation range in the pole's direction OR prints a
# >= BREAKOUT_ATR_MULT x ATR bar that way. Only breakouts are kept as valid patterns.
ATR_N = 14                # ATR period for the adaptive breakout threshold
CONSOL_MAX_WATCH = 60     # max bars to watch the flag before giving up (timeout)
CONSOL_MIN_BARS = 20      # drop breakouts whose consolidation (flag) is shorter than this many bars
FIB_HOLD = 0.5            # flag must hold this fib of the pole (closing basis) or it fails
BREAK_BUFFER = 0.0        # extra fraction of pole range beyond FIB_HOLD before a fail counts
BREAKOUT_ATR_MULT = 2.0   # a bar moving >= this x ATR in the pole direction also = a breakout
# Breakout redefined around the consolidation's EQUILIBRIUM (NOTES §12): an anchored VWAP from the
# pole end = the volume-weighted center the flag balances on (we have full volume). The breakout is a
# CLOSE beyond a band = VWAP +/- BREAKOUT_VWAP_K x ATR in the pole direction (a real deviation from
# fair value), instead of merely poking the consolidation's extreme bar.
BREAKOUT_VWAP_K = 1.0     # band half-width in ATRs around the anchored VWAP

# ── volume: activity WINDOW + pattern SIGNATURE (experiments/dynamic_pole.py) ──
# Volume is fully populated, so we can use it two ways.
# (1) ACTIVITY WINDOW — define WHEN to hunt by volume increase instead of / with the clock. A bar is
#     "active" when volume >= VOL_ACTIVE_MULT x its rolling-mean baseline (a surge whenever it happens).
#     NQ volume runs well past the 2 PM clock stop (2-4 PM ET is ~1/3 of daily volume), so a volume
#     window is LONGER + shifted later than 8-2.
ACTIVITY_MODE = "clock"        # "clock" (8-2 ET) | "volume" (surge only) | "clock+volume" (both)
VOL_BASELINE_N = 100           # bars for the rolling-mean volume baseline
VOL_ACTIVE_MULT = 1.2          # bar volume >= this x baseline = "active"
# (2) PATTERN SIGNATURE — confirm the pattern with volume (classic flag: pole expands, flag contracts,
#     breakout surges). Master toggle + per-leg toggles; each rejects patterns that fail it.
VOL_SIG_ENABLED = False
VOL_POLE_RISING = True         # pole avg volume >= baseline (a real, participated thrust)
VOL_FLAG_QUIET = True          # flag avg volume < pole avg volume (participation dries up)
VOL_BREAKOUT_SURGE = True      # breakout bar volume >= VOL_BREAKOUT_MULT x baseline (conviction)
VOL_BREAKOUT_MULT = 1.5

# ── pole SEED source (experiments/dynamic_pole.py) ──
# How poles are FOUND before the dynamic trace refines them:
#   "template" — the frozen shape scan (finds a pole+flag gestalt, grabs its pole, then traces).
#   "spike"    — seed a pole wherever a candle's directional BODY >= SPIKE_ATR_MULT x ATR. ATR is
#                adaptive, so a spike is a spike at any volatility (no fixed %). The trace +
#                flag-watch + min-bar filters do the quality work (the §14 swing-dump failed only
#                because it had no downstream machine; here it does). Caveat: ATR = magnitude not
#                direction, so a lone fat candle / chop bar can seed — rely on downstream to reject.
#   "bank"     — a BANK of parametric flag variations (many slightly-tweaked shapes); each window
#                keeps its BEST (min) distance across the bank, so a flag that matches ANY variation
#                seeds. Widens coverage vs one perfect template. Size/length are NOT varied
#                (magnitude-free norm + dynamic trace handle those) — only SHAPE.
SEED_MODE = "template"     # ATR-spike seeding tested worse (64% fail vs 20%); template pre-qualifies
SPIKE_ATR_MULT = 2.0       # a candle body this many x ATR (in its direction) seeds a pole
# template-bank sweep (SEED_MODE="bank"): each combo = one variation (WINDOW bars, pole+flag).
BANK_POLE_BARS = [8, 10, 14]        # pole length -> pole:flag ratio (flag = WINDOW - pole)
BANK_POLE_CURVE = [0.8, 1.2]        # pole shape: <1 concave (decel), >1 convex (accel)
BANK_FLAG_SLOPE = [-0.4, -0.15, 0.1]  # flag drift as fraction of pole height: down / mild-down / up

# ── dynamic pole trace (experiments/dynamic_pole.py) ──
# The scan anchor is just a SEED inside the move; grow the pole from it candle-by-candle to its
# TRUE extremes instead of the frozen POLE_BARS. FORWARD finds the pole's far end (bottom if
# bearish / top if bullish); BACKWARD finds its origin (the swing high/low it began from).
# A step continues while the adjacent candle does NOT close past the current candle's high/low
# (against the pole) by POLE_TRACE_BUFFER_ATR x ATR — wicks / marginal closes don't count.
POLE_TRACE_BUFFER_ATR = 0.25       # counter-close must clear the adjacent candle's high/low by this x ATR
# cool-down patience (fraction-of-pole): end the FORWARD pole after it stalls (makes no new extreme)
# for more than this fraction of its OWN current length. Self-scaling — a 10-bar pole may drift ~3
# bars trying to resume; a 30-bar pole ~10. 1 = max patience (wait a full pole-length); 0/None = off
# (pure reversal rule = ends only on a counter-close past the prior high/low). Backward = reversal-only.
POLE_TRACE_STALL_FRAC = 1 / 3
POLE_TRACE_MAX_BACK = 20           # cap bars extended BACKWARD (don't swallow the previous move)
POLE_TRACE_MAX_FWD = 60            # cap bars extended FORWARD (safety)
POLE_TRACE_MIN_BARS = 5            # drop poles of 4 candles or fewer (keep >= 5-bar poles)

# ── regime alignment (higher-timeframe 32-MA fan; NOTES §16) ──
# Tag each breakout with the HTF fan regime at that moment; a breakout is ALIGNED when the HTF
# agrees with the pole direction (bull-score for longs / bear-score for shorts >= REGIME_SPLIT).
# The analysis showed aligned breakouts ~3x better return/drawdown than counter-trend.
REGIME_ENABLED = True
REGIME_HTF = "60m"        # timeframe for the fan regime (60m recommended; 15m / 1d also valid)
REGIME_FAN = (5, 200, 0.05)   # fan (lo, hi, eps) for regime_score at REGIME_HTF
REGIME_SPLIT = 50         # HTF agree-score >= this = aligned with the pole direction
REQUIRE_ALIGNED = False   # True = keep only aligned breakouts; False = keep all + tag them
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

# The hand-drawn template's OWN proportions (12 bars = 4 pole + 5 flag + 3 breakout).
_DRAWN_POLE = 4           # drawn pole length within the template
_DRAWN_SETUP = 9          # drawn setup length (pole+flag) within the template


def _interp(tmpl, length):
    """Stretch a (W,4) template to (length,4) by interpolating each column (same shape, more bars)."""
    sx = np.linspace(0.0, 1.0, tmpl.shape[0])
    dx = np.linspace(0.0, 1.0, length)
    return np.stack([np.interp(dx, sx, tmpl[:, c]) for c in range(tmpl.shape[1])], axis=1)


def _build_setup(tmpl):
    """Frozen shape at the CONFIGURED lengths: interpolate the drawn POLE segment to POLE_BARS
    and the drawn FLAG segment to (WINDOW-POLE_BARS) separately, then join. Keeps each segment's
    drawn shape while setting the pole:flag bar counts from the config (e.g. 10:30)."""
    pole = _interp(tmpl[:_DRAWN_POLE], POLE_BARS)
    flag = _interp(tmpl[_DRAWN_POLE:_DRAWN_SETUP], WINDOW - POLE_BARS)
    return np.vstack([pole, flag])


# pattern name -> (direction, side, SETUP template = WINDOW bars at POLE_BARS:flag lengths)
SETUP = {
    "bull_flag": (+1, "long",  _build_setup(BULL_FLAG)),
    "bear_flag": (-1, "short", _build_setup(BEAR_FLAG)),
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
    """Boolean mask over an epoch-second array: True where the bar's ET time is in session.
    Minute-precise: keeps START_HOUR:00 through END_HOUR:00 inclusive (a hard stop), so a
    2:55 PM bar is excluded when END_HOUR=14 — only up to exactly 2:00 PM ET passes."""
    if not SESSION_ENABLED:
        return np.ones(len(ts), bool)
    import pandas as pd
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(SESSION_TZ)
    tod = et.hour.to_numpy() * 60 + et.minute.to_numpy()
    return (tod >= SESSION_START_HOUR * 60) & (tod <= SESSION_END_HOUR * 60)


def describe():
    s = (f"{SESSION_START_HOUR%12 or 12}{'AM' if SESSION_START_HOUR<12 else 'PM'}"
         f"-{SESSION_END_HOUR%12 or 12}{'AM' if SESSION_END_HOUR<12 else 'PM'} ET") if SESSION_ENABLED else "all hours"
    return f"{NAME}: {TF} | setup {WINDOW} bars | match p{MATCH_PCT} | fwd {FWD_WINDOW} | session {s}"
