# Fanning Regime Detection System (NQ) — Research Notes

> **STATUS: RESEARCH / IN PROGRESS — not a production strategy.**
> This documents an *idea being explored*, the logic built so far, and what the
> data has said. Nothing here beats buy-and-hold yet. Treat every rule as a
> hypothesis under test, not a settled signal.

Data: NQ (Nasdaq-100 futures), 2005–2025, parquet OHLCV at 1m/5m/15m/60m/1d in
`NQdata/`. All research runs on the local Python 3.11 venv (pure pandas, no LEAN
engine needed) — see "How to run" below.

---

## 1. The concept

Trade the **trend the way it actually moves**: detect *market regime* from a
fan of moving averages, fractally, across three timeframes that each do a
different job:

- **HTF (1d) = bias** — which direction are we allowed to trade?
- **MTF (1h) = setup** — is a move compressing/consolidating in that direction?
- **LTF (15m) = timing** — when exactly do we enter (and exit)?

The thesis: a higher timeframe gives permission, the next one down confirms the
setup, the lowest times the entry. A fractal cascade — HTF → MTF → LTF.

## 2. Measurement layer — the fan + the regime score

On each timeframe we plot **32 moving averages** (lengths geometrically spaced)
and read their **slopes**:

- green = MA sloping up, red = sloping down, yellow = flat (within ±EPS).

That fan is collapsed into a **0–100 regime score split three ways** that sums
to 100:

- **bullish %** — weight of MAs sloping up
- **consolidation %** — weight of MAs flat
- **bearish %** — weight of MAs sloping down

**Longer MAs carry more weight** (weight ∝ MA length) so the slower, more
meaningful averages dominate the score — a "geometrically weighted" vote.

Each timeframe uses its **own native fan length** so they don't overlap:

| Timeframe | Fan lengths (bars) | ≈ horizon |
|-----------|--------------------|-----------|
| 1d (HTF)  | 5 → 500            | ~2 years  |
| 1h (MTF)  | 5 → 250            | ~2 weeks  |
| 15m (LTF) | 5 → 100            | ~1 day    |

## 3. Multi-timeframe alignment (no look-ahead)

Everything is evaluated on the **15m clock**. The most recent *closed* 1d and 1h
regime scores are forward-filled onto each 15m bar, so at any entry we only use
higher-timeframe information that was actually available at that moment.

## 4. Signal logic (current hypothesis)

- **Entry**: 15m bull score crosses up through a level `X`, **while recently
  coiled** (consolidation score was high in the last `COIL_K` bars), **gated by
  alignment** (e.g. 1d bull ≥ HTF_GATE, optionally 1h bull ≥ MTF_GATE).
- **Exit**: 15m bull score falls below `EXIT_TH` ("LTF flips").
- **Stop**: wide ATR stop (`entry − ATR_MULT × ATR`), disaster-brake only.
- Costs modeled per turn.

Key tunables live at the top of `nq_mtf_signals.py`:
`FAN, COIL_K, COIL_LEVEL, EXIT_TH, HTF_GATE, MTF_GATE, ATR_MULT, X_SWEEP`.

## 5. Research findings so far (the honest scoreboard)

Tested rigorously (costs + out-of-sample where relevant) on NQ/SPY:

| Idea | Result |
|------|--------|
| MA crossover (trend) — SPY & NQ | **no edge** |
| RSI dip-buy (mean-reversion) — SPY & NQ daily | real per-trade edge, but loses to buy&hold (barely invested) |
| MA-spread "coil" (compression) | the only MA leg with real fwd-return edge (+0.21% / 10d, 1132 samples) |
| Volume-spike breakout | **negative** edge — volume spikes cluster at reversals, not continuations |
| Fractal bear-stack (LTF/HTF) | bearish stacks precede *bounces* — NQ mean-reverts |
| **MTF fan-transition long system (this doc)** | HTF alignment helps; earlier entry (low X) is **worse**; best config +24%/20y vs buy&hold +368% |

**Two robust lessons:**
1. On NQ, **mean-reversion signals carry edge; trend/breakout signals don't.**
2. **A real per-trade edge ≠ beating buy-and-hold** — opportunity cost (sitting
   in cash on a 20-year uptrend) kills every "wait for a signal" long strategy
   so far.

**Surprises that overturned assumptions:**
- Volume confirmation *hurts* (anti-predictive on NQ).
- Catching the transition *earlier* hurts — early flips are mostly false starts.
- The full HTF+MTF+LTF cascade over-filters (in market ~2% of the time).

## 6. Open questions / next steps

- **Beat the opportunity-cost wall**: test "always invested + add exposure on
  signal" instead of cash↔long, so we capture the underlying uptrend.
- **Calibrate EPS per timeframe** to a volatility measure so scores are truly
  comparable across 1d/1h/15m (intraday currently skews to "consolidation").
- **Better consolidation/squeeze metric** (Bollinger bandwidth squeeze looked
  more sensitive than MA-spread) and a real squeeze hi/lo range for breakouts.
- **Short side / mean-reversion variant**: the data keeps pointing at buying
  weakness — worth testing the fan system as a dip-buyer, not a breakout-rider.
- **Walk-forward validation** before trusting any tuned threshold.

## 7. Scripts & how to run

All run with the 3.11 venv from the `NQdata/` folder:

```powershell
cd "C:\Users\jakers\Desktop\algo\NQdata"
& "C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe" <script>.py
```

| Script | What it does |
|--------|--------------|
| `nq_mtf_signals.py` | **the engine** — MTF regime scores, signal generation, entry-level × alignment return sweep |
| `nq_mtf_regime.py` | regime cascade visualization (1d → 1h → 15m drill-down PNGs) |
| `nq_ma_fan.py` | 32-MA slope-colored fan (single timeframe) |
| `nq_regime_indicators.py` | Bollinger squeeze + ADX regime PNGs |
| `nq_decompose.py` | edge-test each pattern leg separately |
| `nq_fractal.py` | fractal MA tier measurements + role discovery |

Everything is gross-of-slippage beyond the simple per-turn cost model, daily/
intraday only, and **research-grade** — validate before risking anything.
