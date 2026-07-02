# profile_shape_filter

**Purpose:** turn the clean-vs-foggy profile look into a NUMBER — reject scattered / multi-peak /
trending zones, keep clean single-peak consolidations.
**Role:** gate in the LIVE state machine — runs on the session's bars-so-far, feeds the arm/disarm
confluence (see `../../../ARCHITECTURE.md` "Runtime model").
**Attached to:** VISION 8 · CHECKLIST Phase 5 (gate)
**Status:** [~] research build — provisional metric, eyeballing against real price

## Files
- `shape_filter.py` — `score(profile)` → `shape_score` 0-100 + components (VA tightness, POC
  prominence, n_peaks, POC position, top-bin share). `main()` scores every session → `output/shape_scores.csv`.
- `make_examples.py` — the **visual study**: picks a spread of real NQ sessions (clean / foggy /
  big-R:R / poor-R:R) and renders each as its 5m candles + volume profile + a **scorecard**
  (shape metrics *and* zone-calibration geometry) → `output/examples.html`. This is how we match
  number-vs-picture before trusting the metric.

**Provisional:** metrics, weights, and the ≥50 `shape_ok` threshold are first-pass — built to be
refined against the gallery. Not promoted to `engine/gates/` until confirmed. Pairs with `../zone_calibration`.
