"""
NQ edge test: does "buy when RSI(14) crosses below 30" have edge on NQ futures?
Reads the parquet directly (pure pandas) — no LEAN engine needed.
Run from the NQdata folder with the 3.11 venv python.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from algokit.data import load_tf
from algokit.indicators import rsi

TF = "60m"   # hourly bars
df = load_tf(TF)
close = df["close"]

rsi14 = rsi(close, 14)

# signal: RSI crosses below 30
oversold = (rsi14 < 30).to_numpy()
entry = oversold[1:] & ~oversold[:-1]
dates = close.index[1:][entry]

H = 5
fwd = close.shift(-H) / close - 1.0
after = fwd.reindex(dates).dropna()
base = fwd.dropna()

print("=== NQ %s: buy when RSI(14) crosses below 30 ===" % TF)
print("range:", close.index.min().date(), "->", close.index.max().date(), "| bars:", len(close))
print("signals:", len(after))
print("avg %d-bar return after signal: %+.2f%%  (win %.0f%%)" % (H, after.mean() * 100, (after > 0).mean() * 100))
print("avg %d-bar return any bar:      %+.2f%%  (win %.0f%%)  <- baseline" % (H, base.mean() * 100, (base > 0).mean() * 100))
edge = (after.mean() - base.mean()) * 100
print("EDGE: %+.2f%% per %d bars -> %s" % (edge, H, "HAS EDGE" if edge > 0 else "no edge"))
print("NQ buy & hold over period: %+.0f%%" % ((close.iloc[-1] / close.iloc[0] - 1) * 100))
