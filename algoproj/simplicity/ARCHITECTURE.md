# simplicity — Architecture (configs → engine → outputs)

How the pieces wire together. Companions: `NOTES.md` (concept/findings), `VISION.md`
(the 15-step system), `CHECKLIST.md` (tracker), `COMMANDS.md` (how to run).
Status tags: **[built]** exists now · **[planned]** designed, not built yet.

---

## Two tracks
- **research/** = discover & test (messy is fine).  **engine/** = execute (clean, fast, live-ready).
- **Promotion rule:** nothing enters `engine/` until it's proven in `research/` **and the user says
  so — the user decides when.** research = discover, engine = execute.

## Promotion path (research → engine) — how a proven idea becomes real
Both trees are organized by the **same job-layers** so promotion is a clean 1:1 move within a layer
(`structure → structure`, `gates → gates`, …). When you say *promote `<X>`*:
1. The solidified logic moves `research/<layer>/<X>/` → `engine/<layer>/<X>.py` — **self-contained**:
   it may use `engine/data_feed` + `strategy_config` only, never research/ or plotting deps.
2. Any REAL parameters it needs are added to `strategy_config.py` (the concrete source of truth);
   run/experiment knobs stay in `research_config.py`. One setting, one home.
3. `run_simplicity.py` auto-discovers the module (recursive) → it flips to **WIRED** in the pipeline.
4. It's logged in `CHECKLIST.md` (Promotion log) with date + `source → dest`.
- **Research layout mirrors the engine layers** — `research/{structure,gates,setup,execution}/` for
  things that map to an engine stage, plus `research/studies/` for pure discovery/analytics that may
  never promote (buckets, rankings, edge tests, the future session archive), and `research/chart/`
  (cross-cutting viewer). This is the reorg that makes "how does this get promoted?" obvious.
  *(Recommended; see CHECKLIST — research is currently flat per-component.)*

## Two configs, feeding ONE engine
The same engine runs regardless of which config feeds it; only the config differs.

- **`strategy_config.py` — CONCRETE / REAL** **[built]** — the strategy itself + market frictions:
  data paths, sessions, the `FILTER_*` gate, day-vol params, execution costs, signal/entry/exit/risk
  slots. Identical in backtest and live. This is the "real" settings.
- **`research_config.py` — RESEARCH / RUN** **[built]** — how you're testing *right now*:
  `ACTIVE_FILTER` (variant selector), `STARTING_BALANCE`, backtest date range (sweeps later).
  Re-exports `strategy_config` (superset), so "run off research" = import it. `ACTIVE_FILTER` and
  the dead `TRADEABLE_REGIMES` were removed from `strategy_config` — one setting, one home.

**The rule for where a setting goes:** *is it a property of the STRATEGY, or of a RUN?*
Strategy (filters, entry/exit, sizing *rule*, frictions) → `strategy_config`. Run/experiment
(starting balance, dates, variant selector, sweeps) → `research_config`.

## One engine, selectable config
- `engine/` pipeline (see `run_engine.bat`): `data_feed → session_state → vol_filter →
  session_anchors → volume_profile → shape_filter → zone_calibration → fib_bias → setup_arm →
  entry → risk → execution → trailing_stop`. Wired so far: **data_feed, session_state, vol_filter,
  session_anchors, volume_profile** (5/13). The rest promote in as confirmed.
- You **SELECT the config** (research | real) and run it through the same engine. Both the chart
  and the (future) backtest take a config selection — swap the inputs, not the engine.

## Runtime model — LIVE session state machine **[design; not built yet]**
The strategy is a **live, event-driven, bar-by-bar range-breakout engine.** One **session-state
object** is the spine; every component is a function of *state-at-this-bar*, recomputed as bars arrive.

- **Session state machine.** Always knows the CURRENT session and the NEXT one — when each opened, its
  **live** high/low (and *when* each extreme was made, re-updating), time elapsed in-session, and time
  until the next open. Same template per session (Asia / London / NY), tracking the next one too.
- **Everything updates live.** Anchors, the **running** volume profile (POC / value area), shape /
  tightness, fib, and the zone size/tightness metrics all recompute each bar — and **each is a GATE.**
- **Causality by construction (no look-ahead).** Components run on the session's **bars-so-far**; the
  backtest replays bars and only ever passes bars **≤ now**, so look-ahead is *impossible* and the SAME
  code runs backtest and live. (The batch research functions already work on any window → they double
  as the incremental engine — feed them the session-so-far.)
- **Arm / disarm confluence engine (the "lock").** A setup is **not** locked at a fixed time. Gates
  STACK — shape filter + fib bias + zone size vs the session range + range/tightness calc + zone
  calibration + time-in-session + time-until-next-open — and when they **align**, the setup **ARMS**:
  an entry decision / **resting orders** (breakout stops beyond the range, or fades at the range edge)
  are placed **before the next session opens**. If a validation breaks, it **DISARMS** and the resting
  orders are pulled. Continuously re-evaluated each bar — validations arm, invalidations disarm.
- **The trade.** The incoming session's volume triggers the resting order; manage with **aggressive
  volume-based trailing** (+ breakeven). Entry timeframe is smaller than the range's timeframe.

**Edge framing.** The edge is **not** a predictive component (the isolated components test flat — treat
those as *diagnostics*, not verdicts). It's the **confluence + R:R geometry** of a tight, well-defined
range breakout: small defined invalidation vs room to run. **Judge the system fully wired, not piece by
piece** — the mechanics (stop placement, resting orders, breakeven, aggressive trailing, DCA) are the
substance, not "how far price drifts after a break."

## Chart — config-selectable **[built]**
`research/chart` visualizes what a config covers: multi-TF candles+volume + dark shade overlays
(session windows, high-vol days) + a sidebar of the loaded config. A **CONFIG selector (real |
research)** in the top bar switches the vol-day overlay + sidebar to that config — real uses
`FILTER_DAY_VOL` regimes, research uses `ACTIVE_FILTER`. (Both snapshot into the manifest at build.)

**Replay mode [planned] — the engine's visual frontend / backtest inspector.** Cut price back to any
point and step **forward bar-by-bar**. Because the engine runs on bars-so-far, replay = the live engine
driven interactively: at each bar a **modular state panel** shows the running numbers — session timing
(in / until next), live hi/lo, running profile POC / value area, zone size & tightness, fib bias, each
**gate's strength / alignment**, and the setup's **ARM / DISARM** state with the validation/invalidation
that flipped it. You watch *why* it armed, placed resting orders, entered, trailed. It's the **same
causal engine** as backtest + live, so the replay IS the backtest unfolding step-by-step, with trades
marked on the chart (cf. Prior art: `algoproj/webui` chart + BUY/SELL markers + equity).

## Outputs — separated by config **[planned]**
Runs store artifacts (equity-curve PNGs, backtest results) in **different places per track**, so
research and real never mix:
- research runs → `backtest/output/research/`
- real runs    → `backtest/output/real/`

**What promotes a research output to "real" (decided now, same discipline as engine promotion):**
the output's track is determined **automatically by which config ran it** — a run driven by
`research_config` writes to `research/`, a run driven by `strategy_config` writes to `real/`.
**Nothing is manually copied between them.** "Promoting to real" is not a file move — it's the
**human graduating the tested values into `strategy_config`** (the concrete config); after that,
runs under it land in `real/` on their own. So promotion happens at the CONFIG level (a human
decision), and output routing is just a mechanical consequence — never a hand-copied PNG.

**No-duplication rule:** a setting lives in exactly ONE config. When `research_config` is built,
run/testing knobs (`ACTIVE_FILTER`, `STARTING_BALANCE`, dates, sweeps) move there and are **deleted
from `strategy_config`** — never kept in both.

## Backtest / equity-curve engine **[planned — separate top-level folder]**
`backtest/` (its own folder, not under research) wires a **chosen config** into the engine and
produces equity curves → PNGs stored per-config (above). It is the thing that *connects* the two
configs to the engine. **Not built** — and there's nothing to measure yet (no risk management, no
returns; current focus is visualization only).

## Session Archive — the causal record substrate **[future — documented, not built; NOTES F9]**
`research/studies/session_archive/` — "replay, written to disk." A builder steps every session
bar-by-bar (the same causal math as chart replay, reusing the engine components incrementally) and
persists, per bar: timestamp, OHLC, volume, and **every measurement made at that bar** (running
POC/VA, shape score + components, zone R:R, %-gain in-session, live hi/lo, time-in/until) — sequenced,
scored, machine-readable (parquet: one row per bar keyed by `sid` + bar index) + a session-summary
table, **tagged with the `research_config` it ran under**. Merge per day → a queryable history to run
`analyze_*.py` on and mine geometry/scoring patterns (maybe derive rules; maybe not). It also hosts a
NEW untested ingredient — the **extension context** (decay / overextension / healthy-extension: how
far/fast price stretched from value, mean-revert risk) — a context/bias input, not a direction call.
Open question: extended / off-hours handling. Deferred until the core gates exist to feed it.

## Data **[built]**
`data/NQ` + `data/ES` — clean parquets, real volume = `Up + Down`, regenerated by
`data/build_data.py` from the TradeStation source. Gitignored (large).

## Flow (one line)
select config (**research | real**) → engine pipeline runs on `data/` →
**chart**: visualize overlays  ·  **backtest [planned]**: equity-curve PNG stored per-config.

---

## Prior art — the existing backtest / walk-forward UI (reference; do NOT reinvent) **[built, elsewhere]**
The whole backtest + walk-forward stack already exists in `algoproj` (same style of UI). When
simplicity has entry/exit + risk and needs measurement, its `backtest/` **reuses this engine +
these patterns** rather than rebuilding:

- **`algoproj/webui/`** — Flask + PyWebView + ECharts dark dashboard (`run_webui.bat`). Pages:
  **Analyzer** (run/optimize → Summary / Trades / Equity / **Chart** / Validation), **Runs**,
  **Strategies**, **WFO** (walk-forward results, `js/pages/wfo.js`). Key API (`server.py`):
  `/api/run/chart` = candles + **BUY/SELL markers** (trades on the chart — exactly the "see where
  trades were taken" ask), `/api/run/equity` = **equity curve + drawdown**, `/api/wfo` =
  **walk-forward** run.
- **`algoproj/_archive/app/`** — the original **Streamlit** version (Analyzer | Runs; Backtest |
  Walk-Forward Optimization | Anchored WFO; detailed WF labeling in `views/wfopt.py`). Archived.
- **Engine:** `algokit/wfo.py` (walk-forward: train/test folds, anchored), `optimize.py`
  (`min;max;incr` grids), `params.py`, `validation.py` (IS/OOS), `significance.py`, `runs.py`
  (versioned run registry: per-run config / metrics / trades / equity / chart).

Not wired to simplicity yet — documented here so we build on it, not around it.
