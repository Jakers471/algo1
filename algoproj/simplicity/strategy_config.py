"""
simplicity — MASTER STRATEGY CONFIG (the single source of truth).

Everything that defines the strategy lives HERE: the file/folder/module map, the
data, the volatility filter/era, the (to-be-built) signal / entry / exit / risk
rules, and the execution costs. Import this ONE module everywhere. Locking a value
here locks it project-wide, so the whole setup is replicable from this file alone.

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
#   research/                <- ALL exploration/analysis lives here first
#       volume_buckets/          hierarchical volume + volatility profile + dashboard
#       volatility_ranking/      structured most-vs-least-volatile output
#       volatility_filter/       the calendar volatility gate (research until confirmed)
#   engine/                  <- confirmed, solidified, live-ready pieces (promotion target)
PROJECT = {
    "research_buckets": "research/volume_buckets/",
    "research_ranking": "research/volatility_ranking/",
    "research_vol_filter": "research/volatility_filter/",
    "dashboard": "research/volume_buckets/output/volume_dashboard.html",
    "engine": "engine/  (empty until pieces are confirmed & promoted)",
}

# ==================================================================================
# DATA                                                                      [LOCKED]
# ==================================================================================
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")            # simplicity's OWN clean parquets (self-contained)
BUCKETS_OUT = os.path.join(ROOT, "research", "volume_buckets", "output")  # shared research artifact
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

# Per-day volatility proxy the filter classifies on:
#   'avg_range' = (High-Low)/Close*100     |   'mean_vol' = |ln(Close/PrevClose)|*100
VOL_METRIC = "avg_range"
TRAIL_WINDOW = 20                # trading days; CAUSAL (prior-window mean, no look-ahead)
REGIME_PCTILES = (33.0, 66.0)    # low / medium / high split (percentiles within the era)
TRADEABLE_REGIMES = ("high",)    # regimes the strategy may act in
MIN_TRAIL_VOL = None             # optional hard floor (%) on trailing vol; None = off

# ==================================================================================
# SIGNAL / ENTRY / EXIT                                                        [TBD]
# ==================================================================================
# The strategy itself is not built yet. These slots are reserved so that, once the
# signal exists, its exact rules live here and nowhere else.
SIGNAL = None                    # e.g. the setup detector + its parameters
ENTRY = {                        # how a signal becomes a position
    "trigger": None,             # e.g. "breakout_close" / "stop_order_at_level"
    "side": None,                # "long" / "short" / "both"
}
EXIT = {
    "stop": None,                # invalidation level rule (1R)
    "target": None,              # reward rule (R multiple or level)
    "time_stop": None,           # max hold, if any
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
