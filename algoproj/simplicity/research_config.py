"""
research_config — RESEARCH / RUN config (how we're testing right now).

A SUPERSET of the concrete `strategy_config` (re-exported here) PLUS run/experiment knobs
that must NOT live in strategy_config -- one setting, one home (no duplication). See
ARCHITECTURE.md.

  * "run off REAL"     -> import strategy_config   (the strategy + frictions only)
  * "run off RESEARCH" -> import research_config    (all of the above + the run knobs below)

Rule: a value is here only if it's a property of a RUN/experiment, not the strategy.
"""
from strategy_config import *  # noqa: F401,F403  (re-export the concrete config)

# --- run / experiment knobs (research only; never in strategy_config) ---------------
ACTIVE_FILTER = "high"        # filter_variants variant to test / overlay:
#                               all | high | medium | low | high_medium | not_high | extremes
STARTING_BALANCE = 100_000    # $ account size for backtest equity curves (research runs)
BACKTEST_START = None         # e.g. "2018-01-01"; None = full available history  (honored by run_backtest)
BACKTEST_END = None           # e.g. "2024-12-31"; None = latest                  (honored by run_backtest)
MAX_REPLAY_TRADES = 300       # trade-replay export size (research/chart/build_trades.py); 0 = all. CLI arg overrides.
