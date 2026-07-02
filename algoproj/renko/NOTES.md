# renko — Concept, Spec, Roadmap

*Living notes for the `renko` strategy line. Companion to `README.md` (premise) and
`RANTS.md` (raw idea log). As of 2026-07-01.*

---

## 1. The core idea

Take **TIME off the chart.** Renko prints a brick only when price moves a fixed amount
(`brick_size`); until then, nothing. The result is a chart of **price mileage**, not elapsed
time — noise from slow/choppy periods collapses into "no new brick," and only real
displacement shows. Trend-follow the bricks: **buy white, sell black**, ride until color flips,
size and stop off the fixed brick height (mechanical R:R).

This is the deliberate inverse of the paused lines: they freed *bars* while keeping the *time*
axis; this frees us from time entirely by fixing *price*. Fixed price is the good kind of fixed
— it's what makes risk exact.

Source of the thesis: `derivative.md` (DM exchange with a veteran trend-follower). Taken as a
**hypothesis to validate**, not gospel — the edge gate from the paused work still rules.

---

## 2. Architecture (from the source screenshots)

### MPF — Multiple Price Frames
The Renko analogue of multi-timeframe. Frames are **brick sizes**, not clocks:
- **SPF** — small price frame (small bricks; fine; entry/trigger).
- **LPF** — large price frame (large bricks; coarse; context/core direction).
Signal = **color alignment across frames** ("buy white, sell black when colors align across
MPFs"). Same fractal principle as everything before, but the scale ladder is price, not time.

### Core + Hedge state machine (`images/hedge_core_flowchart.webp`, `hedge_core_switch_frames.webp`)
The system's spine — resolves continuation-vs-reversal with two frames:
1. **Enter core** in the LPF trend direction.
2. **SPF starts reversing** → open an **SPF hedge** (protects the core against a real turn).
3. Resolve:
   - **LPF bar remains same trend** → SPF reversal was noise → **close SPF hedge, remain LPF
     core** (trend suspension → continuation).
   - **LPF bar reverses trend** → **close LPF core; the SPF hedge becomes the new core**
     (trend reversal).

Three labelled regimes on the frames image: **hedge onset / core-switch template** (small
frame), **trend suspension** (hedge on, core held), **trend reversal** (original core unwound,
hedge promoted to new core). This is the flag line's *"LTF tight stop / HTF runway = R:R
engine"* realized cleanly on price frames.

### Execution params (`images/brick_params_tsl.webp`)
Source example: **brick size 20**, **offset 5**, **TSL = 5 ticks below current brick low**
(mirror for shorts). So: a fixed brick, an offset (exact role TBD), and a **trailing stop that
trails the brick** — the ride-and-trail exit. Units (ticks vs points) and instrument (source
used MNQ) to be pinned down for NQ.

### The 3 states (the trend-follower's framing)
- **Trend / countertrend** — vector / speed.
- **Momentum acceleration** — directional velocity.
- **Range expansion / volatility breakout** — squeeze (Bollingers outside Keltners).

### R:R vs win-rate map (`images/rr_vs_winrate_heatmap.webp`)
The profitability surface: which win rate each R:R needs to clear breakeven (1:2 → 33%, 1:3 →
25%, …). Same **geometry-first** lens the paused work reframed into — fixed bricks make the R:R
axis exact, so this map is directly actionable, not theoretical.

### Framework overview (`images/strategy_framework_overview.webp`)
A products/instruments universe (futures, equity index, …) + a **P&L-response-rate-to-spot-
movement** pyramid (stability / movement / increment) and a SPEED / INCREMENT / MOVEMENT
triangle — i.e. brick size is chosen to tune how sensitively P&L responds to spot. Bigger
bricks = slower, calmer response; smaller = faster, twitchier. This is the sizing/optics dial.

---

## 3. Spec — v0 (TBD, nothing built yet)

Nothing is built. First decisions to lock before code:
1. **Brick engine.** Close-based classic Renko vs. high/low (wick) vs. ATR-brick. Leaning
   **fixed-size, close-based, confirmed-brick-only** (the source implies fixed = baked-in R:R).
2. **No look-ahead / repaint safety.** The forming brick repaints; the engine and any backtest
   must act only on **confirmed** bricks. This is the single most important correctness rule —
   Renko edges evaporate if you peek at the unconfirmed brick.
3. **Data.** Synthesize bricks from the existing NQ store (20 yr). Bricks need a price path;
   1m OHLC is the practical input (tick if we have it). Decide the intrabar tie-break rule
   (which of high/low is hit first) conservatively.
4. **Brick size(s).** Pick SPF / LPF for NQ (in points/ticks). Start with a couple and eyeball.
5. **Findings + chart.** Emit bricks/signals as findings JSON; reuse `tv_chart` to render a
   Renko view (scroll years). Same findings→chart loop as the siblings.

**Then** (only after the representation looks right): the core+hedge machine, measured against
forward **R** to the color-flip (thesis-matched horizon), out-of-sample, after costs.

---

## 4. Lessons inherited (do NOT relearn — see the sibling NOTES)

- **Edge is the gate; detection/representation is easy.** A Renko chart is a *sensor*, not an
  edge. Prove forward R OOS after costs, or it's just a prettier chart.
- **Measurement horizon = holding thesis.** Ride-to-flip in R; never a fixed tiny forward window
  (the fwd-6 error).
- **Trade WITH the larger frame** — the one conditional pulse ever found. MPF alignment is that,
  built in.
- **Breadth for sample size**, never looser quality. Brick sizes × instruments.
- **Beware sensor-vs-machine and component-alone traps** (flag §14/§17): the core+hedge machine
  is the stateful trader; a lone brick color is not a signal.
- **Non-stationarity is real** (the flag R:R flipped sign by decade). Any Renko edge gets the
  same decade / sub-period split before it's believed.

---

## 5. Findings log

### F1 — brick engine built + the cost/1R lens (2026-07-01)
`engine/bricks.py` (close-based, confirmed-only, 2-box reversal; grid algorithm, self-test
passes) + `engine/build_bricks.py` (runner). Built over the full **20 yr of NQ 1m** (6.2M bars).
Findings written to `findings/bricks_1m_<size>pt.npz` (arrays: ts / open / close / dir / src_i).

The runner leads with the **expectancy tax** — round-turn cost as a % of one brick of risk
(1R), with `algokit.costs.FuturesCost` (2.25/side + 1 tick slip, NQ $20/pt):

| brick | bricks/20yr | /trading-day | color flips | 1R (1-brick) | **cost / 1R** |
|------:|------------:|-------------:|------------:|-------------:|--------------:|
| 10 pt | 182,154 | 36.1 | 46,357 | $200 (40t) | **7.2%** |
| 25 pt | 36,429 | 7.2 | 10,362 | $500 (100t) | **2.9%** |
| 50 pt | 10,197 | 2.0 | 3,060 | $1,000 (200t)| **1.5%** |

**Read (this is the whole point of leading with cost):** small bricks are a **cost trap.** A
10-pt brick hands the broker **7.2% of every 1R** before the trade is even right or wrong — on a
thin intraday edge that's often the entire edge. This is *exactly* where the veteran's "$50/day
on one micro MNQ" instinct (many small turns) is suspect. Bigger bricks = far lower cost drag but
fewer trades (2/day at 50pt). The brick-size choice is a **direct expectancy knob**, visible on
trade zero — not a cosmetic setting. No signal yet; this is pure representation + the cost frame.

**Next (per the build order):** the expectancy harness (turn any brick signal into trades → R,
net of costs, sized, OOS) before any signal work — so nothing ever gets measured cost-free.

### F2 — grid-price fills are fantasy: the +0.49R "edge" that wasn't (2026-07-01)
The first harness run (`harness/expectancy.py`, trade-every-flip baseline) printed
**+0.49R/trade over 10,362 trades, stable OOS** — flagged as too good to be real, and it was.
The bug: fills at the brick's GRID price. A close-based brick only *confirms* when a 1m bar
**closes at/past** its grid line, so the only tradable price at that moment is that bar's
close — at a flip it is always at-or-past the line AGAINST the trade. Measured mean gap per
side: **0.46R @ 10pt, 0.23R @ 25pt, 0.14R @ 50pt** (fixed-points overshoot vs shrinking 1R).

| brick | grid-fill expectancy | honest-fill expectancy | phantom edge |
|------:|---------------------:|-----------------------:|-------------:|
| 10 pt | +0.86R | −0.05R | +0.91R |
| 25 pt | +0.49R | +0.02R | +0.46R |
| 50 pt | +0.32R | +0.04R | +0.28R |

**Read:** honest expectancy ≈ 0 everywhere (25pt t-stat 0.73 — noise). Every-flip Renko has
no directional edge on NQ, consistent with the project's core lesson. The harness now takes
`src_close` and fills every market order at the confirming 1m close (limit targets may still
fill at nominal). **The tell to remember:** any Renko result whose edge GROWS as bricks
shrink is fill fantasy.

### F3 — MPF alignment (the source's actual strategy) = no edge, honestly measured (2026-07-01)
`harness/mpf.py`. The signal from derivative.md — *"Buy white, sell black. When colors align
across MPFs"* — plus the core+hedge flowchart. Key reduction: on ONE instrument, core+hedge
nets to zero exposure while frames disagree, so the whole state machine ≡ **long when
SPF & LPF both white, short when both black, flat on disagreement** (this harness IS the
machine, minus the extra hedge round-turn costs). Honest fills, full 20yr, R = 1 SPF brick:

| SPF:LPF | n | expectancy | OOS | t-stat |
|--------:|------:|-----------:|-------:|-------:|
| 10:25 | 28,359 | −0.03R | −0.01R | — |
| 10:50 | 24,699 | −0.04R | −0.05R | — |
| 25:50 | 6,711 | +0.04R | +0.03R | 0.97 |

**Read:** zero, everywhere, before AND after the OOS split — alignment adds nothing over the
(also-zero) every-flip baseline. The R:R *geometry* the veteran promised is real (avg win
~3.2R vs avg loss ~1.7R at ~35% win rate) but the market prices it fairly: it nets to
breakeven. Direction still isn't predictable on NQ; if this line has anything, it's in the
asymmetry/exit side, not the entry signal.

**Caveat found while testing — fixed-point bricks are non-stationary:** NQ went ~1,500 →
~20,000 over the sample, so a 10pt brick is 0.7% of price in 2005 and 0.05% in 2024 —
**82% of all 10:25 trades land in 2020–2024.** Any future brick engine pass should consider
%-of-price or ATR-scaled bricks (keeps R exact in R-terms, restores comparability across eras).

### F4 — ATR bricks + the full MPF sweep: exits and VOLUME carry signal, entries don't (2026-07-01)
Both F3 follow-ups built and run. **Data note first: the 1m store is a back-adjusted
continuous contract** (2005 prints ~4700 vs real NQ ~1550), which rules out %-of-price
bricks — so the stationarity fix is **ATR-scaled bricks**: size = k × daily ATR20, re-set
monthly from prior-month data only, re-anchor on change (`engine.build_bricks_adaptive`,
per-brick `bsize` kept so 1R = that brick's own size = risk-normalized sizing baked in).
Ladder `config.ATR_KS = 0.04/0.08/0.16/0.32/0.64` (~10/20/40/80/160pt today). Sweep driver:
`harness/sweep.py` (pairs / 5-frame score / exits / volume), honest fills throughout,
gross AND net reported.

1. **Pair matrix (10 pairs):** fine SPFs are cost-annihilated (0.04: cost ≈ 0.5R/trade →
   net −0.56R; even GROSS is ~−0.08, so no signal hiding behind costs). Gross improves
   monotonically with coarser frames; best net 0.32:0.64 at +0.003R (t=0.05). Alignment
   entries alone: still nothing, now on stationary bricks.
2. **5-frame alignment score (|Σcolors| ≥ 3/4/5):** all negative. Deeper alignment ≠ edge;
   churn at the finest frame + costs dominate.
3. **Exits (entry fixed = fresh alignment onset):** gross expectancy rises MONOTONICALLY
   with exit width on 0.08:0.32 — align-break −0.014R → trail-6-bricks +0.13R → ride-to-
   LPF-flip **+0.22R gross** (net ≈ 0 after costs). The asymmetry thesis is visible in the
   geometry: wider exits buy bigger right tails. (Trail-1/2 ≡ align-break by construction:
   a 2-box reversal's first opposing brick already prints 2 bricks off the peak.)
4. **VOLUME (per-brick volume intensity vs trailing-200-brick median, causal; a-priori
   gates <0.8 / 0.8–1.5 / ≥1.5):** the cleanest gradient found so far, same direction in
   BOTH pairs tested and in OOS: HIGH-intensity entry bricks beat LOW by ~0.12–0.15R gross
   (e.g. 0.16:0.64: LOW −0.024R vs HIGH +0.099R gross; OOS HIGH net +0.19R, t=1.78).
   The veteran said volume is redundant ("all is contained in the bricks") — the data
   disagrees: how fast/heavy a brick fills carries information its color doesn't.

**Focused combo (single follow-up shot, not a grid): HIGH-vol entry + wide exit, coarse pair.**
`0.32:0.64, trail-3-bricks, rv≥1.5`: **net +0.13R/trade, PF 1.10, maxDD −70R, n=968,
OOS +0.23R** — and net-positive in 3 of 4 five-year eras (2005s +0.11 / 2010s 0.00 /
2015s +0.17 / 2020s +0.22), gross-positive in all four. `0.32:0.64 align +HIGHvol` similar
but milder. **Honesty check: t ≈ 1.0–1.5 after two rounds of selection — exactly what
selection bias manufactures from noise.** Status: *candidate, not edge.* To believe it:
(a) hold-out re-test on data/instrument not used in the selection (MNQ/ES, or post-2025
NQ), (b) trade-count is small — widen carefully (more instruments, not looser gates),
(c) check entry-hour/session concentration. Cost/1R by era (the other honesty lens):
0.32-frame costs fell 9.4% → 1.2% of 1R from 2005→2020s; early eras are cost-hostile at
every frame below 0.32.

**Where this leaves the thesis:** direction from brick colors alone = dead (three ways now).
What survives: R:R geometry widens with exit width (real, gross), and brick volume intensity
tilts entries (real, both frames, OOS-consistent). The candidate system is: coarse ATR frames,
alignment-onset entry gated by high volume intensity, trail-k exit. Validation, not more
sweeping, is the next move.
</content>
