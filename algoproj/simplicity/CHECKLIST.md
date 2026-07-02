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
- `[E]` **engine/data_feed.py PROMOTED** — loads all NQ+ES clean parquets (run_engine shows WIRED 1/10)

## Phase 1 — Calendar volatility (WHEN to trade)
- `[R]` Bucket data hierarchically: all → year → quarter → month → day → hour/session, total volume per slice — `research/volume_buckets`
- `[R]` Volatility per bucket: Mean Vol %, HV %, Vol Range %, Avg Daily Range % — `research/volume_buckets`
- `[R]` Volume + volatility dashboard (charts + full tables + Δ vs prev) — `research/volume_buckets/output/volume_dashboard.html`
- `[R]` Era cutoff — drop the low-vol 2005-2014 decade (recent HV ≈ 2× early) — `strategy_config.ERA_START_YEAR`
- `[R]` Volatility ranking — structured most-vs-least volatile per level — `research/volatility_ranking`
- `[E]` **When-to-trade filter PROMOTED** — intraday gate (session/hour + optional daily vol-regime, toggleable `FILTER_SESSION/HOUR/DAY_VOL`) → `engine/vol_filter.py` (WIRED 2/10); research copy kept for testing
- `[R]` Filter variants bank (high / low / medium / not_high / extremes / all) for A/B testing — `research/volatility_filter/filter_variants.py`
- `[R]` Random/unconditional baseline in the test (`evaluate()` compares each variant vs a Monte-Carlo same-size random null)
- `[ ]` **Hypothesis test** — "strategy better in high-vol periods": run `evaluate()` with strategy per-day R; H holds only if `high` beats the **random baseline** (top tail) AND `low` (blocked on the strategy existing)

## Phase 2 — Session structure (WHERE)
- `[R]` Session high/low/open anchors — Asia/London/NY/Close, color-coded — `research/session_anchors` (+ chart overlay in a minimizable Indicators panel, toggleable levels/sessions)
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

## Phase 6 — Measurement & backtest (FUTURE — blocked on entry/exit + risk mgmt)
- `[ ]` Trades on the chart — BUY/SELL markers showing exactly where trades were taken
- `[ ]` Equity curve (+ drawdown)
- `[ ]` Walk-forward testing with detailed WF labeling (train/test folds, anchored)
- **Prior art (don't reinvent):** you already built all of this in `algoproj/webui` (Flask+PyWebView+ECharts:
  Analyzer/Runs/Strategies/WFO; `/api/run/chart` = candles+BUY/SELL markers, `/api/run/equity` = equity+DD,
  `/api/wfo` = walk-forward) + the original Streamlit `algoproj/_archive/app`; engine =
  `algokit/{wfo,optimize,validation,significance,runs}`. simplicity's `backtest/` reuses this. See ARCHITECTURE.md.

## Cross-cutting
- `[~]` **Fresh TradingView lightweight chart** (`research/chart`) — rewired to simplicity data; multi-timeframe (NQ+ES); OHLC cached to JSON, load max ~2000 bars/TF for speed; side menu showing which instrument/TF/config is loaded (clean format); overlay the filter-selected periods. No old flag-strategy baggage.
- `[R]` Config filter selector `ACTIVE_FILTER` (pick which variant tv/backtest uses) — `strategy_config`
- `[R]` Config split DONE — `research_config.py` (run/testing: `ACTIVE_FILTER`, `STARTING_BALANCE`, dates) re-exports `strategy_config`; removed `ACTIVE_FILTER` + dead `TRADEABLE_REGIMES` from `strategy_config` (no duplication)
- `[R]` Chart config selector (real | research) — top-bar toggle switches vol-day overlay + sidebar to that config
- `[ ]` `backtest/` folder (separate top-level, FUTURE): run engine with a chosen config → equity-curve PNGs stored per-config (`output/research/` vs `output/real/`). Blocked: no risk mgmt / returns yet — visualization only for now.

---

## Promotion log (research → engine)

| piece | confirmed | from → to |
|-------|-----------|-----------|
| data_feed | 2026-07-01 | data build (research) → `engine/data_feed.py` (loads all NQ+ES parquets; WIRED 1/10) |
| vol_filter | 2026-07-01 | `research/volatility_filter` → `engine/vol_filter.py` (session/hour + optional day-vol gate; WIRED 2/10) |
