# simplicity — Concept, Lessons, Spec, Findings

*Living notes for the `simplicity` strategy line. Companion to `RANTS.md` (raw idea log).
Started 2026-07-01. Everything lives under `algoproj/simplicity/`, foldered by job.*

---

## 1. What `simplicity` is

A clean restart. The three prior lines — **renko**, **flag_pattern**, **flag_triangle**
(and the sibling **structure_detection**) — were increasingly elaborate machines for
detecting price *structure*. They all converged on the same wall: **detection is easy,
naked directional edge on intraday NQ is not there** (~9 honest negatives across template
flags, dynamic poles, VWAP breakouts, slope-on-swings, regime fans, MTF alignment, HMM,
renko color/MPF). `simplicity` throws out the elaborate detectors and starts from the few
things that actually *survived*, built up from the simplest possible foundation.

**Simpler in theory** = fewer moving parts, each one earned. We add nothing until the layer
under it is proven on real data, out-of-sample, after costs.

---

## 2. What actually survived the prior lines (the seeds we build on)

Only three things were ever un-killed. `simplicity` starts from these, nothing else:

1. **Volume is the one real gradient.** Renko F4: HIGH volume-intensity entry bricks beat
   LOW in both frame pairs, in-sample AND out-of-sample. The veteran's "no need for volume,
   all is in the bricks" was wrong on the data. Volume carries information price alone does
   not. **This is why the first job is a full volume profile of the data.**
2. **Asymmetry / R:R geometry, not direction.** The flag's VWAP-band R:R was net-positive
   OOS (+0.13–0.146R, a plateau across RR 1.5→4, cost-robust) while every *direction* signal
   was ≈0. You don't predict which way — you find setups where *right = big, wrong = small*.
   (Caveat: that one edge is decade-non-stationary; ES is the untested decider.)
3. **Volatility is persistent and forecastable** (HMM: vol-regime autocorr @1d = 0.82, OOS
   monotonic forward-vol) — but it's **magnitude, not direction** → a sizing/risk/filter tool.

## 3. Lessons carried (do NOT relearn the hard way)

- **Edge is the gate.** Prove forward R, OOS, after costs — or it's just a prettier chart.
- **Measure over the real holding horizon in R**, never a fixed tiny forward window (the fwd-6 error).
- **Grow sample by breadth** (markets × timeframes), never by loosening quality thresholds.
- **Non-stationarity is real** — split by decade/sub-period before believing anything (the flag
  R:R flipped sign by decade; NQ data is a back-adjusted continuous contract so %-of-price is invalid).
- **Fills must be honest** — grid/nominal fills faked +0.5R/trade in renko.
- **A component alone is meaningless; coherence is in the relationship** (the 32k lone-pole dump).
- **Descriptor ≠ machine** — a heatmap/profile is a *sensor*, not an edge.

---

## 4. Spec — v0

### Job 1 — hierarchical volume profile (`volume_buckets/`)  [BUILT 2026-07-01]
Take the full NQ history and bucket the timeline top-down, recording **total volume** in
every slice at every level:

```
all  ->  year  ->  quarter  ->  month  ->  day  ->  hour / session
```

- **Span:** 20 full calendar years **2005–2024** (data runs 2005-01-11 .. 2025-01-10; the
  10-day 2025 tail is dropped and 2005 is treated as a full year — it is short its first ~7
  trading days, immaterial). 20 years → 80 quarters → 240 months → **5,040 trading days**.
- **Clock:** everything bucketed on **Eastern (America/New_York)** — NQ liquidity follows the
  US session and every sibling used ET.
- **Sessions** (clean 24h partition, no gaps): `asia` 18:00–03:00 · `london` 03:00–09:30 ·
  `newyork` 09:30–16:00 (US RTH cash) · `close` 16:00–18:00 (post-close + the 17:00 maint break).
- **Volume source rule** (forced by F1 below): all→day use the REAL 1d volume; hour/session
  take that real daily total and SPLIT it by the intraday (5m) proportions within the day
  (winsorized at the day's 99th pct to kill corrupt spike-bars). Absolute hour/session numbers
  are real-contract-*scaled* estimates; their *shape* is real.
- **Run:** `python simplicity/volume_buckets/build_buckets.py` → 9 files in `output/`.

### The full target system (`VISION.md`) + build tracker (`CHECKLIST.md`)
The end goal is a 15-step system (see `VISION.md`): calendar-volatility filter → session
hi/lo anchors → **Volume Profile** between them → POC / Value Area → measure zone %/bars →
calibrate timeframe & risk → reject scattered profiles → node entry → Fib bias →
session-break stats → Value-Area breakout w/ volume → aggressive trailing stops. Progress is
tracked in `CHECKLIST.md` (scratch off as we go).

**Runtime model (2026-07-02, refined with the user).** The strategy is a **live, bar-by-bar range-
breakout engine** (full spec in `ARCHITECTURE.md`): a **session-state spine** tracks current + next
session (live hi/lo, time-in/until); every component recomputes on the session's **bars-so-far** →
causality is enforced by construction (backtest passes bars ≤ now; same code runs live). Setups
**ARM/DISARM on stacked confluence** (shape + fib + zone size/tightness + timing), resting orders
before the next open, aggressive trailing on the way out. **The edge is confluence + R:R geometry, not
prediction** — the isolated components test flat (diagnostics, not verdicts); judge the system *fully
wired*, since the mechanics (stop placement, resting orders, breakeven, trailing, DCA) are the substance.

### Structure + workflow  (2026-07-01)
**research-first.** Every idea is built and tested in `research/` first; a piece is only
solidified and **promoted into `engine/`** (clean, fast, live-API-ready) after the **user
explicitly confirms it — the user decides when.** research = discover, engine = execute.
`strategy_config.py` is the single source of truth (project map, data, era/filter, TBD
signal/entry/exit/risk slots, execution costs). Layout:
`research/{volume_buckets, volatility_ranking, volatility_filter, + placeholder step folders}`,
`engine/` (data_feed + vol_filter promoted so far).

**See `ARCHITECTURE.md`** for the full configs → engine → outputs wiring: **two selectable configs**
— `strategy_config` (concrete/real) and `research_config` (run/testing: ACTIVE_FILTER, starting
balance, dates — **built**) — feeding **one engine**; the chart has a real|research selector; and
a future separate `backtest/` folder stores equity-curve PNGs in different places per config
(research vs real) so they never mix.

### Job 2 — calendar volatility filter + ranking (`research/gates/volatility_filter`, `volatility_ranking`)  [BUILT 2026-07-01]
`build_buckets.py` now also computes four volatility stats per slice at every level (Mean Vol %,
HV %, Vol Range %, Avg Daily Range %) from OHLC — shown in the dashboard as charts + tables.
`volatility_filter/vol_filter.py` = the WHEN-TO-TRADE gate: filters **intraday bars by session
and/or hour** (the core — trade inside high-activity windows) plus an **optional daily vol-regime**
gate, each **toggleable in config** (`FILTER_SESSION` / `FILTER_HOUR` / `FILTER_DAY_VOL`, ANDed).
`mask(index)` → boolean over any intraday index; `passes(ts)` for one bar. (Reshaped from a
daily-only gate 2026-07-01 — filtering belongs at session/hour, not just per-day.)
`volatility_ranking/rank_volatility.py` = structured most-vs-least-volatile output per level. Status:
**PROMOTED to `engine/vol_filter.py`** (2026-07-01, WIRED 2/10; self-contained via `data_feed`);
the research copy stays for testing/variants.

**Filter variants — the hypothesis test (`volatility_filter/filter_variants.py`).** The single
hypothesis we must confirm: **the strategy performs better in high-volatility / high-activity
periods.** Locking `tradeable = high` alone doesn't prove it — we need its opposites to compare.
So a bank of variants over the low/med/high regimes: `all` (baseline), `high` (the claim),
`medium`, `low` (opposite), `high_medium`, `not_high` (complement of high), `extremes`. When the
strategy emits per-day R, `evaluate()` reports expectancy under each variant **and vs a Monte-Carlo
RANDOM same-size baseline** (a null of random day-samples). **Critical: H is real only if `high`
beats RANDOM (top tail), not merely `low`.** If `high` beats `low` but not random, the "edge" is
just that low-vol days are unusually bad (a survivorship-flavored artifact), not that high-vol is
good. Descriptive baseline already shows the volume↔vol link: high-vol days average **~582k**
contracts vs low-vol **~293k** (~2×), but that's context, not the edge — the real test waits for
the strategy.

---

## 5. Findings log

### F1 — the volume-data finding: only 1d volume is real (2026-07-01)
Before building anything on volume, checked the volume column across timeframes. **Only the
1-day parquet has trustworthy volume** (~381k contracts/day, matches real NQ). **Every
intraday parquet is corrupt in absolute terms:**

| tf | median vol/bar | day-agg vs real 1d |
|---|---|---|
| 1m | 3,443 | **1,273×** inflated |
| 5m | 150,165 | **4,601×** |
| 15m | 474,376 | **17,249×** |
| 60m | 21,782,074 | **41,124×** |

Worse, the inflation is **not a fixable unit scale** — the per-day 5m/1d ratio itself varies
602×–9,769× (**CV 1.59**), with absurd single bars (a 1.008-billion-contract "minute" on
2022-11-30). So intraday absolute volume and per-day intraday proportions are unreliable.

**BUT the aggregate intraday *shape* is clean** — summed over 20yr the ET-hour profile is a
textbook RTH curve and the 17:00 ET maintenance break reads ~0:

- 09:00 ET **15.8%**, 10:00 ET **22.0%** (RTH open = the peak), midday dip 12–13:00 ~8%,
  afternoon ramp to 15:00 **12.9%** (close), overnight hours each <0.3%, 17:00 ET **0.009%**.

**Consequence for the whole project:** treat intraday volume only as a **shape/proportion**,
never an absolute; anchor any real-contract number to the 1d volume. This is why `build_buckets`
splits the real daily total by winsorized intraday shares. (Prior lines used volume only as a
*relative intensity* vs a rolling baseline, which is why they weren't obviously broken by this.)

### F2 — the volume hierarchy itself (2026-07-01)
20yr total = **1,919,659,060 contracts** over 5,040 trading days. Two clean structural facts
fall straight out of the buckets:

- **Volume tracks crisis + the modern regime.** By year: 2008 GFC **5.49%**, then a decline
  through the low-vol bull to the 2013 trough **2.94%**, then a strong secular rise from 2018
  (**6.15%**) to the 2022 bear peak **8.71%** (2023 8.25%, 2024 7.88%). The last 7 years hold
  ~50% of all 20yr volume — recent NQ is a different, much heavier-traded market (echoes the
  non-stationarity lesson).
- **RTH dominates, but less than first thought.** With REAL intraday volume (F4 rebuild) the
  session split is `newyork` **77.7%**, `london` **10.0%**, `close` **5.9%**, `asia` **4.6%** —
  overnight carries real volume the earlier anchored-shape estimate (89/3/7/0.6) understated. US
  session still leads, but London/Asia aren't negligible.

### F4 — the intraday volume IS real; the parquet builder corrupted it (2026-07-01)
**Root cause found + source located.** The corruption in F1 was NOT missing data — the raw
TradeStation source (`C:\Users\jakers\Documents\TradeStation 10.0\Data\nq120.txt` 1m /
`nq520.txt` 5m / `nq6020.txt` 60m / `nq1day20.txt` daily, 2005-01-11..2025-01-10) stores
intraday volume as **two columns, `Up` and `Down`** (up-tick vs down-tick volume). The parquet
builder **concatenated them as strings** instead of summing: `Up=5, Down=108 -> "5108"`;
`Up=100008, Down=968 -> "100008968"` (the fake 100M bar). **Real intraday volume = Up + Down.**
Verified: 5m Σ(Up+Down) per day = **96-99% of the daily `Vol`** column every day; per-bar
median 321, max 44k (sane). So the Volume Profile (VISION 4-6, volume-at-price) IS buildable —
from the TradeStation source, not the current parquets. **DONE (2026-07-01):** `data/build_data.py`
rebuilds clean parquets from the TradeStation source (`volume = Up + Down`) into
`data/NQ/` and `data/ES/` (ES 2005-2025, for future cross-instrument breadth/OOS);
`strategy_config` points at them; buckets re-run on real intraday volume (dropped the
"real-daily x shape" workaround). Effect: session split shifted from the shape-estimate
(RTH 89%) to REAL (RTH 77.7%, overnight higher) — see F2. Parquets are gitignored (big);
regenerate with `build_data.py`. Deps pinned in `requirements.txt`.

### F3 — volatility non-stationarity: cut the calm early decade (2026-07-01)
The first decade is far calmer than the recent one — mean annualized HV **2005-2014 = 7.72%**
vs **2015-2024 = 15.48%** (recent is **2.01×**), same story in avg daily range (0.73% → 1.39%).
Including 2005-2014 in any volatility-based selection dilutes it, so `ERA_START_YEAR = 2015`
cuts it (configurable). Most-volatile slices: 2020 (COVID; March HV 62.8%, the 16th ranged
10.3%) and 2022 (bear); least: 2017 (calmest, HV ~6.7%). High-vol months carry ~2× the volume
of low-vol months — volume and volatility travel together, as expected.

Outputs (`volume_buckets/output/`): `bucket_all.csv` (1), `bucket_year.csv` (20),
`bucket_quarter.csv` (80), `bucket_month.csv` (240), `bucket_day.parquet` (5,040),
`bucket_hour.parquet` (122,341 day×hour), `bucket_session.parquet` (21,499 day×session),
`profile_hour_of_day.csv` (24), `profile_session.csv` (4).

**Viz (2026-07-01):** one self-contained dark HTML dashboard, `output/volume_dashboard.html`,
regenerated from the buckets by `make_dashboard.py`. Top = four overview charts (year bars /
month area / hour-of-day profile / session bars); below = **detailed tables of every bucketed
number** (Year 20 / Quarter 80 / Month 240 / Day 5,040 / Hour-of-day 24 / Session 4), each
scrollable with exact volume + % of all. (A click-to-drill-down variant was built and then
removed — the user preferred the flat overview-plus-tables layout.)

### F5 — volume profile: spread volume across each bar's H-L, not close-only (2026-07-02)
The first profile binned each 5m bar's whole volume onto its **close** price in 2-pt rows. A single
high-volume bar (e.g. the NY open) then spiked one bin and **stole the POC** from a larger but
diffuse consolidation. Real example — `2024-07-11 newyork`: **55.8%** of volume sat in the bottom
third (a tight base after an impulse down), yet POC read at the TOP (pos 0.95), VA 83% of range →
scored "foggy 11/100". Fix: distribute each bar's volume across every bin its **[low, high]** spans
(overlap-weighted). POC then lands where volume truly is (0.16, the base), VA tightens to 56%.
Effect on 2020-2025 gate survival: clean+R:R **9.4% → 14.3%**; NY R:R-ok **32.7% → 54.1%**; POC-vs-mid
back to ~0.50 (balanced). The pre-fix survival numbers are void. **Re-promoted to
`engine/structure/volume_profile.py` 2026-07-02** — research + engine now in sync.

### F6 — the zone is the BASE, not the whole session (future parallel study) (2026-07-02)
`2024-07-11` exposed a deeper point: profiling the **whole session** lumps an impulse leg + a tight
base into one range, so a genuinely clean base ("clean move down, tight sideways consolidation at the
low" — a structure the user likes) still reads part-directional. The real tradeable **zone is the
current tight base** that forms *after* a leg (= the pole+flag structure from the flag work): stop =
base edge (tight 1R), runway = the leg/range (the room) — the LTF-tight-stop / HTF-runway R:R made
real. PLAN: build a **base/consolidation detector** as a SEPARATE engine (`base_profile`) and study it
**side-by-side** vs the current whole-session `volume_profile` on the chart's per-session module cards;
promote whichever reads better. Deferred deliberately — it shifts the strategy more than we want right
now. shape_filter + zone_calibration would then score the detected base, not the session.

### F7 — per-session module cards on the chart (2026-07-02)
Built: Indicators → `modules` on, click any session (NQ 1m/5m) → a floating card with that session's
crisp mini volume-profile (candles + two-tone bars + POC/VA, examples-quality because zoomed), its
timing (open/close/duration/next session + gap, ET), and its shape + R:R scores. Solves two asks at
once — the profile finally looks crisp on the chart (per-session, zoomed) and you can see how each
session hands to the next. Same card is the seed of the planned replay state panel. Data enriched in
`build_chart_data.py` (shape/zone/next per profile); rendered in `make_chart.py` (`#demo` auto-opens).

### F8 — chart REPLAY v1 + "chat about" enriched (2026-07-02)
Replay a session bar-by-bar: the module recomputes the volume profile + shape + zone on **bars-so-far**
(causal) and the scores EVOLVE as price moves — the live/backtest engine model made visual. Ported
`volume_profile` / `shape_filter` / `zone_calibration` to JS (`computeProfile/Shape/Zone` in make_chart)
so the recompute runs in-browser; candle data now carries per-bar volume. Controls in the module:
|< < play > >| + scrubber + speed; a gold "now" line tracks on the main chart. Demo: `2025-01-10 NY`
reads 33/100 R:R 1.99 at bar 42/78 but decays to 26/100 R:R 1.58 by the close (value area widened).
"chat about" markdown now includes EVERYTHING in one block: timing, range/VA, shape, zone, top-10
volume nodes, and the full per-bar OHLC+Volume table.

**PLANNED (write-it-down, wire later):** replay should also show the **state-machine states it passes
through** — ARM / DISARM, setup qualified/rejected, validations/invalidations — as they flip during the
session. Those gates (`setup_arm` etc.) don't exist yet, so v1 only shows the profile/shape/zone
recompute; the state-transition panel layers onto this same card once the gates are built. This IS the
replay "modular state panel" from ARCHITECTURE — the session module card is its seed.

### F9 — Session Archive + extension context (FUTURE — documented, not built) (2026-07-02)
**The idea (user):** persist, per session, the FULL causal time-series the replay tool computes — for
every bar: timestamp, OHLC, volume, PLUS every measurement made at that bar (running POC/VA, shape
score + components, zone geometry/R:R, % gain in-session so far, live hi/lo, time-in/until) — all
sequenced, timed, scored, machine-readable, and TAGGED with the exact `research_config` + settings it
ran under. It's "replay, written to disk" — the machine-readable twin of the chart replay: an entire
session stepped through, but saved as code instead of watched.
Then **merge time**: bucket per day, stitch sessions across history → a queryable substrate. Run
analytics scripts on it to mine geometry/scoring patterns and maybe **derive more rules** (or confirm we
don't need them — "maybe we notice something interesting"). Open question: how to treat extended / off
hours (the gap between sessions).
**New signal it enables — the contextual EXTENSION element:** decay / overextension / healthy-extension.
How far/fast has price stretched from its value/base, and is that a *healthy* trend extension or an
*overextension* (mean-revert risk)? — decaying over time. A NEW, UNTESTED ingredient (like `fib_bias`):
a context / sizing / bias input, NOT a direction predictor. It would be one of the per-bar measurements
recorded in the archive, so it's minable alongside everything else.
**Where it fits:** `research/studies/session_archive/` — a builder (`build_archive.py`) that reuses the
engine components run INCREMENTALLY (same causal math as replay) → structured parquet (one row per bar,
keyed by sid + bar index) + a session-level summary table, config-tagged; then `analyze_*.py` on top.
The extension signal gets its own component (`research/gates/extension_context/`) once explored.
**What it adds to the strategy:** a data substrate for pattern discovery + a new context measurement.
Deferred deliberately (don't get ahead) — revisit after the core gates exist and can feed it.

### F10 — research reorganized to mirror engine LAYERS (2026-07-02)
research/ was a flat pile of per-component folders while engine/ was organized by job-layer — the
inconsistency made promotion feel fuzzy. Fixed: research/ now mirrors engine —
`structure/` (volume_profile, session_anchors), `gates/` (volatility_filter, profile_shape_filter,
zone_calibration, fib_bias), `execution/` (entry_trigger, trailing_stops), `setup/` (future),
`studies/` (pure discovery: volume_buckets, volatility_ranking, session_break_stats), `chart/` (viewer).
Promotion is now a **1:1 layer move** (`research/gates/X` → `engine/gates/X.py`). All import-path
bootstraps (+1 dirname to reach simplicity/), cross-layer data paths, `build_chart_data` sibling refs,
`.gitignore`, `strategy_config.BUCKETS_OUT`, and every MD path reference were updated; each script was
re-run to verify. Added `research/README.md` (the layer map) + a README per layer. See ARCHITECTURE
"Promotion path".

### F11 — fib_bias: NO directional edge (2026-07-02)
Tested the UNTESTED VISION ingredient honestly (like session_break_stats): for each session, bucket
its close by fib position in range, measure the NEXT session's direction vs base rate. 7,764 sessions
(era >= 2015): base P(next up) = 54.3%; per-zone P(next up) = 51.8-56.4% (lifts 0.95-1.04), spread
max-min just 4.6pts, NO zone beyond 2-sigma. **Fib carries no directional edge on NQ** — dog that
didn't bark, consistent with the core thesis (direction isn't predictable; hunt R:R geometry). So
`setup_arm` gets NO fib direction gate; the fib chart overlay stays as geometry-only visual reference.
Gates confirmed for setup_arm so far: shape_filter (quality) + zone_calibration (R:R) + vol/session
timing. Direction stays unpredicted by design.

### F12 — run ledger: scorecards bound to configs/params (2026-07-02)
Before tuning anything, built `research/runs/` so we never change blindly or lose info. Every research
run appends a SCORECARD to append-only `runs.jsonl`: run_id + git commit + the component PARAMS it used
+ a strategy_config snapshot + the output METRICS + a note. `runlog.record(kind, params, metrics, note)`
enrolls a script; each tunable script now exposes its knobs in one PARAMS block (shape_filter WEIGHTS/
TIGHT_DEN/PROM_DEN/SHAPE_OK; zone RR_MIN/TF_BANDS; fib EDGES). `analyze_runs.py` reads the ledger and
shows params+metrics per run in order → a before/after tune is two rows you diff by eye. Baselines
seeded (git 4db5fda78): shape median 39 / ok 21.1%; zone median R:R 1.85 / ok 44%; fib base 54.3% /
spread 4.6pts. This is per-RUN provenance; the future session_archive (F9) is the per-BAR record —
together nothing is lost. How the tuning loop works: run (logs baseline) → change a PARAM → run with a
note → `analyze_runs`.

### F13 — the fib_bias isolated test is measuring an arbitrary construct (methodology) (2026-07-02)
User's correction, and it's right: the F11 test bolts fib to endpoints that are essentially made-up —
"where the session CLOSE sits in the range" -> "next session's open->close direction". Those points
have no structural relationship to the strategy's real mechanics (an armed range-breakout setup: entry
at a node, stop at the range/VA edge, R:R geometry, aggressive trail). So F11's "no directional edge"
is NOT a verdict that fib is worthless — it's a **diagnostic** that fib-detached-from-a-setup predicts
nothing. Exactly the project's standing lesson: *a component alone is meaningless; coherence is in the
relationship; isolated components test flat — diagnostics, not verdicts* (the 32k lone-pole dump).
The TRUE test of fib bias only exists IN CONTEXT — once `setup_arm` + entry exist, ask "does the fib
reading improve THIS setup's R:R outcome / entry quality?", not "does fib position predict next-session
direction." Same caution applies to shape/zone isolated numbers: judge the system *fully wired*. So:
DO NOT drop fib on the strength of F11; keep it as chart geometry and defer any bias judgment to
in-context testing after the setup exists. (This is also why we hunt R:R geometry, not direction.)

### F14 — chained-session REGIME / CONTEXT gate (big FUTURE idea; plan carefully) (2026-07-02)
User's idea: we've bucketed ALL of price into per-session records (hi/lo, range%, direction, shape,
POC/VA, volume, R:R). CHAIN them across the timeline -> (a) one composite / higher-timeframe volume
profile (a giant sideways heatmap = multi-day/week value + naked POCs = a real structural reference),
and (b) a REGIME score from the SEQUENCE of session characters: e.g. a tall directional session then a
tight consolidation = impulse+base; a run of overlapping balanced ranges = rangebound; successive
higher session hi/lo = trend. It sits at the TOP of the decision tree as a context/bias gate that
COLORS everything downstream.
My take (kept honest): frame it as REGIME / CONTEXT, NOT a direction call. "consolidation vs trending
vs transitioning" + extension state (healthy vs over-extended, F9) is the defensible, valuable part; a
"bullish/bearish" DIRECTION score is the exact trap we keep hitting (fib, session-break, poles all died
there — direction isn't predictable on NQ). So the regime gate should CONDITION setup selection + R:R
(which setups arm, how wide the target, fade vs continuation), NOT pick trade direction. The composite
HTF-profile half is solidly real (longer-horizon value / naked POCs are genuine references). Validate
IN-CONTEXT (F13): judge whether regime-conditioning improves the WIRED setup's outcomes — never the
regime score in isolation vs next-direction. The building blocks already exist (per-session shape /
zone / range / dir); the new work is the sequence-aggregation + composite profile + the scoring.
Connects to base_profile (F6), extension_context (F9), session_archive (F9/F12). Likely lands as a new
top-of-tree layer (a `research/context/` or `research/gates/regime`) feeding setup_arm. Deferred.

Also built (2026-07-02): `research/strategy_map/` — a decision-tree map of the whole strategy (the
"see it on a tree/neural-net" request), generated from the pipeline, colored by build status.

### F15 — composite profile = the SAME scoring machinery at a larger scale (refines F14) (2026-07-02)
User sharpened the composite-profile half of F14, and it's the strongest part: combine a week (N
sessions) of volume profiles into ONE composite profile, then run the SAME shape_filter + zone_calibration
on it — a weekly clean/foggy score + weekly POC/VA + weekly R:R. Two powers fall out:
  1. SCALE-DEPENDENT R:R. At the bottom (or top) edge of a massive weekly consolidation, the local stop
     is still tight (nearby structure) but the ROOM is the whole weekly range -> R:R measured at the
     composite scale is far larger than the same setup vs its session alone. = the LTF-tight-stop /
     HTF-runway mechanism extended one level up. Where you sit within the composite range sets the R:R.
  2. MULTI-SCALE CONFLUENCE = a bigger setup score. A setup clean/good at BOTH the session scale AND the
     weekly composite scale is much higher-conviction. Same code composes across timeframes -> stack the
     scores. This is real multi-timeframe volume-profile confluence, built from parts we already have.
Still CONTEXT/GEOMETRY, not direction: "bear consolidation" is a structural label; the edge position gives
R:R asymmetry BOTH ways (long has room up / breakdown short has room down) — we score geometry, never
predict the break (thesis intact). Open design Qs: window (fixed week vs rolling vs adaptive), off-hours
gaps (F9), and — per F13 — validate IN-CONTEXT (does the multi-scale score improve the WIRED setup's
outcomes?), never in isolation. Deferred; this is how F14's composite-profile piece actually gets built.

### F16 — shape "tightness" was INVERTED; replaced with a peaked va_pct curve (2026-07-02)
User caught it in replay (chat_about.md): a tight coil scored only ~47 and the score ROSE as the
breakout began. Traced to the 40%-weighted tightness term `tight = 1 - va_pct/80`, where
va_pct = VA_width / session_range. As price breaks out the range expands -> va_pct shrinks -> tight
rises -> the score perversely REWARDED range expansion. Worse, its max (tight=1) sat at va_pct->0,
which is a spike-and-run, NOT a consolidation; a clean bell coil sits at va_pct ~35-45 and only earned
~0.5. FIX: tightness is now a PEAKED curve -- rises 0->1 as va_pct goes 0->TIGHT_PEAK(40), falls 1->0
as va_pct goes 40->TIGHT_HI(85). Clean coil peaks; a spike (low va_pct) AND a scatter/bimodal (high
va_pct) both score low. Mirrored in chart JS computeShape so REPLAY matches; chart rebuilt.
Verified: flagged coils 47->66 and 48->59; bimodal day stays foggy 25->29; inversion gone
(coil->breakout->thrust OLD 49->56->62 RISES, NEW 67->61->49 FALLS -- coil is now the peak). Ledger
(git f0e39d167 -> new run): median score 39->52, shape_ok 21%->59%.
SIDE EFFECT to tune next: 59% pass is now too loose -- SHAPE_OK (still 50) needs re-raising (~62?) to
restore a selective gate; separate logged tune. The CURVE is the fix; the THRESHOLD is the next knob.
This is the first run-ledger tune: baseline vs peaked-tightness-curve both live in runs.jsonl.

### F17 — shape prominence made breakout-robust (POC / mean of value-area bins) (2026-07-02)
Second half of F16: user still saw the score RISE as price broke out, even after the tightness fix.
Traced to the peakedness term prominence = POC / mean(ALL bins): the breakout leg expands the range,
adding many thin NONZERO bins that dilute the mean, so POC/mean inflates (demo: empty bins alone drove
prominence 2.86->5.20 = +16 score pts; real Dec-30 london 2.23->3.69). Same disease as the close-only
POC bug and the tightness bug -- a metric normalized against the whole EXPANDING range. Fix: prominence =
POC / mean of the VALUE-AREA bins only; the breakout leg's thin bins fall OUTSIDE the VA so they can't
dilute the denominator. Recalibrated PROM_DEN 4->2 (VA-based prominence ~1.2-2.3 vs old ~1.5-3.2), chosen
so peakc's spread matches the old one -> change ISOLATED to breakout-robustness (ledger: median 52->52,
shape_ok 58.6%->58.9%). Mirrored in chart JS computeShape; chart rebuilt. Verified: synthetic coil vs
coil+breakout shape FALLS 74->59 (was rising), prominence near-flat 1.61->1.8 (was 2.86->5.20). Deep cure
still base_profile (F6): profile the COIL not the whole session and none of these range-normalization
bugs can occur. THRESHOLD still pending: SHAPE_OK 50 (~59% pass) -> re-raise once user re-checks in replay.
