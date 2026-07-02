"""
renko — single source of truth for the Renko line (mirrors flag_pattern/signal_config.py).

Everything about brick construction, the instrument, and costs lives here so the engine,
harness, and any future signal all import ONE config. Keep it clean and complete — this is
the assembly point (same discipline as the sibling strategies).

UNITS: brick size is in INDEX POINTS. NQ = $20/point, tick = 0.25pt = $5/tick. So a 25pt
brick = 100 ticks = $500 of price travel per brick on 1 NQ contract.
"""
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))

# ── data source ──────────────────────────────────────────
# Bricks are built from CLOSES of this timeframe. 1m = finest we have (6.2M bars, 2005→),
# the most faithful price path short of ticks. Close-based off 1m never peeks intrabar →
# zero repaint / zero look-ahead by construction.
SOURCE_TF = "1m"

# ── brick construction (close-based, confirmed-only) ─────
BRICK_SIZE   = 25.0   # points per brick. Sweep candidates: 10 / 25 / 50.
REVERSAL_BRICKS = 2   # boxes price must move AGAINST the trend to flip color.
                      # 2 = traditional trend-following Renko (filters noise, the point of Renko).
                      # 1 = pure Renko (flips on any 1-brick counter-move; noisier).

# ── instrument / cost specs (NQ E-mini; matches algokit.costs.FuturesCost) ─
POINT_VALUE = 20.0    # USD per index point
TICK        = 0.25    # points per tick
TICK_VALUE  = 5.0     # USD per tick (= POINT_VALUE * TICK)

# Derived: how many ticks of price travel one brick is (the native 1R denominator).
def brick_ticks(brick_size=None):
    return (BRICK_SIZE if brick_size is None else brick_size) / TICK

# ── output ───────────────────────────────────────────────
FINDINGS_DIR = os.path.join(_ROOT, "findings")

def bricks_path(brick_size=None, tf=None):
    bs = BRICK_SIZE if brick_size is None else brick_size
    tf = SOURCE_TF if tf is None else tf
    return os.path.join(FINDINGS_DIR, f"bricks_{tf}_{bs:g}pt.npz")

# ── ATR-scaled (adaptive) bricks — the stationarity fix ─────────────────────
# Fixed-point bricks aren't comparable across 20yr (NQ daily ATR20: ~18pt 2005 → ~300pt
# 2025; F3 caveat). Adaptive brick size = ATR_K * daily ATR20, re-set MONTHLY from the
# prior month's last completed day (never look-ahead), rounded to the tick. The frame
# ladder below is geometric (×2) and calibrated so ~0.04/0.10/0.20 match today's
# 10/25/50pt bricks.
ATR_LOOKBACK_D = 20
ATR_KS = [0.04, 0.08, 0.16, 0.32, 0.64]   # the MPF ladder (small → large price frames)

def bricks_path_atr(k, tf=None):
    tf = SOURCE_TF if tf is None else tf
    return os.path.join(FINDINGS_DIR, f"bricks_{tf}_atr{k:g}.npz")
