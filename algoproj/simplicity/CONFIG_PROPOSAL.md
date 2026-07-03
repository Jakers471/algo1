# Config reorg — a more intuitive shape (PROPOSAL, nothing wired)

**Problem:** today's config groups knobs by *code-module type* (`Structure — scales`,
`Quality gates`, …). But you think in terms of the **chart indicators** and *what each one
measures*. Those two vocabularies don't line up, so the wiring feels invisible — especially
the **module card**, which shows a pile of derived numbers with no obvious config home.

**Key realisation:** there is really only ONE indicator — **the volume profile** — and
`shape`, `zone`, `fib`, `ladder` are all just **measurements taken off that profile** (at one
or more scales). They aren't siblings of the profile; they're its children. The module card =
"show me every measurement off this session's profile."

Only two things in the whole config are NOT derived from the profile: the **when-to-trade
filter** (a time gate) and **risk/costs** (trade mechanics).

So: reorganise the config as the **derivation tree**, in three layers — shown here in YAML
(indentation = the parent→child chain; no braces, no quotes to wade through).

---

## Layer 1 — THE SKELETON  (facts the chart draws; no tuning)
_chart indicators: sessions · times · anchors · levels_

```yaml
skeleton:
  clock: America/New_York
  era_start_year: 2015
  sessions:                      # ET, no gaps, covers 24h
    asia:    [18:00, 03:00]
    london:  [03:00, 09:30]
    newyork: [09:30, 16:00]
    close:   [16:00, 18:00]
  # anchors / levels / times have NO knobs — read straight off the session state.
```

## Layer 2 — THE PROFILE @ N SCALES  (the one real indicator + its measurements)
_chart indicators: profile  +  the MODULE CARD (= the `measure:` block below)_

Each scale = **a lookback window → a volume profile → measurements off that profile**.
The SAME measurement code runs on every scale (the profile dict is the seam), so a scale
only says *how its window is defined*; measures `inherit` the session's knobs unless overridden.

```yaml
scales:

  - name: session                # 5m session profile — the base dimension
    on: true
    window:  { kind: session, tf: 5m }
    profile: { row_size: 2.0, va_pct: 0.70 }      # -> POC / VAL / VAH / bins
    measure:                                       # <-- THIS is the module card
      shape:                                       # clean-vs-foggy score 0..100
        weights: { tight: 0.40, peak: 0.30, single: 0.20, central: 0.10 }
        tight_peak: 40.0
        tight_hi:   85.0
        prom_den:   2.0
        single_2:   0.5
        single_else: 0.15
        ok: 50                                     # score >= ok  =>  "clean"
      zone:                                        # risk / R:R / entry-timeframe
        rr_min: 2.0
        tf_bands: [[0.25, 1m], [0.60, 5m], [null, 15m]]   # height% -> entry TF
      fib:                                         # context only (no directional edge)
        edges: [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0001]

  - name: base                   # the coil INSIDE the session (tighter 1R stop)
    on: false
    window:  { kind: coil, band_mult: 5.0, min_bars: 8 }
    profile: inherit
    measure: inherit

  - name: htf                    # trailing composite (runway + context)
    on: false
    window:  { kind: composite, days: 7, bins: 70, min_bars: 200 }
    profile: inherit
    measure: inherit
```

## Layer 3 — THE TRADE  (uses the measurements; NOT tied to one indicator)

```yaml
# 3a. Combine the scales into trade geometry -> the TARGET LADDER card
ladder:
  stop_from:    base
  targets_from: [session, htf]
  min_rr: 0.5

# 3b. WHEN to trade — orthogonal time gate (the shaded overlay, not a profile measure)
when:
  session: { on: true,  allow: [newyork] }
  hour:    { on: false, allow: [9, 10, 11, 12, 13, 14, 15] }
  day_vol: { on: false, regimes: [high] }
  news:    { on: false }                    # unbuilt

# 3c. THE DECISION — setup_arm: which measurements must ALIGN to arm  [unbuilt]
#     reads measures from the ENABLED scales, BY PATH -> you SEE what feeds the arm
arm:
  require:    [session.shape.ok, session.zone.rr_ok]   # the confluence stack
  invalidate: null

# 3d. Mechanics
entry:
  type: breakout_both
  entry_tf: 5m
  entry_window_bars: 78
  fill: coil_edge
  min_coil_pct: 0.05
exit:
  stop: coil_edge
  target: ladder_rung
  target_r: 2.0
  max_hold_bars: 156
  same_bar: stop_first
risk:
  sizing: risk_pct
  risk_per_trade_pct: 1.0
costs:
  point_value: 20.0
  tick: 0.25
  commission_per_side: 2.25
  slippage_ticks: 1
```

---

## Why this reads better

- **The config now mirrors the chart.** Layer 1 = the skeleton you always see; Layer 2 = the
  profile + its module-card readouts; Layer 3 = the trade. No more hunting for where a
  module number lives.
- **Indentation shows the parent→child chain.** `shape`/`zone`/`fib` are visibly *nested under*
  the profile that feeds them, so "what is shape connected to?" answers itself.
- **`scales` unifies `volume_profile` / `base` / `htf`** into one indicator at N windows
  (this is F37's direction) — and `inherit` keeps params in one place.
- **`arm.require` names its inputs by path** (`session.shape.ok`), so the decision layer shows
  exactly which measurements it consumes — the thing that's totally opaque today.

## The YAML question (worth deciding, since you raised it)
YAML reads better than the Python dicts — but the config is currently **live Python that the
engine imports directly**. Two ways to get the YAML feel:
  1. **Author in YAML, load it** (`config.yaml` + a tiny loader) — prettiest to read/edit, but
     adds a parse step + a `pyyaml` dep, and you lose Python niceties (comments-as-code, `os.path`).
  2. **Keep Python but shape it like this tree** (nested dicts, this same layout) — no new dep,
     still importable, 90% of the readability win.
Recommend **(1)** if this is meant to be *the* human-facing control surface (it increasingly is,
via the chart), **(2)** if you'd rather not add a load step. Either way the STRUCTURE above is
the point; YAML vs dict is the surface.

## Open questions before this becomes real (decide first, don't rewrite yet)
1. **F37 fork:** is `base` a real adaptive **coil detector** (`window.kind: coil`), or just
     another fixed-lookback rung of a pure geometric ladder? This layout supports either — but
     the answer changes what `base` means.
2. **`inherit` vs explicit per-scale measure knobs** — start with inherit (one place to tune);
     allow overrides only if a scale genuinely needs different thresholds.
3. **The chart `config_panel`** would walk this tree instead of the flat block list — status
     dots per node (live / off / not-wired / no-engine) fall out of the nesting naturally.
