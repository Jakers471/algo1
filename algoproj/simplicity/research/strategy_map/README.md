# research/strategy_map

Two reasoning tools for the wiring — both generated from the live config so they never drift.

## `build_map.py` → `strategy_map.html` — the CONFIG CONTROL PANEL
Every dial in `strategy_config` + `research_config` on one page, grouped by stage, each with its config
path, current value, and a badge for whether the **backtest uses it now**:
- **LIVE** (green) — applied today · **NOT WIRED** (amber) — configured but ignored (a gate waiting on
  `setup_arm`) · **REFERENCE** (blue) — bias/geometry judged in-context (e.g. `fib_bias`) · **FUTURE** (grey)
  · **LOCKED** (frictions).
The amber NOT-WIRED dials are the wiring to-do list; building `setup_arm` turns each into an on/off toggle.
**Run:** `python research/strategy_map/build_map.py` → open `strategy_map.html`.

## `build_flow.py` → `flow.html` — the INTERACTIVE FLOW EDITOR
A blank board + a bottom tray of every component (run knobs, data, filters, structure, gates, setup_arm,
trade, risk, measure). Drag a piece up onto the board, move it by its title, drag its green out-port → another's
grey in-port to link, click a line to cut. Auto-saves to localStorage; **Export** writes `flow.json` (your
layout + links + the derived linear order) so an arrangement can be reviewed / turned into the real pipeline;
**Import** reloads one. This is the "lay out the execution succession yourself" tool.
**Run:** `python research/strategy_map/build_flow.py` → open `flow.html`.

Outputs are generated (gitignored). Related: NOTES F37 (SCALES = the geometric ladder = the module cards).
