# simplicity — Build Checklist

Scratch off as we go. Mirrors `VISION.md` (the full 15-step system) in build order.
Companion: `strategy_config.py` (single source of truth), `NOTES.md` / `RANTS.md`.

## Status legend
- `[ ]` not started
- `[~]` in research — work in progress
- `[R]` **built in research**, working & verified
- `[C]` built — **awaiting your confirmation** to solidify & promote to `engine/`
- `[E]` **confirmed & promoted to `engine/`** (live-ready)

**Promotion rule:** nothing moves `research/` → `engine/` without your explicit OK.
**You say when.** Claude never promotes on its own.

---

## Phase 0 — Foundation & workflow
- `[R]` Master config — single source of truth (`strategy_config.py`)
- `[R]` research/ vs engine/ split + research-first workflow
- `[R]` Placeholder scaffold + this checklist
- `[R]` Execution/costs locked (point value, tick, commission, slippage) — `strategy_config` (sizing/entry still TBD)

## Phase 1 — Calendar volatility (WHEN to trade)
- `[R]` Bucket data hierarchically: all → year → quarter → month → day → hour/session, total volume per slice — `research/volume_buckets`
- `[R]` Volatility per bucket: Mean Vol %, HV %, Vol Range %, Avg Daily Range % — `research/volume_buckets`
- `[R]` Volume + volatility dashboard (charts + full tables + Δ vs prev) — `research/volume_buckets/output/volume_dashboard.html`
- `[R]` Era cutoff — drop the low-vol 2005-2014 decade (recent HV ≈ 2× early) — `strategy_config.ERA_START_YEAR`
- `[R]` Volatility ranking — structured most-vs-least volatile per level — `research/volatility_ranking`
- `[C]` **Calendar volatility filter** — causal daily gate (trailing vol → low/med/high regime) — `research/volatility_filter`  ← awaiting your OK to promote
- `[ ]` → on confirm: promote vol_filter to `engine/`

## Phase 2 — Session structure (WHERE)
- `[ ]` Session high/low anchors — London / NY / Asia, single + combinations — `research/session_anchors`
- `[ ]` Session-break conditional stats — e.g. London-high break → NY-high break probability — `research/session_break_stats`

## Phase 3 — Volume Profile & Value Area (the zone)
- `[ ]` Volume Profile between session anchors (not VWAP) — `research/volume_profile`
- `[ ]` POC + Value Area = the consolidation zone
- `[ ]` Measure the zone: duration (bars) + height (%)
- `[ ]` Profile shape / tightness rejection — skip scattered / multi-peaked days — `research/profile_shape_filter`

## Phase 4 — Setup calibration & bias
- `[ ]` Height% / duration → entry timeframe + stop distance / R:R — `research/zone_calibration`
- `[ ]` Fib off session high/low as directional bias (UNTESTED — test standalone) — `research/fib_bias`

## Phase 5 — Entry & exit
- `[ ]` Entry trigger at a specific volume node — `research/entry_trigger`
- `[ ]` Value-Area breakout + volume confirmation = the entry signal
- `[ ]` Aggressive trailing stop management (off prior candle / range) — `research/trailing_stops`

## Cross-cutting
- `[~]` Fresh TradingView lightweight chart — chart + minimal sidebar, overlay everything the code sees; no old flag-strategy baggage — `research/chart`

---

## Promotion log (research → engine)
_Nothing promoted yet._

| piece | confirmed | from → to |
|-------|-----------|-----------|
| —     | —         | —         |
