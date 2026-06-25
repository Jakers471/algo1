# webui - algoproj Quant Analyzer (Flask + PyWebView + ECharts)

A desktop dashboard rewrite of the Streamlit app (`../app/`), reusing the **same engine**
(`algokit`, `strategies`, `runs`, `wfo`, `validation`, `significance`). This layer is
presentation-only: a Flask JSON API over the engine + a vanilla-JS / ECharts dark UI in a
PyWebView window. No analytics logic lives here.

## Run

```
webui\run_webui.bat            # desktop window (PyWebView)
webui\run_webui.bat --web      # serve only, open http://127.0.0.1:8780
```

Needs `flask` and `pywebview` in the 3.11 venv (`pip install flask pywebview`).

## Layout

```
webui/
  server.py            Flask API + static host + PyWebView launcher
  static/
    index.html         SPA shell (sidebar + topbar + main)
    css/theme.css      teal/slate dark theme (shared design system)
    css/app.css        algoproj-specific additions (tabs, controls, flags)
    js/echarts.min.js  vendored ECharts
    js/charts.js       ECharts builders (+ candles, equityDD for this app)
    js/components.js    el(), sortableTable(), kpi() ... (window.UI)
    js/widgets.js      controls + formatters + progress + flags (window.W)
    js/app.js          API helper, sidebar nav, hash router
    js/pages/
      runs.js          Runs page (run-vs-run, one strategy) + window.runRows()
      strategies.js    Strategies page (strategy-vs-strategy champions)
      analyzer.js      Analyzer (run/optimize + Summary/Trades/Equity/Chart/Validation)
      wfo.js           window.renderWFO() - walk-forward results renderer
```

## API (server.py)

| Endpoint | Returns |
| --- | --- |
| `GET /api/strategies` | name + DEFAULT + signal/execution/sweepable key lists |
| `GET /api/date-range?ltf=` | `[minDate, maxDate]` |
| `GET /api/runs?kind=` | run metas (the registry, optionally filtered) |
| `GET /api/run?path=` | meta/config/metrics/analysis (or settings/result/steps for WFO) |
| `GET /api/run/equity?path=` | daily equity + % curve (+ benchmark) |
| `GET /api/run/trades?path=` | trade records |
| `GET /api/run/chart?path=` | candles + BUY/SELL markers (windowed) |
| `GET /api/run/validation?path=&split=` | live IS/OOS recompute at any split |
| `POST /api/backtest` | run + save a backtest, returns meta |
| `POST /api/wfo` | run + save a walk-forward optimization, returns meta + result |

Pages register into `window.PAGES[id] = { id, render(main) }`; the router calls the active
page. Shared helpers: `window.UI`, `window.W`, `window.Charts`, `window.API`,
`window.runRows(metas)`.
