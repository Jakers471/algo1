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

### F18 — base_profile built + side-by-side study vs volume_profile (2026-07-02)
Built the parallel profiler (F6) WITHOUT touching the whole-session one. `base_profile` detects the tight
base via a causal contraction scan (band = BAND_MULT=5 x median bar-range; walk back from the last bar
while the window range stays within band; MIN_BARS=8) and profiles ONLY that window -- so the impulse leg
/ breakout are excluded and the range-normalization bugs we patched (F5/F16/F17) can't arise. Key design
win: it emits the SAME profile-dict shape as volume_profile, so shape_filter + zone_calibration score it
with ZERO changes -- the profile dict is the seam; the gates don't care who produced it. Proves the
"build a second version, don't rewrite" model.
Findings (make_compare.py, 2024): base detected in 78% of sessions (median = 27% of session bars). On
trend/impulse days the WHOLE session reads foggy (correctly -- it's a trend) but the coil INSIDE reads
clean: shape 46->80, 42->72, 40->69 (+29..+34), and crucially risk 1R collapses ~3-4x (59.6->15.7pt,
63.8->12.3pt) because you risk against the tight coil not the trending range = the LTF-tight-stop geometry
made real; entry TF often drops 5m->1m. Already-clean sessions are a wash (-1) -- no harm. Logged to the
run ledger (kind=base_profile). PROMOTE-PENDING (user decides): base could replace volume_profile, or
COMPLEMENT it (multi-scale confluence, F15: score both). Still needs in-context validation (F13) before live.

### F19 — multi-scale nested structure: base < session < HTF (the three timeframes) (2026-07-02)
User's insight after the base companion card: base_profile and volume_profile COMPLEMENT each other --
two scales of the SAME price structure, a smaller one (the base/coil) nested INSIDE a larger one (the
session). Run them as dual profilers simultaneously and you locate the small structure within the large.
Add the HTF composite (F14/F15: days/weeks combined) and you get a THIRD scale: base (smallest, ~min-hrs)
< session (medium, hrs) < HTF composite (largest, days/weeks) -- three nested timeframes of the same
volume-profile machinery. The profile-dict is the seam: the SAME shape/zone gates score all three.
Sharpening (my add): the scales don't just stack for confluence -- each plays a DIFFERENT ROLE in the
trade. BASE = the entry trigger + tight stop (1R, small). SESSION = the immediate zone the base sits in
(first target / the range being broken). HTF = the context/regime + the runway (big target) + "at value
or extended". So a trade takes its STOP from the smallest scale and its RUNWAY from the largest -- the
LTF-tight-stop / HTF-runway mechanism generalized across three scales. Confluence = when the scales AGREE
(clean base, at a session edge, at HTF value) = the A+ setup; setup_arm reads all three. Still geometry /
context, NOT direction (scales give R:R asymmetry + conviction, not a direction call); validate the stack
IN-CONTEXT (F13), never in isolation. Architecture: same engine, multiple PROFILER WINDOWS running in
parallel, each emitting a profile dict -> scored -> combined. base+session already run together on the
chart card; the HTF composite profiler is the missing third (deferred).

### F20 — all gate params centralized in strategy_config (source of truth) (2026-07-02)
Per user (stressed): config must be on par with everything we tune AND promote cleanly to engine without
breaking. Moved every tunable knob into strategy_config: PROFILE (row/va), SHAPE (weights, tight_peak/hi,
prom_den, single, shape_ok), ZONE (rr_min, tf_bands), BASE (band_mult, min_bars), HTF (days, bins), FIB
(edges). research modules + the promoted engine volume_profile READ these dicts; a future promoted engine
gate reads the SAME dict -> identical behavior, clean promotion, nothing breaks. runlog.config_snapshot
captures them (ledger config == what produced the run). build_chart_data injects them into the manifest;
the chart JS (computeShape/Zone/Base) reads them so REPLAY/scoring stay in sync with config. Tune in ONE
file, re-run, compare in the ledger.

### F21 — durations -> best entry timeframe (needs a bar-aggregation engine) (FUTURE) (2026-07-02)
User's idea: the DURATIONS we measure per scale (base ~min-hrs, session ~hrs, HTF ~week) are exactly what
we need to pick the most geometrically-concise TIMEFRAME to enter on. Fully building it needs a BAR-
AGGREGATION ENGINE: intercept X source timeframes, aggregate to Y target timeframes, then let the engine
decipher which timeframes line up best for R:R + scores -> the "which timeframe should we enter on"
decision, derived from the structure's own dimensions instead of a fixed entry TF. Ties into
zone_calibration (already maps height%->entry TF crudely) + the multi-scale stack (F19). Deep dive later,
not rushing -- just captured. Likely a new tool (research/tools/bar_agg or an engine/feed extension)
feeding the profilers at chosen TFs.

### F22 — geometric scale-ladder: N nested profiles + a target ladder (FUTURE VISION) (2026-07-02)
User's generalization of the 3-scale stack (F19): use ~6 GEOMETRICALLY-scaled time dimensions instead of
3 fixed ones -- each lookback a constant ratio (xr) of the one below (bars 20->60->180->540->1620->4860,
~30m->2h->8h->1.5d->1wk->1mo). Why geometric: market structure is ~self-similar across scales, so a
geometric ladder gives EVEN coverage in log-time and matches how consolidations NEST inside consolidations
(HTF > MTF > LTF, "compressed onto each other" = the same price at N resolutions). Each scale runs the same
profile machinery (the dict seam) -> a stack of nested value areas.
The trade geometry falls out of the ladder:
  - STOP from the smallest ALIGNED scale (tight 1R).
  - TARGETS = a LADDER: each larger scale's VA edges / naked POCs are scale-out targets (a stack, not one).
  - ENTRY TF = the scale where the current coil is tightest/cleanest (ties to F21 bar-aggregation).
  - R:R = (distance to a larger-scale target) / (small-scale stop) -- naturally huge at the edge of a big
    nested range with a tight coil.
Geometric scaling keeps PARAMS tiny (one ratio + a count define the whole ladder) -> less overfitting.
New pieces vs F19: (a) geometric ladder design, (b) NESTING/containment test (small VA inside large VA),
(c) the target LADDER, (d) entry-TF from the tightest coil. Caveats: still GEOMETRY not direction (F13);
"nested" needs a formal containment rule; more scales = more compute/overfit risk; validate in-context.
Visualize as an N-card scale ladder (module stack extended) or nested VA boxes on the chart. Deferred --
the end-state of the base/session/HTF direction; build after the 3-scale confluence + setup_arm exist.

### F23 — scales must be config-TOGGLEABLE + proportions configurable (2026-07-02)
Requirement (user): every scale/dimension must be independently ON/OFF in config -- backtest or trade on
ONE dimension, or any subset, by shutting off the other scales' gates. And the geometric ladder's
PROPORTIONS (ratio r + count, each scale's lookback) must be easily editable in config. So when the
geometric scale-ladder (F22) is built it's driven by a config block, e.g. SCALES = [{name, on, lookback,
...}] -- enable/disable per scale + tune the ratio, all in strategy_config (source of truth, F20).
Applies to the current 3 scales too (base/session/HTF each toggleable). setup_arm reads only the ENABLED
scales' scores. Keeps the multi-scale system flexible + testable one dimension at a time.

### F24 — sequencing: build the TRADE (entry/stop/TP) at one scale BEFORE setup_arm (2026-07-02)
User's instinct (agreed): build entry/stop/take-profit at the smallest dimension first -> you have a
complete, MEASURABLE trade, then replicate/extrapolate outward across scales. Why this order is right:
(1) setup_arm's job is to ARM/pull RESTING ORDERS -- it needs a trade (entry/stop/TP) to exist first;
(2) zone_calibration already gives 80% of it (stop = VA/base edge = 1R, room = target, R:R, entry_tf) --
we make it a concrete tradeable def + a fill model + the target ladder + the entry trigger; (3) correct
METHODOLOGY: measure the UNCONDITIONAL trade population's R first (base rate), THEN setup_arm filters and
we check if gating adds LIFT (same pattern as the vol-filter hypothesis test). Needs a minimal backtest
loop (step bars, rest orders, fill at confirming close F1, manage stop/TP, record R) -- which is the thing
that finally answers "is there edge" in real R after costs. So: entry/stop/TP (base scale) -> measure R
-> setup_arm gates it -> extrapolate the target ladder across scales (F22). ENTRY/EXIT config slots get filled.

### F25 — R:R GEOMETRY (now, from structure) vs REALIZED R (backtest, later): keep separate (2026-07-02)
User's correction to F24: measuring R:R does NOT need a backtest. R:R is GEOMETRY -- stop + target LEVELS
derived from the multi-scale readings (stop = the smallest/tightest scale's edge; TARGETS = a LADDER of
each larger scale's VA edges / POCs / naked levels), and R:R = target-distance / stop-distance. Static,
computed from price structure NOW (zone_calibration is a crude single-scale version). Stops/TPs get
"reprogrammed" from the nested readings and stack into a ladder (scale-out targets that come down into
each other). SEPARATE thing: a precise BACKTEST engine that steps bars, places the orders, manages the
trade, and records REALIZED R (did price hit the ladder targets or the stop) + trade management -- later.
NEXT MOVE: the R:R-geometry / TARGET-LADDER engine (research) -- from the enabled scales output a stop
level + ordered target ladder + R:R per rung; draw the levels on the chart (boxes already show the scales).
Geometry-only, no simulation. THEN the backtest measures whether those levels get hit (realized R). This
is the concrete trade DEFINITION (entry/stop/TP geometry) that setup_arm later arms.

### F26 — target_ladder: the multi-scale R:R GEOMETRY engine BUILT (2026-07-02)
Built research/setup/target_ladder (geometry only, NO backtest; F25). `ladder({base,session,htf})` -> 1R =
the BASE coil (high-low = the tight stop from the smallest scale); TARGETS = every larger scale's VA edges
/ POC / extremes in the breakout direction, ordered nearest-first into a scale-out LADDER with R:R per rung;
computed for BOTH directions (direction unpredicted, F13). The multi-scale generalization of
zone_calibration's single R:R. Params in strategy_config.LADDER. On the chart: a TARGET LADDER card at the
bottom of the module stack -- 2025-01-10 NY: 1R=194.5pt, up rungs htf POC 0.86R / htf VAH 2.58R / htf high
3.7R (rungs come down into each other). The concrete trade DEFINITION (entry/stop/TP geometry) that
setup_arm arms + a backtest later measures. Logged to ledger (kind=target_ladder). Study: median 2
rungs/session; upside often one-sided (coil sits near an extreme) -- honest geometry.

### F27 — R:R asymmetry is trade-SELECTION, not direction (the key distinction) (2026-07-02)
User asked: doesn't the ladder's R:R (big room up vs small down) naturally serve a DIRECTION bias? Answer:
NO -- and this is the pillar that keeps the whole approach honest. Room != probability; the two are
independent and can even OPPOSE. Demo case: coil near the session TOP -> big R:R up (weekly levels far),
small R:R down (session low near). But at a range top the mean-revert odds arguably favor DOWN while the
room favors UP -> geometry and probability point opposite ways. So R:R asymmetry is NOT "which way price
goes"; it's "which side's breakout is worth resting an order on." DIRECTION is decided by the FILL (which
resting order triggers), not by us. R:R decides whether the trade was worth resting. This is exactly the
project thesis (hunt asymmetry not direction, F13): right = big, wrong = 1R. Edge math: risk 1R to make
2-3R is positive expectancy well under 50% hit rate -> no direction edge needed (good, we don't have one
on NQ). TRAP to never make: turning "big room up" into "price will go up." Whether to rest one side or
both, and which R:R qualifies, is a setup_arm/entry decision (deferred) -- the ladder only surfaces the
asymmetry.

### F28 — debugging discipline: fix the bug because it's WRONG, not because it looks better (2026-07-02)
User's rule (hold forever, especially staring at a red equity curve): fix the MECHANICAL error (stop not
applied, fill price wrong, sign flipped, roll-gap in back-adjusted data, R denominator tiny) because it's
INCORRECT, then take whatever number falls out. Don't stop debugging the moment it turns positive; don't
keep debugging past correctness just because you dislike the answer. The bug is done when the CODE IS RIGHT,
not when the P&L is good -- different stopping conditions, easy to swap without noticing. Applied to the
first backtest: entry-at-coil-edge (a resting stop fills at its level, not a runaway close) + R = actual
entry-stop (not the coil proxy) + fixed-fractional $ (variable stops != 1 contract) were CORRECTNESS fixes;
the min_coil_pct filter was flagged as a TRADING CHOICE (in config, logged), not a fix. Number taken as-is.

### F29 — first backtest: UNCONDITIONAL base rate (SUPERSEDED by F30 — original numbers were a BUG) (2026-07-02)
backtest/run_backtest.py -- honest sim of target_ladder trades (both-sided coil breakout, stop = coil edge
= 1R, TP = first ladder rung >= 2R, time-stop 156 bars, honest fills, commission+slippage), era >= 2015,
UNCONDITIONAL (no gating). **v1 reported 1,897 trades: win 24.9%, avg -0.170R, total -322.5R, PF 0.77, max
DD 366R -- THESE NUMBERS ARE VOID (see F30).** The equity curve told on it: all the loss was a single CLIFF
in the first ~250 trades, then flat-to-slightly-up for the remaining ~1,600. An edgeless strategy bleeds
EVENLY across all trades; this bled once, early, then stopped -> the damage was localized to the start of
the data = a bug, not the market. Corrected base rate + root cause in F30. NEXT unchanged: setup_arm ->
re-run conditional -> does gating lift avg R / win% above ~33%?

### F30 — the backtest CLIFF was an era/profile mismatch; corrected base rate ≈ BREAKEVEN (2026-07-03)
Chased the F29 opening cliff (equity screenshot). Root cause, fully mechanical (F28 discipline -- fixed
because it's WRONG): the backtest filters the PRICE BARS to era >= 2015 but never filtered the PROFILE set.
base_profile.json holds all 12,050 sessions 2005-2025; **5,336 are pre-2015**. For each, `i0 =
searchsorted(t, session_end, "right")` returns **0** (session_end predates the first era bar), so the trade
enters at BAR 0 (2015-01-01, back-adjusted price ~7246) but with a 2005 coil's levels (high ~4727 / low
~4713). The breakout check `h[0] >= H_` is then trivially true (instant fake entry), and risk = entry - stop
= 7246 - 4713 ≈ **2533 points** -- the entire ~2500pt corrupt population. 305 such fake trades = **-294.7R of
the -322.5R total.** FIX (one line, pure correctness guard): after computing i0, `if i0 <= 0 or i0 >= n:
continue` -- skip any profile whose session falls outside the era-filtered bars.
CORRECTED base rate (era >= 2015, unconditional, target >= 2R): **1,592 trades, win 29.6%, avg -0.017R,
total -27.7R, PF 0.97, max DD 75.3R** (was 366R). Max risk_pts now 304 (was 3265), 99pct 151, zero trades
> 500pt. Curve is now evenly distributed (trough -72R in Dec-2019, no opening cliff). By session:
asia +0.005R (n778) / london -0.030R (n550) / ny -0.057R (n264). READ: raw multi-scale geometry, no quality
gating, after costs = **essentially breakeven** (not the -0.17R disaster) -- exactly what honest ungated
geometry should look like. The gate for gates is now small: lift 29.6% -> ~33%+ win. Logged to ledger
(note=fix-era-profile-mismatch, git 2e7e82f6b). Lesson banked (F28): the EQUITY CURVE SHAPE is a debugger --
front-loaded loss = localized data bug, not edge.

### F31 — TRADE REPLAY page: step through each backtest trade + its outcome, with the 3 module cards (2026-07-03)
Built a sibling of the main chart (`research/chart/trade_replay.html`) to step through the backtest's trades
one-by-one on candles. ACCURACY PRINCIPLE (the whole point): the backtest is the SINGLE SOURCE OF TRUTH --
`run_backtest.py` now exports `trades.json` with each trade's exact geometry (entry/stop/target/exit times +
prices, coil hi/lo, dir, R, outcome); the page RENDERS that, never re-simulates (no JS drift). Pipeline:
`run_backtest.py` (trades.json) -> `build_trades.py` (attaches the same 3-scale readings base⊂session⊂HTF +
ladder, scored by the same gates, + a compact 5m bar slice per trade [setup session .. exit+pad] and a
downsampled trailing-week HTF slice) -> `data/trades_data.js` -> `make_trade_replay.py` -> the page. On the
page: browse prev/next/scrub/filter-by-outcome; entry(gold)/stop(red)/target(green)/coil(faint) price lines +
entry & exit markers drawn from the sim; a gold "now" line you scrub bar-by-bar entry->exit showing
mark-to-market R (FINAL R/outcome is the sim's, authoritative); and the SAME 3 module cards + target ladder
the main chart shows (the setup context that armed the trade). SIZE: all ~1600 trades × full 5m lifecycle =
~43MB (too heavy to inline), so build_trades caps to the most-recent N (default MAX_TRADES=300 -> 6.3MB;
`0`=all) and stores bars as compact arrays [t,o,h,l,c,v] loaded via `<script src=trades_data.js>` (works on
file://, unlike fetch). Verified end-to-end on real data (nav / filter / stepping / final-R = sim R). The
user only wanted a practical recent slice, not the whole history at once.
TRADE-DRAW STYLE (chosen from a 6-option mockup, 2026-07-03): the **R-multiple ladder** (option 03) --
green reward bands stacked away from entry (opacity grows per R) with dashed kR dividers + labels, a red 1R
risk band entry->stop, and entry(gold)/stop/target axis lines + entry & exit markers. Direction-aware
(reward above for longs, below for shorts). Drawn on the SVG overlay (lightweight-charts has no native filled
price bands) so it redraws on pan/zoom; bands capped at 8 (target line still marks the true R). You read
profit in R straight off the chart. NEXT natural step: once setup_arm exists, this same page shows only the
ARMED trades + the gate states that armed them.

### F32 — per-run PERFORMANCE REPORTS live under research/runs (machine-readable + clean HTML view) (2026-07-03)
User: the loose backtest/output equity.png (stale matplotlib, still showing the void -322R numbers) looked
bad AND felt duplicated vs the runs ledger. Resolution: the RUNS SYSTEM owns the detailed analysis, saved
BOTH machine-readable and as a clean HTML view. Pipeline: `run_backtest.py` records per-trade excursion
(MAE/MFE/ETD + bars) + writes trades.json (+context), then calls `research/runs/make_report.build()` ->
`research/runs/analytics.analyze()` computes the full NinjaTrader-style breakdown (returns, Sharpe/Sortino/
Calmar/Ulcer, trade quality, excursion, Monte-Carlo risk-of-ruin, time&exposure) split ALL/LONG/SHORT +
a daily equity/drawdown series -> writes `reports/<run_id>/analysis.json` (SOURCE OF TRUTH, mineable, incl.
the full trade list) + `report.html` (professional dark view: headline cards + ECharts equity/drawdown +
tables, matching the algoproj webui "Quant Analyzer") + rebuilds `reports/index.html` (the "< all runs"
browser). ECharts vendored from webui (`research/runs/lib/echarts.min.js`, offline). The retired equity.png/
equity.html are gone; `_report` SVG removed from run_backtest. .gitignore TRACKS analysis.json (durable
archive), regenerates the HTML. FIXES found while building: (a) equity dropped Sun-eve/holiday trades ->
built the day calendar as business-days ∪ trade-exit-days so equity reconciles to start+total_pnl exactly
($72,267 = 100k-27,733; net -27.73%, not the buggy -35%); (b) equity curve was green on a LOSING run ->
colored by net sign (red when final<start); (c) right y-axis labels ($k) were cut off -> grid right margin.
Entry point is `reports/index.html` (each run = a new timestamped folder; open the newest). This is the
per-RUN analytics twin of the ledger scorecard: runs.jsonl = index, reports/<id>/ = the drill-down.

### F33 — FUTURE gate: red-folder fundamental NEWS filter (ForexFactory) (2026-07-03)
User's idea (documented, deferred): download high-impact ("red folder") fundamental news events from
ForexFactory (https://www.forexfactory.com/calendar) and use them as a TIMING gate -- e.g. do NOT trade
30 min before or after a red-folder release (FOMC, CPI, NFP, etc.). Fits the WHEN-to-trade layer alongside
the vol/session filter: a `research/gates/news_filter` that loads a news-events table (date/time/impact,
ET) and exposes `blocked(ts, window=30min)` -> setup_arm/backtest skip bars inside any red-folder window.
Needs: (1) a manual/one-time download of the red-folder calendar to a data file (ForexFactory has no clean
free API; export or scrape the weekly calendar, store as CSV/parquet in ET), (2) map events onto the bar
timeline, (3) a config knob (BLOCK_MINUTES, which impact levels). In-context test (F13): does blocking news
windows improve the WIRED setup's R? Deferred until setup_arm exists. Connects to volatility_filter (both
are WHEN gates).

### F34 — two CONFIG SOURCES OF TRUTH; runs saved separated by source (2026-07-03)
Locked the config model (user). `strategy_config` = the MAIN/real truth a good strategy graduates to;
`research_config` = the experimental one, and **the backtest runs off it by default** (it re-exports
strategy_config + run knobs). Each is tagged `CONFIG_SOURCE` ("strategy" / "research"). Every backtest run
is now SAVED SEPARATED by source: `research/runs/reports/<source>/<run_id>/` (same format: analysis.json +
report.html); the runs index gained a Config column + colored tag. `run_backtest --real` runs off
strategy_config (getattr fallbacks for research-only knobs). Also wired the previously-DEAD research_config
knobs: `BACKTEST_START/END` (date window, honored by the backtest) + `MAX_REPLAY_TRADES` (trade-replay
export size, moved out of a local build_trades constant). Rule reaffirmed: a value lives in strategy_config
(strategy) or research_config (run) — one setting, one home; everything done connects to one of the two.

### F35 — back to ONE dimension (5m); extra scales are OPT-IN via config (2026-07-03)
Strategic reset (user): the multi-scale stack (base ⊂ session ⊂ HTF) was getting ahead of the edge. Collapse
to the SINGLE base dimension — the 5m session volume_profile — lock the minimal backtestable skeleton, then
add gates/scales one at a time from config. Implemented: `BASE`/`HTF` got an `"on"` flag (default False);
`build_chart_data` only computes/attaches the base + htf scales (and the ladder, which needs base) when
enabled; the chart defaults to 5m and gates the live replay base-recompute on `BASE.on`. So the chart now
shows only the 5m session profile until you enable a scale (e.g. HTF days=14 -> 2-week lookback). This is the
"minimal skeleton + toggle layers" plan: green LIVE dials run today; the gates/filters are configured but
NOT wired until setup_arm applies them (see the control panel, F37).

### F36 — the CHART became the control surface: config-status panel + Run backtest (via a local server) (2026-07-03)
The chart sidebar now IS the config panel + run console. (1) Config-status panel: every knob + sub-parameter
from both configs, each with STATUS DOTS — green live / red off / orange not-wired / purple no-engine — read
from `manifest.config_panel` (built in build_chart_data). So you can see exactly what's connected; the amber
NOT-WIRED dials are the setup_arm to-do list. (2) Run backtest: date pickers + a research|strategy source
select + a Run button with a live countdown/progress bar; on done it opens that run's report + the trade
replay in separate windows (opened in the click gesture so popup-blockers don't kill them). CONSTRAINT +
FIX: a file:// page can't launch Python, so `serve.py` (stdlib http server) + `run_chart.bat` serve the
chart at localhost and expose `POST /run {start,end,source}` -> runs run_backtest (dates via env override) +
build_trades -> returns run_id + report/replay URLs. On file:// the Run button disables itself and says to
launch run_chart.bat. Consolidated to ONE config view (removed a duplicate drawer, per user).

### F37 — SCALES = the geometric-timeframe ladder = the module cards (config must speak DIMENSIONS) (2026-07-03)
User caught a real misalignment: the config names the scales by IMPLEMENTATION MODULE — `PROFILE`
(volume_profile 5m), `BASE` (base_profile = a coil DETECTOR), `HTF` (htf_profile = a day/week composite) —
three different mechanisms. But F19/F22/F23 frame them as ONE profile machine run at N nested SCALES, each a
DIMENSION defined by a LOOKBACK (geometric ladder: 20->60->180->540->1620->4860 bars, constant ratio). And
each ACTIVE scale is exactly one of the MODULE CARDS that pop up on the chart — so SCALES (the geometric
ladder) and the module stack are ONE system: enable N dimensions -> N module cards. ALIGNMENT: replace
PROFILE/BASE/HTF with a `SCALES = [{name, on, lookback}]` ladder (F23), ordered smallest->largest, 5m base
always on, rest opt-in; names = dimensions/roles, not modules. OPEN FORK (undecided): (A) PURE lookback
ladder (F22) — drop the coil detector; the "coil" is just the tightest/cleanest scale; tiny params; OR (B)
keep base_profile's adaptive coil DETECTION as a special smallest scale + fixed lookbacks above. Decide
before rewriting the SCALES config. Also built this session as the REASONING SURFACE for all this: the
`strategy_map` is now a CONFIG CONTROL PANEL (every dial, LIVE vs NOT-WIRED vs no-engine) + an interactive
`flow.html` FLOW EDITOR (drag components from a bottom tray, connect them into your execution order, export
flow.json) — see build_map.py / build_flow.py.

### F38 — config retiered by ALTITUDE + the chart became a LIVE control surface + wiring≠promotion (2026-07-03)
The config *felt* far heavier than the actual logic. Two reasons, both real: (a) it mixed three kinds of thing
at ONE altitude — decisions you tune, calibration you set once, and facts you never touch — so the ~8 real
knobs were buried under ~30 constants; (b) it described the full multi-scale VISION (F19-F26) while the code
runs the F35 one-dimension skeleton. **The config outran the code.** Fix: retiered `strategy_config.py` into
**CONTROL PANEL / STRUCTURE / CALIBRATION / FACTS**, each knob STATUS-TAGGED — `[WIRED]` (changes a backtest
number today) · `[SENSOR]` (measured/drawn but NOT gating until setup_arm) · `[CHART]` (display only) ·
`[FACT]`. Surfaced the two real gate thresholds (`GATE_SHAPE_OK`, `GATE_RR_MIN`) up into the control panel;
kept EVERY existing name (verified: 37/37 symbols, values identical) so nothing broke. Pre-shrink file parked
at `_archive/strategy_config_full_2026-07-02.py`. Two HONESTY fixes baked into the comments: the `FILTER_*`
gates are `[SENSOR]` (the backtest trades ALL sessions until setup_arm reads them), and `BASE/HTF["on"]` are
CHART-only toggles (the backtest uses all three profiles regardless).
Chart side: rewrote the sidebar to render the tiers + honest dots (wired green / sensor amber / chart blue /
fact grey / unbuilt red); one shared `research/chart/config_panel.py` defines the panel for both the build and
a NEW `serve.py` `/config` endpoint that **reloads the config live** — edit the config, reload the page, the
sidebar updates (no rebuild, no restart; the backtest was already a fresh process so Run always read current
config). THE TWO-AXIS REALIZATION (the thing that kept confusing us): **PROMOTION** state (research→engine,
the checklist legend) ≠ **WIRING** state (does it change a backtest number). Honest runtime, documented in
CHECKLIST "Config alignment": the backtest reads the research **profile JSONs + target_ladder**, it does NOT
import `engine/`; `run_simplicity.py` is a *wiring tracker* (prints WIRED x/13), not the thing that trades — so
`[E]` = "promoted & importable", not "this is what produces the backtest." Reference sketches built to make the
config legible: `CONFIG_PROPOSAL.md`, `config_proposal_v2.yaml`, and `viz/config_viz.html` (a mock candlestick
chart per config block, so you SEE what each knob draws). Format stays Python (no pyyaml dep; system python
lacks it) — a small Python control panel gives the same edit→rerun workflow YAML would.

### F39 — setup_arm v1 built + FIRST GATED RESULT: win-rate lift, NO expectancy lift yet (2026-07-03)
Built `research/setup/setup_arm/setup_arm.py` — v1 **arm-once** confluence gate: ARM a coil iff
`session_filter passes AND shape_ok AND rr_ok` (ANDs the built SENSORS, reads the control-panel thresholds; no
direction call — the OCO fill decides direction). Wired ONE line into `run_backtest.py`, gated behind
`SIMP_ARM=1` (env) or `SETUP["on"]` (default OFF → base rate preserved). This is the piece that turns the four
`[SENSOR]` gates into REAL gates. First head-to-head (era>=2015, target>=2R, 1 contract):

| | base rate | gated (session+shape+rr) |
|---|---|---|
| trades | 1,592 | 134  (disarmed 1,893) |
| win rate | 29.6% | **43.3%** (+13.7pts) |
| avg R | -0.017 | -0.027 |
| total R | -27.7 | -3.7 |
| PF | 0.97 | 0.93 |
| max DD | 75.3R | 13.9R |
| outcomes | 295 tgt / 1043 stop / **254 time (16%)** | 3 tgt / 40 stop / **91 time (68%)** |

READ (honest, F13/F28 — take the number as-is): the win-rate lift is REAL (+13.7pts — the gates genuinely
select coils that get stopped less), **but expectancy did NOT improve** (avg R slightly worse, PF still <1). WHY:
the outcome mix flipped from 16%→**68% TIME exits**; only **3 of 134** reached the 2R target. The gates prefer
clean/tight/QUIET coils — which don't get stopped, but also lack the momentum to run to 2R, so they grind and
time out near breakeven. High win rate (few big losers), tiny payoff (almost no big winners). **The binding
constraint moved from ENTRY quality to the EXIT.** n=134 with 3 targets = small/noisy → a DIAGNOSTIC, not a
verdict. Next lever = **exit mechanics** (trailing_stops / closer first target / shorter time-stop), NOT more
entry gating; also worth trying higher `rr_min`, lower `shape_ok`, or loosening the NY-only session gate (asia
was the best base-rate session, +0.005R). Both runs logged to the ledger (runs.jsonl).
Also HARDENED the run harness while testing it end-to-end: the chart date pickers now **default + lock to the
DATA range** — data ends 2025-01-10, but the picker had defaulted to the 2026 calendar → empty future window →
"no trades" → serve.py 500. Now `run_backtest` prints a clear empty-window reason (`... matched 0 bars (data
available 2005-01-11..2025-01-10)`), `serve.py` surfaces it to the chart, and a stray double-bind on port 8765
was cleared. (NQ data is ~18mo stale vs today — refresh via `data/build_data.py` when wanted.)

### F40 — config-driven TP engines + real scale toggles → FIRST honestly-positive config; + engine promotions (2026-07-03)
Three things this session, all wired for real and verified end-to-end.

**1. Scale toggles made REAL.** `HTF["on"]` now gates whether htf levels feed the `target_ladder` in the
**backtest** (not just the chart) — off ⇒ session-only ladder targets. `run_backtest` passes
`htf=None` when off; `build_trades` already gates the replay cards. base = the core trade universe (coil =
entry/1R), always used; its flag gates only the base-card display. So "off" now means *not used*, everywhere.

**2. New config-driven TAKE-PROFIT engines** (`EXIT["target"]` selector, all wired):
  - `fixed_rr`  — a clean constant 1:target_r TP (e.g. 1:3), independent of the ladder.
  - `ladder_rung` — the existing multi-scale first-rung ≥ target_r.
  - `trailing` — no fixed TP; arm at +`trail_arm_r`, hold the stop `trail_gap_r` behind the best price.
Target is derived at FILL for fixed_rr/trailing (both sides tradeable); the manage loop branches on the method.

**RESULT — the first positive expectancy** (era≥2015, after costs, honest fills):

| config | trades | win% | avg R | PF | maxDD |
|---|---|---|---|---|---|
| ladder 2R (old base rate) | 1,592 | 29.6% | -0.017 | 0.97 | 75R |
| fixed_rr 1:3 (ungated) | 6,124 | 34.1% | +0.007 | 1.01 | 141R |
| trailing (ungated) | 6,124 | 39.8% | +0.026 | 1.05 | 71R |
| **trailing + setup_arm (default)** | 959 | **47.8%** | **+0.035** | **1.10** | **19R** |

Trailing beat both fixed targets — it directly cures F39's 68%-time-out disease (rides partial moves instead
of dying at a far target). And **setup_arm gating STACKS on trailing**: expectancy +0.026→+0.035R, PF
1.05→1.10, DD 71R→19R. So the DEFAULTS are now `EXIT.target="trailing"` + `SETUP["on"]=True` (the graduated
config). Honest caveats (F13/F28): PF 1.10 is modest and unvalidated — still needs OOS / ES / walk-forward
before it means anything; ~96 trades/yr. But it's the first time gating + exit + costs all point positive.
`SIMP_ARM=0/1` forces gating off/on for A/Bs regardless of config.

**3. Promotions to engine/ (5/13 → 8/13 WIRED).** Migrated the mature, self-contained pieces out of
research: `shape_filter` + `zone_calibration` → `engine/gates/`; `setup_arm` + `target_ladder` →
`engine/setup/` (each = a pure function + the engine path-bootstrap + `DESCRIBE`/`check()`, reading params
live from strategy_config). `run_simplicity` now shows shape_filter / zone_calibration / setup_arm WIRED.
`fib_bias` deliberately NOT promoted (it's a study with no live edge, F11). The backtest still runs off the
research copies for now (research = the test bench); rewiring the backtest onto engine/ is a later migration.

**Also:** every backtest now saves the FULL config that produced it — `runlog.config_snapshot()` extended to
LADDER/SETUP/ENTRY/EXIT/RISK/costs/source, and `analytics.analyze` writes it as `analysis.json.config_snapshot`
(so each run's report is self-describing / reproducible). And the trade-replay module cards are config-driven
(only enabled scales show; disabled ones hidden, trade lines stay truthful from the sim record).

### F41 — LIVE trade-replay: arm states + resting orders + the trailing stop shown bar-by-bar (2026-07-03)
To see WHY trades die under trailing (not just the final R), extended the trade-replay into a full per-trade
LIVE replay — the "replay state panel" parked since F8, now buildable because setup_arm exists. ACCURACY
(F31): the sim is the source of truth — `run_backtest` now EXPORTS, per trade, the per-bar **`path`**
(`[t, live-stop, armed]` — the actual trailing ratchet) + the **`arm`** gate states (session/shape/rr + the
shape_score & rr values) + `method`; the page RENDERS them, never re-simulates. (build_trades needed no change
— `rec = dict(tr)` carries new fields through.) On the page, as you scrub/play a trade:
  - **resting orders** drawn pre-entry (buy-stop ↑ / sell-stop ↓ at the coil edges, OCO); the untriggered side
    fades after the fill;
  - the **trailing stop as a stepped staircase** climbing bar-by-bar (you watch it ratchet up and then take you
    out) — for fixed methods it's a flat line;
  - a **state panel** (top-left) that updates each bar: STAGE (resting → in-trade · pre-arm → trailing → EXIT),
    the setup_arm gate pills (session/shape/rr, green/red), the TP method (trailing arm/gap, or fixed R), and
    live mark-to-market R / live stop / R-to-stop.
Everything is CONFIG-DRIVEN off the run's exported config (tp_method, trail_arm/gap, setup_on) — so the replay
shows whatever the strategy actually did. This is the diagnostic surface for the trailing "still dying" problem:
step a losing trade and watch whether the trail armed too early / sat too tight / gave back an MFE.
**Extended (same session):** the trade replay now BUILDS UP bar-by-bar like the main chart's session replay,
not laid-out-static. The replay range starts at the setup-SESSION START; while the session is FORMING the
module card RECOMPUTES on bars-so-far (ported computeProfile/Shape/Zone into the replay; the run exports the
gate params in `config.gates`) — so shape/VA%/prominence/peaks/R:R EVOLVE as it plays, then the coil sets →
RESTING (both breakout-stop orders drawn at the coil edges) → the fill fires → trailing manages → EXIT. The
state panel shows the phase (FORMING/RESTING/IN-TRADE·pre-arm/trailing/EXIT). Press |< or play to replay from
the forming phase; play restarts from the top. = "watch the setup actually happen", the full-execution replay.

### F42 — the FULL strategy spec (clarified with the user) + fix #1: trade the NEXT session's open (2026-07-03)
The user spelled out the original design; confirmed it IS what we're building. **THE SPEC:**
1. In EVERY session, measure coil strength — is there a clean consolidation? (base_profile + shape_filter).
2. ~15 min BEFORE the next session opens, if the range qualifies, rest STOP orders above AND below it (OCO).
3. **We scan a session and trade the NEXT session's OPEN** — scan asia → trade the london open; scan london →
   trade the NY open. Only the liquid opens (london, newyork). Breakout one way at the open + continuation.
4. While IN a trade, keep scanning the new session for ANOTHER coil (same detection). If one forms + qualifies,
   add ANOTHER resting stop but ONLY in the direction of the trade we're in (short→sell, long→buy). Manage same.
This is a continuous, session-by-session BREAKOUT-and-PYRAMID engine.

**Alignment audit (what's built vs missing):** coil detect + score ✅ · qualify (shape+rr) ✅ · rest both sides
OCO ✅ · breakout+continuation ✅. GAPS: (#1 timing) we armed AT the session boundary, not 15 min before;
(#2 which open) the session gate checked the COIL's session (NY-only) = trading the illiquid CLOSE open —
backwards from intent; (#3) no per-session-search view in the replay; (#4) NO pyramiding (one trade per coil).

**FIX #2 shipped (this session):** `setup_arm` now checks the coil's **NEXT** session (via `_next_session`,
cycle asia→london→newyork→close→asia); `FILTER_SESSION["allow"]` re-meant to = **the OPENS we trade** (default
`["london","newyork"]`). So we now arm asia coils (→london open) + london coils (→NY open), which is the spec.
RESULT (era≥2015, trailing, gated): **1,817 trades, 35.3% win, +0.013R, PF 1.02, DD 70R.** The tell: TIME-exits
collapsed **639 → 64** — trading the LIQUID opens, breakouts resolve (target/stop) instead of timing out at the
old illiquid close open. Per-open edge: **london→NY open = +0.056R (the edge)**, asia→london open = −0.045R
(a drag). So `allow:["newyork"]` isolates the good half (scan london, trade the NY open). Honest, and it
matches the intuition that the NY open is the money window. NEXT (queued, in order): #1 arm 15 min before the
open (needs base_profile to finalize the coil that early — causal), #3 per-session-search replay, #4 pyramiding.

### F43 — where volume actually acts + FUTURE entry refinements (breakout volume confirmation) (2026-07-03)
CLARIFICATION (user asked, good catch): volume runs the strategy in TWO separate stages, easy to miss:
  1. **QUALIFY the setup (volume-based, baked in):** the data has real volume (Up+Down, F4); `volume_profile`
     + `base_profile` distribute it across price to build the profiles (POC/VA/bins); `shape_filter` scores the
     coil's VOLUME DISTRIBUTION (clean single peak = solid). All of that is computed BEFORE the backtest and
     stored in the profile JSONs. So volume DECIDES which coils arm.
  2. **SIMULATE the fill (price-only, by design):** `run_backtest` reads those JSONs + loads only O/H/L/C, because
     the entry is a PRICE event (a resting stop fills when price touches the coil edge) — no volume needed there.
So "the backtest loads only OHLC" is NOT a bug: the volume work is upstream, in the profiles. Adding volume on
the ENTRY BAR (below) is a NEW third use, not currently loaded.

FUTURE ENTRY REFINEMENT — breakout VOLUME CONFIRMATION (deferred; measure vs the plain touch in the ledger):
a real breakout has a volume surge; a false break is thin. Measure: `breakout_bar_volume >= vol_mult ×
coil_baseline`, where `coil_baseline = sum(coil bins volume) / coil bars` (avg per-bar volume during the quiet
consolidation). Two engine variants (config `ENTRY["confirm"] = "touch" | "close_volume"`, + `vol_mult`):
  * **A — confirmed-close entry:** wait for a bar to CLOSE beyond the edge WITH the volume surge, enter at the
    close. Filters false breaks BUT enters past the edge → wider 1R → worse R:R (you pay with fill price), and it
    bends the pure resting-order model into "watch + confirm."
  * **B — rest-then-scratch (keeps the resting model):** the resting stop still fills AT the edge on touch (good
    price), then if the breakout bar / next bar is thin (< vol_mult × baseline) exit immediately (fast scratch).
    Keeps the great entry + cuts the false-break bleed; costs a small scratch loss on hollow breaks. More moving
    parts. LIKELY the better fit for this strategy (35% win w/ many stop-outs = probably false breaks reversing).
Needs: load `volume` in run_backtest, compute coil_baseline from the coil dict, the config knob, swap the entry
check. DISTINCT from the RANGE volume-accumulation gate (arm only if the COIL itself accumulated enough volume —
a gate on the coil, not the breakout bar). Both are cheap, both deferred as entry-refinement experiments.

### F44 — fix #1: place the resting orders 15 min BEFORE the open (the original design, causal) (2026-07-03)
The original idea: find the london range, and ~15 min before the NY open rest OCO stops around it. Built it
CAUSALLY: `ENTRY["place_lead_min"]=15`; `base_profile` finalizes the coil on the session EXCLUDING its last
`place_lead_min` (so the range is known before we place) and emits `place_ts` = the placement time; `run_backtest`
starts the entry window at `place_ts` (fallback session_end). No look-ahead — the coil never sees the 15 min after
we commit. RESULT vs placing AT the open (era≥2015, NY-open-only, trailing, gated): 900 trades, 36.2% win,
+0.046R, PF 1.08 — slightly lower expectancy but **max DD 48R→31R** (smoother equity), and it's the honest
live-realistic model (orders resting before the open, not filled at the instant of it). base_profile.json rebuilt.
GAPS DONE: #2 (next-open) + #1 (15-min lead) + #3 (per-session replay). Remaining: #4 pyramiding.
