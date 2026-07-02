# fib_bias

**Purpose:** test whether Fib off the session hi/lo gives a directional lean (the UNTESTED VISION
ingredient). `fib_bias.py` buckets each session's close by its fib position in range and measures the
NEXT session's direction vs the base rate (+ a 2-sigma noise band).
**Role:** would be a bias gate in the arm/disarm confluence — IF it had an edge.
**Attached to:** VISION 10 · CHECKLIST Phase 4
**Status:** `[R]` **edge test done — NO directional edge.** Across 7,764 sessions (era ≥ 2015), P(next
up) per fib zone is 51.8–56.4% vs a 54.3% base (lifts 0.95–1.04, spread 4.6pts, no zone > 2-sigma).
**Fib is NOT a direction gate** — consistent with the project thesis (direction isn't predictable on
NQ). The fib overlay stays on the chart as **geometry only** (visual reference), not a signal. (NOTES F11.)
