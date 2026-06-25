"""
Fractal MA framework on NQ daily.
Tiers:  LTF = 10/20/50   MTF = 100/150/200   HTF = 300/400/600
Measures: 9 pairwise distances (% of price), 3 tier spreads, 1 alignment score.
Then DISCOVERS rules by edge-testing each tier's role (probe = 10d fwd return;
the real strategy will use LTF exits + wider ATR later).
"""
import pandas as pd, numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from algokit.data import load_tf
from algokit.indicators import fan, ma_spread

LTF = [10, 20, 50]; MTF = [100, 150, 200]; HTF = [300, 400, 600]
ALL = LTF + MTF + HTF
H = 10

df = load_tf("1d")
dt = df.index.normalize()
close = df["close"]
ma = fan(close, ALL)

def dist(a, b):                      # fast minus slow, % of price (+ = bullish)
    return (ma[a] - ma[b]) / close * 100

pairs = {"L:10-20": (10,20), "L:20-50": (20,50), "L:10-50": (10,50),
         "M:100-150": (100,150), "M:150-200": (150,200), "M:100-200": (100,200),
         "H:300-400": (300,400), "H:400-600": (400,600), "H:300-600": (300,600)}
D = {k: dist(*v) for k, v in pairs.items()}

def spread(grp):                     # tier compression: (max-min)/price %
    return ma_spread([ma[n] for n in grp], close)
ltf_sp, mtf_sp, htf_sp = spread(LTF), spread(MTF), spread(HTF)

# alignment: +1 full bull fan (10>20>...>600), -1 full bear, ~0 tangled
order = pd.concat([ma[n] for n in ALL], axis=1)
gaps = np.sign(order.iloc[:, :-1].to_numpy() - order.iloc[:, 1:].to_numpy())   # 8 adjacent gaps
align = pd.Series(np.nanmean(gaps, axis=1), index=close.index)

# --- tier states ---
htf_bull = (ma[300] > ma[400]) & (ma[400] > ma[600]) & (close > ma[300])
htf_bear = (ma[300] < ma[400]) & (ma[400] < ma[600]) & (close < ma[300])
mtf_coil = mtf_sp < mtf_sp.rolling(252).quantile(0.25)
mtf_up   = ma[100] > ma[200]
ltf_bull = (close > ma[10]) & (ma[10] > ma[20]) & (ma[20] > ma[50])
ltf_bear = (close < ma[10]) & (ma[10] < ma[20]) & (ma[20] < ma[50])

# --- snapshot (latest bar) so you can SEE the 13 numbers ---
i = -1
print("=== SNAPSHOT %s ===" % dt[i].date())
print("pair distances (%% of price):")
for k in pairs: print("   %-10s %+6.2f%%" % (k, D[k].iloc[i]))
print("tier spreads:  LTF %.2f%%  MTF %.2f%%  HTF %.2f%%" % (ltf_sp.iloc[i], mtf_sp.iloc[i], htf_sp.iloc[i]))
print("alignment:     %+.2f  (+1 bull fan / -1 bear fan)" % align.iloc[i])

# --- discovery: edge-test each role (probe) ---
fwd = close.shift(-H) / close - 1.0
base = fwd.dropna(); bm = base.mean()*100
def test(name, sig):
    sig = sig.fillna(False); a = fwd.reindex(close.index[sig.to_numpy()]).dropna()
    return (name, len(a), a.mean()*100, (a>0).mean()*100, a.mean()*100 - bm)

tests = [
    ("HTF bullish (bias?)",        htf_bull),
    ("HTF bearish (bias?)",        htf_bear),
    ("MTF coil",                   mtf_coil),
    ("MTF coil + HTF bull",        mtf_coil & htf_bull),
    ("MTF coil + MTF uptrend",     mtf_coil & mtf_up),
    ("LTF bull stack",             ltf_bull),
    ("LTF bear stack",             ltf_bear),
    ("HTFbull+MTFcoil+LTFbull",    htf_bull & mtf_coil & ltf_bull),
    ("HTFbear+MTFcoil+LTFbear",    htf_bear & mtf_coil & ltf_bear),
]
rows = [test(n, s) for n, s in tests]
print("\n=== DISCOVERY: %dd fwd return by role (baseline %+.2f%%, win %.0f%%) ===" % (H, bm, (base>0).mean()*100))
print("%-26s %6s %8s %6s %8s" % ("role", "n", "fwd%", "win%", "EDGE%"))
print("-"*58)
for name, n, f, w, e in rows:
    flag = "  <-- short edge" if e < -0.15 and n >= 30 else ("  <-- long edge" if e > 0.15 and n >= 30 else ("  (small n)" if n < 30 else ""))
    print("%-26s %6d %+7.2f %5.0f %+7.2f%s" % (name, n, f, w, e, flag))
