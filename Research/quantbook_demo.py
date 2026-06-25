"""
PATH B DEMO — the SAME crossover study as pandas_research_demo.py,
but done through LEAN's real engine via QuantBook.

Run this FROM the directory that contains start.py + the Launcher
runtimeconfig (the built bin dir). It bootstraps the .NET runtime by
executing start.py, then uses QuantBook for history + indicators.
"""
import os, runpy

# --- 0) BOOTSTRAP: run LEAN's start.py to load the .NET runtime + AlgorithmImports
g = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "start.py"))
globals().update(g)  # pulls in QuantBook, Resolution, indicators, etc.

# --- 1) HISTORY: one call replaces the manual unzip/parse/rescale from Path A
qb = QuantBook()
spy = qb.AddEquity("SPY", Resolution.Daily).Symbol
df = qb.History(spy, 5000, Resolution.Daily)   # pandas DataFrame, prices already in $
print("=== SPY HISTORY via qb.History() ===")
print("rows:", len(df), "| columns:", list(df.columns))
close = df["close"].droplevel(0) if df.index.nlevels > 1 else df["close"]
print("close range: %.2f -> %.2f" % (close.min(), close.max()))

# --- 2) INDICATORS: built-in, one call each (vs hand-coding in pandas)
import pandas as pd
def series(ind):
    s = qb.Indicator(ind, spy, 5000, Resolution.Daily)["current"]
    return s.droplevel(0) if s.index.nlevels > 1 else s   # drop the symbol level
sma20 = series(SimpleMovingAverage(20))
sma50 = series(SimpleMovingAverage(50))
bb = qb.Indicator(BollingerBands(30, 2), spy, 5000, Resolution.Daily)
print("\n=== INDICATORS via qb.Indicator() ===")
print("SMA20 points:", sma20.count(), "| BollingerBands columns:", list(bb.columns))

# --- 3) SIGNALS: same SMA20/50 crossover logic as Path A
# pd.concat auto-aligns the two series on their shared dates; sort + de-dup the
# index, then compare positionally with numpy so index labels can't cause trouble.
ma = pd.concat({"fast": sma20, "slow": sma50}, axis=1).dropna()
ma = ma[~ma.index.duplicated()].sort_index()
print("\n=== INDEX SANITY ===")
print("aligned rows:", len(ma), "| unique dates:", ma.index.is_unique,
      "| sorted:", ma.index.is_monotonic_increasing)

above = (ma["fast"] > ma["slow"]).to_numpy()
cross_up = above[1:] & ~above[:-1]   # was below, now above
cross_dn = ~above[1:] & above[:-1]   # was above, now below
dates = ma.index[1:]
print("\n=== RESEARCH FINDING: SMA20/SMA50 crossovers ===")
print("bullish crossovers (buy):", int(cross_up.sum()))
print("bearish crossovers (sell):", int(cross_dn.sum()))
print("most recent 3 bullish signals:",
      [str(t.date()) for t in dates[cross_up][-3:]])

# --- 4) DOES THE SIGNAL HAVE EDGE? measure SPY's forward return after each buy
# Clean close series aligned to the signal dates, then look H trading days ahead.
H = 20  # ~1 month forward
c = close[~close.index.duplicated()].sort_index().reindex(ma.index)
fwd = c.shift(-H) / c - 1.0          # H-day forward return at every date

buy_dates = dates[cross_up]
after_buy = fwd.reindex(buy_dates).dropna()   # forward return following each buy
baseline = fwd.dropna()                        # forward return on ANY random day

print("\n=== EDGE TEST: %d-day forward return after a buy signal ===" % H)
print("signals measured:      %d" % len(after_buy))
print("avg return after buy:  %+.2f%%   (win rate %.0f%%)"
      % (after_buy.mean() * 100, (after_buy > 0).mean() * 100))
print("avg return any day:    %+.2f%%   (win rate %.0f%%)   <- baseline"
      % (baseline.mean() * 100, (baseline > 0).mean() * 100))
edge = (after_buy.mean() - baseline.mean()) * 100
print("EDGE (buy minus baseline): %+.2f%% per %d days -> %s"
      % (edge, H, "looks promising" if edge > 0 else "no edge / worse than random"))

print("\nPATH B DEMO DONE — same study, LEAN engine did the data + indicator work.")
