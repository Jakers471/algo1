# 03 - Quant Engineer build log: WFE / IS-vs-OOS reframe

Role: Quant Engineer. Input: `02_data_walkforward_spec.md`. Status: DONE, verified.

## What was built

### Engine - `algokit/wfo.py`
- **Per-window in-sample block** (spec A): each `steps[i]` now carries `is` = the chosen config's
  metric block over its TRAIN window `[train_lo, train_hi]` (one extra `_score` call per window).
  (`is` is a reserved word, so set by key after building the dict.)
- **Walk-Forward Efficiency** (spec B): `result.wfe = {wfe, is_cagr_mean, oos_cagr, per_window,
  rating, note}`. Overall WFE = `oos_cagr / mean(is_cagr_i)`, null when `mean(is_cagr) <= 0`
  (with an explanatory note). Per-window WFE null when that window's IS cagr <= 0. Ratings:
  excellent >0.70, good 0.50-0.70, weak 0.30-0.50, overfit <0.30.
- **Consistency / validity** (spec C): `result.consistency = {n_windows, n_pos_oos,
  oos_sharpe_std, worst_window_dd, concentration_pct, concentrated}` (concentrated = one window
  made >50% of OOS profit - TradeStation's validity flag).
- **`result.is_avg`**: mean of the per-window IS blocks (for the IS-vs-OOS aggregate table).
- **Span fix** (spec D): the overfit ceiling (`full_best.metrics`) and its equity curve are now
  measured over the **OOS span `[oos_lo, oos_hi]`** (was `[lo, hi]`). The config is still *chosen*
  on the full range (the hindsight/overfit part) but *measured* on the same span as the
  walk-forward. `equity.oos` and `equity.full` now share a start date.

### Save - `algokit/runs.py`
- `save_wfo` persists `is_avg`, `wfe`, `consistency` into `result.json` (alongside existing
  `oos`, `equity`, `full_best`, `stability`; `steps.json` already carries the new `is` block).

### UI - `webui/static/js/pages/wfo.js`
- `normalizeWFO` passes `wfe`, `consistency`, `is_avg` through from a saved run.
- **Overview tab** is now the headline: WFE KPI + rating, IS-CAGR-avg and OOS-CAGR KPIs, a plain
  "Read:" verdict, the **In-sample (avg) vs Out-of-sample** metrics table, consistency + validity
  flags, and the overfit ceiling demoted to a single reference note.
- **Equity tab**: relabeled "best-on-full" -> "Overfit ceiling (hindsight)"; both curves on the
  same OOS span; caption updated.
- **Windows tab**: rebuilt as per-window **IS net | IS sharpe | OOS net | OOS sharpe | WFE**
  (with a note that per-window WFE is noisy and the aggregate is the reliable number).
- **Stability tab**: unchanged.

## Verification (acceptance checks from spec F)
Ran a live WFO via `POST /api/wfo` and read it back via `/api/run`:
- WFE 0.411 (weak); is_cagr_mean 0.0196; oos_cagr 0.008. [check 3 holds]
- `steps[i].is` present for every window. [check 2]
- consistency: 7/17 windows positive, concentrated=False. [check 4]
- `equity.oos.dates[0] == equity.full.dates[0]` = True (shared start). [check 1]
- Overfit ceiling measured over OOS span = +25.3% vs honest OOS +14.6% (now comparable). [check 6]
- `node --check` passes on wfo.js; engine `py_compile` clean.

## Deviations from spec
- None material. Per-window WFE can be extreme when IS cagr is tiny-but-positive (e.g. 85x); we
  display it raw with the caveat note rather than capping, and steer the user to the aggregate.

## Not in this build (deferred, per spec G)
- Lock WFO methodology per strategy (`wfo_methodology.json`) - the meta-overfitting fix. Next.
- Per-window OOS equity segment markers on the master curve (table covers per-window for now).
