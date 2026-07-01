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
