# research/structure/htf_profile

**Purpose:** the third, largest scale (NOTES F15/F19). Composites the trailing `HTF_DAYS` (~a week) of 5m
volume into ONE profile ending at the session OPEN — causal context you walk INTO the session with (it
does not peek at the session). Gives the "where has the market balanced this week" reference + "at value
vs extended". Kept SEPARATE from volume_profile / base_profile: three independent modules, tuned side by
side. Emits the same profile-dict shape, so shape_filter + zone_calibration score it unchanged (the seam).
**Role in a trade:** HTF = the runway (big target) + regime context; base = the tight stop; session = the
zone between. Direction stays unpredicted (F13).
**Files:** `htf_profile.py` — `compute(since_ts)` (trailing-week composite per session) + ledger row.
Params: `HTF_DAYS` (7), `HTF_BINS` (70 coarse rows), `MIN_HTF_BARS`.
**On the chart:** the top card of the 3-scale module stack (HTF → session → base); static during replay.
