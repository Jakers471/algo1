# research/runs — the RUN LEDGER (scorecards bound to configs + params)

Don't tune blind. Every research run that produces numbers logs a **scorecard** to the append-only
`runs.jsonl`: `run_id` · git commit · the component **params** it used · a **strategy_config snapshot**
· the output **metrics** · a note. Nothing is ever overwritten — change a knob, re-run, and BOTH the
before and after are kept forever. This is the info we refuse to lose.

## Use it (the tuning loop)
1. Run a script — it auto-logs. Add a note as trailing words:
   `python research/gates/profile_shape_filter/shape_filter.py baseline before tuning`
2. Tune a param (e.g. `SHAPE_OK` 50 → 45 at the top of `shape_filter.py`), re-run with a note:
   `python .../shape_filter.py shape_ok 45`
3. Compare: `python research/runs/analyze_runs.py [kind]` — every run's params + metrics in order, so
   before/after is two rows you diff by eye (e.g. `shape_ok_pct` 21.1 → …).

## Wired so far
`shape_filter`, `zone_calibration`, `fib_bias`, `base_profile`, `htf_profile`, `target_ladder`, and the
`backtest` each call `runlog.record(...)` at the end of `main()`, and expose every tunable knob in one
`PARAMS`/constants block at the top of the file. Add `runlog.record(kind, params, metrics, note)` to any
new script to enroll it. (The chart/viz builders — `build_trades`, `make_*` — don't log; they produce
pictures, not metrics.)

## Files
- `runlog.py` — `record()` / `load()` / `config_snapshot()` / `git_commit()` / `note_from_argv()`.
- `analyze_runs.py` — the analytics reader over the ledger.
- `runs.jsonl` — the durable append-only history (**git-tracked**; the record we don't lose).

Complements the future per-bar `session_archive` (NOTES F9): that stores every bar's causal state;
this stores per-**run** params + metrics. Together = full provenance of what we ran and what it produced.
