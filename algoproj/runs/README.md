# Run registry

Every backtest and walk-forward optimization the Analyzer runs is saved here, numbered and
labeled. The layout mirrors the app's separation of concerns: a run has an **identity**, a
**Performance** story (what it did), and a **Robustness** story (whether you can trust it).

## Structure

```
runs/
  RUNS.md          human registry: one row per run, all strategies + types
  index.json       machine registry (drives the UI's Runs/Strategies pages)
  <strategy>/
    backtest/
      run_NNNN/     a single-config backtest    (numbered per strategy)
    walk_forward/
      wfo_NNNN/     a walk-forward optimization (rolling or anchored)
```

Numbering is per strategy + type, so each strategy has its own `run_0001..` and `wfo_0001..`
sequences. Archived registries live alongside in `../runs_archive/<timestamp>/` (gitignored).

## What each run stores, by concern

A `backtest/run_NNNN/` folder:

| File | Concern | Used by |
| --- | --- | --- |
| `meta.json` | **Identity** - name, backtest_type, date/timestamp, parent + config DIFF, `config_labeled` (signal vs account/execution), headline | Runs/Strategies tables, Report header |
| `config.json` | **Identity** - the exact reproducible config | param-diff compare |
| `metrics.json` | **Performance** - full extended summary | Report -> Performance -> Summary |
| `trades.parquet` | **Performance** - trade-by-trade log (enriched) | Report -> Performance -> Trades |
| `equity.parquet` | **Performance** - per-bar equity / returns (+ benchmark) | Report -> Performance -> Equity; compare overlays |
| `chart.html` | **Performance** - candle + order chart (legacy; the web UI rebuilds candles live) | - |
| `analysis.json` | **Robustness** - `in_out_sample`, `walk_forward`, `significance`, `benchmark` | Report -> Robustness |

A `walk_forward/wfo_NNNN/` folder is **all Robustness** (it is itself an out-of-sample test):

| File | Holds |
| --- | --- |
| `meta.json` | identity + objective, train/test days, anchored, n_windows, n_configs, date_range, headline (OOS) |
| `config.json` | the shared base config of the sweep |
| `settings.json` | the sweep grid + walk-forward options |
| `steps.json` | per-window: train range (`train_bars`), picked params, train score, test range (`test_bars`) + test metrics |
| `result.json` | stitched OOS metrics, best-on-full yardstick, parameter stability |

## How the UI reads it

- **Runs** page / **Strategies** page -> `index.json` (headlines only; fast).
- **Run report** -> loads one run; **Performance** reads metrics/trades/equity/chart, **Robustness**
  reads `analysis.json` (or `result.json`/`steps.json` for a WFO run).

So the storage already separates "what happened" from "can I trust it" - the report just renders
those two groups as its two sections.
