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

### Next (not built — decide with user)
Nothing beyond Job 1 is committed yet. The volume profile is the substrate; where it leads
(volume-conditioned setups, session selection, volume-anchored R:R) is the next conversation.

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
- **RTH is ~90% of everything.** Session split (real-scaled): `newyork` **89.4%**, `close`
  **6.7%**, `london` **3.3%**, `asia` **0.6%**. Any volume-based idea lives in the US session;
  overnight is nearly empty. (Consistent with the flag work's 8AM–2PM ET session filter.)

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
