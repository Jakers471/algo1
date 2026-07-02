# dynamic_pole

The **dynamic pole → flag-watch → breakout** line of the flag_pattern strategy. It reuses
`flag_pattern`'s template scan **as a coarse seed**, then unfreezes everything downstream: the pole is
traced candle-by-candle to its true extremes (both directions), the consolidation is watched forward
to a VWAP-equilibrium breakout, and volume can gate both *when* we look and *whether* the pattern
confirms. See the parent `../NOTES.md` §22 for the full write-up and honest edge status.

## Coupling (this is a SUBFOLDER, not a standalone strategy)
Everything imports the shared control panel **`../signal/signal_config.py`** — the template (`SETUP`),
session, and all `POLE_TRACE_* / CONSOL_* / BREAKOUT_VWAP_K / SEED_MODE / VOL_* / ACTIVITY_MODE` knobs
live there. Findings are written to the shared **`../findings/`** so `tv_chart` discovers them.

## Files
- `dynamic_pole.py` — seed (template scan or ATR spike) → trace the pole → flag-watch → breakout;
  writes `../findings/dynamic_pole_5m.json`. Draws pole band, variable flag, true-swing fib segments,
  and the anchored-VWAP center + band on the chart.
- `vwap_rr/vwap_rr.py` — R:R backtest: entry/stop on the VWAP band (bearish: sell-stop lower band /
  stop upper band; bullish mirror), targets at 1–4R, first of stop/target. Gross, in-sample.

## Run (from `algoproj/` root)
```bash
python "strategy research/flag_pattern/dynamic_pole/dynamic_pole.py" --save
python "strategy research/flag_pattern/dynamic_pole/vwap_rr/vwap_rr.py"
```

## Honest status
Detection is clean (variable pole+flag anchored to real structure, visible VWAP equilibrium). `fwd` is
still ≈0 (no naked edge). The one live positive is the **in-sample** band R:R (best +0.096R at 1:2) —
unproven until costs + an **out-of-sample split** hold. Next: re-run R:R on the volume-signature
setups, then the OOS split.
