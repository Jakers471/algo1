# session_anchors

**Purpose:** per-session HIGH / LOW / OPEN anchors (London / NY / Asia / Close) for every day —
the reference levels the Volume Profile (Phase 3) is built between, and the color-coded levels
drawn on the chart. VISION step 3.
**Run:** `python research/session_anchors/session_anchors.py`
**Outputs:** `output/session_anchors.json` (`{colors, anchors:[{date,session,high,low,open,start,end}]}`)
**On the chart:** the Indicators panel (top-left, minimizable) toggles anchors on/off, levels
(High/Low, Open), and per-session (color-coded); drawn as horizontal segments across each session
(shows on 1m/5m NQ, where anchor times align to the bar grid).
**Details:** ET sessions; Asia's 00:00–03:00 folds onto the prior day's session so each is one span.
**Attached to:** VISION 3 · CHECKLIST Phase 2
**Status:** [R] built & verified (20,471 sessions over 20yr; chart overlay wired)
