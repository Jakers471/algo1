# session_anchors

**Purpose:** session HIGH/LOW levels + **forward breach tracking**. Each session's high/low is
fixed at session end, then scanned forward: when does a later bar CLOSE through it? Feeds the
Volume Profile (Phase 3) and the session-break stats (VISION 11/13).
**Run:** `python research/session_anchors/session_anchors.py`
**Outputs:** `output/session_anchors.json` (machine-readable, **gitignored** — large/regenerable):
per level `{date, session, type(high/low), level, start(formed), hit, status, breach_ts,
breach_price, duration_bars, duration_sec, stop}`. `status` = `hit` / `ongoing` / `unbreached_cap`.
**On the chart** (Indicators panel, minimizable): each level draws as a horizontal line from
formation extending forward until breached — **solid = hit** (ends at the breach), **dashed =
ongoing** (extends to now). Color-coded per session; toggle levels (High/Low) and sessions.
Shows on 1m/5m NQ (times align to the bar grid).
**Details:** ET sessions; Asia's 00:00–03:00 folds onto the prior day. Breach is CLOSE-based on 5m;
forward scan capped at `MAX_FWD_BARS` (deep-history only).
**Attached to:** VISION 3 / 11 · CHECKLIST Phase 2
**Status:** [R] built — 40,942 levels; 91.7% hit, median ~5.8h to breach; chart overlay wired.
