# flag_pattern

A research strategy for the **fractal flag pattern** on NQ: a large directional move (**pole**),
a **consolidation** (flag), and a **continuation** (breakout) that resumes the pole. Built
incrementally with the user over many sessions — and still early. **This is a long-running,
evolving strategy; expect to keep refining, not to "finish" it.**

> **If you are a future agent (or human) picking this up: read this file, then `NOTES.md`, then
> `RANTS.md`. Then follow the workflow below. Do not restructure or "clean up" without matching
> the conventions here — the structure and the docs ARE the project.**

---

## Read these first (in order)
1. **README.md** (this) — orientation + workflow + conventions.
2. **NOTES.md** — the clean, technical concept + current state + roadmap (§1–§12). The source of
   truth for *what exists* and *what's planned*. Honest about where the edge stands.
3. **RANTS.md** — the user's raw ideas verbatim, timestamped, in order. The *why* behind decisions.
   Where the vision lives.

---

## How we work (the workflow — keep doing this)
This strategy is built through a tight, repeatable loop. Honor it:

1. **User rants an idea** (often messy, typo-heavy, intuitive). That's a feature — capture it.
2. **Reflect it back + be honest.** Restate what they mean, correct misunderstandings, and say
   plainly when something won't work or is unproven. The user explicitly values honesty over
   validation. Anchor everything to: *does it improve forward edge?* (detection is easy; edge is hard.)
3. **Small experiment or feature**, run against real data (`--norm`, `--scales`, an `experiments/`
   script, an `analysis/` script). Report the actual numbers.
4. **Visualize it** — emit **findings JSON** and view it in `tv_chart`. Seeing beats tables.
   The user thinks visually; the chart is how ideas get judged.
5. **Document** — update `NOTES.md` (technical) and append to `RANTS.md` (verbatim rant + summary).
   Timestamp. Attach images to `images/`.
6. **Commit + push** when asked.

Communication style that works here: engage deeply with the theory, give a clear recommendation
(not a menu), keep the honest edge-check front and center, and always leave a "here's the next
fork" at the end.

---

## Folder structure (self-contained strategy)
```
flag_pattern/
  README.md      <- you are here (workflow + orientation)
  NOTES.md       <- concept, current state, roadmap (§1–§12)
  RANTS.md       <- verbatim idea journal, timestamped
  images/        <- annotated screenshots referenced by the docs
  signal/        <- the signal: signal_config.py (single source of truth) + nq_fractal_match.py
  findings/      <- output JSON per variant (flag_5m.json, _free, _w18_free, ...); read by tv_chart
  test/          <- forward-edge tests (threshold sweeps, etc.)
  analysis/      <- studies that produce PNG/CSV into analysis/output/
  experiments/   <- one-off investigations (e.g. magnitude-free normalization)
```
Shared engine lives in `algokit/patterns.py` (`scan`, `scan_free`, `matches_under`).
The viewer lives in `algoproj/tv_chart/` (project-level, reused across strategies).

## Environment
- Run from the `algoproj/` root. Python venv:
  `..\Launcher\bin\Debug\.venv311\Scripts\python.exe` (has numpy/pandas/matplotlib/flask/pyarrow).
- Data: `algoproj/NQdata/*.parquet` (gitignored, ~20yr NQ). Load via `algokit.data.load_tf`.

## Common commands (from algoproj/ root)
```bash
# generate findings (base / magnitude-free / multi-length)
python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save
python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save --norm free --scales 9,18,36
python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save --max-retrace 0.5   # strong only

# forward-edge test / time-of-day study
python "strategy research/flag_pattern/test/nq_flag_breakout_test.py"
python "strategy research/flag_pattern/analysis/time_of_day.py"

# view findings on the chart
tv_chart\run.bat            # then pick a findings file from the dropdown
```

## Where this is heading (integration)
Everything is controlled from **`signal/signal_config.py`** — the single assembly point. As
pieces land (approach B, filters, indicators, alignment), their knobs go there. **End goal:**
a thin `algoproj/strategies/flag_pattern.py` adapter (`DEFAULT` + `run()`, like
`strategies/fanning_mtf.py`) reads that config, turns signals into entries/exits, and runs a
**backtest in the webui**. Research (this folder) → config (control panel) → adapter → webui
backtest. See NOTES.md §13. Keep the config clean and complete so that bring-together stays easy.

## The signal in one paragraph (current state)
A hand-drawn flag template (`signal_config.py`) is matched by **distance** against every sliding
window (`patterns.scan`), keeping the closest, non-overlapping, **8 AM–2 PM ET** windows. Each
match records its forward outcome (`fwd` at horizons, `mfe`/`mae`) and its **fib retracement**
(how far the flag pulled back into the pole; strong ≤ 0.5). Modes: `--norm free` (magnitude-free),
`--scales` (multiple bar-lengths via template interpolation). **Known limitation:** it's a single
combined window with a fixed pole:flag ratio and a fixed-shape, fixed-length consolidation — which
is why the next major build is **approach B** (separate variable-length pole-swing + consolidation;
NOTES §7.3, §12). The honest status of the edge is in NOTES §6.
