# research/structure/base_profile

**Purpose:** the PARALLEL profiler (NOTES F6/F18) — profile the detected consolidation BASE, not the whole
session. A causal contraction scan finds the tight window price is in at session end; only those bars get
profiled, so the impulse leg / breakout fall outside it and the range-normalization distortions we keep
patching in `volume_profile` (POC placement, tightness, prominence — F5/F16/F17) can't arise.
**The seam:** it emits the SAME profile-dict shape as `volume_profile`, so `shape_filter` +
`zone_calibration` score it with ZERO changes. The whole-session profiler is untouched — this is a
side-by-side study; promote the better one (or keep both as multi-scale, F15). **You decide when.**

## Files
- `base_profile.py` — `detect(hi,lo)` (contraction scan) + `compute()` → base profiles + run-ledger row.
  Params: `BAND_MULT` (window range ≤ BAND_MULT × median bar-range), `MIN_BARS`.
- `make_compare.py` — side-by-side gallery: whole session vs base, both scored by the same gates →
  `output/compare.html`. Sorted by where isolating the base changes the shape read most.

## Findings (2026-07-02, first build)
Base detected in **78%** of sessions (median 27% of the session's bars). On trend/impulse days the
session reads foggy but the base reads clean — **shape +29 to +34** (e.g. 46→80, 42→72) and **risk 1R
drops ~3–4×** (59.6→15.7pt) because the stop is the tight coil, not the trending range (the LTF-tight-stop
geometry). Already-clean sessions are a wash (−1). PROVISIONAL; validate in-context (F13) before trusting live.
