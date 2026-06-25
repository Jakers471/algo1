# algoproj — NQ Futures Quant Research

Standalone pandas research on NQ (Nasdaq-100) futures. The work centers on a
fractal moving-average "fan" regime-detection system (32 MAs per timeframe,
each colored by its own slope, collapsed into a 0-100 bull/consolidation/bear
regime score across 1d / 1h / 15m timeframes) plus a body of strategy
edge-testing: every candidate rule is checked against a buy-and-hold baseline
with realistic costs before it is trusted.

## This project does NOT use the QuantConnect LEAN repo

Everything here is **self-contained pure pandas/numpy/matplotlib** — it reads
the cleaned NQ parquet files and a VIX CSV directly and writes PNG/HTML
outputs. It does **not** import or depend on the surrounding QuantConnect LEAN
engine that lives in `algo/`. LEAN was only used for an early throwaway demo
(`quantbook_demo.py`) which remains under `algo/Research/` and is **not** part
of algoproj.

## Folder structure

```
algoproj/
  README.md                project overview (this file)
  config.py                shared absolute paths to data/VIX/output + helpers
  algokit/                 reusable library (data/indicators/regime/costs/backtest/metrics/charts)
  research/
    edge_tests/            does a signal beat the baseline? forward-return probes
    regime/                multi-timeframe fan-regime engines + trade charting
  viz/                     plotting/visualization scripts (save PNGs)
  docs/                    design notes (FANNING_REGIME_SYSTEM.md)
  output/                  all generated *.png / *.html outputs
```

The scripts are thin consumers of `algokit/`, which holds the shared logic
extracted from what used to be copy-pasted inline:

| Module | Public surface |
| --- | --- |
| `algokit/data.py` | `TF`, `load_tf(tf)`, `align(series, target_index)`, `load_vix()` |
| `algokit/indicators.py` | `INDICATORS` registry + `@indicator`; `sma`, `fan`, `slope_pct`, `geom_lengths`, `rsi`, `atr`, `bollinger_bands`, `bollinger_bandwidth`, `adx`, `ma_spread`, `compression` |
| `algokit/regime.py` | `regime_score(df, lo, hi, n_ma=32, slope_L=5, eps=0.03)` -> (bull, consol, bear) |
| `algokit/costs.py` | `FlatCost(per_turn=0.0002)` (default, reproduces prior numbers), `FuturesCost(...)` |
| `algokit/backtest.py` | `run_long_only(close, low, entry_sig, exit_sig, atr, atr_mult, cost, start)` |
| `algokit/metrics.py` | `total_return`, `cagr`, `sharpe`, `max_drawdown`, `win_rate`, `expectancy`, `summary` |
| `algokit/charts.py` | `lightweight_chart(...)` (mod-menu locked-config HTML), `fan_plot(...)`, `regime_ribbon(...)` |

The large `NQ_*.parquet` data files are **not** stored here — they live in
`C:\Users\jakers\Desktop\algo\NQdata` and are referenced via absolute paths in
`config.py`. The VIX history CSV lives at
`C:\Users\jakers\Desktop\algo\VIX_History.csv`.

## Scripts

| Script | What it does |
| --- | --- |
| `research/edge_tests/nq_edge_test.py` | Edge test: does "buy when RSI(14) crosses below 30" beat the baseline on hourly NQ? |
| `research/edge_tests/nq_decompose.py` | Decomposes the trend/pullback/coil/volume-breakout pattern, edge-testing each leg and combination separately. |
| `research/edge_tests/nq_fractal.py` | Fractal MA framework (LTF/MTF/HTF tiers): pairwise distances, tier spreads, alignment score; discovers rules by edge-testing each tier's role. |
| `research/regime/nq_mtf_regime.py` | Multi-timeframe regime engine (1d -> 1h -> 15m) with a 32-MA fan regime score; cascade drill-down, saves regime PNGs. |
| `research/regime/nq_mtf_signals.py` | MTF fan-regime signal + return engine: enter on consolidation->bullish transition gated by higher-timeframe alignment; sweeps entry level X. |
| `research/regime/nq_mtf_combos.py` | Same MTF engine across different timeframe combinations, EPS auto-scaled per timeframe volatility. |
| `research/regime/make_trade_chart.py` | Logs every trade of the best combo, diagnoses why returns are poor, emits a Lightweight-Charts HTML with entry/exit markers. |
| `viz/nq_ma_fan.py` | Giant 32-MA fan on NQ daily, each MA colored by its own slope (green/red/yellow). Saves `nq_ma_fan.png`. |
| `viz/nq_slope_scan.py` | Characterizes the MA-slope regime, runs an edge test on detected breakouts, saves `nq_slope_heatmap.png`. |
| `viz/nq_signal_plot.py` | Plots discovered LTF bear-stack mean-reversion entry signals (raw vs HTF-uptrend-filtered). Saves `nq_signals.png`. |
| `viz/nq_regime_indicators.py` | Regime indicators kept fractal: Bollinger squeeze + ADX trend/range. Saves `nq_bbands.png` and `nq_adx.png`. |
| `viz/nq_regime_ribbon.py` | Paints the 9 fractal MAs by regime (compressed/up/down) with an HTF directional mask. Saves `nq_regime_ribbon.png`. |

## How to run

Use the project's Python 3.11 venv. Scripts can be run from the `algoproj`
root — the config bootstrap at the top of each script resolves data and output
paths regardless of the working directory.

```powershell
cd C:\Users\jakers\Desktop\algo\algoproj
& "C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe" research\regime\nq_mtf_signals.py
```

Any other script runs the same way, e.g.:

```powershell
& "C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe" viz\nq_ma_fan.py
```

Generated PNG/HTML files are written to `output/`.

## STATUS

STATUS: research-phase, nothing beats buy-and-hold yet. See
`docs/FANNING_REGIME_SYSTEM.md` for the design notes behind the fractal MA-fan
regime system.
