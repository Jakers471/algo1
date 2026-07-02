# fib_bias

**Purpose:** test whether Fib off the session hi/lo gives a directional lean (the UNTESTED VISION
ingredient). `fib_bias.py` buckets each session's close by its fib position in range and measures the
NEXT session's direction vs the base rate (+ a 2-sigma noise band).
**Role:** would be a bias gate in the arm/disarm confluence — IF it had an edge.
**Attached to:** VISION 10 · CHECKLIST Phase 4
**Status:** `[R]` **isolated test done — NO signal in isolation (diagnostic, NOT a verdict).** Across
7,764 sessions (era ≥ 2015), P(next up) per fib zone is 51.8–56.4% vs a 54.3% base (lifts 0.95–1.04,
spread 4.6pts, none > 2-sigma). (NOTES F11.)

**Important caveat (NOTES F13):** this test bolts fib to an *arbitrary construct* — "session-close
fib position → next-session direction" — endpoints with no structural tie to the real strategy (an
armed range-breakout setup: entry at a node, stop at the range/VA edge, R:R, trail). Per the project's
standing lesson, *a component alone is meaningless — isolated components test flat as a diagnostic, not
a verdict.* So we do **not** drop fib on this result. Keep it as chart geometry; the true test of fib
bias only exists **in context** — once `setup_arm` + entry exist, ask "does the fib reading improve
THIS setup's R:R / entry quality?", not "does it predict next-session direction."
