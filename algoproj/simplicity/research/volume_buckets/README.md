# volume_buckets

**Purpose:** bucket 20yr NQ top-down (all → year → quarter → month → day → hour/session) and
record TOTAL VOLUME + four volatility stats (Mean Vol / HV / Vol Range / Avg Daily Range) per slice.
**Run:**
- `python research/volume_buckets/build_buckets.py` — builds the bucket files
- `python research/volume_buckets/make_dashboard.py` — builds the dashboard from them
**Outputs:** `output/bucket_{all,year,quarter,month,day,hour,session}.*`, `profile_*.csv`,
`volume_dashboard.html` (charts + full tables + Δ vs prev)
**Attached to:** VISION 1-2 · CHECKLIST Phase 1
**Status:** [R] built & verified
