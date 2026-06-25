# 02 - Data Scientist spec: walk-forward data model (IS vs OOS + WFE)

Role: Data Scientist. Input: `01_quant_walkforward_findings.md`. Output for: Quant Engineer.

Implements the quant's reframe: the primary comparison becomes **In-Sample vs Out-of-Sample**
per window, summarized by **Walk-Forward Efficiency (WFE)**. "Best-on-full" stays only as a
labeled **overfit ceiling**, computed over the **same span as OOS** (fixes the span bug).

---

## A. New per-window data (engine: `wfo.optimize`)

For each window we ALREADY compute the chosen config + its OOS (test) metric block. ADD the
chosen config's **in-sample (train) metric block**, computed the same way on the train slice.

`steps[i]` schema (add `is`, keep the rest):
```
{
  fold, train_from, train_to, test_from, test_to,
  train_bars:[lo,hi], test_bars:[lo,hi], params, train_score,
  test: { total_return, cagr, sharpe, max_drawdown, exposure, round_trips, win_rate, expectancy, profit_factor },   # OOS (existing)
  is:   { ...same keys... }    # NEW: chosen config on its TRAIN window [train_lo, train_hi]
}
```
Implementation note: one extra `validation._segment(bestA rets/trades/in_market over [train_lo,
train_hi], ppy)` per window. Arrays already in hand.

## B. Walk-Forward Efficiency (engine -> `result.wfe`)

Use **annualized return (CAGR)** as the return measure (the standard; TradeStation uses
annualized return).

- Per window: `wfe_i = oos_cagr_i / is_cagr_i` **only if `is_cagr_i > 0`**, else `null` (and tag
  the window "IS not positive").
- Overall: `wfe = oos_cagr_stitched / mean(is_cagr_i over windows)` if `mean(is_cagr_i) > 0` else
  `null`. `oos_cagr_stitched` = `result.oos.cagr` (already computed).
- Always also expose the raw inputs so the user sees them even when WFE is null:
  `is_cagr_mean`, `oos_cagr` (= result.oos.cagr).

`result.wfe` schema:
```
{
  wfe: <float|null>,             # overall; null when IS not positive
  is_cagr_mean: <float>,         # mean annualized IS return across windows
  oos_cagr: <float>,             # annualized stitched OOS return
  per_window: [<float|null>...], # one WFE per window, aligned to steps
  rating: "excellent|good|weak|overfit|na",   # >0.7 | 0.5-0.7 | 0.3-0.5 | <0.3 | null
  note: "<short string>"         # e.g. "IS return not positive - WFE undefined; judge OOS directly"
}
```
Thresholds (from sources): excellent >0.70, good 0.50-0.70, weak 0.30-0.50, overfit <0.30.

## C. Consistency + validity (engine -> `result.consistency`)

```
{
  n_windows, n_pos_oos,                 # # windows with OOS total_return > 0
  oos_sharpe_std,                       # std of per-window OOS sharpe (dispersion; lower=steadier)
  worst_window_dd,                      # min over windows of OOS max_drawdown (most negative)
  concentration_pct,                    # max(window OOS net, 0) / sum(positive window OOS nets)
  concentrated: <bool>                  # true if concentration_pct > 0.50 (TradeStation validity flag)
}
```
Reads: "X of N windows positive", "one window made >50% of the OOS profit" (fragile), etc.

## D. Equity curves (fix the span bug)

- `result.equity.oos`  = stitched OOS daily %-curve over `[oos_lo, oos_hi]` (UNCHANGED).
- `result.equity.full` = best-on-full config's daily %-curve over **`[oos_lo, oos_hi]`** (CHANGE:
  was `[lo, hi]`). Same span as OOS so the two lines are directly comparable.
- `full_best.metrics` = best-on-full config's metric block over **`[oos_lo, oos_hi]`** (CHANGE:
  was `[lo, hi]`). The config is still *chosen* on the full range (that's the overfit); it is
  *measured* over the OOS span for a fair head-to-head.
- Relabel everywhere: "best-on-full" -> **"Overfit ceiling (best single config, chosen with
  hindsight)"**. It is secondary, not the headline.

## E. UI spec (`webui/static/js/pages/wfo.js`, `renderWFO`, multi-tab)

**Overview tab** (the new headline):
- Big **WFE** read-out with rating word and the note (when null). E.g. "WFE 0.58 - good
  (50-70%): meaningful decay but a real edge survives." When null: show `is_cagr_mean` and
  `oos_cagr` directly with the "IS not positive" note.
- **IS vs OOS aggregate table**: rows = total_return, cagr, sharpe, max_drawdown, win_rate,
  exposure, round_trips, profit_factor; cols = **In-sample (avg)** vs **Out-of-sample**.
  (In-sample avg = mean of per-window `is` blocks; OOS = `result.oos`.)
- **Consistency flags** (W.flag): positive-window ratio, OOS Sharpe dispersion, and the
  concentration validity flag (red if concentrated).
- A small, secondary line: the overfit-ceiling net over the OOS span, clearly labeled as
  hindsight (not the headline).

**Equity tab**:
- Primary: the stitched **OOS master curve** (honest). Mark **window boundaries** (vertical
  guides at each test_from) so the master curve is decomposable.
- Secondary, faint/dashed: the **overfit ceiling** curve on the same span, labeled.
- Caption: the gap is what hindsight buys; the honest line is the OOS.

**Windows tab** (replace the current per-fold table):
- Columns: fold | train period | **IS net | IS sharpe** | **OOS net | OOS sharpe** | **WFE** |
  picked params. WFE cell shows "n/a (IS<=0)" when null. Color OOS net pos/neg.

**Stability tab**: unchanged (parameter stability).

## F. Acceptance checks (Engineer must verify)

1. `result.equity.oos.dates[0] == result.equity.full.dates[0]` (curves now share a start date).
2. `steps[i].is` present with all keys for every window.
3. `result.wfe.wfe` is null exactly when `is_cagr_mean <= 0`; otherwise equals
   `oos_cagr / is_cagr_mean` (within float tolerance).
4. `concentration_pct` in [0,1]; `concentrated` true iff > 0.5.
5. UI: Overview shows WFE (or the IS-not-positive note); Windows shows per-window IS vs OOS + WFE;
   Equity shows OOS primary + ceiling secondary with shared start.
6. No "best-on-full" used as a headline anywhere; it is labeled "overfit ceiling".

## G. Deferred (note, not this build)

- **Lock WFO methodology per strategy** (`wfo_methodology.json`) - the meta-overfitting fix.
  Spec it next; it changes the Analyzer's Optimize panel (fixed train/test/objective per
  strategy). Do AFTER this WFE reframe lands.
