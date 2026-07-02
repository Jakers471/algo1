# volume_profile

**Purpose:** one Volume Profile per session, bounded by that session's own HIGH↔LOW (NY with NY,
London with London, Asia with Asia). Bins the price range and distributes the session's REAL 5m
volume (Up+Down) by close → **POC** (balance point) + **Value Area** (VAL/VAH, 70% of volume = the
consolidation zone), measured in %-height and bars so it adapts across volatility. VISION 4–6.
**Run:** `python research/structure/volume_profile/volume_profile.py`
**Outputs:** `output/volume_profile.json` (gitignored): per session `{date, session, sid, high, low,
poc, val, vah, start, end, bars, height_pct, va_pct_of_range}`.
**On the chart:** Indicators panel **`profile`** toggle → POC (solid) + VAH/VAL (dashed) drawn across
each session, color-coded (NY/London/Asia); respects the session toggles. 1m/5m NQ.
**Findings (2026-07-02):** 15,475 profiles. Median session height Asia 0.23% / London 0.33% / NY 0.66%;
value area ≈ 54% of the full range; POC sits ~mid (≈0.51) — sessions are, on average, balanced.
**Runtime:** promoted to `engine/volume_profile.py`; in the live engine it runs on the session's
**bars-so-far** (a *running* profile), causality by construction — see ARCHITECTURE.md "Runtime model".
**Attached to:** VISION 4-6 · CHECKLIST Phase 3
**Status:** [R] built (POC + value area per session + chart overlay). Next: shape/tightness filter, entry.
