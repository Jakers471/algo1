"""
simplicity — MASTER STRATEGY CONFIG (single source of truth).

Reorganised 2026-07-03 by ALTITUDE, not by module. The full pre-shrink version is kept
verbatim at  _archive/strategy_config_full_2026-07-02.py  for reference.

    TIER 1  CONTROL PANEL   -- the handful of DECISIONS you actually tune. Edit these.
    TIER 2  STRUCTURE       -- profile/scale params that feed the backtest (rebuild JSON after a change).
    TIER 3  CALIBRATION     -- sensor internals you tuned once and rarely touch again.
    TIER 4  FACTS           -- market constants + data paths. You basically never touch these.

STATUS TAGS (the thing you kept asking about — what's actually connected):
    [WIRED]   changes a backtest number today.
    [SENSOR]  measured + drawn on the chart, but does NOT gate a trade yet (waits for setup_arm).
    [CHART]   only affects the chart display, not the backtest.
    [FACT]    a definition/constant, not a decision.

Run/testing knobs (ACTIVE_FILTER, STARTING_BALANCE, backtest dates) live in research_config.py —
one setting, one home. Import THIS module everywhere; locking a value here locks it project-wide.
"""
import os

# ##################################################################################
# ##  TIER 1 — CONTROL PANEL   (the decisions you actually make; edit here)        ##
# ##################################################################################

ERA_START_YEAR = 2015            # [WIRED] drop the calm 2005-2014 decade (recent HV ~2x). 2005 = use all.

# --- WHEN to trade ------------------------------------------------------------------
# FILTER_SESSION["allow"] = the session OPENS we trade. We SCAN a session's coil and trade the breakout at
# the NEXT session's open, so setup_arm arms a coil only if its NEXT session is in `allow`
# (asia->london open, london->newyork open). Default = the two liquid opens. [WIRED via setup_arm]
FILTER_SESSION = {"on": True,  "allow": ["newyork"]}                 # OPENS we trade: NY open only (scan london) — the edge (F42)
FILTER_HOUR    = {"on": False, "allow": [9, 10, 11, 12, 13, 14, 15]}  # ET hours-of-day [SENSOR — not wired]
FILTER_DAY_VOL = {"on": False, "regimes": ["high"]}                  # daily vol-regime gate [SENSOR — not wired]

# --- the two GATE THRESHOLDS setup_arm will arm on ----------------------------------
# [SENSOR] surfaced here so you tune selectivity in one place. They flow into SHAPE/ZONE below.
GATE_SHAPE_OK = 50               # min "clean" score (0-100) to consider a coil tradeable
GATE_RR_MIN   = 2.0              # min reward:risk to arm a setup

# --- the TRADE (all [WIRED] — the backtest reads these live) -------------------------
ENTRY = {
    "type": "breakout_both",     # rest breakout-STOP orders on BOTH coil edges; OCO (first fill wins)
    "entry_tf": "5m",
    "entry_window_bars": 78,     # cancel the resting orders if no breakout within this many bars (~1 session)
    "fill": "coil_edge",         # a resting STOP fills at the COIL EDGE (+ slippage; a gap fills at the open)
    "min_coil_pct": 0.05,        # skip noise: coil height must be >= this % of price to be tradeable
}
EXIT = {
    "stop": "coil_edge",         # 1R = the base coil (the other edge)
    # --- TAKE-PROFIT ENGINE (pick ONE; all config-driven, all wired) --------------------
    "target": "trailing",        # [WIRED] "fixed_rr" | "ladder_rung" | "trailing"
    #   fixed_rr    -> a clean, constant TP at 1:target_r (e.g. 1:3), independent of the ladder
    #   ladder_rung -> first target_ladder rung with R:R >= target_r (multi-scale geometry)
    #   trailing    -> no fixed TP; ride a trailing stop (arm at +arm_r, hold gap_r behind best)
    "target_r": 3.0,             # fixed_rr: the fixed R:R (1:3)   ·   ladder_rung: min rung R:R to take
    "trail_arm_r": 1.0,          # trailing: start trailing once the trade reaches +arm_r in profit
    "trail_gap_r": 1.5,          # trailing: keep the stop this many R behind the best price reached
    "max_hold_bars": 156,        # time-stop: exit at market if nothing hit (~2 sessions)
    "same_bar": "stop_first",    # if stop & target hit in one bar, assume STOP (pessimistic / honest)
}
RISK = {
    "sizing": "risk_pct",        # fixed fractional: risk a set % of the account to the stop each trade
    "risk_per_trade_pct": 1.0,   # % risked to the 1R stop -> $ PnL = R x (pct% of start balance)
    "max_contracts": None,
    "max_concurrent": None,
}

# Which config this is (identity). research_config overrides to "research". Runs are saved
# separated by source (reports/<source>/…). strategy = the main/real truth a good strategy graduates to.
CONFIG_SOURCE = "strategy"


# ##################################################################################
# ##  TIER 2 — STRUCTURE   (feeds the backtest via prebuilt JSON; rebuild after edits) ##
# ##################################################################################
# CHANGING THESE requires rebuilding the profile JSONs (run the volume_profile / base_profile /
# htf_profile scripts) before the backtest sees the change — they're baked in at build time.
#
# SCALE TOGGLES are now REAL (2026-07-03): HTF["on"] gates whether htf levels feed the target_ladder in
# the backtest (off -> session-only ladder targets) AND whether the htf card shows. BASE is the core trade
# universe (the coil = entry + 1R), always used by the backtest; its "on" flag gates only the base-card
# DISPLAY. session (PROFILE) is the always-on base dimension. (Only relevant when EXIT.target="ladder_rung".)
PROFILE = {"row_size": 2.0, "va_pct": 0.70}                    # [WIRED] the 5m session profile (base dimension)
BASE = {"on": False, "band_mult": 5.0, "min_bars": 8}          # [WIRED core / display toggle] the coil (LTF)
HTF  = {"on": False, "days": 7, "bins": 70, "min_bars": 200}   # [WIRED when on] trailing composite -> ladder targets
# multi-scale TARGET LADDER (R:R geometry): 1R = the base coil; targets = the larger scales' VA/POC/extremes.
LADDER = {"stop": "base_range", "min_rr": 0.5, "sources": ["session", "htf"]}   # [WIRED]

# The confluence ARM/DISARM engine (setup_arm, v1 built 2026-07-03). Reads the gates above.
# [WIRED when "on"] — flip "on" True to gate the backtest; False = unconditional base rate.
SETUP = {
    "on": True,                           # master switch: apply setup_arm gating (False = base rate). ON: it adds lift (F40)
    "gates": ["session", "shape_ok", "rr_min"],   # v1 confluence stack (ANDed) — the enabled sensors
    "arm_rule": "all",                    # ARM when ALL enabled gates pass (arm-once)
    "invalidate": None,                   # what DISARMS + pulls the resting orders mid-window (v2)
}


# ##################################################################################
# ##  TIER 3 — CALIBRATION   (sensor internals; tuned once, rarely touched)        ##
# ##################################################################################
# These are the guts of the SENSORS. They shape HOW a score is computed, not WHETHER you trade.
# You touched SHAPE during the F16/F17 tuning; leave it unless you're deliberately re-tuning.
SHAPE = {                                            # shape_filter "clean vs foggy" (NOTES F16/F17)
    "weights": {"tight": 0.40, "peak": 0.30, "single": 0.20, "central": 0.10},
    "tight_peak": 40.0, "tight_hi": 85.0,            # peaked tightness curve on va_pct (F16)
    "prom_den": 2.0,                                 # prominence = POC / mean(VA bins) (F17)
    "single_2": 0.5, "single_else": 0.15,            # single-peak score for 2 / 3+ peaks
    "shape_ok": GATE_SHAPE_OK,                       # <- the DECISION lives up in the control panel
}
ZONE = {"rr_min": GATE_RR_MIN,                       # <- the DECISION lives up in the control panel
        "tf_bands": [[0.25, "1m"], [0.60, "5m"], [None, "15m"]]}   # None = inf; height% -> entry TF
FIB = {"edges": [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0001]}   # fib zones ([SENSOR] no dir edge, F11/F13)

# daily vol-regime machinery (only used when FILTER_DAY_VOL["on"])
VOL_METRIC = "avg_range"         # per-day proxy: 'avg_range'=(H-L)/C*100 | 'mean_vol'=|ln(C/prevC)|*100
TRAIL_WINDOW = 20                # trading days; CAUSAL (prior-window mean, no look-ahead)
REGIME_PCTILES = (33.0, 66.0)    # low / medium / high split (percentiles within the era)
MIN_TRAIL_VOL = None             # optional hard floor (%) on trailing vol; None = off


# ##################################################################################
# ##  TIER 4 — FACTS   (market constants + data paths; you never tune these)       ##
# ##################################################################################
# --- execution / costs (NQ e-mini; matches algokit.costs.FuturesCost) ---------------
POINT_VALUE = 20.0               # [FACT] $ per index point (NQ = $20/pt)
TICK = 0.25                      # [FACT] min price increment (points)
TICK_VALUE = 5.0                 # [FACT] $ per tick (0.25 * $20)
COMMISSION_PER_SIDE = 2.25       # [FACT] $ per contract per side
SLIPPAGE_TICKS = 1               # [FACT] ticks of slippage assumed per fill
FILL_RULE = "confirming_close"   # [FACT] honest fills: market orders fill at the confirming bar close

# --- clock + sessions ---------------------------------------------------------------
INSTRUMENT = "NQ"                # Nasdaq-100 e-mini futures (back-adjusted continuous)
CLOCK = "America/New_York"       # everything bucketed / gated on ET
SPAN = (2005, 2024)             # full even 20 calendar years available in the data
SESSIONS = {                     # [FACT] ET session partition (no gaps, covers 24h)
    "asia":    ("18:00", "03:00"),
    "london":  ("03:00", "09:30"),
    "newyork": ("09:30", "16:00"),  # US RTH cash session (~78% of volume)
    "close":   ("16:00", "18:00"),  # post-close + 17:00 maintenance break
}

# --- data paths ---------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")            # simplicity's OWN clean parquets (self-contained)
BUCKETS_OUT = os.path.join(ROOT, "research", "studies", "volume_buckets", "output")
SOURCE_TXT_DIR = r"C:/Users/jakers/Documents/TradeStation 10.0/Data"   # raw TradeStation export (Up+Down vol)
TF_SOURCES = {                   # timeframe -> clean parquet under DATA_DIR/NQ/ (volume = real Up+Down)
    "1d": "NQ/NQ_1d.parquet", "60m": "NQ/NQ_60m.parquet", "15m": "NQ/NQ_15m.parquet",
    "5m": "NQ/NQ_5m.parquet", "1m": "NQ/NQ_1m.parquet",
}
ES_SOURCES = {                   # S&P 500 e-mini -- future cross-instrument breadth / OOS
    "60m": "ES/ES_60m.parquet", "15m": "ES/ES_15m.parquet",
    "5m": "ES/ES_5m.parquet", "1m": "ES/ES_1m.parquet",
}

# --- project map (the replication manifest) -----------------------------------------
PROJECT = {
    "research_buckets": "research/studies/volume_buckets/",
    "research_ranking": "research/studies/volatility_ranking/",
    "research_vol_filter": "research/gates/volatility_filter/",
    "dashboard": "research/studies/volume_buckets/output/volume_dashboard.html",
    "engine": "engine/  (layers: feed/state/structure/gates/setup/execution)",
}
