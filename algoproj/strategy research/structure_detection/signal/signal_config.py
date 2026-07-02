"""
structure_detection — signal control panel (single source of truth).

Detects market STRUCTURE as a forward progression of swing highs / swing lows: track the highest
high and lowest low; when one is broken, lock in the pullback extreme as a swing and stair-step on.
Run at 3 "grains" (dimensions) on one timeframe — LTF = fine-grained (small swings), HTF = coarse
(big swings). Highs connect to highs, lows connect to lows → the structure lines.

Grain = the minimum retrace (in ATR) needed to confirm a swing: small grain = many small swings
(fine), large grain = few big swings (coarse). All ATR-relative so it adapts to volatility.
"""
NAME = "structure_detection"

# ── data ─────────────────────────────────────────────────
TF = "5m"                    # timeframe scanned
HISTORY_START = "2024-01-01" # ~1 year is enough to scroll and see (data ends 2025-01-10)

# ── swing detection ──────────────────────────────────────
ATR_N = 14                   # ATR period for the adaptive grain threshold

# 3 grains / dimensions on the one timeframe: confirm a swing after a retrace >= grain x ATR.
# LTF = fine (small retrace → many swings) ... HTF = coarse (big retrace → few, major swings).
GRAINS = {
    "LTF": 0.75,   # fine-grained structure
    "MTF": 2.0,    # medium
    "HTF": 5.0,    # coarse / major structure
}
