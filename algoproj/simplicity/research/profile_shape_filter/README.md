# profile_shape_filter

**Purpose:** Turn the clean-vs-foggy profile look into a NUMBER — reject scattered / multi-peak zones, keep clean single-peak (concentration around POC, va_pct_of_range, peakedness → shape_ok).
**Role:** gate/component in the LIVE state machine — runs on the session's bars-so-far, feeds the arm/disarm confluence (see `../../ARCHITECTURE.md` "Runtime model").
**Attached to:** VISION 8 · CHECKLIST Phase 5 (gate)
**Status:** [ ] not started
