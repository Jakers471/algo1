"""
Multi-timeframe regime engine on NQ: 1d (HTF) -> 1h (MTF) -> 15m (LTF).
Each timeframe: a 32-MA fan collapsed into a 0-100 regime score split 3 ways
(bullish / consolidation / bearish), longer MAs weighted more (geometric).

Cascade drill-down:
  1d full  ->  zoom 1h into the latest 1d-bullish window  ->  zoom 15m into the
  latest 1h-bullish sub-window (with the consolidation squeeze range boxed).

Outputs: nq_regime_1d.png, nq_regime_1h.png, nq_regime_15m.png

Refactored: scores come from algokit.regime.regime_score, the fan/slope from
algokit.indicators, data from algokit.data. The cascade plotting stays local.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.indicators import geom_lengths, fan, slope_pct
from algokit.regime import regime_score

GREEN="#21a121"; RED="#d62728"; YELLOW="#f2c800"
LENGTHS=geom_lengths(5,500,32)
BULL_THRESH=70
SLOPE_L=5

def compute(df, eps):
    """per-MA slope-color + 0-100 bull/consol/bear scores (scores via regime_score)."""
    close=df["close"]
    ma=fan(close, LENGTHS)
    colors=[]
    for n in LENGTHS:
        sl=slope_pct(ma[n], SLOPE_L).to_numpy()
        c=np.where(sl>eps,GREEN,np.where(sl<-eps,RED,YELLOW)); colors.append(c)
    bull,consol,bear=regime_score(df, 5, 500, slope_L=SLOPE_L, eps=eps)
    return dict(close=close, ma=ma, colors=colors, bull=bull, bear=bear, consol=consol)

def last_run(mask):
    """integer [start,end] of the last contiguous True run; None if none."""
    m=mask.to_numpy(); idx=np.where(m)[0]
    if len(idx)==0: return None
    e=idx[-1]; s=e
    while s-1>=0 and m[s-1]: s-=1
    return s,e

def longest_run(mask):
    """integer [start,end] of the LONGEST contiguous True run; None if none."""
    m=mask.to_numpy().astype(bool); best_len=0; best=None; s=None
    for i,v in enumerate(m):
        if v and s is None: s=i
        elif not v and s is not None:
            if i-s>best_len: best_len=i-s; best=(s,i-1)
            s=None
    if s is not None and len(m)-s>best_len: best=(s,len(m)-1)
    return best

def plot_tf(comp, sl, title, out, box=False):
    close=comp["close"].iloc[sl]; idx=close.index
    x=np.arange(len(close))
    fig,(axp,axr)=plt.subplots(2,1,figsize=(13,9),sharex=True,
                               gridspec_kw={"height_ratios":[3,1.2]})
    axp.set_yscale("log")
    axp.plot(x,close.to_numpy(),color="black",lw=0.5,alpha=0.25,zorder=1)
    for j,n in enumerate(LENGTHS):
        y=comp["ma"][n].iloc[sl].to_numpy(); cs=comp["colors"][j][sl]
        pts=np.array([x,y]).T.reshape(-1,1,2); segs=np.concatenate([pts[:-1],pts[1:]],axis=1)
        axp.add_collection(LineCollection(segs,colors=cs[1:],linewidths=0.8,zorder=3))
    axp.set_xlim(0,len(close)-1)
    lo,hi=np.nanmin(close.values),np.nanmax(close.values); axp.set_ylim(lo*0.97,hi*1.03)
    if box:   # consolidation squeeze range over the bars where consol dominates
        bb=comp["bull"].iloc[sl].to_numpy(); rr=comp["bear"].iloc[sl].to_numpy()
        cc=comp["consol"].iloc[sl].to_numpy()
        cmask=cc>=np.maximum(bb,rr)
        if cmask.any():
            seg=close.to_numpy()[cmask]
            axp.axhline(seg.max(),color="purple",ls="--",lw=1.2)
            axp.axhline(seg.min(),color="purple",ls="--",lw=1.2,label="squeeze hi/lo")
    axp.set_title(title)
    axp.legend(handles=[Patch(color=GREEN,label="up"),Patch(color=YELLOW,label="sideways"),
                        Patch(color=RED,label="down")],loc="upper left",fontsize=9)
    # regime score panel (stacked to 100)
    b=comp["bull"].iloc[sl].to_numpy(); c=comp["consol"].iloc[sl].to_numpy(); r=comp["bear"].iloc[sl].to_numpy()
    axr.stackplot(x,b,c,r,colors=[GREEN,YELLOW,RED],alpha=0.9)
    axr.axhline(BULL_THRESH,color="black",ls="--",lw=1,label=f"bull thresh {BULL_THRESH}")
    axr.set_ylim(0,100); axr.set_ylabel("regime 0-100"); axr.legend(loc="upper right",fontsize=8)
    pos=np.linspace(0,len(idx)-1,8).astype(int)
    fmt="%Y-%m-%d" if (idx[-1]-idx[0]).days>20 else "%m-%d %H:%M"
    axr.set_xticks(pos); axr.set_xticklabels([idx[p].strftime(fmt) for p in pos],rotation=20,fontsize=8)
    plt.tight_layout(); plt.savefig(out,dpi=170); plt.close()

# ---- build the cascade ----
d1=load_tf("1d");  c1=compute(d1, eps=0.15)
h1=load_tf("60m"); c1h=compute(h1, eps=0.06)
m15=load_tf("15m");c15=compute(m15, eps=0.03)

# 1d: full length
plot_tf(c1, slice(max(LENGTHS)+5,len(d1)),
        "NQ 1d (HTF) — 32-MA fan + regime score (full history)", os.path.join(OUTPUT_DIR,"nq_regime_1d.png"))

# find latest 1d-bullish run -> window for 1h
run=last_run(c1["bull"]>=BULL_THRESH)
s,e=d1.index[run[0]], d1.index[run[1]]
print("1d bullish window:", s.date(), "->", e.date())
h_sl=np.where((h1.index>=s)&(h1.index<=e))[0]
h_slice=slice(h_sl[0],h_sl[-1]+1)
plot_tf(c1h, h_slice, f"NQ 1h (MTF) — zoomed into 1d-bullish window {s.date()}..{e.date()}", os.path.join(OUTPUT_DIR,"nq_regime_1h.png"))

# within that, latest 1h-bullish run -> window for 15m
bh=c1h["bull"].iloc[h_slice]
runh=longest_run(bh>=BULL_THRESH)
if runh:
    s2,e2=bh.index[runh[0]], bh.index[runh[1]]
else:
    s2,e2=s,e
print("1h bullish sub-window:", s2, "->", e2)
m_sl=np.where((m15.index>=s2)&(m15.index<=e2))[0]
if len(m_sl)<10: m_sl=np.where((m15.index>=s)&(m15.index<=e))[0][-400:]
m_slice=slice(m_sl[0],m_sl[-1]+1)
plot_tf(c15, m_slice, f"NQ 15m (LTF) — zoomed into 1h-bullish window (squeeze range boxed)", os.path.join(OUTPUT_DIR,"nq_regime_15m.png"), box=True)
print("SAVED nq_regime_1d.png, nq_regime_1h.png, nq_regime_15m.png")
