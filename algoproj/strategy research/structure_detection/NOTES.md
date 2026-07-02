# structure_detection — Concept, Lessons, Spec

*Living notes for the `structure_detection` strategy. Sibling of `flag_pattern`. As of 2026-07-01.*

---

## 1. The core idea (shared principle, different detection)

Same fractal principle as `flag_pattern`: price moves **up / down / sideways** at every scale, nested.
But the **detection method is different.** Instead of matching a hand-drawn template, we
**decompose price across many scales and let structure emerge from the pieces** — the
binary-decomposition idea (see `../flag_pattern/images/idea_binary_scale_decomposition.png` and
`idea_mtf_efficiency_heatmap.png`).

The user's framing (recorded verbatim-ish so we don't misread it again):
> the windows find the **pieces** to the [structure]. it's the same idea as a binary decomposition.
> the windows are run, each run combines **more and more data than the last**, **temporally and
> spatially aware** (the micro data inside those windows). [the pieces then assemble into structure]

So the detector is:
- **Many window sizes** run over price (a scale ladder), each folding in more data than the last.
- Each window is **temporally aware** (where in time) and **spatially aware** (the micro-structure
  *inside* it — the price anatomy: where it opened/closed, its range, its internal moves).
- The output is a **decomposition** — a stack of what price is doing at every scale, from which
  **structure** (trend / consolidation / transition, i.e. the up/down/sideways states) is assembled.

*(Exact detector spec — the per-window data, how scales relate, and how pieces assemble — TBD with
the user in the next step.)*

---

## 2. Lessons carried from flag_pattern (do NOT relearn the hard way)

These are earned, expensive lessons from the sibling strategy — they apply directly here:

- **Descriptor ≠ parser (sensor vs state machine, flag §17).** Computing features per window gives a
  *pile of independent descriptors*. A pattern/edge is a **relationship** between pieces over time,
  which needs a stateful assembler. A decomposition/heatmap is a **sensor**, not a detector — do not
  fall in love with the map and mistake it for the thing that finds structure.
- **A component alone is meaningless (flag §14).** 32k standalone "poles" were noise; a pole is
  *retrospective*. Coherence lives in the **relationship**, never in a component. The decomposition
  must assemble relationships, not just emit per-scale labels.
- **Efficiency > magnitude (flag §16, §21).** Directional **efficiency** (net ÷ path, dimensionless
  0–1) is the scale-free way to say "trending vs chop." ATR/magnitude catches spikes (wrong axis).
- **Conditional edge is real (flag §21).** The flag has no naked edge, but it pays **with** the
  bigger multi-scale trend and loses against it (R:R gradient: counter −0.06R → aligned +0.05..0.08R).
  Whatever we detect here, **trade WITH the larger structure** is the one signal that showed a pulse.
- **Sample-size traps (flag §9.1, §19).** Overlapping windows → millions of rows but a *tiny*
  effective sample. Grow N by breadth (timeframes/markets), never by loosening quality. Validate
  **out-of-sample** (split history) before believing any edge.
- **Edge is the gate (flag §6, §20).** Detection is easy; forward edge is the whole game. Cheapest
  decisive test first; no big apparatus before a signal is confirmed.

---

## 3. Spec — v1 (2026-07-01)

**Idea (user, verbatim in RANTS §1):** a *forward progression of swing lows / swing highs* on
**3 dimensions of one timeframe** — LTF (fine) / MTF / HTF (coarse). Track the highest high & lowest
low; when one breaks, lock in the pullback extreme as a swing and **stair-step** on. Highs connect
to highs, lows connect to lows → the structure lines.

**v1 detector** (`signal/structure.py`): an **ATR-threshold swing tracker**. Follow the running
extreme in the current direction; when price retraces from it by **≥ grain × ATR**, lock that
extreme in as a swing (H or L) and flip direction. The confirmed swings alternate H, L, H, L —
connect them to draw the structure.
- **Grain = the dimension.** `GRAINS = {LTF: 0.75, MTF: 2.0, HTF: 5.0}` × ATR. Small grain → many
  small swings (fine); large grain → few major swings (coarse). ATR-relative = volatility-adaptive.
- **Data:** `TF = 5m`, `HISTORY_START = 2024-01-01` (~1 year, enough to scroll).
- **Finding:** `findings/structure_<tf>.json` → per grain, an ordered list of swing points `{t,p,k}`.
- **Counts (1yr 5m):** LTF 29,279 · MTF 7,961 · HTF 1,423 swings. Static viz confirmed clean nesting
  (`analysis/viz_structure.py` / `output/`).

**Known simplification / to refine:** v1 confirms a swing on an *ATR-sized retrace* (zigzag style).
The user's exact wording was *break-driven* ("update the lowest low before the break, stair-step") —
i.e. lock the pullback low as a higher-low when the **prior high is broken**. v1 approximates that;
the precise break-of-structure semantics are a refinement once the visual looks right.

**Next:**
1. Interactive **tv_chart structure view** (reuse datastore/candles/paging; draw the swing lines per
   grain; scroll a year). No flag-pattern right panel.
2. Refine the break/update rules (true break-of-structure vs ATR-retrace; horizontal levels).
3. *Then* the trading logic on top (structure states → entries), measured against forward edge
   out-of-sample (the flag_pattern lessons in §2).

---

## 4. Regime-first line — sensor built, poles counted (2026-07-01)

Pivoted to **"regime FIRST, then decode poles."** Built three things:

- **Regime candle coloring** — `indicators/regime.py` wraps `algokit.regime.regime_score` (the 32-MA
  fan → bull/consol/bear 0–100). tv_chart got a **3-state (argmax) candle-color mode**: each candle
  tints green(bull)/amber(consol)/red(bear). It's a **color-only** indicator (`overlay=False`, no
  lines drawn) so the 0–100 scores don't squash the price scale. This is the regime shown ON price.
- **Regime poles** — `signal/regime_poles.py`: a pole = a contiguous run where bull (or bear) ≥ THRESH
  for ≥ MIN_BARS. Counted over 20 yr: thresh 70 → **684**, thresh 50 → **1,632**, thresh 40 → **2,381**
  (it's a dial). Emits findings tv_chart flags. **THE KEY FINDING:** template ~1,500 · regime fan
  ~700–2,400 · slope-on-swings ~1–2k *real* — **every detection method converges on ~1,500–2,000 clean
  poles / 20 yr of 5m NQ.** Sample size is **market-limited, not detector-limited.** No detector
  redesign changes the order of magnitude; the fix is **breadth** (timeframes × instruments).
- **MTF Efficiency Heatmap REBUILT** — `analysis/mtf_efficiency_heatmap.py`. The user's lost favorite
  quanted-era viz, reconstructed faithfully: 5 TFs (1m/5m/15m/1h/4h-resampled) × 7 lookbacks of signed
  directional **efficiency** (net ÷ path = Kaufman ratio, ±0.12 threshold), red→black→teal, price-
  regime panel + score line. Original `.py` is **gone** (whole-Desktop search confirmed); now owned in
  algoproj. This is the multi-scale regime **sensor**.

## 5. MTF alignment / trend-ride — thoroughly tested, NO naked edge (2026-07-01)

### ⚠️ The "fwd-6" error — a real methodology lesson
For a long stretch, forward-edge was measured over **tiny fixed horizons** (fwd6 = 6 bars; 30 min on
5m, 6 min on 1m). For a **trend-riding** thesis that measures **nothing** — you cannot judge "ride the
trend" over a scalp window. The user called it out bluntly ("who sits in a trade for 5 min, we
*ride*"). **LESSON: the measurement horizon must match the strategy's holding thesis.** A trend-ride
is measured by holding to the trend's END (or a real trailing exit), in **R** — never a fixed small
bar count. Treat every earlier fwd6/fwd24 "no edge" read on a riding idea as suspect for this reason.

### Are the timeframes aligned? No — this part is real (`analysis/mtf_alignment.py`)
Per-TF efficiency scores, 20 yr: the 5 TFs share a state only **18.9%** of the time (81% diverge); 5m
vs 1h agree only **50%** (divergence grows with scale separation). So the configuration the user
described — HTF bull while LTF is bear (a pullback) — happens constantly. **The setup exists.**

### The correct trend-ride test (`analysis/mtf_ride.py`)
Setup: **1h BULL + 15m CHOP + 1m was-bear-then-flips-bull** → enter the 1m flip; stop = pullback low;
**HOLD until the 1h regime stops being bull** (ride the trend); outcome in R. 52k trades, **avg hold
2.6 h, best +84R** — the rides are REAL and big. But expectancy **≈ 0** (−0.02R gross), 22% win, 59%
stop-out.

### Stop widening was the deciding test — and it DIDN'T rescue it
Widened the stop (tight 1m low → 15m-structure low → ATR15×1.5): stop-outs **59% → 41%**, win 22% →
25%, hold 0.8 h → 1.2 h — but **expectancy stayed −0.01R.** Fewer stop-outs is exactly offset by a
bigger risk denominator (best 84R → 51R). **Expectancy is INVARIANT to stop placement ⇒ the leak is
the ENTRY/signal, not the stop.** You can't fix a flat signal by moving the stop.

### Verdict
The 3-TF alignment trend-ride, measured **correctly** (ride to trend end, R-based, three stops), is
**breakeven gross → negative after costs.** Multi-timeframe alignment does **not** carry a naked entry
edge. Consistent with everything: alignment is a **filter on a structured setup** at best (flag §16
regime-align ~3×, flag §21 conditional edge — both in-sample / small), **never a standalone signal.**

## 6. Where to go after this (honest, cumulative)

We have now tested — thoroughly, over 20 yr — **template flags, dynamic pole + VWAP breakout,
slope-on-swings, regime fan/heatmap, regime poles, and 3-TF alignment trend-ride.** **Every naked
forward-edge measurement ≈ 0.** The inescapable truth: **detection / regime / context is easy; naked
forward edge in these intraday NQ patterns is not there.** Only two results ever showed a pulse — both
**alignment-as-a-filter-on-a-structured-setup**, both unvalidated:
1. flag **§21** conditional edge (VWAP-band R:R gradient by multi-scale trend) — best **+0.096R @ 1:2**,
   **in-sample**.
2. flag **§16** regime-align ~3× return/drawdown — **small sample**.

**Priority from here (stop hunting detectors — five methods converged on ~0):**
1. **OUT-OF-SAMPLE the one positive.** Split history in half: does the flag VWAP-band R:R (+0.096R @1:2)
   hold in **both** halves, and survive **costs**? This is the deferred make-or-break. If it dies,
   that's decisive — and we stop.
2. **Breadth.** Run the apparatus on **ES / CL / GC**. Either edge appears somewhere (universality) or
   the "works across markets" thesis dies. Also the only real sample-size fix.
3. **Reframe if 1–2 are empty.** Accept these patterns are a **context/feature, not a tradeable
   signal** — fold into a larger model, OR go find where edge actually lives (different holding
   periods, different markets, a fundamentally different approach). The bottleneck was **never
   detection.**

---

## 7. Spectral / regime deep-dive — hunting hidden structure (2026-07-01)

Built a full spectral toolkit on the aggregate MTF efficiency score (installed scipy, ssqueezepy,
datashader, pywt; plotly already present):
- `mtf_score_cwt.py` (CWT scalogram + global spectrum), `mtf_score_stft.py` (Fourier/STFT),
  `mtf_score_ssq.py` (synchrosqueezed — sharp ridges), `mtf_score_datashader.py` (crisp dense render),
  `mtf_score_cwt_3d.py` (interactive plotly 3D), `mtf_score_cwt_perTF.py` (per-TF CWT).
- **Verdict across 7 lenses: broadband / near-1/f (fractal noise) at every tradeable scale, redundant
  across TFs, NO exploitable periodicity.** Ridges *drift*, never hold at a fixed period (per-TF CWT
  showed the 5 TFs are highly *redundant*, not a clean filter bank — partly why MTF added little).
- `mtf_convergence.py` — collapsed the 5 TF scores into ONE agreement line + a 30-sec edge read.
  Result: **noise.** All-5-aligned doesn't predict (buckets all ~50% win, ~0 fwd; the *most*-split
  bucket was least-bad). Efficiency has **no persistence** — that was the whole problem.

## 8. Volatility clustering + HMM regime — the first PERSISTENT signal (2026-07-01)

Key correction: vol doesn't "trend" — it **clusters and mean-reverts** (Mandelbrot '63, Engle Nobel),
with the leverage effect. Persistence is a settled stylized fact.
- `mtf_vol_heatmap.py` — MTF realized-vol heatmap (percentile per scale). Shows **sustained blocks**
  (the Aug-2024 spike is a clear bright column; calm stretches dark). **Vol-regime autocorr @ 1 day =
  0.82** (vs efficiency ~0). Real, persistent structure you can see.
- `hmm_regime.py` — Gaussian HMM (hmmlearn) on daily NQ [return, vol], 3 states, **fit on TRAIN half,
  FILTERED/causal decode (no look-ahead)**. Found clean calm/normal/turbulent regimes, persistence
  **0.94–0.97** (~3-week stays), nailed 2008 & 2020. **OOS: the regime predicts FORWARD VOL cleanly &
  monotonically (0.50 / 0.69 / 1.12%)** — the first real OOS-validated positive on the project. It does
  **NOT** predict direction (fwd returns all positive/bull-drift-dominated). Caveat: non-stationarity
  (train-era vol thresholds over-label recent years turbulent).
- **Takeaway: vol is real, persistent, forecastable — but it's MAGNITUDE, not DIRECTION.** Value =
  sizing / risk / filter, and it maps onto the flag's squeeze→expansion.

## 9. CAPSTONE (pre-registered) + the flag survivor's R:R (2026-07-01)

`flag_by_regime.py` — pre-registered before looking: metric = **net-R expectancy** (not win rate),
min-n 80/bucket, causal (yesterday's) regime labels, flag-alone baseline, sub-period check, cost
0.75pt round-turn, RR 2, kill unless a bucket clears +0.05R monotonically AND holds in both OOS halves.
- **Regime conditioning of the flag: NEGATIVE.** "Turbulent +0.233R" is the **non-stationarity/date
  confound** — turbulent concentrates in the recent, higher-paying period; within sub-periods the regime
  excess is ~+0.05R (tiny), normal is flat, calm underpowered, pattern non-monotonic. The HMM adds **no
  directional edge.** (9th honest negative.)
- **Incidental survivor:** the flag-alone baseline (VWAP-band R:R) is **net-positive OOS (+0.146R),
  positive in BOTH sub-periods.** The §20/§21 thread survived out-of-sample. Un-killed, standalone.

`flag_rr_sweep.py` — is the asymmetry a plateau or a 1:2 cherry-pick? **1R = VWAP band width; target =
RR×1R.** Two findings, read straight:
- **GOOD — real geometry:** within the recent decade it's positive across **RR 1.5→4 (a PLATEAU**, not a
  spike at 1:2), and **cost-robust to 1.5pt** round-turn. Win rate falls as target extends, payout rises
  to compensate, product stays positive. The asymmetry is capturable across a *range* of targets.
- **BAD — decade-non-stationary:** the **FULL 20yr is NEGATIVE at every RR**; the edge is entirely
  post-2015. ~**−0.24R/trade in 2005–2015, ~+0.13R in 2015–2025** — it **flipped sign**. Either an
  *evolved-market* edge (real but recent) or a reverting fluke; the sweep can't distinguish.
- **Verdict: un-killed but decade-unstable.** The decider is **ES (same sweep) — NOT YET RUN.**

## 10. THE REFRAME — hunt asymmetry, not direction (the real deliverable, 2026-07-01)

The project spent itself proving **direction isn't predictable from price structure** (~9 negatives) —
true and worth knowing. The pivot: **stop hunting direction; hunt R:R asymmetry (geometry).**
- **Breakeven math changes "good":** 1:2 needs 33% win, 1:3 needs 25%. You don't need to predict
  direction — you need setups where *right = big, wrong = small.* The survivor: 40% win at 1:2 vs 33%
  breakeven = the edge is the **geometry**, never the direction call.
- **R:R is a STRUCTURE you find, not a number you pick.** Three questions, in order: (1) **invalidation
  level** = 1R (tight stop behind *nearby* structure); (2) **realistic target** = reward (*room* to the
  next level); (3) reward/risk ≥ 2 or **skip the trade.** Most charts become *no-trade* — correct.
- **The whole MTF machine, relabelled:** it was never a direction predictor — it's an **R:R engine.**
  The **LTF pullback manufactures the tight stop** (nearby level); the **HTF context says which way has
  room** (far target). Same machine, correct label. That's why "alignment doesn't predict direction but
  the pullback compresses risk" was the point all along, not a consolation prize.
- **Next move:** not "a better direction signal" — **"more setups with good geometry, stacked,"** +
  robustness (cost/RR-plateau ✓ done for NQ; **ES ←** the decider on whether the one geometry edge is
  structure or luck). Then: a fresh idea (this section closes the regime/spectral arc).
