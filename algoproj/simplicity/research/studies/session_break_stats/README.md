# session_break_stats

**Purpose:** test the session-level breach data for any predictability / edge — honestly, vs
baselines. Three angles: (1) base rates (hit% + speed), (2) conditional breaks `P(Y|X)` vs `P(Y)`
= lift, (3) directional FOLLOW-THROUGH after a level breaks (continuation vs drift + stability).
**Run:** `python research/studies/session_break_stats/session_break_stats.py`
**Outputs:** `output/session_break_stats.json` + console report.
**Finding (2026-07-02): NO exploitable edge.**
- Base rates: levels almost always breach (Asia 91–96% / London 89–95% / NY 81–91%). London
  breaks fast (~1.4h), NY holds ~16–18h (widest range) — structural character, not prediction.
- Conditional: lifts ~1.0 (0.98–1.10) — one session's break doesn't predict another's beyond base rate.
- Follow-through: after a break, ~+0.004% over 1–3h, 46–52% win, **excess-over-drift ≈ 0** — breakouts
  don't continue beyond drift. (A `t=+2.78` case is huge-n noise: excess +0.003%, win <50%.)
- Consistent with the project's core: direction isn't predictable on NQ; the data is a descriptor, not a signal.
**Also `first_touch.py`** — NY-open liquidity-sweep test: which standing overnight level (London/Asia
high or low) is touched FIRST during NY, and does it predict? Finding: London side-first ~51/47 (no
bias), NY runs both extremes ~42% of days. Open→close conditionals look huge (t=12–38) but are
TAUTOLOGICAL (the touch is the move); the honest **forward-from-touch** test is flat (t≈0, ~50% win)
— no edge after the sweep.
**Attached to:** VISION 11 · CHECKLIST Phase 2
**Status:** [R] built — verdict: no directional edge (breach data + first-touch sweep both flat).
