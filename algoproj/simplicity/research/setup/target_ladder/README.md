# research/setup/target_ladder

**Purpose:** the multi-scale R:R GEOMETRY engine (NOTES F25/F26). Geometry only — **no backtest**. From the
nested scales (base < session < HTF) it derives the concrete trade geometry: **1R (stop) = the base coil**
(the tight stop from the smallest scale); **targets = every larger scale's VA edges / POC / extremes** in
the breakout direction, ordered nearest-first into a scale-out **LADDER** with **R:R per rung**; computed
for BOTH directions (direction stays unpredicted, F13). The multi-scale generalization of
`zone_calibration`'s single R:R. This is the trade DEFINITION (entry/stop/take-profit geometry) that
`setup_arm` will arm and a backtest will later measure (realized R).
**Params:** `strategy_config.LADDER` (stop rule, `min_rr`, which scales supply targets).
**Files:** `target_ladder.py` — `ladder({base,session,htf})` + study `main()` + ledger row.
**On the chart:** the `TARGET LADDER` card at the bottom of the module stack (1R + up/down rungs w/ R:R).
