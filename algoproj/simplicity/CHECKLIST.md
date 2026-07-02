# simplicity — Build Checklist

Scratch off as we go. Mirrors `VISION.md` (the full 15-step system) in build order.
Companion: `strategy_config.py` (single source of truth), `NOTES.md` / `RANTS.md`.

## Status legend
- `[ ]` not started
- `[~]` in research — work in progress
- `[R]` **built in research**, working & verified
- `[C]` built — **awaiting your confirmation** to solidify & promote to `engine/`
- `[E]` **confirmed & promoted to `engine/`** (live-ready)

**Promotion rule:** nothing moves `research/` → `engine/` without your explicit OK.
**You say when.** Claude never promotes on its own.

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
- `[ ]` **setup_arm — the confluence ARM/DISARM engine** — stack gates (shape + fib + zone size/tightness + timing) → ARM (place resting orders) / DISARM (pull them) on validation/invalidation, continuously re-evaluated
- `[ ]` Causality rule enforced: components only see bars ≤ now (no look-ahead) — same code live + backtest

## Phase 6 — Entry & exit mechanics (the substance — R:R geometry, not prediction)
- `[ ]` Entry: **resting orders before the next open** — breakout stops beyond the range and/or fades at the range edge (bias-gated) — `research/execution/entry_trigger`
- `[ ]` Value-Area breakout + volume confirmation (the trigger); entry TF smaller than the range TF
- `[ ]` Stop placement (range/VA edge = invalidation) · breakeven logic · DCA-into-range (decide)
- `[ ]` Risk / position sizing — `strategy_config.RISK` + `STARTING_BALANCE`
- `[ ]` **Aggressive volume-based trailing stop** — trail down/up as the move confirms — `research/execution/trailing_stops`

## Phase 7 — Measurement & backtest (FUTURE — blocked on Phases 5-6)
- `[R]` **Per-session module cards** — Indicators `modules` on, click a session (NQ 1m/5m) → floating card
  with that session's crisp mini volume-profile + timing (open/close/duration/next+gap) + shape/R:R scores.
  Solves crisp-VP-on-chart + session hand-off view; = the seed of the replay state panel — `research/chart`
- `[~]` **Chart REPLAY mode** — v1 built: step a session bar-by-bar (|< < play > >| + scrubber + speed),
  the module recomputes profile/shape/zone on **bars-so-far** (causal, JS port) so scores evolve as price
  moves; gold "now" line on the chart. **Pending (gates first):** the **modular state panel** on this same
  card — live hi/lo, fib bias, gate strengths, ARM/DISARM + the validation/invalidation that flipped it —
  layers on once `setup_arm` etc. exist. The engine's visual frontend = the backtest unfolding — `research/chart`
- `[ ]` Trades on the chart — BUY/SELL markers showing exactly where trades were taken
- `[ ]` Equity curve (+ drawdown)
- `[ ]` Walk-forward testing with detailed WF labeling (train/test folds, anchored)
- **Prior art (don't reinvent):** you already built all of this in `algoproj/webui` (Flask+PyWebView+ECharts:
  Analyzer/Runs/Strategies/WFO; `/api/run/chart` = candles+BUY/SELL markers, `/api/run/equity` = equity+DD,
  `/api/wfo` = walk-forward) + the original Streamlit `algoproj/_archive/app`; engine =
  `algokit/{wfo,optimize,validation,significance,runs}`. simplicity's `backtest/` reuses this. See ARCHITECTURE.md.

## Cross-cutting
- `[~]` **Fresh TradingView lightweight chart** (`research/chart`) — rewired to simplicity data; multi-timeframe (NQ+ES); OHLC cached to JSON, load max ~2000 bars/TF for speed; side menu showing which instrument/TF/config is loaded (clean format); overlay the filter-selected periods. No old flag-strategy baggage.
- `[R]` Config filter selector `ACTIVE_FILTER` (pick which variant tv/backtest uses) — `strategy_config`
- `[R]` Config split DONE — `research_config.py` (run/testing: `ACTIVE_FILTER`, `STARTING_BALANCE`, dates) re-exports `strategy_config`; removed `ACTIVE_FILTER` + dead `TRADEABLE_REGIMES` from `strategy_config` (no duplication)
- `[R]` Chart config selector (real | research) — top-bar toggle switches vol-day overlay + sidebar to that config
- `[R]` **Run ledger** (`research/runs/`) — every research run logs a scorecard (params + config snapshot +
  metrics + note) to append-only `runs.jsonl`; `analyze_runs.py` compares across runs. Tune measured, not
  blind. Wired: shape_filter, zone_calibration, fib_bias. Complements future session_archive (NOTES F9/F12).
- `[R]` **fib_bias gallery** (`research/gates/fib_bias/make_examples.py`) — shows on real candles what the
  edge test sees: session + fib lines + close→fpos→zone, then the next session's direction. (NOTES F11)
- `[R]` **Strategy map** (`research/strategy_map`) — decision-tree / neural-net view of the whole pipeline
  (context → spine → structure → gates → setup_arm → execution), colored by build status; generated from the pipeline. (NOTES F14)
- `[ ]` `backtest/` folder (separate top-level, FUTURE): run engine with a chosen config → equity-curve PNGs stored per-config (`output/research/` vs `output/real/`). Blocked: no risk mgmt / returns yet — visualization only for now.
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
  base+session already run together on the chart card; HTF composite is the missing third. (NOTES F19)
- `[ ]` **Replay state panel** — ARM/DISARM + validations/invalidations on the session module card, once `setup_arm` gates exist. (NOTES F8.)

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
