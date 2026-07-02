# renko — Premise & Workflow

*The third strategy line. Sibling of `../strategy research/flag_pattern/` and
`../strategy research/structure_detection/`, but a clean paradigm break from both.
Started 2026-07-01.*

---

## The paradigm shift (why this exists)

The prior two lines (`flag_pattern`, `structure_detection`) are **paused**. They spent
themselves proving one thing over ~9 honest negatives: **direction is not predictable from
time-based price structure on NQ.** The only survivor was never a direction signal — it was
**geometry / R:R asymmetry** (fixed-risk setups where *right = big, wrong = small*), and even
that was decade-unstable and fought the time axis the whole way.

This line removes the thing that was fighting us: **TIME.**

**Renko charts print a brick only when price moves a fixed amount.** No brick forms until price
travels `brick_size`. Time is off the x-axis entirely — the chart is **mileage, not elapsed
time.** A brick that takes a nanosecond and a brick that takes all day are identical. This is
the direct, literal answer to the throughline of the paused work — *"I don't like fixed
anything / no fixed bars"* — except here it's fixed **price**, not fixed **time**, and fixed
price is exactly what we *want* fixed because it makes risk mechanical.

The source of this pivot is a long DM exchange with a veteran trend-follower (`derivative.md`).
His core claims, which we are taking as the working thesis to test (not gospel):
- Time-based charts produce "ECG / seismograph" noise (multicolored bars) that shake you out.
- Renko bricks contain everything: **pure price action, zero indicators** (no volume, no A/D,
  no SMC/ICT, no moving-average spaghetti).
- **Fixed brick size = baked-in risk management** — R:R is precise and mechanical because every
  brick is the same height.
- Trend-following with **no preset targets**: get on, ride, exit only when the signal flips.
- **"Buy white, sell black — when colors align across MPFs."**

---

## The core premise (what we are building toward)

A **systematic Renko trend-following engine** with two moving parts:

### 1. MPF — Multiple Price Frames (the Renko replacement for timeframes)
Instead of 1h / 15m / 1m (time), we use **brick sizes**: a **SPF (small price frame)** and a
**LPF (large price frame)** — same fractal idea, but the "frames" are price increments, not
clocks. Alignment across frames = the signal ("colors align across MPFs").

### 2. Core + Hedge (continuation vs reversal, resolved structurally)
The heart of the system (`images/hedge_core_flowchart.webp`):
1. **Enter the core** in the LPF trend direction.
2. **SPF starts reversing** → open an **SPF hedge**.
3. Fork:
   - **LPF holds** → the SPF reversal was noise → *close the hedge, keep the core.*
   - **LPF reverses too** → *close the core; the SPF hedge becomes the new core.*

This is trend-continuation-vs-reversal decided by two price frames — and it is the same
**"small frame = tight stop, large frame = runway = R:R engine"** idea the flag work arrived at,
made clean because Renko removed the time axis that made it messy before.

Execution detail from the source (`images/brick_params_tsl.webp`): a brick size, an **offset**,
and a **trailing stop** trailing a fixed distance below the current brick low.

---

## What carries over from the paused work (hard-won, do not relearn)

- **Edge is the gate, not detection.** Renko is a *representation*, not an edge. Every claim
  here earns its keep against **forward R**, out-of-sample, after costs — same bar as before.
- **Measurement horizon = holding thesis.** Trend-following is measured by riding to the trend's
  end in **R**, never a fixed small forward window (the fwd-6 lesson). Renko helps: "hold until
  the brick color flips" is a natural, thesis-matched exit.
- **Trade WITH the larger structure.** The one conditional pulse we ever found was aligning with
  the bigger trend — which is *literally* the MPF alignment premise here.
- **Grow N by breadth, never by loosening quality.** More instruments / more brick sizes, not
  looser filters.
- **Beware the "sensor vs. machine" trap.** A brick chart is a sensor; the core+hedge state
  machine is the thing that trades. Don't fall in love with the chart.

---

## Open questions (to resolve as we go — not yet decided)

- **Brick construction:** classic Renko (close-based) vs. high/low (wick) Renko vs. ATR-brick?
  Fixed tick/point size vs. ATR-scaled? The source implies **fixed** (fixed = baked-in R:R).
- **Brick size(s):** what SPF / LPF sizes for NQ? (source example was MNQ, `20` size / `5`
  offset — units TBD: ticks vs points.)
- **The offset:** what exactly the `5 offset` does in the source's brick engine.
- **Repainting:** Renko's known trap — the last brick can repaint until confirmed. The backtest
  must use **confirmed bricks only** (no look-ahead), or the edge is fake.
- **Data source:** reuse the existing NQ tick/1m store to synthesize bricks (we have 20 yr).

---

## Folder layout (mirrors the sibling strategies)

```
renko/
  README.md            premise + workflow (this file)
  NOTES.md             concept, architecture, spec, roadmap, findings — the living doc
  RANTS.md             raw idea log; user rants verbatim, Claude responses summarized
  derivative.md        source: the DM exchange this pivot came from
  images/              the seven source screenshots, descriptively named
  config.py            SINGLE SOURCE OF TRUTH — brick size, instrument, cost specs (control panel)
  engine/              the Renko engine (all library + runner code lives here)
    bricks.py          close-based, confirmed-only brick construction (+ self-test)
    build_bricks.py    runner: loads NQ 1m -> bricks -> findings, prints cost/1R diagnostics
  findings/            outputs (bricks_<tf>_<size>pt.npz)
  (later) harness/     expectancy engine (R, net of costs, sized, OOS) — the real deliverable
  (later) signal/      the core+hedge state machine
  (later) analysis/    studies + output PNGs
```

**Run the engine** (always the 3.11 venv — system Python won't load the parquets):
```
cd algoproj
& "…/Launcher/bin/Debug/.venv311/Scripts/python.exe" renko/engine/build_bricks.py --size 10 25 50
```

**Workflow (same as the siblings):** research emits findings JSON → a chart renders it (reuse
the `tv_chart` datastore/paging asset) → refine → only then trading logic, measured against
forward edge. The findings→chart loop stays the key asset; the detector changes, not the loop.
</content>
</invoke>
