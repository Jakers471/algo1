# structure_detection

A sibling strategy to `flag_pattern`, on the **same fractal principle** but a **different detection
method**: instead of matching a hand-drawn template, **decompose price at many scales** and let the
*structure* emerge from the pieces (binary-decomposition style).

> **Status: strategy definition in progress.** The core idea and carried-forward lessons are in
> `NOTES.md`; the exact detector is being specified with the user. Read `NOTES.md` first.

## Read order
1. **README.md** (this) — orientation + workflow.
2. **NOTES.md** — the concept, the carried-forward lessons from `flag_pattern`, and the evolving spec.
3. `../flag_pattern/NOTES.md` + `RANTS.md` — the sibling strategy's full history; **many hard-won
   lessons there apply directly here** (esp. §17 sensor-vs-state-machine, §20 edge-is-the-gate).

## Workflow (same as flag_pattern — keep doing this)
Rant an idea → reflect it back honestly (edge is the gate, not detection) → small experiment on real
data → **visualize it** (emit findings JSON, view in `tv_chart`) → document (NOTES + a rant log) →
commit. Fast honest loop; no big builds before a cheap test confirms there's edge to chase.

## Folder layout (mirrors flag_pattern)
```
structure_detection/
  README.md      <- you are here
  NOTES.md       <- concept, lessons, spec
  signal/        <- the detector + its single-source config (signal_config)
  findings/      <- output JSON the tv_chart viewer overlays
  analysis/      <- per-topic studies (each self-contained, own output/)
  test/          <- forward-edge / R:R tests
  images/        <- reference screenshots
```

## Reused infrastructure (don't rebuild)
- **`algokit/`** — data (`load_tf`), patterns engine, regime, backtest, costs, metrics.
- **`tv_chart/`** — the standalone viewer. It auto-discovers `strategy research/*/findings/*.json`,
  so **any findings this strategy writes will show up in its dropdown with zero chart changes.**
- Data: `algoproj/NQdata/*.parquet` (full history; evaluate on full history unless a window is
  explicitly set — a standing rule from flag_pattern §9.1).
- Venv: `..\Launcher\bin\Debug\.venv311\Scripts\python.exe`.

## The one carried anchor
Detection is the easy part; **confirming a forward edge is the hard part.** Every idea here earns
its keep against forward returns / R-expectancy, validated out-of-sample — not by looking fractal.
