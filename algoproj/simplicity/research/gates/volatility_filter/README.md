# volatility_filter

**Purpose:** the WHEN-TO-TRADE gate + the bank of variants that TEST the hypothesis
*"the strategy performs better in high-volatility / high-activity periods."*
The gate filters intraday bars by **session and/or hour** (core) + an **optional daily vol-regime**,
each toggleable in `strategy_config` (`FILTER_SESSION` / `FILTER_HOUR` / `FILTER_DAY_VOL`, ANDed).
**Run:**
- `python research/gates/volatility_filter/vol_filter.py` — show enabled filters + % of NQ 5m bars tradeable (`mask(index)` / `passes(ts)`)
- `python research/gates/volatility_filter/filter_variants.py` — compare variants (all/high/medium/low/…)
- `filter_variants.evaluate(per-day R)` — the real test: each variant vs LOW **and vs a RANDOM
  same-size baseline**. H holds only if `high` beats random (top tail), not merely `low`.
**Outputs:** `output/filter_variants.csv`
**Runtime:** promoted to `engine/vol_filter.py`; the WHEN gate, evaluated live per bar — see
ARCHITECTURE.md "Runtime model".
**Attached to:** VISION 2 · CHECKLIST Phase 1
**Status:** [C] `vol_filter` awaiting promotion to engine/ · [R] variants + baseline built (test blocked on the strategy)
