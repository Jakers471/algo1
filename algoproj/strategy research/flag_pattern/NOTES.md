# Flag Pattern — Concept, Current State & Roadmap

*Living notes for the `flag_pattern` strategy. Captures the thinking behind it, exactly
what's built so far, and the open vision to build toward. As of 2026-06-30.*

---

## 1. The core idea

Price is **fractal**. It only ever does three things — moves **up**, **down**, or
**sideways** — and it does them at every scale, nested inside each other. The atomic unit
we care about is the **flag**:

> **large directional move (pole) → pause/consolidation (flag) → continuation (next pole, same direction)**

A bullish pole → consolidation → we want to trade the **breakout** that continues the
original move. Mirror for bearish.

The goal is a pattern that is **adaptive** — *not* pinned to a fixed % size or a fixed bar
count — so the same shape is recognized across time, across magnitudes, and eventually
across markets and timeframes. In the end we want to find the pattern at **many scales**
and line them up to reveal nested structure (small flags inside larger poles/flags).

---

## 2. How detection works today (and what it does NOT do)

Detection is **pure shape-matching by distance** — there are **no separate rules** for the
pole or the flag.

1. **Template** — a hand-drawn ideal flag, stored as **9 bars of OHLC** expressed as
   "% from where the window opened" (`signal_config.BULL_FLAG`, first 9 bars = the setup).
   That's 36 numbers. `BEAR_FLAG` is its mirror.
2. **Normalize every window** — take any 9 consecutive bars, divide all OHLC by the
   window's first open and subtract 1 → also 36 numbers in "% from its own open." This
   removes the **price level** (a flag at 5,000 and at 22,000 compare directly).
3. **Score = Euclidean distance** between the template's 36 numbers and the window's 36.
   `0` = identical shape, higher = less alike.
4. **Slide** the window across all ~1.36M bars, scoring every position (`algokit/patterns.py → scan`).
5. **Select** the closest, non-overlapping, in-session windows: keep scores under the top
   `MATCH_PCT` (0.1%), skip neighbors within `MIN_GAP`, and require the session filter.

**Critical clarifications (things easy to misunderstand):**
- It does **not** "detect a pole, then detect a flag." It matches the **whole 9-bar shape
  at once**. "Pole" (bars 0–3) and "flag" (bars 4–8) are just *labels on regions of the
  drawing*; the algorithm never reasons about them separately. **The drawing IS the rule.**
- It is **not magnitude-adaptive yet.** Normalizing by the opening price removes the price
  *level*, but the template is hardcoded to specific % magnitudes (~0.5% pole). A flag whose
  pole runs +2% produces ~4× bigger numbers → big distance → no match. So today's detector
  effectively means *"find ~0.5%-sized flags shaped like my drawing."* It adapts across
  **time and price level**, but **not across move size** — which is the gap vs the fractal goal.

There are **two axes of scale**, and the current template is frozen on both:
- **Magnitude** — how big the % move is.
- **Duration** — how many bars.

---

## 3. What we measure (forward outcome)

We match the **9-bar setup only** (pole+flag), then measure what happens after:
- **Entry** = the last flag bar.
- **`fwd`** = directional close-to-close return at horizons **1/3/6/12/24** bars
  (long: up = +, short: down = +).
- **MFE / MAE** = max favorable / max adverse excursion over the next `FWD_WINDOW` (12) bars.

Note: there is currently **no breakout detection** — "breakout" is just shorthand for the
forward window. The chart's green/red shading = whether the forward *close return* was
positive, not whether price structurally broke out of the flag.

---

## 4. Filters & context (time of day)

`analysis/time_of_day.py` bucketed every match by **hour in US Eastern** (NQ liquidity
follows the US session). Findings:
- Biggest moves (MFE/MAE) cluster **8 AM–2 PM ET**; **8 AM** has the largest swings.
- **Late afternoon (3–5 PM ET)** is chop — small MFE, negative returns ("low movement").
- Best quality windows ~ **10 AM and 2 PM ET**.

So a **session filter of 8 AM–2 PM ET** was adopted (`SESSION_*` in the config). It
sharpened the edge:

| | matches | bull fwd6 / win | bear fwd6 / win |
|---|---|---|---|
| all hours | 2243 | +0.011% / 52% | +0.007% / 47% |
| **8 AM–2 PM ET** | **1355** | **+0.018% / 54%** | **+0.026% / 51%** |

---

## 5. The system around it

- **`signal/signal_config.py`** — single source of truth for the signal: data (TF, history),
  geometry (window, pole bars, fwd window, horizons), templates, match threshold, de-overlap,
  and the session filter. Everything imports this.
- **`signal/nq_fractal_match.py`** — runs the signal, writes `findings/flag_<tf>.json`
  (each match: pattern, side, score, start/end/entry, `fwd`, `mfe`, `mae`; plus the session
  it was built with).
- **`findings/`** — the JSON the chart reads.
- **`test/nq_flag_breakout_test.py`** — sweeps the distance threshold to show how the
  forward edge holds with sample size.
- **`analysis/time_of_day.py`** → `output/` PNG + CSV.
- **`tv_chart/`** (separate, project-level) — standalone TradingView lightweight-charts
  viewer. Picks any findings file and overlays it: setup bands (pole=blue, flag=amber),
  forward window shaded green/red by outcome, entry markers, a horizon selector, combined
  totals, per-pattern stats, and a year/month activity breakdown. **This findings→chart
  loop is the key asset** — any future idea that emits findings JSON renders here with no
  new chart code. (No more exporting stacks of PNGs.)

**Folder layout:**
```
strategy research/flag_pattern/
  signal/      nq_fractal_match.py, signal_config.py
  findings/    flag_5m.json
  test/        nq_flag_breakout_test.py
  analysis/    time_of_day.py + output/
  experiments/ (one-off investigations)
  NOTES.md     (this file)
```

---

## 6. Where the edge stands (honest)

Even measured correctly (match the setup *before* the breakout, full 20 years, big sample,
session-filtered), the standalone edge is **tiny**: ~**+0.02%/trade**, win rate ~**50–54%**,
and **avg MFE ≈ |avg MAE|** (~0.22% vs −0.21%) — i.e. each setup wiggles roughly
symmetrically with no clean directional pop. The session filter sharpened it but did **not**
create a tradeable edge on its own. **Detection has never been the hard part; confirming a
forward edge is.** Every refinement must earn its keep against forward returns, not just
look right.

---

## 7. The vision / open roadmap

### 7.1 True adaptiveness (kill the two frozen axes)
- **Magnitude** → can be removed by normalizing each window's moves by its *own* size
  (range/volatility), so one template matches a small and a large flag of the same shape.
- **Duration** → genuinely different bar counts must be **scanned at several lengths**
  (9, 18, 36, 72…); a longer window holds more points and can't be collapsed away.

Efficient framing of the "blow it up into ~100 fixed windows" idea: **normalize away
magnitude** (one template covers all sizes) **+ run a handful of duration scales** — same
fractal coverage without a giant redundant template bank. Normalization is also what makes
cross-scale "lining up" *meaningful* (a 9-bar and 60-bar flag only count as the same fractal
unit once both magnitude and length are normalized to a common frame).

### 7.2 Fractal multi-scale & nesting
- Run the same (normalized) detector at multiple **durations** → findings per scale.
- **Line them up** = interval math on the timestamps we already store:
  - **Nesting (containment):** a small match's `[start,end]` sits inside a larger match's →
    small flag inside the big flag/pole. Stack → a tree.
  - **Confluence:** a flag fires at two scales at the **same time** → a stronger structural point.
- Value is as a **context/filter** (e.g. "take the small flag only when it sits inside a
  larger up-pole and larger flag" = trade *with* the bigger structure) — the same lever as
  time-of-day, but potentially much stronger.

### 7.3 Geometric detection: swings + fib retracement (likely the real direction)
**Why the template caps out — one window, not two.** Today a match is a **single** 9-bar
window holding the pole **and** the flag together; there are *not* separate windows for each.
And the split is fixed (`POLE_BARS=4` → 4 pole + 5 flag), so the pole length, the flag
length, **and** their ratio are all locked. It cannot represent a sharp 2-bar pole with a
long 10-bar flag, or vice-versa. Note: even multi-duration (§7.1 / approach A) only stretches
the *whole* window — the internal pole:flag ratio stays fixed at 4:5.

The real fix is to detect pole and flag as **separate components with decoupled lengths** —
a pole-swing of any length, then a flag-consolidation of any length — and pair them. That's
this section's direction. Concretely: replace the fixed picture with **size-free geometry**:
- Detect a **pole** as a directional **swing** (swing-low → swing-high), any size.
- Draw **fib 0→1** from pole bottom to top.
- Measure the **flag** as *how deeply it retraced* (e.g. 0.382 / 0.5) — a **ratio**, so it's
  identical whether the pole was 0.5% or 5% → inherently fractal/adaptive.
- **Breakout** = price reclaims pole top / pushes past 1.0; **stop** = flag low;
  **target** = a fib extension (1.618…).
This gives real, *separate* rules for pole, consolidation depth, S/R (flag high/low), and
breakout — which the template never will. It is the most direct path to "adaptive."

### 7.4 Consolidation & breakout rules
- **Fib retracement (IMPLEMENTED 2026-06-30):** fib 0→1 from pole bottom→top; `retrace` = how
  far the flag pulled back on a CLOSING basis (0 = none, 1 = full 100% retrace). Stored per
  match, drawn on the chart (0/0.5/1 lines for the active match) + shown in the readout
  (held/broke 0.5). `MAX_RETRACE` (config/CLI) filters to "strong" (retrace ≤ 0.5). Theory: a
  strong consolidation holds above the 0.5 fib; deeper = likely to fully retrace / roll into a
  larger-scale consolidation. Caveat: with the current shallow-flag template ~97% of matches
  are already ≤0.5, so the gate mostly bites on looser detectors (mag-free / future swings).
- **Consolidation quality (to refine):** beyond depth, a *clean* consolidation balances up/down
  within a **range** (equilibrium between the pole's high/low) without being too tightly
  bounded — think support/resistance / mean-reversion inside the range. Continuation = a
  **break/deviation out of that range**. The current template treats the flag as a fixed shape,
  not a balanced range; this needs real range / S-R logic (candidate for indicators).
- **Breakout (still undefined):** classically price exits the flag range in the pole's
  direction (bull: above flag high; bear: below flag low), confirmed by a close (+buffer)
  within a lookahead window — else the flag *fizzled* and is dropped. Then measure returns
  **from the breakout bar**, not the flag end.

### 7.5 Context layers (later)
- **Regime / indicators** layer (trend, volatility/squeeze, etc.) as additional filters.
- **Multi-timeframe** — the same pattern/structure across timeframes, not just bar-scales.

---

## 8. Open questions / next decisions

- Magnitude-free normalization vs swing+fib geometric detection — which becomes the primary
  detector? (Fib is the likely end-state; normalization is the cheap stepping stone.)
- If we keep scanning multiple durations, which set of lengths, and how to de-dupe across scales?
- How to formally define "broke out" vs "fizzled," and re-measure returns from the breakout.
- Where regime/MTF context plugs in without exploding complexity.

---

## 9. Experiments

### 9.1 Magnitude-free normalization (2026-06-30)
**Question:** if we match SHAPE regardless of move size (divide each window's %-moves *and*
the template's by their std), do we find the same flag at any magnitude — and is it better?

**Method:** `experiments/magnitude_free_norm.py`. Same template, session, and threshold;
only the scorer differs (`patterns.scan` vs `patterns.scan_free`). Compared count, fwd6,
win%, and the **size spread** of matched windows (range% p10/p50/p90).

| method | pattern | n | fwd6 | win% | range% p10/p50/p90 |
|---|---|---|---|---|---|
| current  | bull | 705 | +0.018 | 53.9 | 0.45 / 0.53 / 0.63 |
| mag-free | bull | 523 | +0.005 | 50.5 | 0.12 / 0.27 / 0.55 |
| current  | bear | 650 | +0.026 | 50.6 | 0.46 / 0.55 / 0.65 |
| mag-free | bear | 469 | +0.007 | 44.6 | 0.13 / 0.30 / 0.73 |

**Result:** the mechanism **works** — `range%` goes from a tight ~0.5% band (current) to a
wide 0.12–0.73% spread (mag-free), i.e. it now detects the shape at many sizes. **But the
edge dropped** (fwd6 +0.018→+0.005, win → ~50/45%). Tiny wiggles vastly outnumber big moves,
so removing size-preference floods the matches with small, noisy flags (median size halved
0.53%→0.27%).

**Conclusion:** the current size-sensitivity was an *accidental quality filter* (bigger
moves = more meaningful). Magnitude-freedom **alone, at a fixed 9-bar length, is not the
unlock.** Real fractal scale-up belongs on the **duration axis** (more bars), or mag-free
needs a **minimum-size floor**.

**Visual confirmation:** saved as a findings file (`findings/flag_5m_free.json`, via
`--norm free`) and viewed on the chart — confirmed varied move sizes and small pole→flag
chains, while every match was still exactly 9 bars (duration not yet varied).

---

## 10. Where we are now — log & decisions (2026-06-30)

- **Two axes confirmed.** `free` removed the **magnitude** axis (visible size variance on the
  chart). The **duration** axis is still hardcoded (`WINDOW=9`) → every match is 9 bars.
- **One window = pole + flag** (fixed length *and* fixed 4:5 split). Pole/flag are labels for
  coloring/breakout, not separately-detected components. See §7.3.
- **The fork:**
  - **(A) Multi-duration scan** — run the same template at several lengths (9/18/36…),
    interpolating the 9-bar shape to each length. Quick, reuses the template; gives total-
    length variance but keeps the internal pole:flag ratio fixed. **← chosen to do first.**
  - **(B) Separate pole-swing / flag-consolidation detector** (swing + fib, §7.3) — decoupled
    lengths, the real adaptive unlock. Bigger build; documented, deferred.
- **Findings naming convention:** `flag_<tf>.json` (base 9-bar, level), `_free` for
  magnitude-free, `_w<L>` for a duration scale — e.g. `flag_5m_w18_free.json`. All render in
  the chart via the dropdown.
- **Building now:** approach A (multi-length scan).

---

## 11. Rant 2 — fib, alignment, consolidation (2026-06-30)

Discretionary definition of a **perfect pattern** (works both directions):
- A **large move (pole)** that is **bigger / more noticeable than the moves around it** — a
  clear deviation up (bullish) or down (bearish).
- Followed by a **pullback that does NOT close below the 0.5 fib** of that pole. Reasoning
  (supply / demand / equilibrium): a move that gives back >50% is less likely to continue and
  more likely to fully retrace → which itself becomes a **consolidation on a higher level**
  (more bars). The failure of a small pattern *is* the formation of a bigger one. Fractal.
- Motivating observation: saw matches marked "won" (fwd +) that had actually **trended down
  and ~100% retraced** the pole — the fwd-return label alone misses this; the **fib gate
  catches it**. (This is why fib was added — §7.4.)

**Alignment / trend score (idea, not built):** bullish patterns nested inside bullish (and the
bear mirror) → an **alignment score**; many aligned = more trending. The trend-following layer
that combines bull + bear patterns into a directional read. Related to §7.2 nesting/confluence.

**Consolidation refinement (idea):** detect consolidations as a **balanced range / equilibrium**
(S/R within the pole's high–low), not a fixed shape — clean = oscillates within a range without
being too bounded; continuation = a break/deviation out of it. Likely needs indicators.

**Impressions:** the *first pole* it finds is impressive; consolidations are weaker / need work.
Direction feels right — keep refining.

**To test / build next (open):**
- Approach **B** (separate pole-swing / flag-consolidation, decoupled lengths) — the big unlock.
- Tune the fib gate: does `MAX_RETRACE ≤ 0.5` improve forward edge on the looser (free / multi) detectors?
- Alignment / confluence score across nested scales (§7.2).
- Range / equilibrium-based consolidation detection (+ indicators).
- Breakout definition (fizzle vs break) and measuring returns from the breakout bar.

---

## 12. Rant 3 — the consolidation problem & approach B (2026-06-30)

Annotated example: `images/example_bear_flag_387.png` (bear flag, match #387).

### The problem the screenshot exposes
The **pole** is great — a sharp, clearly-deviating bearish decline (blue band). But because we
use a **fixed bar-count window**, the "flag" region (everything after the pole) is a static block
that (a) lumps the whole multi-part consolidation together, and (b) **ends long before the real
continuation**. The actual breakout/continuation pole (the circled big red candle on the far
right) happens *way* outside the fixed window — the window can't "wait" for the consolidation to
resolve. **This is what's dampening the pattern.**

### What a real consolidation looks like (read off the chart)
- It has an **equilibrium / center** (a near-horizontal range median).
- It can have **sub-structure / multiple equilibriums**: price chops around one center, drifts a
  little, forms a second (longer) center — both part of one larger consolidation but with a
  shifting median (the drawn blue lines).
- The **0.5 fib acts as resistance** against the pole's opposite direction — price repeatedly
  fails there. **Wicks above 0.5 do NOT count as a break**; you need a real, decent-size deviation
  (a CLOSE beyond, maybe with a buffer, e.g. 0.56). Hard "0.5 close-break = cancelled" is the
  simple version to test first.
- **Continuation** = price finally **breaks the consolidation range in the pole's direction**
  (the circled candle) — that's the breakout pole start. Not a fixed number of bars later.

### VWAP idea (candidate indicator)
Anchor a VWAP (or a VWAP band/range) from the pole start→end. The consolidation is price
"hovering" around/below the 0.5 mark within that band; the **continuation triggers when the VWAP
range is broken in the pole's direction**. Gives a volume-weighted equilibrium for the
consolidation center + a concrete breakout trigger. NOTE: needs volume in the data — verify; if
absent, use an anchored mean / range median as a proxy.

### Two paths considered
1. **More windows + alignment** — scan many more sizes, find lots more patterns, then ALIGN them:
   what is nested inside what, at what window size (**spatial**), and **when** (**temporal**) —
   both matter. This is the §7.2 nesting layer taken further. BUT it still stacks the same
   fixed-shape / fixed-ratio unit; it does **not** fix the consolidation problem, it just organizes
   more flawed units. Valuable as a LATER combination layer, not a fix.
2. **Approach B** — detect pole and flag as separate, variable-length components. Fixes the
   consolidation problem at the root.

**Decision: go with B.** The spatial + temporal alignment (path 1's good part) is the next layer
ON TOP of B, once the unit is clean.

### Approach B — how it actually works (event-driven state machine)
Not a sliding-window template match anymore — a state machine that walks the bars:
1. **Find a pole = a swing.** Detect directional swings (pivot/zigzag, or ATR/%-based): a run from
   swing-low→high (bull) or high→low (bear) that is **noticeably bigger than the moves around it**
   (the "deviation"). Variable length. Record its fib 0→1.
2. **Enter consolidation-watch at the pole's end.** Track a range / equilibrium (midpoint, mean,
   or VWAP). The flag **persists** as long as price holds — does NOT close beyond the 0.5 fib
   against the pole (with the wick-vs-close / buffer rule). Length is open-ended.
3. **Resolve (price-driven, variable length):**
   - price breaks the consolidation range in the **pole direction** → **continuation** (valid
     pattern; the breakout pole starts here; measure outcome from here), OR
   - price closes beyond 0.5 against the pole → **cancelled / failed** → rolls into a *larger*
     consolidation (a higher-scale pattern — fractal).
4. Pole length, flag length, and the breakout location are all set by **price**, not a bar count.
   This directly expresses the discretionary definition.

**Tradeoff:** B has more rules/params (swing sensitivity, the 0.5-break rule + buffer, range
definition, breakout trigger) and is more work than the template — but it captures the real
structure and is fully adaptive. Then run B at multiple scales and apply path-1 alignment on top.

---

## 13. Integration goal — everything assembles here, then backtests in the webui (2026-06-30)

The strategy is being built in pieces (pole detection, consolidation rules, fib, filters,
alignment, indicators...). **All of it is controlled from one place: `signal/signal_config.py`**
— that's the assembly point. As each piece lands, its knobs go into the config, not scattered.

**End goal:** run the finished strategy as a **backtest in the webui** (`algoproj/webui/`). The
webui already backtests strategies — a strategy there is a module in `algoproj/strategies/`
(e.g. `strategies/fanning_mtf.py`) with a **`DEFAULT` dict that "is the strategy"** + a
**`run()`** that returns equity/trades/stats; the webui's chart, report, and run registry all
read it.

**The bridge (planned, not built):** a thin **`strategies/flag_pattern.py`** adapter that
- imports the flag_pattern controls (`signal_config`),
- turns detected signals into **entries/exits** (entry = breakout, stop = flag low, target =
  fib extension, etc.),
- runs the backtest via `algokit.backtest` / `costs` / `metrics` (same as fanning_mtf),
- exposes `DEFAULT` + `run()` so the webui picks it up automatically.

So: **research side** (this folder) discovers/visualises signals → **config** is the single
control panel → **adapter** turns it into a tradeable, backtestable strategy in the webui. Keep
the config clean and complete so that final bring-together is easy. Execution/cost/sizing knobs
are stubbed in the config's "future controls" section for exactly this.

---

## 14. Approach B Stage 1 (swing poles) — tried & ARCHIVED (2026-06-30)

Built a swing/pole detector (ATR zigzag → legs >= POLE_ATR_MULT x ATR = poles) and put the raw
poles on the chart. It did not work as something to look at:
- ~**32,000** poles; a single big candle qualifies as a 3x-ATR "pole" → noise, not sustained moves.
- More fundamentally, **a pole alone is not a pattern.** Dumping every swing is chaos with nothing
  coherent to recognize. Judging a pole detector visually was the wrong call.

Archived to `_archive/` (`nq_swing_poles.py` + `poles_5m.json`). The full swing-based rebuild is
shelved. **Pivot:** keep the template detection that already found recognizable flags (the `free`
version the user liked) and fix ONLY the real complaint — the fixed-length consolidation. See §15.

## 15. Hybrid — template setup + variable-length consolidation watch (2026-06-30)

Keep the mag-free **template match** to find the pole+flag SETUP (recognizable, clean, few). Then,
instead of a fixed forward window, **WATCH the consolidation forward** from the setup:
- it must **hold the 0.5 fib** of the pole (closing basis) — else **FAIL** (cancel; rolls into a
  bigger consolidation, §12),
- it **BREAKS OUT** when price closes beyond the consolidation range in the pole's direction, OR
  prints a >= `BREAKOUT_ATR_MULT` x ATR bar that way,
- capped at `CONSOL_MAX_WATCH` bars (timeout).

Only **breakouts** are kept as valid patterns; the flag band is **variable length**
(pole_end..breakout), and the forward outcome is measured **from the breakout**. Fixes the
screenshot problem without the swing chaos. Script: `signal/nq_flag_breakout.py`.

---

## 16. Rant 5 — regime detection as the fractal backbone (2026-06-30)

Key reframe from the user: **pole / flag / breakout IS a regime sequence** — trending up/down
(pole, breakout) vs consolidation/equilibrium (flag). So regime detection isn't a side quest; it
may be the adaptive, **no-fixed-bars** way to detect the pattern itself. Also flagged (again):
*"inherently i don't like having a fixed bar pole... don't like fixed anything really."* The hybrid
(§15) made the FLAG variable, but the POLE is still the template's fixed 4 bars — that's the open
tension these ideas could resolve.

Two methods introduced (user prototyped them earlier; not 100% sure how they compute; sources partly lost):

### (a) Multi-scale efficiency decomposition
Images: `images/idea_mtf_efficiency_heatmap.png`, `images/idea_binary_scale_decomposition.png`
- Compute a directional **efficiency** score (trend vs chop; ~Kaufman efficiency ratio) at MANY
  lookback scales and across timeframes (1m/5m/15m/1h/4h). Green = efficient up (bull), red =
  efficient down (bear), dark = chop. Stack all rows → a fractal regime map. (35 rows = 5 TFs × 7
  lookbacks in the MTF one.)
- The "binary" version stacks scales L=1..512 on one series + candle **anatomy** rows (body ratio,
  close position, wicks), and reports how often ALL scales AGREE ("full agree: 1.3% bull / 3.9% bear").
- **Why it matters:** this is the scale-free, no-fixed-bars read the user keeps asking for. A pole =
  a stretch of high UP-efficiency; a flag = a stretch of LOW efficiency (chop/equilibrium); a
  breakout = efficiency re-igniting in the pole direction → pole/flag/breakout with ZERO fixed bar
  counts. It's also the **alignment** idea (§7.2): where scales/timeframes agree = strong trend.
- Source: not pinned down (older quanted-era experiment; likely moved/deleted). Concept captured here.

### (b) 32-MA fan regime
Images: `images/idea_32ma_fan_regime_1d.png`, `images/idea_32ma_fan_regime_1h.png`
- A fan of 32 MAs: stacked + expanding = trend (green up / red down), tangled = sideways (yellow);
  bottom panel = a 0–100 regime score (bull thresh 70).
- Source: `_archive/research_backup_2026-06-30/regime/nq_mtf_regime.py` (the MTF regime engine we
  built earlier in algoproj), same family as the live `strategies/fanning_mtf.py`.

### How they'd fit (my read)
1. **Context / alignment FILTER (near-term, cheap, testable):** only take a hybrid flag when a
   higher scale / timeframe regime supports the pole direction (trade *with* the bigger trend).
   This is the user's "alignment score."
2. **Adaptive detector (long-term, the real prize):** replace the fixed-template pole with an
   efficiency-based phase read — high-efficiency directional run = pole, low-efficiency = flag,
   efficiency re-ignites = breakout. Nothing fixed; phases defined by efficiency transitions at
   whatever scale. This is the answer to "I don't like fixed anything."
- Keep combining with fib / ATR / VWAP as before (pullback depth, breakout trigger).

---

## 17. Detection architecture — sensor vs. state machine (synthesis of outside_feedback.md, 2026-06-30)

An outside review (`outside_feedback.md`) pushed the detection theory hard. The load-bearing ideas:

**1. Coherence is in the RELATIONSHIP, never in a component.** A pole is *retrospective* — a big
directional leg only becomes a "pole" once something pauses off it. Detecting poles in isolation
(§14) failed because the object doesn't exist yet. The template worked *despite* its rigidity
because it encodes the pole→flag relationship in one gestalt. Every dead end = detecting a
component alone; every step forward = re-anchoring on the relationship.

**2. Descriptor ≠ machine.** The 32-MA fan and the binary/efficiency decomposition are **state
descriptors** — per-bar labels ("what regime is this bar?"), no memory. The pattern is a **parse**:
"because-pole, therefore-watch-flag, confirmed-by-breakout" — the relational binding of phases over
time. That binding needs a **state machine**. So the fan/decomp are the **sensor** the machine
reads, NOT the machine. (Ribbon green-yellow-green ≠ the pattern.)

**3. Substrate: magnitude → efficiency.** How to say "significant": fixed % (rigid) → ATR magnitude
(adaptive but WRONG axis — measures *bigness*, so a single fat candle qualifies as a pole) →
**directional efficiency** (net displacement / total path; dimensionless 0–1). Efficiency and
magnitude are orthogonal (violent chop = high ATR, ~0 efficiency). Efficiency is unitless → truly
comparable across scales → the real answer to "no fixed anything." (Caveat: it still needs a
lookback = a scale; the knob relocates, it doesn't vanish.)

**4. The machine (target architecture).**
`SEEKING → (sustained high directional efficiency) → POLE-CONFIRMED (anchor fib 0–1) →
FLAG-WATCH (efficiency drops; price oscillates around a center, holds the 0.5) →
BREAKOUT (efficiency re-ignites in pole dir → emit; the breakout SEEDS the next pole = recursion) 
OR FAILED (close past 0.5 → PROMOTE the pole+partial-flag into a node of a LARGER consolidation).`
Phase lengths are set by *when transitions fire*, not bar counts. The **failure branch builds the
nesting tree causally, in time** — multi-scale structure falls out of the machine running, instead
of being reverse-engineered by aligning fixed-scale scans (§7.2).

**The binding is structural, not computed.** FLAG-WATCH can only be *entered from* POLE-CONFIRMED and
carries the pole's fib with it — so a flag is *automatically* bound to the pole you were holding when
you found it. You can't produce an orphaned flag or a context-free pole (exactly what the 32k swing
dump was). The relationship is the **substrate, not an output**: prior versions detected poles + flags
separately and reconciled them *after the fact*; the machine makes the relationship the only way
anything can happen. The sensor (efficiency/fan), the fib (invalidation line), the ATR consult it as
**stateless inputs** — the machine is the *only* stateful piece, and memory-of-what-came-before **is**
the relationship. Hence it's the last piece, not the first.

**5. Consolidation is negative space (the hard part).** A pole announces itself; a flag is the
*absence* of an event until it resolves. Needs **two-sided** quality: a **center** it balances
around (anchored VWAP if volume, else anchored mean / range median) + a **boundary** (0.5) it can't
close past; a healthy retrace *breathes* (~0.3–0.5), not too tight.

**Honest caveats (mine, not in the feedback):**
- The feedback is a brilliant map of the **detection** problem and **silent on edge**. Architecture
  is necessary, not sufficient. Our one real data point — regime-aligned breakouts ~3× better
  (§16 / regime_align) — outweighs any amount of elegance until we have more like it.
- The state machine trades the template's *one* coherent knob (distance) for *many* transition
  thresholds ("high" efficiency, "sustained", "pause"…). Flexibility has a tuning cost.
- "Truly scale-free" is oversold: you still choose which efficiency lookbacks to run — which is
  exactly the timeframes in §18.

## 18. Multi-timeframe (3-TF) framework (2026-06-30)

The concrete, tractable instantiation of §17's recursive machine: **pin the scales to 3 chosen
timeframes** and couple them top-down.

- **HTF = context** (e.g. 1h): overall direction — buy / sell / wait.
- **MTF = confirmation** (e.g. 15m): the setup timeframe.
- **LTF = entry** (e.g. 1m): where you pull the trigger.
(Roughly geometric progression; the exact TFs could eventually be auto-chosen.)

The **same fractal flag** runs on all three; 3 phases (pole → flag → breakout) × 3 TFs. Coupling =
top-down gating:
- HTF in **pole** → beginning of the move → wait.
- HTF in **flag** (range) → wait for direction (though the LTF has intraday opportunity *within*
  the HTF range).
- HTF **bull breakout confirmed** → **longs only**. Inside it (big green candles) drop to MTF and
  look for the *same* flag; when **MTF breaks out**, step to LTF and look for the *same* flag again.
- **Entry on the LTF:** buy-stop at the **consolidation high**, protective stop at the
  **consolidation low** (the won/failed rule, one scale down).

**Why this is the point (the R:R mechanism):** you may be "trading the MTF breakout," but entering
on the **LTF gives a tight stop** (LTF consolidation low) while the **HTF supplies the runway**. The
small LTF risk aggregates into the larger move → far better risk/reward than trading the MTF
directly. This is plausibly the **fix for the drawdown problem** `forward_horizon` exposed (5m
drawdown ~0.25% dwarfs the ~0.04% return; a 1m stop is a fraction of that).

**Reset / reverse the sequence:** LTF fails → keep watching the LTF *unless* price closes below the
50% fib on the MTF → wait for the MTF to re-setup → until the HTF breaks down → whole sequence resets.

**Connection to what's built:** the regime-alignment filter (§16, `regime_align`) — 1h fan regime
gating 5m breakouts, aligned ~3× better — is already a **2-TF slice of exactly this** (HTF context
gating a lower-TF setup). First real evidence the top-down thesis has teeth. The full 3-TF version
adds the LTF tight-entry — the untested, highest-value piece.

---

## 19. Growing the sample — plan (2026-06-30)

Only ~83 1h-aligned 5m breakouts over 20 years — statistically thin (59% win at n=83 ≈ ±11% at
95%) and too infrequent to trade standalone. But 83 = aligned *contexts*, not trades (the MTF
LTF-entry multiplies each). Prioritized fixes:

**DO NOW**
1. **Loosen the setup threshold.** `MATCH_PCT = 0.1` (closest 1-in-1000 windows) is over-strict for
   a rigid template. Loosen toward ~1% for 5–10× more setups, and let the *meaningful* downstream
   filters (held 0.5 / broke out / aligned) do the quality work. Test whether the ~3× aligned lift
   holds at the bigger sample (if it collapses, the 3× was small-sample luck — cheap to learn).
2. **Add timeframes.** The fractal claim requires the pattern on 1m/15m too; 1m alone ≈ 5× the bars.
   Run the same detector per TF. (Nested TFs aren't fully independent — don't sum for significance,
   but real for tradeable frequency.)

**DO LATER**
4. **Alignment as a CONTINUOUS feature**, not a binary gate — keep all breakouts, study outcome vs.
   regime score across the full range instead of discarding ~80%.
5. **More markets** (user has ES futures data; add CL/GC/crypto/etc. later). The universality thesis
   *demands* the pattern generalizes across instruments; each market = a fresh 20 years + genuine
   out-of-sample proof. This is the real sample-size + validation fix.

**Rule:** grow N through **breadth (markets × timeframes)**, never by lowering quality thresholds —
loosening quality just inflates the count with noise (fitting nothing). Breadth adds independent
evidence *and* tests the "works across markets" claim.

---

## 20. R:R test — the deciding experiment (2026-06-30)

Every prior measure was close-to-close held through the full drawdown (can't see a breakout's real
edge). This one trades each breakout properly: **entry** = breakout close, **stop** = consolidation
(flag) low, **target** = entry + targetR × risk (swept), exit on first of stop/target (stop-first
within a bar = conservative), else close after MAX_HOLD. Metric = **expectancy in R**.
Script: `analysis/rr_test/`.

**Result (1,915 breakouts, pct 0.5):**
- Natural excursion: **median MFE +0.81R, median MAE −1.00R** → the typical breakout travels ~0.8R
  in favor and reaches the stop. Symmetric-to-negative — **no asymmetry to exploit.**
- Expectancy ≈ **zero** at every target: 1R −0.008, 1.5R −0.023, 2R −0.003, 3R +0.005 (the "+0.005R
  best" is statistically nothing — wins only 10% at 3R while stopping out 54%).
- Aligned-only (397): same / slightly worse (best +0.003R).

**VERDICT: a proper stop/target does NOT rescue it.** The flag breakout on 5-min NQ has ~zero
expectancy. The MFE median of 0.81R < 1R says the breakout doesn't even reliably travel one unit of
its own risk before reversing.

**Cumulative honest state:** the 5-min NQ single-timeframe flag breakout shows **NO edge in ANY
measurement** — raw forward return, return/drawdown ratio, regime-alignment split, and now R:R
expectancy, all ≈ 0. The pattern is a real, recognizable **structure**, but it is not a standalone
predictive **edge** on this market/timeframe (consistent with: a widely-known chart pattern
shouldn't carry naked edge).

**Open options (honest):**
1. **Breadth** — test the fractal/universality claim on other instruments (ES on hand) + timeframes.
   Either it finds edge somewhere or it definitively kills the "works across markets" thesis. The real test.
2. **Reframe** — treat the flag as a *context/feature* inside a larger model, not a standalone signal.
3. The MTF LTF-entry is the last untested variant, but its premise (HTF context predicts continuation)
   already failed the regime test — so the evidence is against it.

---

## 21. Multi-scale context edge + the pivot to structure_detection (2026-07-01)

Explored: does the flag breakout have a CONDITIONAL edge on multi-scale trend context (a richer
version of the 1h-regime test)? For each breakout, computed directional **efficiency** (net move ÷
path length — "as the crow flies ÷ distance actually walked") over 5 lookbacks (10/20/40/80/160
bars), signed + when the trend agrees with the pole, averaged into one context score.
Scripts: `analysis/context_edge/` (context_edge.py, rr_by_context.py, viz_*.py).

**FINDING (the most promising result so far):**
- Close-to-close: a faint, *sensibly-shaped* signal (top quintile modestly better, stronger at
  longer scales / longer holds). Too small to trust alone.
- **R:R by context quintile** (entry = breakout, stop = consolidation low, target in R) showed a
  **real gradient:** Q1 (chop / against the trend) **−0.06R**, Q4/Q5 (clean trend, agrees)
  **+0.05..+0.08R**; the whole set ≈ 0 because winners and losers **cancel.** So the flag has no
  NAKED edge but a **CONDITIONAL** one — it pays when it fires *with* the bigger multi-scale trend,
  loses against it. This is why every all-in test came up empty.
- Visuals: `viz_efficiency_simple.png` (crow-flies analogy), `viz_outcome.png` (a high-context WIN
  vs a low-context LOSS — same pattern, opposite context).

**HONEST CAVEATS:** in-sample over one 20-yr stretch; ~383/quintile; not perfectly monotonic; thin
vs costs. **NOT yet validated out-of-sample** (the make-or-break — split history in half, does the
gradient hold in both?). Feature matrix saved (`context_matrix_5m.csv`) for reuse.

**MISUNDERSTANDING corrected:** the user's original "scan many windows" idea is NOT the
context-feature-at-breakout reframe above. It's a multi-scale **DECOMPOSITION that FINDS the
pattern's pieces** (binary-decomposition style; cf. `images/idea_binary_scale_decomposition.png`):
run windows of increasing size, each folding in more data than the last, aware of both **temporal**
(when) and **spatial** (where in price — the micro-structure inside each window), and assemble the
pieces into structure. That is a different *detection method* on the same fractal principle.

**PIVOT:** pausing the flag_pattern template/hybrid line. Opening a sibling strategy
`strategy research/structure_detection/` to pursue the decomposition-based detection. The
conditional-edge finding (**trade WITH the multi-scale trend**) and all lessons (§17 sensor-vs-
state-machine & relationship-over-components; §6/§20 edge is the gate) carry forward.

---

## 22. Un-freezing the pole — dynamic candle-by-candle trace (2026-07-01)

Came back to the flag_pattern line (the §21 pivot to `structure_detection/` stays open in parallel;
the user wanted to push the template/hybrid further first). The thread this session: **stop freezing
the pole.**

### Supporting changes made first
- **Geometry bumped 9→40 bars** (`WINDOW=40`, `POLE_BARS=10`): pole 4→10, flag 5→30, at the user's
  request ("stick to frozen, but bigger"). The drawn 12-bar template is interpolated **pole-segment
  and flag-segment separately** (4→10, 5→30) so the frozen shape is kept at a **10:30** ratio (not a
  stretched 4:5). Backward-compatible at 9/4. Rescan (level): fwd6 bull +0.007%/52%, bear
  +0.001%/45% — a bigger frozen setup did **not** help edge (expected: a 30-bar flag at the template's
  fixed ~0.5% magnitude is a flat drift).
- **Session hard-stop fix:** the filter was hour-granular + inclusive, so the whole 2 PM hour (through
  2:59) leaked in. Now **minute-precise 8:00 AM–2:00 PM ET** (`session_mask` uses hour*60+minute).
  Dropped ~370 late matches; starts now span exactly 08:00→14:00 ET.
- **Chart:** the pole fib levels are now **pole-anchored horizontal segments** (top=red, bottom=green,
  0.5=yellow) extending right from the pole — not full-width price lines — so they read as the *pole's*
  levels through the flag. Also the **time axis + crosshair now display ET** (were UTC; 8–2 ET showed
  as 12–7). Display-only; underlying timestamps stay UTC epoch, overlays unaffected.

### The core idea (the user's rule)
The static window is just a **seed dropped inside a move**; grow the pole from it candle-by-candle to
its TRUE extremes both directions:
- **Forward** (bearish): follow price down while the next candle does **not close above the current
  candle's high** (by a buffer, so wicks don't count). Deepest low = pole bottom / end. Mirror bullish.
- **Backward:** the pole usually started earlier/higher than the seed; walk back while each earlier
  candle does **not close below the current candle's low**. Highest high = the true origin / start.

This is the SEED → STATE-MACHINE split (§17) done cheaply: the scan is the coarse **sensor**, the walk
is the per-candle **machine** that only ever runs **inside a matched pole** — so it cannot produce the
§14 32k context-free swings. It also finally makes the fib meaningful: 0→1 spans the *real* swing.

Script: `dynamic_pole/dynamic_pole.py` → `findings/dynamic_pole_5m.json` (renders via the variable
`pole_end` field). Knobs (config): `POLE_TRACE_BUFFER_ATR` (counter-close must clear by this ×ATR),
`POLE_TRACE_MAX_BACK/FWD` (caps), `POLE_TRACE_MIN_BARS`.

### Results (2026-07-01)
- Static pole = 10 bars. **Dynamic (reversal rule) = median 21 bars** (min 3, p90 34, max 74) — real
  poles run ~2× the frozen 10 and vary 3→70+. **90% extend backward** (median +8 bars; confirms "the
  pole should've started higher"); 58% extend forward past the seed.
- **Completeness gauge (accidental but useful):** fwd6 return *from the pole end* measures whether
  price kept going *after* we quit. Cutting too early → high "win" (move still running); a complete
  pole → **low win** (price reverses after). Reversal-rule poles: fwd6 −0.049% / **24% win** = price
  reverses ~76% of the time right after the pole ends → the trace lands near real exhaustion. (This is
  a detection-quality signal, NOT an edge claim.)

### The progress-guard lesson → fraction-of-pole (next build)
First tried a **no-progress guard** (end the pole when it stops making new extremes) but as a **1-bar**
rule → far too twitchy (one pause bar killed the pole → 6-bar stubs, 84% "still going"). The user
confirmed the **concept is right** (a pole should end when it *cools down*, not only when it fully
reverses) — the **scale** was wrong. Chosen fix (user's, most natural): **fraction-of-pole patience**.
- Track `pole_len` (bars start→current extreme) and `stall` (bars since last new extreme); a new
  extreme resets `stall` and grows `pole_len`.
- End the pole when **`stall ≥ f × pole_len`** (cooled down) OR a hard counter-close fires (reversal) —
  whichever first. `f≈1/3`: a 10-bar pole may drift ~3 bars to resume; a 30-bar pole ~10. Self-scaling,
  no fixed bar count. `f=1` = max patience (wait a full pole-length).
- **Caveat to watch on the chart:** long poles could tolerate long stalls (60-bar pole → ~20-bar
  "breath" that's really a flag). If poles swallow their own consolidation, cap the patience / lower f.
- **BUILT (2026-07-01), `POLE_TRACE_STALL_FRAC` (default 1/3):** applied to the FORWARD walk (backward
  stays reversal-only). vs pure reversal it trims exactly the over-runners the caveat feared — **max
  pole 74→48 bars**, median barely moves (21→19), 91% still extend back. Confirms the self-scaling
  works: normal poles untouched, only bloated ones (pole+flag mashed together) get cut at cool-down.
  Ends on whichever fires first: counter-close (reversal) or stall > f×length (cooled). All five
  `POLE_TRACE_*` knobs live in `signal_config.py`; `f=0` = pure reversal rule.

### Flag-watch tie-in — pole → flag → breakout on the dynamic pole (BUILT 2026-07-01)
The cool-down IS the pole→flag transition: when the pole stops trending, the flag has begun. So the
consolidation watch starts exactly at the true pole extreme (`pole_end`). Reused the hybrid's watch
(`_watch`, §15) but anchored on the DYNAMIC pole: hold the pole's 0.5 fib (closing basis) or **fail**;
close beyond the consolidation range in the pole direction (or a ≥`BREAKOUT_ATR_MULT`×ATR spike) =
**breakout**; else **timeout** at `CONSOL_MAX_WATCH`. Breakout is the pole rule firing again → seeds
the next pole (recursion, §17). `dynamic_pole.py` now runs the full pole→flag→resolve machine and keeps
breakouts (outcome measured FROM the breakout). Watch knobs reused from config (`FIB_HOLD`,
`BREAK_BUFFER`, `BREAKOUT_ATR_MULT`, `CONSOL_MAX_WATCH`).
- **Result (2026-07-01):** 1637 poles → **67% broke out** (1093), 20% failed (held-0.5 broken), 13%
  timeout. Kept breakouts: pole median 18 bars, **flag median 11 bars** (p90 43, variable). fwd6 from
  breakout **−0.018% / 37% win** — i.e. still **no naked edge** (consistent with §6/§20), as expected;
  the point of this build was to tie the flag in and SEE it, not to find edge. The fib/range now sit on
  the *true* swing, so the flag rails are meaningful.
- **Chart:** added an **EMA fan indicator (10/20/50/100/200)** — `indicators/emas.py` +
  `algokit.indicators.ema`; appears in the indicator panel automatically. For eyeballing trend /
  dynamic S-R around the poles & flags (candidate filter later).

### Seed source + VWAP breakout (2026-07-01)
- **ATR-spike seeding tested & reverted.** Added `SEED_MODE` (`template` | `spike`); spike = seed a
  pole wherever a candle body ≥ `SPIKE_ATR_MULT`×ATR, then trace/watch/filter as usual. Result: 3×
  more seeds but **64% failed the 0.5 hold** (vs 20% for template) → fewer clean setups (201 vs 386).
  Confirms §14/§17: ATR = *bigness*, not a pole; the downstream machine correctly rejects lone fat
  candles/chop. Kept as an option (`--seed spike`) but default back to **template** (it pre-qualifies a
  pole+flag shape). The principled fix if revisited = seed on directional **efficiency**, not magnitude.
- ⭐ **STARRED (user likes this) — anchored VWAP as the consolidation equilibrium.** The volume-weighted
  center the flag balances on, with an ATR band, is a keeper: it gives the consolidation a real
  two-sided definition (center + boundary, §17.5) and a concrete, *visible* breakout reference. This is
  the piece to build the breakout/entry/stop logic around going forward.
- **Breakout redefined around the consolidation equilibrium (NOTES §12 realized).** Volume is present
  and fully populated, so the breakout now references an **anchored VWAP from `pole_end`** (the
  volume-weighted center the flag balances on) with a band = VWAP ± `BREAKOUT_VWAP_K`×ATR. Breakout =
  a **close beyond the band in the pole direction** (a real deviation from fair value) instead of
  poking the consolidation's extreme bar. Emitted per breakout as a `vwap` series and **drawn on the
  chart** (cyan center + dashed band) for the active match.
  - **Effect:** breakouts 66%→**79%**, timeouts 219→**66**, kept (flag ≥20) 386→**528**; fwd6 still
    ≈0 (−0.005% / 41% — a trigger change was never going to create edge). Value = principled,
    *visible* equilibrium trigger; more patterns resolve instead of timing out.
- **Filters:** `POLE_TRACE_MIN_BARS=5` (drop poles ≤4 bars), `CONSOL_MIN_BARS=20` (drop flags <20
  bars). All seed/trace/consolidation knobs live in `signal_config.py`.

### Sample-size diagnosis (2026-07-01)
Why only ~528 over 20 yr? Traced the funnel: 1.36M windows → ~1,696 seeds (closest 0.5% shape +
session + de-overlap) → 1,559 poles (≥5 bars) → 1,234 breakouts (79%) → **528** (flag ≥20). Key
finding from a seed-threshold sweep (0.5→5%): loosening the seed **10× only ~2×'s the kept count**
(528→1,078) and the pole/flag geometry is **unchanged** — so **the seed is NOT the binding
constraint; the downstream conjunction is** (most setups never form a 20-bar hold that then breaks
out). Loosening the seed to ~2% is a free ~2× (quality intact, not the §19 "lower quality" trap). The
real sample fix is **breadth** (§19): more timeframes (1m ≈ 5× bars), more instruments (ES/CL/GC = a
fresh 20 yr + genuine OOS each), and MTF nesting (§18) where trade *frequency* lives. Reframe:
~500–1,000/instrument/TF is thin for one market but fine as *evidence if it generalizes*.

### VWAP-band R:R backtest (2026-07-01) — FIRST positive R:R
`dynamic_pole/vwap_rr/`. Entry/stop on the VWAP band at the breakout: bearish = SELL-stop at lower band,
stop above upper band (bullish mirror); 1R = band width; target = RR×risk; stop-first within a bar
(conservative), expire at max_hold. **528 breakouts, gross, in-sample:**
| RR | win% | expectancy(R) | total(R) |
|---|---|---|---|
| 1 | 52.8 | +0.071 | +37.4 |
| 2 | 32.0 | **+0.096** | +50.8 |
| 3 | 18.0 | +0.071 | +37.4 |
| 4 |  9.5 | +0.044 | +23.1 |
First time a naked R:R came back **positive** (every prior test ≈0, §20), best at **1:2**. HEAVY
caveats: **gross (no costs)** on a tight ~2-ATR stop; **in-sample, one stretch**; **fill-optimism**
(assumes exact band fill); higher-RR rows softened by expiry mark-to-close. NOT trusted until (1)
costs modelled and (2) **out-of-sample split** holds — the make-or-break. Different risk structure vs
§20 (band stop + favorable band entry) is why it differs; could be real small edge or fit/fill.

### Volume — activity WINDOW + pattern SIGNATURE (2026-07-01)
Volume is fully populated (median ~150k/bar). Volume-by-ET-hour shows the 2–4 PM ET block is ~1/3 of
daily volume — i.e. the hard 2 PM clock stop **cuts off a high-participation stretch**; only ~49% of
high-volume bars fall inside 8–2. Two uses added (`dynamic_pole/dynamic_pole.py`, all knobs in config):
- **(1) Activity window** (`ACTIVITY_MODE` = clock | volume | clock+volume): hunt when volume ≥
  `VOL_ACTIVE_MULT`× its rolling baseline (a *surge*, strips the time-of-day shape), instead of / with
  the clock. **Pure-volume window ≈ 3,493 seeds vs the clock's 1,696 (~2×)** — confirms it's LONGER +
  shifted later, recovering the afternoon. Helps sample at the seed stage.
- **(2) Pattern signature** (`VOL_SIG_ENABLED` + per-leg): classic flag volume — pole expands (≥
  baseline), flag contracts (< pole avg), breakout surges (≥ `VOL_BREAKOUT_MULT`×baseline). Strict
  conjunction: drops ~75% of breakouts (528→132) but survivors win **45–47% vs 41%** — modest quality
  lift, steep sample cost. fwd still ≈0 (no edge created), but the win-rate nudge may help the band
  R:R (untested). Defaults OFF (clock / sig off) so baseline is unchanged until toggled.

---

## 23. Sibling update + the fwd-horizon lesson (2026-07-01)

Work continued in the sibling `structure_detection/` (regime-first line): rebuilt the lost **MTF
efficiency heatmap**, added a **regime candle-color** indicator + **regime poles**, and thoroughly
tested **MTF alignment / 3-TF trend-ride** — see `structure_detection/NOTES.md §4–6`. Two results
that bear directly on flag_pattern:

- **⚠️ fwd-horizon lesson.** Trend-riding ideas were being judged on **fwd6 (6-bar) close returns** —
  meaningless for a ride (30 min on 5m). **Measure over the strategy's real holding horizon, in R.**
  This casts doubt on any earlier short-horizon "no edge" read; `analysis/forward_horizon/` numbers
  should be re-read with holding-thesis in mind.
- **Every detection method converges on ~1,500–2,000 poles / 20 yr** (template, regime fan, slope) and
  **every naked forward-edge test ≈ 0** (incl. a correctly-measured MTF trend-ride: real rides,
  best +84R, but breakeven gross, and expectancy invariant to stop placement → the *entry* has no
  edge). Detection was never the bottleneck; **edge is.**

**The one live positive remains flag §21 / §20** (VWAP-band R:R, best **+0.096R @ 1:2**, in-sample).
**Next, highest priority: OUT-OF-SAMPLE split** (does it hold in both halves?) **+ costs.** That is now
the single make-or-break for the whole project. Then breadth (ES/CL/GC). Stop hunting new detectors.

---

## 24. The flag SURVIVOR + the R:R reframe (2026-07-01)

Full write-up in `../structure_detection/NOTES.md §7–10`. What lands back on flag_pattern:
- **The one un-killed thread is the flag's R:R geometry**, not any direction signal. The VWAP-band
  R:R (1R = band width; entry = breakout band edge; stop = opposite band edge) is **net-positive OOS**
  (+0.13R plateau across RR 1.5→4, cost-robust to 1.5pt). Everything directional (template, pole,
  slope, regime fan, MTF alignment, HMM regime, timeframe convergence) came up ≈0 — ~9 negatives.
- **BUT the edge is decade-non-stationary:** FULL 20 yr is NEGATIVE at every RR; it's entirely a
  post-2015 phenomenon (~−0.24R/trade 2005–2015 → ~+0.13R 2015–2025, sign flip). Un-killed but
  **decade-unstable** — evolved-market edge or reverting fluke; **ES is the decider (not yet run).**
- **HMM vol regime** predicts forward VOLATILITY out-of-sample (real), but **not direction** — it's a
  sizing/risk/filter tool, and conditioning the flag on it added nothing (pre-registered NEGATIVE,
  confounded with the date effect).
- **THE REFRAME (the deliverable):** stop hunting direction; hunt **asymmetry / R:R geometry.** The MTF
  machine was never a direction predictor — it's an **R:R engine** (LTF pullback = tight stop / nearby
  level; HTF context = which way has *room* / far target). Next move = *more setups with good geometry,
  stacked* + robustness (cost/RR ✓, ES ←), not a better direction signal.
