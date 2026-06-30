# _archive

Deprecated code kept for reference. Not part of the active project path.

- **`app/`** — the original **Streamlit** Strategy Analyzer UI. Superseded by the
  Flask + vanilla-JS Quant Analyzer in `../webui/` (launch via `webui/run_webui.bat`).
- **`run_analyzer.bat`** — launcher for the archived Streamlit app.

Both still import the shared engine in `../algokit` and `../strategies`, so they remain
runnable, but new work happens in `webui/`.
