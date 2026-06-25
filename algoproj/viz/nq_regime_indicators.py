"""
Regime-detection indicators on NQ daily, kept fractal (3 timeframes):
  A) Bollinger Band squeeze  -> compression regime (orange = squeeze)
  B) ADX                     -> trend vs range (green up-trend / red down-trend / orange range)
Saves nq_bbands.png and nq_adx.png.

Indicators come from algokit.indicators; plotting stays local.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.indicators import bollinger_bandwidth, bollinger_bands, adx as adx_ind

GREEN="#2ca02c"; ORANGE="#ff8c00"; RED="#d62728"; NEUTRAL="#bdbdbd"
df=load_tf("1d")
dt=df.index.normalize()
close=df["close"]; high=df["high"]; low=df["low"]
x=mdates.date2num(dt.to_pydatetime())

# ---------- A) Bollinger squeeze, fractal lengths LTF/MTF/HTF ----------
def bb(n, k=2):
    mid,up,lo=bollinger_bands(close,n,k)
    return bollinger_bandwidth(close,n,k), mid, up, lo          # bandwidth %, mid, upper, lower

lens={"LTF (20)":20,"MTF (100)":100,"HTF (300)":300}
bw={name:bb(n) for name,n in lens.items()}
def squeeze(bwidth): return (bwidth < bwidth.rolling(252).quantile(0.25))   # low width = squeeze

fig,axes=plt.subplots(4,1,figsize=(22,13),sharex=True,gridspec_kw={"height_ratios":[3,1.3,1.3,1.3]})
ax0=axes[0]; ax0.set_yscale("log")
ax0.plot(x,close,color="black",lw=0.7,label="NQ close")
bwid,mid,up,lo=bw["MTF (100)"]
ax0.plot(x,up,color="tab:blue",lw=0.7,alpha=.6); ax0.plot(x,lo,color="tab:blue",lw=0.7,alpha=.6)
ax0.plot(x,mid,color="tab:blue",lw=0.8,alpha=.7,label="BB(100)")
sq=squeeze(bwid).fillna(False).to_numpy()
ax0.fill_between(x,close.min()*0.9,close.max()*1.05,where=sq,color=ORANGE,alpha=0.18,label="MTF squeeze")
ax0.set_ylim(close[300:].min()*0.95,close.max()*1.05)
ax0.set_title("NQ — Bollinger Band squeeze (compression) at 3 timeframes  |  orange = squeeze"); ax0.legend(loc="upper left")

for ax,(name,(bwid,_,_,_)) in zip(axes[1:],bw.items()):
    sq=squeeze(bwid).fillna(False).to_numpy()
    ax.plot(x,bwid,color="black",lw=0.7)
    ax.fill_between(x,0,bwid,where=sq,color=ORANGE,alpha=0.7,label="squeeze")
    ax.set_ylabel(name+" bw%"); ax.legend(loc="upper right",fontsize=8)
axes[-1].xaxis.set_major_locator(mdates.YearLocator(1)); axes[-1].xaxis_date()
plt.tight_layout(); plt.savefig(os.path.join(OUTPUT_DIR,"nq_bbands.png"),dpi=190); plt.close()

# ---------- B) ADX trend/range regime ----------
adx,plus_di,minus_di=adx_ind(high,low,close,14)

def regime_color(i):
    if np.isnan(adx.iloc[i]): return NEUTRAL
    if adx.iloc[i]<20: return ORANGE                       # range / chop
    if adx.iloc[i]>25: return GREEN if plus_di.iloc[i]>minus_di.iloc[i] else RED
    return NEUTRAL                                          # 20-25 = transitional
cols=[regime_color(i) for i in range(len(close))]

fig,(axp,axa)=plt.subplots(2,1,figsize=(22,11),sharex=True,gridspec_kw={"height_ratios":[3,1.3]})
axp.set_yscale("log")
S=30
xs,ys=x[S:],close.to_numpy()[S:]; cs=cols[S:]
pts=np.array([xs,ys]).T.reshape(-1,1,2); segs=np.concatenate([pts[:-1],pts[1:]],axis=1)
axp.add_collection(LineCollection(segs,colors=cs[1:],linewidths=1.6))
axp.set_xlim(x[S],x[-1]); axp.set_ylim(close[S:].min()*0.95,close.max()*1.05)
axp.set_title("NQ — ADX trend/range regime  |  green=up-trend  red=down-trend  orange=range(ADX<20)")
axp.legend(handles=[Patch(color=GREEN,label="up-trend"),Patch(color=RED,label="down-trend"),
                    Patch(color=ORANGE,label="range / chop"),Patch(color=NEUTRAL,label="transitional")],loc="upper left")
axa.plot(x,adx,color="black",lw=0.8,label="ADX")
axa.plot(x,plus_di,color=GREEN,lw=0.6,alpha=.7,label="+DI"); axa.plot(x,minus_di,color=RED,lw=0.6,alpha=.7,label="-DI")
axa.axhline(20,color="orange",ls="--",lw=0.8); axa.axhline(25,color="green",ls="--",lw=0.8)
axa.set_ylabel("ADX / DI"); axa.legend(loc="upper right",fontsize=8)
axa.xaxis.set_major_locator(mdates.YearLocator(1)); axa.xaxis_date()
plt.tight_layout(); plt.savefig(os.path.join(OUTPUT_DIR,"nq_adx.png"),dpi=190); plt.close()
print("SAVED nq_bbands.png, nq_adx.png")
