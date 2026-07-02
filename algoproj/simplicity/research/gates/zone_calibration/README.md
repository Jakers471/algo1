# zone_calibration

**Purpose:** turn a session's zone (range hi/lo + value area) into trade GEOMETRY before entry —
stop / 1R, room, R:R, and the entry timeframe.
**Role:** the R:R engine + a gate in the LIVE state machine — runs on the session's bars-so-far,
feeds the arm/disarm confluence (see `../../../ARCHITECTURE.md` "Runtime model").
**Attached to:** VISION 7 · CHECKLIST Phase 5 (gate)
**Status:** [~] research build — provisional geometry, eyeballing against real price

## Files
- `zone_calibration.py` — `calibrate(profile)` → `risk_pts` (1R = value-area edge), `room_pts`
  (range / measured move), `rr = room/risk`, `entry_tf` (tight+short → smaller TF), `rr_ok` (≥ 2).
  `main()` calibrates every session → `output/zone_calibration.csv`.

The gallery that shows this against real candles lives in `../profile_shape_filter/make_examples.py`
(one scorecard covers both shape + zone).

**Provisional:** stop = VA edge, target = full range, entry-TF bands, and the R:R ≥ 2 threshold are
first-pass — to be refined. Not promoted to `engine/gates/` until confirmed.
