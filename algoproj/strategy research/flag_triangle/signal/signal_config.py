"""
flag_triangle — signal control panel (single source of truth).

Finds sideways CONSOLIDATIONS — rectangles/horizontal channels, triangles
(symmetric / ascending / descending), sloped channels (flags) and pennants — by
fitting trendlines through swing highs and swing lows and classifying by the two
slopes. Swings come from the same ATR-threshold tracker as structure_detection.
"""
NAME = "flag_triangle"

# ── data ─────────────────────────────────────────────────
TF = "5m"                     # timeframe scanned
HISTORY_START = "2024-01-01"  # keep the findings file light enough to scroll

# ── swing detection ──────────────────────────────────────
ATR_N = 14                    # ATR period for the adaptive grain threshold
SWING_GRAIN = 1.0             # confirm a swing after a retrace >= grain x ATR

# ── consolidation window ─────────────────────────────────
MIN_BARS = 10                 # shortest consolidation (start swing -> end swing)
MAX_BARS = 120                # longest consolidation
MIN_PIVOTS = 4                # need at least this many swings (>=2 highs + >=2 lows)
CONTAIN_MIN = 0.85            # fraction of bars that must sit inside the fitted lines
CONTAIN_TOL = 0.25           # containment tolerance, in ATR, outside the lines

# ── shape classification (slope of each bound over the window, in channel-widths) ─
FLAT = 0.40                   # |line move / avg width| below this = flat bound
CONVERGE = 0.72              # width_end < width_start * CONVERGE  -> converging (triangle)
PENNANT_MAX_BARS = 30         # a converging consolidation this short (after a sharp move) = pennant

# ── continuation context ─────────────────────────────────
PRIOR_BARS = 10               # lookback before the consolidation to gauge the incoming move
POLE_ATR = 3.0                # incoming move >= this x ATR marks a "pole" (flag/pennant context)

# ── forward outcome (measured from the end of the consolidation = breakout bar) ──
HORIZONS = [1, 3, 6, 12, 24]  # forward returns (bars) recorded per match
FWD_WINDOW = 12               # window for MFE / MAE
