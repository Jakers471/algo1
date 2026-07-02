# chart

**Purpose:** the fresh TradingView lightweight chart to SEE everything the code looks at, overlaid —
multi-timeframe, no old flag-strategy baggage. Rewired to simplicity's own clean data.
**Run:**
- `python research/chart/build_chart_data.py` — cache last ≤2000 bars/TF (NQ+ES) → `data/*.json` + `manifest.json`
- `python research/chart/make_chart.py` — build the self-contained `chart.html`
- open `research/chart/chart.html`
**Features:** NQ/ES + 1m/5m/15m/60m/1d switchers · candles + volume · side menu (clean format) showing
what's LOADED (instrument/tf/bars/range/max-cache) and the full CONFIG on the chart (era, vol metric,
trail, regime pctiles, active filter, tradeable, sessions, costs) · OVERLAY toggle drawing the
`ACTIVE_FILTER` selected volatile periods. Library vendored in `lib/` (works offline). Data inlined so
it opens off disk; loads fast (≤2000 bars/TF).
**Outputs:** `data/<INST>_<tf>.json`, `data/manifest.json`, `chart.html` (generated — gitignored)
**Planned — REPLAY mode:** scrub price back + step forward bar-by-bar; a modular state panel shows the
running numbers (session timing, live hi/lo, running profile POC/VA, zone size/tightness, fib bias,
gate strengths, ARM/DISARM + the validation/invalidation that flipped it). Because the engine runs on
bars-so-far, replay = the live engine driven interactively = the backtest unfolding. See ARCHITECTURE.md.
**Attached to:** VISION (visualization for all steps) · CHECKLIST Cross-cutting + Phase 7
**Status:** [~] core built (multi-TF + config sidebar + anchors/times/profile/fib overlays); replay mode = planned
