# chart

The TradingView lightweight chart to SEE everything the code looks at, overlaid — on simplicity's own
clean data, no old flag-strategy baggage. Library vendored in `lib/` (offline); data inlined so it opens
off disk.

## Build + open
- `python research/chart/build_chart_data.py` — cache ≤6000 bars/TF (NQ+ES) → `data/*.json` + `manifest.json`
  (also bakes per-session profiles + the `config_panel` for the sidebar).
- `python research/chart/make_chart.py` — build the self-contained `chart.html`.
- Open it two ways:
  - **`run_chart.bat`** (from the simplicity root) — starts `serve.py` at `localhost` and opens the chart
    there **so the Run-backtest button works**. (preferred)
  - or double-click `chart.html` (file://) — everything works except the Run button (it disables itself).

## ONE dimension by default (5m)
The chart defaults to the **5m session volume_profile** — the single base dimension. The extra scales
(`base` coil, `htf` week) are **opt-in via config** (`strategy_config.BASE["on"]`, `HTF["on"]`); when off,
only the session profile loads. Enable a scale (e.g. `HTF days=14` → 2-week lookback) and its module card
appears. (NOTES F35; each active scale = one module card, F37.)

## Sidebar = the control surface (config + run)
- **Run backtest** — from/to dates + a `research | strategy` config select + a **▶ Run** button with a live
  countdown/progress bar; on done it opens that run's report + the trade replay in separate windows.
- **Loaded** — current instrument/tf/bars/range.
- **Vol-day overlay** — `real | research` toggle for the high-vol-day shading (display only).
- **Config** — the status panel: every knob + sub-parameter with dots — green live / red off / orange
  not-wired / purple no-engine (read from `manifest.config_panel`). (NOTES F36)

## Overlays + modules
Indicators panel (top-left): anchors (session hi/lo + breach) · times · profile (POC/VAH/VAL) · fib ·
**modules**. With `modules` on (NQ 1m/5m), click a session's candles → a floating card with that session's
crisp mini volume-profile + timing + shape/R:R scores. **REPLAY:** open a session card → `replay` → step it
bar-by-bar; profile/shape/zone recompute on **bars-so-far** (causal JS port) so scores evolve; gold "now"
line on the chart. **chat log** — each card's `chat about` saves a full markdown snapshot to a persistent
drawer for asking targeted questions.

## Trade replay (sibling page)
`build_trades.py` + `make_trade_replay.py` → `trade_replay.html`: step through each backtest trade & its
outcome — entry/stop/target/exit drawn from the sim's own geometry, the R-multiple ladder overlay, bar-by-bar
now-line with running R, and the same module cards. Caps to `research_config.MAX_REPLAY_TRADES`. (NOTES F31)

**Outputs** (generated, gitignored): `data/*.json`, `chart.html`, `trade_replay.html`, `data/trades_data.js`.
