"""
simplicity — MASTER STRATEGY CONFIG (the single source of truth).

Everything that defines the strategy lives HERE: the file/folder/module map, the
data, the volatility filter/era, the (to-be-built) signal / entry / exit / risk
rules, and the execution costs. Import this ONE module everywhere. Locking a value
here locks it project-wide, so the whole setup is replicable from this file alone.

This is the CONCRETE / REAL config (the strategy + frictions). Run/testing knobs
(ACTIVE_FILTER, starting balance, dates, sweeps) will live in a separate `research_config`
that imports this -- see ARCHITECTURE.md (two configs -> one engine -> outputs stored per config).

Named `strategy_config` (not `config`) on purpose -- `algoproj/config.py` already
exists on the path; this avoids the name clash.

Status legend:  LOCKED = decided & in use.   TBD = slot reserved, strategy not built.
"""
import os

# ==================================================================================
# WORKFLOW + PROJECT MAP  (the replication manifest)                        [LOCKED]
# ==================================================================================
# WORKFLOW: every idea is built & tested in research/ FIRST. Only after the user
# confirms it does it get solidified and PROMOTED into engine/ (the clean, fast,
# live-ready pieces). Nothing enters engine/ unconfirmed. research = discover;
# engine = execute.
#
# simplicity/
#   strategy_config.py       <- THIS FILE (single source of truth)
#   NOTES.md / RANTS.md      <- concept + raw idea log + findings
#   VISION.md                <- the full 15-step target system
#   research/                <- ALL exploration/analysis lives here first (mirrors engine LAYERS)
#       structure/               volume_profile, session_anchors  (market structure)
#       gates/                   volatility_filter, profile_shape_filter, zone_calibration, fib_bias
#       setup/  execution/       future arm/entry/risk/trailing studies
#       studies/                 pure discovery: volume_buckets, volatility_ranking, session_break_stats
#       chart/                   the cross-cutting viewer
#   engine/                  <- confirmed, solidified, live-ready pieces (promotion target; same LAYERS)
PROJECT = {
    "research_buckets": "research/studies/volume_buckets/",
    "research_ranking": "research/studies/volatility_ranking/",
    "research_vol_filter": "research/gates/volatility_filter/",
    "dashboard": "research/studies/volume_buckets/output/volume_dashboard.html",
    "engine": "engine/  (layers: feed/state/structure/gates/setup/execution)",
}

# ==================================================================================
# DATA                                                                      [LOCKED]
# ==================================================================================
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")            # simplicity's OWN clean parquets (self-contained)
BUCKETS_OUT = os.path.join(ROOT, "research", "studies", "volume_buckets", "output")  # shared research artifact
# Raw source for the clean data (TradeStation export; volume = Up + Down). build_data.py reads this.
SOURCE_TXT_DIR = r"C:/Users/jakers/Documents/TradeStation 10.0/Data"
INSTRUMENT = "NQ"                 # Nasdaq-100 e-mini futures (back-adjusted continuous)
TF_SOURCES = {                    # timeframe -> clean parquet under DATA_DIR/NQ/ (volume = real Up+Down)
    "1d": "NQ/NQ_1d.parquet",
    "60m": "NQ/NQ_60m.parquet",
    "15m": "NQ/NQ_15m.parquet",
    "5m": "NQ/NQ_5m.parquet",
    "1m": "NQ/NQ_1m.parquet",
}
ES_SOURCES = {                    # S&P 500 e-mini (DATA_DIR/ES/) -- future cross-instrument breadth / OOS
    "60m": "ES/ES_60m.parquet", "15m": "ES/ES_15m.parquet",
    "5m": "ES/ES_5m.parquet", "1m": "ES/ES_1m.parquet",
}
CLOCK = "America/New_York"        # everything bucketed / gated on ET
SPAN = (2005, 2024)              # full even 20 calendar years available in the data
SESSIONS = {                     # ET session partition (no gaps, covers 24h)
    "asia":    ("18:00", "03:00"),
    "london":  ("03:00", "09:30"),
    "newyork": ("09:30", "16:00"),  # US RTH cash session (~89% of volume)
    "close":   ("16:00", "18:00"),  # post-close + 17:00 maintenance break
}

# ==================================================================================
# ERA + VOLATILITY FILTER  (the gate; vol_filter.py + rank_volatility.py)   [LOCKED]
# ==================================================================================
# The first decade (2005-2014) is ~2x calmer than 2015-2024 (recent HV 15.5% vs 7.7%);
# it skews vol-based selection, so we cut it. Set 2005 to use all 20yr.
ERA_START_YEAR = 2015

# --- WHEN-TO-TRADE FILTERS (session/hour primary, day optional) --------------------
# Each toggles independently. A timestamp is tradeable only if ALL *enabled* filters pass.
# Session & hour are the core (trade inside high-activity windows, not every day equally);
# the daily vol-regime gate is optional. Flip "on" to enable/disable each.
FILTER_SESSION = {"on": True,  "allow": ["newyork"]}                 # ET sessions (keys of SESSIONS)
FILTER_HOUR    = {"on": False, "allow": [9, 10, 11, 12, 13, 14, 15]} # ET hours-of-day
FILTER_DAY_VOL = {"on": False, "regimes": ["high"]}                 # daily vol-regime gate (optional)

# --- daily vol-regime machinery (only used when FILTER_DAY_VOL["on"]) ---------------
# Per-day volatility proxy: 'avg_range'=(High-Low)/Close*100 | 'mean_vol'=|ln(C/prevC)|*100
VOL_METRIC = "avg_range"
TRAIL_WINDOW = 20                # trading days; CAUSAL (prior-window mean, no look-ahead)
REGIME_PCTILES = (33.0, 66.0)    # low / medium / high split (percentiles within the era)
MIN_TRAIL_VOL = None             # optional hard floor (%) on trailing vol; None = off
# NOTE: ACTIVE_FILTER / STARTING_BALANCE / backtest dates live in research_config.py
# (run/testing knobs, not strategy settings). One setting, one home -- no duplication.
# The gate's day-vol regimes are FILTER_DAY_VOL["regimes"] above (there is no TRADEABLE_REGIMES).

# ==================================================================================
# GATE PARAMS  --  the tunable knobs for the profilers + gates.                [TUNING]
# ==================================================================================
# SINGLE SOURCE OF TRUTH for everything we tune. research reads these; a PROMOTED engine
# module reads the SAME dicts -> identical behavior, clean promotion, nothing breaks. The
# chart injects them into the manifest so replay/scoring stay in sync. Every run snapshots
# them to the run ledger (research/runs). Tune HERE, re-run, compare in the ledger.
PROFILE = {"row_size": 2.0, "va_pct": 0.70}          # volume_profile + base_profile binning
BASE = {"band_mult": 5.0, "min_bars": 8}             # base detector (causal contraction scan)
HTF = {"days": 7, "bins": 70, "min_bars": 200}       # trailing-week composite profiler
SHAPE = {                                            # shape_filter "clean vs foggy" (NOTES F16/F17)
    "weights": {"tight": 0.40, "peak": 0.30, "single": 0.20, "central": 0.10},
    "tight_peak": 40.0, "tight_hi": 85.0,            # peaked tightness curve on va_pct (F16)
    "prom_den": 2.0,                                 # (prominence-1)/prom_den; prominence = POC / mean(VA bins) (F17)
    "single_2": 0.5, "single_else": 0.15,            # single-peak score for 2 / 3+ peaks
    "shape_ok": 50,                                  # score >= this = "clean" (threshold -- tune next)
}
ZONE = {"rr_min": 2.0, "tf_bands": [[0.25, "1m"], [0.60, "5m"], [None, "15m"]]}  # None = inf; height% -> entry TF
FIB = {"edges": [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0001]}   # fib zones (edge test: no dir edge, F11/F13)
# multi-scale TARGET LADDER (R:R geometry, NOTES F25): 1R = the base coil; targets = the larger scales'
# VA edges / POC / extremes, ordered into a scale-out ladder per direction. Geometry only (no backtest).
LADDER = {"stop": "base_range", "min_rr": 0.5, "sources": ["session", "htf"]}

# ==================================================================================
# SETUP (arm/disarm) / ENTRY / EXIT  --  LIVE state machine (see ARCHITECTURE.md)  [TBD]
# ==================================================================================
# The strategy is a live, bar-by-bar range-breakout engine: a session-state spine + gates that
# ARM/DISARM a setup on stacked confluence, resting orders before the next open, aggressive trail.
# Not built yet -- slots reserved so the exact rules live here and nowhere else.
SETUP = {                        # the confluence gates that must align to ARM a setup
    "gates": None,               # e.g. shape_ok, fib_bias, zone_size vs range, tightness, time_in/until
    "arm_rule": None,            # how the gates combine to arm
    "invalidate": None,          # what disarms + pulls the resting orders
}
ENTRY = {
    "type": None,                # "breakout_stop" (beyond range) | "edge_fade" | both
    "side": None,                # "long" | "short" | "both" (bias-gated by fib)
    "resting": None,             # place resting orders before the next session opens
    "entry_tf": None,            # smaller TF than the range's TF
    "dca": None,                 # DCA into the range? (decide)
}
EXIT = {
    "stop": None,                # invalidation = range / value-area edge (1R)
    "breakeven": None,           # move to BE after X
    "trail": None,               # aggressive volume-based trailing
    "target": None,              # R multiple / next level, if used
}

# ==================================================================================
# RISK MANAGEMENT                                                              [TBD]
# ==================================================================================
RISK = {
    "sizing": None,              # 'fixed' | 'risk_pct' (see algokit.sizing)
    "risk_per_trade_pct": None,  # % of equity risked to the stop
    "max_contracts": None,
    "max_concurrent": None,
}

# ==================================================================================
# EXECUTION / COSTS  (NQ e-mini; matches algokit.costs.FuturesCost)         [LOCKED]
# ==================================================================================
POINT_VALUE = 20.0               # $ per index point (NQ = $20/pt)
TICK = 0.25                      # min price increment (points)
TICK_VALUE = 5.0                 # $ per tick (0.25 * $20)
COMMISSION_PER_SIDE = 2.25       # $ per contract per side
SLIPPAGE_TICKS = 1               # ticks of slippage assumed per fill
FILL_RULE = "confirming_close"   # honest fills: market orders fill at the confirming bar close (NOTES F1 / renko lesson)
