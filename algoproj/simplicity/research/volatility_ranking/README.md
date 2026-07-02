# volatility_ranking

**Purpose:** rank the buckets most → least volatile (HV; day = avg range), tag each High/Med/Low,
and show the EARLY-vs-RECENT era comparison that justifies the cutoff (recent HV ~2× the calm decade).
**Run:** `python research/volatility_ranking/rank_volatility.py`
**Outputs:** `output/rank_{year,quarter,month,day}.csv`, `era_comparison.csv`
**Attached to:** VISION 2 · CHECKLIST Phase 1
**Status:** [R] built & verified
