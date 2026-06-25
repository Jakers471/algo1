"""
Plot the discovered entry signals on NQ price:
  - raw LTF bear-stack entries (fresh cross into close<10<20<50)
  - same, FILTERED by HTF uptrend regime (price > 600MA, 300>400>600)
Marks the discrete entry bar of each episode (not every bar).

Data + fan come from algokit; signal/plotting stay local.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.indicators import fan

df = load_tf("1d")
dt = df.index.normalize()
close = df["close"]
ma = fan(close, [10,20,50,200,300,400,600])

ltf_bear = (close < ma[10]) & (ma[10] < ma[20]) & (ma[20] < ma[50])
htf_bull = (ma[300] > ma[400]) & (ma[400] > ma[600]) & (close > ma[300])

entry_raw  = ltf_bear & ~ltf_bear.shift(1).fillna(False)          # fresh entry into bear stack
entry_filt = entry_raw & htf_bull                                  # only in HTF uptrend

x = mdates.date2num(dt.to_pydatetime())
fig, ax = plt.subplots(figsize=(22, 11))
ax.semilogy(x, close, color="black", lw=0.8, label="NQ close")
for n, c, a in [(50,"tab:green",.7),(200,"tab:orange",.7),(600,"tab:red",.8)]:
    ax.semilogy(x, ma[n], lw=1.0, color=c, alpha=a, label=f"MA{n}")

er = entry_raw.fillna(False).to_numpy()
ef = entry_filt.fillna(False).to_numpy()
ax.scatter(x[er & ~ef], close[er & ~ef], marker="v", s=55, color="gray", alpha=.55,
           label="LTF bear entry (raw, %d)" % int((er & ~ef).sum()), zorder=4)
ax.scatter(x[ef], close[ef], marker="^", s=90, color="lime", edgecolor="black",
           label="LTF bear entry in HTF uptrend (%d)" % int(ef.sum()), zorder=5)

ax.set_title("NQ — discovered mean-reversion entry signals (LTF bear-stack dips)")
ax.legend(loc="upper left", fontsize=9)
ax.xaxis.set_major_locator(mdates.YearLocator(2)); ax.xaxis_date()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR,"nq_signals.png"), dpi=260); plt.close()
print("entries raw:", int(er.sum()), "| filtered by HTF uptrend:", int(ef.sum()))
print("SAVED nq_signals.png")
