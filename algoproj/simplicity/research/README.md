# research/ — discover & test (mirrors the engine LAYERS)

Every idea is built and proven here first. These folders mirror `engine/`'s job-layers, so
**promotion is a 1:1 move within the same layer** (`research/gates/X/` → `engine/gates/X.py`).
See `../ARCHITECTURE.md` "Promotion path (research → engine)".

- **structure/** — market STRUCTURE the strategy computes: `volume_profile`, `session_anchors`
- **gates/** — confluence GATES: `volatility_filter` (WHEN), `profile_shape_filter`, `zone_calibration`, `fib_bias`
- **setup/** — the ARM/DISARM engine studies (future: `setup_arm`)
- **execution/** — entry / risk / fills / trailing studies: `entry_trigger`, `trailing_stops`
- **studies/** — pure DISCOVERY / analytics that may never promote: `volume_buckets`, `volatility_ranking`,
  `session_break_stats` (+ future `session_archive`)
- **chart/** — the cross-cutting viewer (multi-TF chart, per-session module cards, replay)

Nothing here is live-ready until you confirm it and it's promoted to `engine/`. research = discover; engine = execute.
