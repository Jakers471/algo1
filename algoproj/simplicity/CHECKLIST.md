# simplicity — Build Checklist

Scratch off as we go. Mirrors `VISION.md` (the full 15-step system) in build order.
Companion: `strategy_config.py` (single source of truth — now tiered + status-tagged), `NOTES.md` /
`RANTS.md`. See **Config alignment** just below for how these items map to the config's wiring tags.

## Status legend
- `[ ]` not started
- `[~]` in research — work in progress
- `[R]` **built in research**, working & verified
- `[C]` built — **awaiting your confirmation** to solidify & promote to `engine/`
- `[E]` **confirmed & promoted to `engine/`** (live-ready)

**Promotion rule:** nothing moves `research/` → `engine/` without your explicit OK.
**You say when.** Claude never promotes on its own.

## Config alignment — PROMOTION state vs WIRING state (added 2026-07-03, nothing removed)
Two DIFFERENT axes, easy to conflate (this caused real confusion):
- **This checklist's legend** (`[ ]`/`[~]`/`[R]`/`[C]`/`[E]`) = **PROMOTION** state (research → engine).
- **The config's status tags** (`strategy_config.py`, now organised in TIERS: control-panel / structure /
  calibration / facts) = **WIRING** state — does the knob actually change a backtest number *today*?
  `[WIRED]` yes · `[SENSOR]` measured/drawn but **not gating yet** (waits for `setup_arm`) ·
  `[CHART]` display only · `[FACT]` constant.

**They are not the same axis.** A piece can be promoted (`[E]`) yet be a `[SENSOR]` that gates nothing
(vol_filter), or still `[~]` in research yet already feed the backtest (base_profile).

**Honest runtime note:** backtest numbers come from `backtest/run_backtest.py`, which reads the research
**profile JSONs** + `target_ladder` — it does **not** import `engine/`. `engine/run_simplicity.py` is a
*wiring tracker* (prints WIRED x/13), not the thing that trades. So `[E]` means "promoted & importable",
not "this is what produces the backtest."

**Reconciliation — what each component really is:**

| component | promotion | config tier · wiring tag | affects a backtest today? |
|---|---|---|---|
| data_feed | `[E]` | facts · **WIRED** | ✅ data in |
| volume_profile (5m session) | `[E]` | structure · **WIRED** | ✅ via JSON (rebuild to apply) |
| base_profile (coil) | `[~]` | structure · **WIRED** | ✅ the trade universe (the `on` toggle is CHART-only) |
| htf_profile (composite) | `[~]` | structure · **WIRED** | ✅ ladder targets (the `on` toggle is CHART-only) |
| target_ladder | `[~]` | structure · **WIRED** | ✅ builds the trade geometry |
| entry / exit / risk | `[ ]` slots | control-panel · **WIRED** | ✅ inline in run_backtest |
| costs / era | `[E]`/`[R]` | facts · **WIRED/FACT** | ✅ |
| vol_filter (session/hour/day) | `[E]` | control-panel · **SENSOR** | ❌ backtest trades ALL sessions |
| shape_filter | `[~]` | gate `GATE_SHAPE_OK` · **SENSOR** | ❌ not gating yet |
| zone_calibration | `[~]` | gate `GATE_RR_MIN` · **SENSOR** | ❌ not gating yet |
| fib_bias | `[R]` (no edge) | calibration · **SENSOR** | ❌ chart geometry only |
| session_anchors | `[E]` | — · **CHART** | ❌ chart levels only |
| session_state | `[E]` | — (engine scaffold) | ❌ backtest doesn't use engine/ |
| **setup_arm** | `[ ]` | structure `SETUP` · **UNBUILT** | — the unlock: turns every SENSOR above into a real gate |
| entry_trigger / trailing_stop | `[ ]` | execution (folder empty) · **UNBUILT** | — logic currently inline in run_backtest |

**Bottom line:** the backtest is a straight line (base coil → ladder targets → entry/exit/risk). Every
`[SENSOR]` becomes a real gate only when `setup_arm` reads it. The pre-shrink config is kept at
`_archive/strategy_config_full_2026-07-02.py`; the readable mock is `config_proposal_v2.yaml` +
`viz/config_viz.html`. The chart sidebar renders these same wiring tags live (`serve.py` `/config`).

**Update 2026-07-03 (NOTES F40):** `setup_arm` is now BUILT + default ON, so `shape_filter` + `zone_calibration`
flipped from `[SENSOR]` (measured, not gating) to **`[WIRED]` — they now gate the backtest** (via setup_arm).
`session filter` likewise gates now. `htf` toggle is **real** (off ⇒ not fed to the ladder, not just hidden).
New `[WIRED]` take-profit selector (`fixed_rr` / `ladder_rung` / `trailing`; default `trailing`). Promotions:
shape_filter · zone_calibration · setup_arm · target_ladder → `engine/` (WIRED 8/13). `fib_bias` stays a
`[SENSOR]`/study (no live edge). Every run now stores its full `config_snapshot` in `analysis.json`.

---

## Phase 0 — Foundation & workflow
- `[R]` Master config — single source of truth (`strategy_config.py`)
- `[R]` research/ vs engine/ split + research-first workflow
- `[R]` Placeholder scaffold + this checklist
- `[R]` Execution/costs locked (point value, tick, commission, slippage) — `strategy_config` (sizing/entry still TBD)
- `[E]` **engine/data_feed.py PROMOTED** — loads all NQ+ES clean parquets (run_engine shows WIRED 1/10)

## Phase 1 — Calendar volatility (WHEN to trade)
- `[R]` Bucket data hierarchically: all → year → quarter → month → day → hour/session, total volume per slice — `research/studies/volume_buckets`
- `[R]` Volatility per bucket: Mean Vol %, HV %, Vol Range %, Avg Daily Range % — `research/studies/volume_buckets`
- `[R]` Volume + volatility dashboard (charts + full tables + Δ vs prev) — `research/studies/volume_buckets/output/volume_dashboard.html`
- `[R]` Era cutoff — drop the low-vol 2005-2014 decade (recent HV ≈ 2× early) — `strategy_config.ERA_START_YEAR`
- `[R]` Volatility ranking — structured most-vs-least volatile per level — `research/studies/volatility_ranking`
- `[E]` **When-to-trade filter PROMOTED** — intraday gate (session/hour + optional daily vol-regime, toggleable `FILTER_SESSION/HOUR/DAY_VOL`) → `engine/vol_filter.py` (WIRED 2/10); research copy kept for testing
- `[R]` Filter variants bank (high / low / medium / not_high / extremes / all) for A/B testing — `research/gates/volatility_filter/filter_variants.py`
- `[R]` Random/unconditional baseline in the test (`evaluate()` compares each variant vs a Monte-Carlo same-size random null)
- `[ ]` **Hypothesis test** — "strategy better in high-vol periods": run `evaluate()` with strategy per-day R; H holds only if `high` beats the **random baseline** (top tail) AND `low` (blocked on the strategy existing)

## Phase 2 — Session structure (WHERE)
- `[R]` Session high/low levels + **forward breach tracking** — extend until price closes through (solid=hit / dashed=ongoing), saves when/where/duration (machine-readable) — `research/structure/session_anchors` (+ chart Indicators panel: toggle levels/sessions, color-coded; chart loads 6000 bars)
- `[R]` Session-break stats + edge test — base rates, conditional lift, breakout follow-through vs drift — `research/studies/session_break_stats`. **Verdict: no directional edge** (lifts ~1, follow-through excess ~0); breach data is a descriptor, not a signal.

## Phase 3 — Volume Profile & Value Area (the zone)
- `[R]` Volume Profile per session (bounded by session high↔low; real Up+Down volume) — `research/structure/volume_profile`
- `[E]` **Volume spread across each bar's H-L (not close-only)** — fixed 2026-07-02: close-only let a
  single high-volume bar steal the POC from a diffuse base (NOTES F5). **Re-promoted to
  `engine/structure/volume_profile.py` 2026-07-02** (median VA now 47%); research + engine in sync.
- `[R]` POC + Value Area = the consolidation zone (VAL/VAH, 70%)
- `[R]` Measure the zone: duration (bars) + height (%) + VA/range%
- `[R]` Chart overlay: POC (solid) + VAH/VAL (dashed) per session, color-coded (Indicators `profile` toggle)
- `[~]` Profile shape / tightness rejection — `research/gates/profile_shape_filter`: `score()` (0-100) + visual
  gallery (`make_examples.py`) built; PROVISIONAL metrics/threshold, refine before promoting
- `[~]` **`base_profile` BUILT (side-by-side study)** — profiles the detected consolidation BASE, not the
  whole session; emits the same dict so `shape_filter`/`zone_calibration` score it unchanged (the seam).
  `make_compare.py` shows session vs base. Finding: base detected in 78% of sessions; on trend days session
  reads foggy but base reads clean (shape +29..+34) with risk 1R ~3-4x tighter. `research/structure/base_profile`.
  **Promote-pending — you decide** (replace / complement per F15; validate in-context F13). (NOTES F6/F18)
- `[~]` **`htf_profile` BUILT (3rd scale)** — trailing-week composite ending at session open; same dict →
  same gates. The three profilers (base ⊂ session ⊂ HTF) run together on the chart's 3-card module stack,
  replay-all (session+base live, HTF static). `research/structure/htf_profile`. Promote-pending. (NOTES F19)
- `[R]` **All gate params centralized in `strategy_config`** (PROFILE/SHAPE/ZONE/BASE/HTF/FIB/LADDER) — research +
  engine + chart JS all read them; ledger captures them; tune in one file → clean promotion, nothing breaks. (NOTES F20)
- `[~]` **`target_ladder` BUILT — multi-scale R:R geometry** (`research/setup/target_ladder`): 1R = base coil;
  targets = larger scales' VA/POC/extremes as a scale-out ladder w/ R:R per rung, both directions. Geometry only
  (no backtest). On the chart module stack as the TARGET LADDER card. The trade def `setup_arm` will arm. (NOTES F25/F26)

## Phase 4 — Setup calibration & bias
- `[~]` Height% / duration → risk (1R=VA edge) + room + R:R + entry timeframe — `research/gates/zone_calibration`
  (`calibrate()` + shared gallery scorecard built; PROVISIONAL geometry, refine before promoting)
- `[R]` Fib off session hi/lo — chart overlay built (0.5 solid + golden-zone dotted per session, toggleable).
  **Isolated test (2026-07-02): no signal in isolation** — P(next up) per fib zone 51.8-56.4% vs 54.3% base
  (spread 4.6pts, none >2σ). **But this is a DIAGNOSTIC, not a verdict (NOTES F13):** it bolts fib to an
  arbitrary construct (close-position → next-session dir) with no tie to a real setup. Do NOT drop fib —
  keep as chart geometry; true test is IN-CONTEXT once setup_arm/entry exist. `research/gates/fib_bias` (F11/F13)

## Phase 5 — Live engine spine (state machine + arm/disarm)  ← the runtime model
*(see `ARCHITECTURE.md` "Runtime model — LIVE session state machine". Everything updates on
bars-so-far; causality is enforced by construction; setups arm/disarm on stacked confluence.)*
- `[E]` **Session state machine BUILT** (the spine) — per-bar causal state: current + next session, live hi/lo (+ when made), time-in-session, time-until-next — `engine/session_state.py` (WIRED 5/13)
- `[ ]` Wire the promoted components as **live readers of state** (run on the session's bars-so-far, not batch)
- `[ ]` **Zone calibration** — zone size %/bars → entry timeframe + stop distance / R:R (gate) — `research/gates/zone_calibration`
- `[R]` **setup_arm — the confluence ARM/DISARM engine** — stack gates (shape + fib + zone size/tightness + timing) → ARM (place resting orders) / DISARM (pull them) on validation/invalidation, continuously re-evaluated.
  **v1 BUILT + wired (NOTES F39):** `research/setup/setup_arm/setup_arm.py` = arm-once `session AND shape_ok AND rr_ok`;
  one-line gate in `run_backtest.py`, toggled by `SIMP_ARM=1` env or `SETUP["on"]` (default off = base rate). First
  gated run: win 29.6%→**43.3%** but expectancy flat (68% time-outs → the **EXIT** is now the constraint, not entry).
  TODO v2: continuous DISARM (re-check mid-window) + multi-scale confluence (read session/htf, not just the coil).
- `[~]` **FULL STRATEGY SPEC + fixes (NOTES F42)** — clarified with the user: scan EVERY session for a coil, rest
  OCO stops ~15min before the NEXT session opens, trade that open's breakout (asia→london, london→NY), and while
  IN a trade keep scanning for a new coil to PYRAMID a same-direction add-on. Build order:
  - `[R]` **#2 trade the NEXT session's open** — `setup_arm` now gates on the coil's next session (`_next_session`);
    `FILTER_SESSION.allow` = the OPENS we trade (`["london","newyork"]`). Fixed the old NY-coil→close-open mistake.
    Result: 1,817 trades, 35.3% win, +0.013R, PF 1.02, time-outs 639→64; london→NY +0.056R, asia→london −0.045R.
  - `[R]` **#1 arm 15 min BEFORE the open** — `ENTRY["place_lead_min"]=15`; base_profile finalizes the coil that
    early (excludes the last 15 min of the session → CAUSAL) + emits `place_ts`; run_backtest places the resting
    orders at `place_ts`. Result vs at-open: 900 trades, 36.2% win, +0.046R, PF 1.08, **max DD 48R→31R** (smoother,
    and the honest live model — orders resting before the NY open, the original design).
  - `[R]` **#3 per-session-search replay** — `build_trades` evaluates EVERY session in the slice (coil + shape/rr +
    setup_arm verdict + the open it'd trade); the replay draws each session's open line, verdict label
    (✓ARMED▶NY / ✗rejected / no coil) + coil range box (green=armed, grey=rejected), and the state panel shows
    the live scan of the current session. You watch it hunt asia→london→ny across the day, not just the winner.
  - `[ ]` **#4 pyramiding** — same-direction add-on when a new coil forms mid-trade (multi-entry backtest).
- `[ ]` Causality rule enforced: components only see bars ≤ now (no look-ahead) — same code live + backtest

## Phase 6 — Entry & exit mechanics (the substance — R:R geometry, not prediction)
- `[ ]` Entry: **resting orders before the next open** — breakout stops beyond the range and/or fades at the range edge (bias-gated) — `research/execution/entry_trigger`
- `[ ]` Value-Area breakout + volume confirmation (the trigger); entry TF smaller than the range TF
- `[ ]` **Breakout VOLUME CONFIRMATION — future entry refinement (NOTES F43)** — a real break has a volume surge
  (`breakout_bar_vol >= vol_mult × coil_baseline`, coil_baseline = coil volume / bars). Two variants, config
  `ENTRY["confirm"]="touch"|"close_volume"`: **A** confirmed-close entry (filters false breaks but worse fill →
  worse R:R; bends the resting-order model) · **B** rest-then-scratch (fill at edge on touch, exit fast if the
  break is thin — keeps the good fill + resting model; likely the better fit). Needs raw `volume` loaded in
  run_backtest (only OHLC today — volume already acts UPSTREAM in the profiles/shape gate, F43). Distinct from a
  RANGE volume-accumulation gate (arm only if the coil itself gathered enough volume). Both cheap; A/B in the ledger.
- `[ ]` Stop placement (range/VA edge = invalidation) · breakeven logic · DCA-into-range (decide)
- `[R]` Risk / position sizing — `strategy_config.RISK` + `STARTING_BALANCE` (fixed-fractional, wired in the backtest)
- `[R]` **Config-driven TAKE-PROFIT engines (NOTES F40)** — `EXIT["target"]` selector: `fixed_rr` (constant 1:R) ·
  `ladder_rung` (multi-scale) · `trailing` (arm at +arm_r, hold gap_r behind best). All wired in the backtest.
  **Trailing won** (first positive expectancy: trailing + setup_arm = PF 1.10 / +0.035R / 47.8% / DD 19R) — it
  cures the F39 time-out problem. Defaults now `trailing` + `SETUP.on=True`.
- `[R]` **Trailing stop (fixed-R version) BUILT** — currently inline in `run_backtest` (arm/gap in R). TODO:
  the *volume-based* aggressive trail + breakeven + a promoted `engine/execution/trailing_stop.py` — `research/execution/trailing_stops` (still a stub).

## Phase 7 — Measurement & backtest (FUTURE — blocked on Phases 5-6)
- `[R]` **Per-session module cards** — Indicators `modules` on, click a session (NQ 1m/5m) → floating card
  with that session's crisp mini volume-profile + timing (open/close/duration/next+gap) + shape/R:R scores.
  Solves crisp-VP-on-chart + session hand-off view; = the seed of the replay state panel — `research/chart`
- `[~]` **Chart REPLAY mode** — v1 built: step a session bar-by-bar (|< < play > >| + scrubber + speed),
  the module recomputes profile/shape/zone on **bars-so-far** (causal, JS port) so scores evolve as price
  moves; gold "now" line on the chart. **Pending (gates first):** the **modular state panel** on this same
  card — live hi/lo, fib bias, gate strengths, ARM/DISARM + the validation/invalidation that flipped it —
  layers on once `setup_arm` etc. exist. The engine's visual frontend = the backtest unfolding — `research/chart`
- `[R]` **Trades on the chart — TRADE REPLAY page** (`research/chart/trade_replay.html`, built by
  `build_trades.py` + `make_trade_replay.py`) — step through each backtest trade & its outcome: entry/stop/
  target/exit drawn from the sim's own geometry (`backtest/output/trades.json` = source of truth), entry &
  exit markers, bar-by-bar "now" line with running mark-to-market R, and the SAME 3 module cards
  (base⊂session⊂HTF) + target ladder the main chart shows. Browse prev/next, scrub, filter by outcome.
  Caps to the most-recent N trades (default 300, config `MAX_TRADES`; `0`=all) to stay light. (NOTES F31)
- `[R]` **Backtest engine BUILT** (`backtest/run_backtest.py`) — honest sim of the target_ladder trades
  (coil-edge fills, 1R=coil, TP=ladder rung, time-stop, costs, no look-ahead; records MAE/MFE/ETD excursion).
  **UNCONDITIONAL base rate ≈ BREAKEVEN** (1,592 trades, 29.6% win, -0.017R, PF 0.97, max DD 75R) after fixing
  the era/profile mismatch bug (F30). The number `setup_arm` must beat with lift: 29.6% → ~33%+ win. (F28/F29/F30)
- `[R]` **Per-run PERFORMANCE REPORTS** (`research/runs/analytics.py` + `make_report.py`) — every backtest run
  writes `reports/<run_id>/analysis.json` (machine-readable, full NinjaTrader-style breakdown ALL/LONG/SHORT +
  daily equity/drawdown + the trade list) and a clean `report.html` (dark, ECharts equity/drawdown + headline
  cards + tables, matching the webui Quant Analyzer); `reports/index.html` = the "< all runs" browser. Runs owns
  the analysis (no more loose equity.png). Open `research/runs/reports/index.html` → newest run. (NOTES F32)
- `[R]` Equity curve (+ drawdown) — ECharts, in each run's `report.html` (colored by net result; reconciles to $)
- `[ ]` Walk-forward testing with detailed WF labeling (train/test folds, anchored)
- **Prior art (don't reinvent):** you already built all of this in `algoproj/webui` (Flask+PyWebView+ECharts:
  Analyzer/Runs/Strategies/WFO; `/api/run/chart` = candles+BUY/SELL markers, `/api/run/equity` = equity+DD,
  `/api/wfo` = walk-forward) + the original Streamlit `algoproj/_archive/app`; engine =
  `algokit/{wfo,optimize,validation,significance,runs}`. simplicity's `backtest/` reuses this. See ARCHITECTURE.md.

## Cross-cutting
- `[~]` **Fresh TradingView lightweight chart** (`research/chart`) — rewired to simplicity data; multi-timeframe (NQ+ES); OHLC cached to JSON, load max ~2000 bars/TF for speed; side menu showing which instrument/TF/config is loaded (clean format); overlay the filter-selected periods. No old flag-strategy baggage.
- `[R]` Config filter selector `ACTIVE_FILTER` (pick which variant tv/backtest uses) — `strategy_config`
- `[R]` Config split DONE — `research_config.py` (run/testing: `ACTIVE_FILTER`, `STARTING_BALANCE`, dates) re-exports `strategy_config`; removed `ACTIVE_FILTER` + dead `TRADEABLE_REGIMES` from `strategy_config` (no duplication)
- `[R]` **Two config SOURCES OF TRUTH + runs separated by source** (NOTES F34) — `CONFIG_SOURCE` tags each
  (strategy=main/real, research=experimental the backtest runs off); runs saved under `reports/<source>/<run_id>/`;
  index has a Config column; `run_backtest --real` runs off strategy_config. Wired the dead `BACKTEST_START/END`
  + `MAX_REPLAY_TRADES` research_config knobs.
- `[R]` **Config retiered by ALTITUDE + live control surface** (NOTES F38) — `strategy_config` reorganised into
  CONTROL PANEL / STRUCTURE / CALIBRATION / FACTS, every knob status-tagged `[WIRED]`/`[SENSOR]`/`[CHART]`/`[FACT]`
  (37/37 names preserved; pre-shrink copy in `_archive/`). Chart sidebar renders the tiers + honest dots; new
  `serve.py` `/config` endpoint reloads config LIVE (edit config → reload page → sidebar updates, no rebuild).
  `config_panel.py` = one shared panel def. Honest fix: `FILTER_*` are SENSORS (backtest trades all sessions),
  `BASE/HTF.on` are CHART-only. Reference sketches: `CONFIG_PROPOSAL.md`, `config_proposal_v2.yaml`,
  `viz/config_viz.html` (a mock candlestick chart per config block). See also "Config alignment" up top (two axes).
- `[R]` **Run harness hardened** (NOTES F39) — chart date pickers default + LOCK to the data range (data ends
  2025-01-10; picker had defaulted to the 2026 calendar → empty window → "no trades" → 500). `run_backtest` +
  `serve.py` now report a clear empty-window reason instead of a mystery 500.
- `[R]` **Chart = the control surface** (NOTES F36) — sidebar config-STATUS panel (every knob + sub-param, dots:
  live/off/not-wired/no-engine) + a **Run backtest** button (dates + source + countdown) that opens the report +
  replay on done. Needs the local server: **`run_chart.bat` / `serve.py`** (file:// can't run Python).
- `[R]` **Single dimension by default (5m)** (NOTES F35) — chart shows only the 5m session profile; `BASE`/`HTF`
  scales are opt-in via `strategy_config` `"on"` flags (load only when enabled). Minimal skeleton first, add layers.
- `[ ]` **`SCALES` config = the geometric ladder = the module cards** (NOTES F37) — replace PROFILE/BASE/HTF
  (module names) with `SCALES=[{name,on,lookback}]` (dimensions by lookback, F22/F23). OPEN FORK: pure lookback
  ladder vs keep the base coil detector. Each active scale = one chart module card.
- `[R]` **Run ledger** (`research/runs/`) — every research run logs a scorecard (params + config snapshot +
  metrics + note) to append-only `runs.jsonl`; `analyze_runs.py` compares across runs. Tune measured, not
  blind. Wired: shape_filter, zone_calibration, fib_bias. Complements future session_archive (NOTES F9/F12).
- `[R]` **fib_bias gallery** (`research/gates/fib_bias/make_examples.py`) — shows on real candles what the
  edge test sees: session + fib lines + close→fpos→zone, then the next session's direction. (NOTES F11)
- `[R]` **Strategy map → CONFIG CONTROL PANEL + FLOW EDITOR** (`research/strategy_map`, NOTES F37) —
  `build_map.py`→`strategy_map.html` = every config dial with LIVE / not-wired / no-engine status (reads the live
  config); `build_flow.py`→`flow.html` = an interactive board (drag components from a bottom tray, connect them into
  your execution order, export `flow.json`). Replaced the old static decision-tree.
- `[R]` **Per-config run storage DONE** — runs are stored per config source under `research/runs/reports/<source>/`
  (research vs strategy), never mixed (NOTES F34). (This is the item once planned as a separate `backtest/output/` split.)
- `[R]` **Research reorganized to mirror the engine LAYERS** (2026-07-02) — `research/{structure,gates,setup,
  execution}/` for stage-mapped components + `research/studies/` for pure discovery + `research/chart/`.
  Promotion is now a 1:1 layer move (see ARCHITECTURE "Promotion path"). Map: structure={volume_profile,
  session_anchors}; gates={volatility_filter, profile_shape_filter, zone_calibration, fib_bias};
  execution={entry_trigger, trailing_stops}; studies={volume_buckets, volatility_ranking, session_break_stats}.
  All import paths + `.gitignore` + `BUCKETS_OUT` updated; every script re-verified running; index + per-layer READMEs added.

## Future / parked ideas (documented, deferred — don't get ahead)
- `[ ]` **Session Archive** (`research/studies/session_archive`) — persist every session's full causal
  per-bar record (OHLC + volume + every measurement + %-gain), sequenced/scored/machine-readable and
  **tagged with the research_config it ran under** = "replay written to disk"; merge per day → mine with
  `analyze_*.py` for geometry/scoring patterns / candidate rules. Open Q: extended/off-hours. (NOTES F9, ARCHITECTURE.)
- `[ ]` **Extension context** (`research/gates/extension_context`) — decay / overextension / healthy-extension
  measurement (how far/fast price stretched from value; mean-revert risk), a NEW untested context/bias
  ingredient (like fib). Rides on the Session Archive. (NOTES F9, VISION.)
- `[ ]` **Regime / context gate** (top of the decision tree) — chain the session buckets into a composite
  HTF volume profile + a regime score (consolidation / trending / transitioning + extension state) that
  CONDITIONS setup selection & R:R — explicitly NOT a direction call. Building blocks already exist
  (per-session shape/zone/range/dir); new work = sequence-aggregation + composite profile + scoring. (NOTES F14.)
- `[ ]` **Multi-scale profiler stack** (base ⊂ session ⊂ HTF) — run `base_profile` + `volume_profile` + a
  future HTF composite profiler in parallel (same profile-dict seam, same gates). Each scale plays a role:
  base = tight stop (1R), session = zone/first target, HTF = runway + context. Confluence when they agree.
  **All three built + run together on the chart's 3-card stack (replay-all).** Next: combine the scores
  into a multi-scale confluence input for setup_arm. (NOTES F19)
- `[ ]` **Bar-aggregation engine → best entry timeframe** — intercept X source TFs, aggregate to Y target
  TFs, decipher which timeframes line up best for R:R + scores (the "which TF to enter on" decision from the
  structure's own durations, F21). Deep dive later.
- `[R]` **Replay state panel — BUILT (NOTES F41)** — the trade-replay now shows per-bar arm-gate states
  (session/shape/rr pills), resting orders (buy/sell-stop at the coil edges), and the **trailing stop as a live
  staircase** climbing bar-by-bar, + a state panel (stage / method / mark-to-market R / live stop). Config-driven
  off the run's exported config. The sim exports the per-bar `path` + `arm`; the page renders (F31, no re-sim).
  TODO: continuous DISARM validations/invalidations once setup_arm v2 (mid-window) exists.
- `[ ]` **News filter gate** (`research/gates/news_filter`) — red-folder fundamental events from ForexFactory
  (https://www.forexfactory.com/calendar; manual download → CSV/parquet in ET); `blocked(ts, window=30min)` so
  the backtest/setup_arm skip bars within ±30min of a high-impact release (FOMC/CPI/NFP). A WHEN-to-trade gate
  alongside the vol/session filter; config knob BLOCK_MINUTES + impact levels. Deferred to after setup_arm. (NOTES F33)

---

## Promotion log (research → engine)

| piece | confirmed | from → to |
|-------|-----------|-----------|
| data_feed | 2026-07-01 | data build (research) → `engine/data_feed.py` (loads all NQ+ES parquets; WIRED 1/10) |
| vol_filter | 2026-07-01 | `research/gates/volatility_filter` → `engine/vol_filter.py` (session/hour + optional day-vol gate; WIRED 2/10) |
| session_anchors | 2026-07-02 | `research/structure/session_anchors` → `engine/session_anchors.py` (session hi/lo + breach + boundaries; WIRED 3/10) |
| volume_profile | 2026-07-02 | `research/structure/volume_profile` → `engine/volume_profile.py` (per-session POC + value area; WIRED 4/10) |
| session_state | 2026-07-02 | built directly in engine (the spine) → `engine/session_state.py` (per-bar causal session state; WIRED 5/13) |
| volume_profile (H-L fix) | 2026-07-02 | re-promoted `research/structure/volume_profile` → `engine/structure/volume_profile.py` (spread volume across bar H-L, not close-only; NOTES F5) |
| shape_filter | 2026-07-03 | `research/gates/profile_shape_filter` → `engine/gates/shape_filter.py` (pure `score(profile)`; params live from `cfg.SHAPE`; NOTES F40) |
| zone_calibration | 2026-07-03 | `research/gates/zone_calibration` → `engine/gates/zone_calibration.py` (pure `calibrate(profile)`; `cfg.ZONE`; NOTES F40) |
| target_ladder | 2026-07-03 | `research/setup/target_ladder` → `engine/setup/target_ladder.py` (pure `ladder(scales)`; `cfg.LADDER`; disabled scales drop out; NOTES F40) |
| setup_arm | 2026-07-03 | `research/setup/setup_arm` → `engine/setup/setup_arm.py` (v1 `decide(coil)` = session AND shape_ok AND rr_min; imports engine gates; NOTES F40) |
| — engine WIRED 5/13 → **8/13** | 2026-07-03 | shape_filter / zone_calibration / setup_arm now WIRED in `run_simplicity`. Backtest still runs off research copies (test bench); rewiring the backtest onto engine/ is a later migration. |
