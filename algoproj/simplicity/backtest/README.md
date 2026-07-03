# backtest — the R measurement engine

Honest simulation of the `target_ladder` trades (NOTES F24/F29). Both-sided coil breakout, OCO; entry =
the resting STOP fills at the **coil edge** (+slippage; gap→open); stop = the other coil edge (**1R**);
take-profit = the first ladder rung ≥ `target_r`; time-stop after `max_hold_bars`; costs = commission both
sides + entry/stop slippage; same-bar stop+target → **stop first** (pessimistic). **No look-ahead.**
UNCONDITIONAL — no `setup_arm` gating; this measures the **base rate** the gates must beat with LIFT.
All rules in `strategy_config` (ENTRY / EXIT / RISK); `$` uses **fixed-fractional risk** (R × pct-of-balance).

**Run:** `python backtest/run_backtest.py` → `output/equity.html` (curve + drawdown + R-distribution +
breakdowns) + `output/trades.csv` + a run-ledger row. **Verdict (v1):** negative base rate (F29) — expected.
**Known limits:** back-adjusted roll gaps may inject a few spurious trades; trades can overlap (per-setup R,
not a single-position account); entry/hold windows are bar-counts.
