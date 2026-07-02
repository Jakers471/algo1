# engine/ — confirmed, live-ready strategy pieces

This folder holds only **solidified** components: hard, fast, clean, no research or
plotting, built to drop into a backtest or a live API loop with nothing in the way.

**Runtime model — a LIVE, bar-by-bar state machine** (full spec in `../ARCHITECTURE.md`
"Runtime model"). The engine is event-driven: a **session-state** spine tracks the current +
next session (live hi/lo, time-in/until), and every component recomputes on the session's
**bars-so-far** each bar — so causality is enforced by construction (backtest passes bars ≤ now;
same code runs live). Setups **arm/disarm on stacked confluence** (shape + fib + zone size +
tightness + timing), resting breakout/edge orders before the next open; manage with aggressive
trailing. The edge is confluence + R:R geometry (a range breakout), not prediction.

**Pipeline** (`run_engine.bat` → `run_simplicity.py`, 13 stages):
`data_feed → session_state → vol_filter → session_anchors → volume_profile → shape_filter →
zone_calibration → fib_bias → setup_arm → entry → risk → execution → trailing_stop`.

**Promotion rule (hard):** a piece enters `engine/` ONLY after it is built and proven in
`research/` **and the user explicitly says to move it.** Claude never promotes on its own —
**the user decides when.** research = discover; engine = execute. Every promotion is logged in
`../CHECKLIST.md` (Promotion log).

**Wired so far (4/13):** `data_feed`, `vol_filter`, `session_anchors`, `volume_profile`.
