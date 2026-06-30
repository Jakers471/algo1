"""
Decompose the trend/pullback/coil/volume-breakout pattern: edge-test each leg
(and combinations) separately to see which piece drives the predictive power.
NQ daily, H-day forward return vs random-day baseline.
"""
import pandas as pd, numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from algokit.data import load_tf
from algokit.indicators import fan, slope_pct, ma_spread

L = 10
MAS = [20, 50, 100, 200]
H = 10   # forward horizon (days)

df = load_tf("1d")
close = df["close"]; high = df["high"]; vol = df["volume"]
ma = fan(close, MAS)
slope = {n: slope_pct(ma[n], L) for n in MAS}

all_up      = pd.concat([slope[n] > 0 for n in MAS], axis=1).all(axis=1)
spread      = ma_spread([ma[n] for n in MAS], close)
compressed  = spread < spread.rolling(252).quantile(0.20)
vol_spike   = vol > 1.5 * vol.rolling(20).mean()
breakout    = close > high.rolling(20).max().shift(1)
uptrend     = close > ma[200]
long_pull   = (close < ma[20]) & (close < ma[50]) & (close > ma[100]) & (close > ma[200])

# sequential helpers
coil_recent  = compressed.rolling(15).max().astype(bool)
vol_recent   = vol_spike.rolling(3).max().astype(bool)
trend_recent = all_up.rolling(60).max().astype(bool)
pull_recent  = long_pull.rolling(20).max().astype(bool)

fwd  = close.shift(-H) / close - 1.0
base = fwd.dropna()
base_mean, base_win = base.mean()*100, (base > 0).mean()*100

def test(name, sig):
    sig = sig.fillna(False)
    a = fwd.reindex(close.index[sig.to_numpy()]).dropna()
    if len(a) == 0:
        return (name, 0, 0, 0, -99)
    return (name, len(a), a.mean()*100, (a > 0).mean()*100, a.mean()*100 - base_mean)

legs = [
    ("all MAs upsloping",          all_up),
    ("MAs compressed (coil)",      compressed),
    ("volume spike",               vol_spike),
    ("20-day breakout",            breakout),
    ("breakout + uptrend",         breakout & uptrend),
    ("breakout + volume",          breakout & vol_recent),
    ("breakout + coil(recent)",    breakout & coil_recent),
    ("breakout + volume + uptrend",breakout & vol_recent & uptrend),
    ("coil -> breakout + uptrend", breakout & coil_recent & uptrend),
    ("coil + vol + breakout + up", breakout & coil_recent & vol_recent & uptrend),
    ("trend->pullback->breakout",  breakout & trend_recent & pull_recent & uptrend),
    ("FULL (all 5 legs)",          breakout & trend_recent & coil_recent & vol_recent & uptrend),
]

rows = [test(n, s) for n, s in legs]
rows.sort(key=lambda r: r[4], reverse=True)

print("NQ daily — %d-day forward return by pattern leg (baseline: %+.2f%%, win %.0f%%)\n"
      % (H, base_mean, base_win))
print("%-30s %7s %9s %7s %8s" % ("signal", "n", "fwd%", "win%", "EDGE%"))
print("-" * 65)
for name, n, fwd_m, win, edge in rows:
    tag = "  <== best" if edge == rows[0][4] and edge > 0 else ("  (weak n)" if 0 < n < 15 else "")
    print("%-30s %7d %+8.2f %6.0f %+7.2f%s" % (name, n, fwd_m, win, edge, tag))
