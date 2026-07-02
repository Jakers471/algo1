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
it opens off disk; loads fast (≤6000 bars/TF).
**Per-session MODULE cards** (Indicators → `modules` on; NQ 1m/5m): click any session's candles and a
floating, draggable, closeable card pops up — the session's own crisp mini volume-profile (candles +
two-tone bars + POC/VA, examples-quality because it's zoomed to that session), its **timing** (open /
close / duration / next session + gap, ET), and its **shape + R:R scores**. This is the on-demand way
to see the profile crisp on the chart AND how each session hands to the next; it's also the seed of the
planned replay state panel. (`#demo` in the URL auto-opens the latest card for a quick look.)
**Outputs:** `data/<INST>_<tf>.json`, `data/manifest.json`, `chart.html` (generated — gitignored)
**Planned — REPLAY mode:** scrub price back + step forward bar-by-bar; a modular state panel shows the
running numbers (session timing, live hi/lo, running profile POC/VA, zone size/tightness, fib bias,
gate strengths, ARM/DISARM + the validation/invalidation that flipped it). Because the engine runs on
bars-so-far, replay = the live engine driven interactively = the backtest unfolding. See ARCHITECTURE.md.
**Attached to:** VISION (visualization for all steps) · CHECKLIST Cross-cutting + Phase 7
**Status:** [~] core built (multi-TF + config sidebar + anchors/times/profile/fib overlays + per-session module cards); replay mode = planned
