"""
Multi-timeframe fan-regime SIGNAL + RETURN engine on NQ.

Regime score per timeframe (32-MA fan -> bull/consol/bear 0-100, longer MAs
weighted more). Timeframes: 1d (HTF bias) / 1h (MTF) / 15m (LTF entry timing),
each with its OWN native fan length so they don't overlap.

Idea under test: don't wait for a high score (late) -- enter on the
consolidation -> bullish TRANSITION, gated by higher-timeframe alignment.
We SWEEP the entry level X and the alignment config to find where the edge
actually starts and which alignment pays.

Entry : bull_LTF crosses up through X, while recently coiled, gated by alignment
Exit  : bull_LTF falls below EXIT_TH (LTF flips)   |   wide ATR stop

Refactored to consume algokit (data / regime / indicators / backtest / metrics);
numbers are unchanged.
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from algokit.data import load_tf, align
from algokit.indicators import atr as atr_ind
from algokit.regime import regime_score
from algokit.backtest import run_long_only
from algokit.costs import FlatCost
from algokit import metrics

# ---- params (tunable) ----
FAN = {"1d": (5,500,0.15), "1h": (5,250,0.06), "15m": (5,100,0.03)}  # (min,max,eps)
COIL_K      = 20      # LTF bars to look back for "was coiled"
COIL_LEVEL  = 40      # consol score that counts as coiled
EXIT_TH     = 30      # exit when LTF bull score drops below this
HTF_GATE    = 50      # 1d bull score required for HTF-bullish
MTF_GATE    = 50      # 1h bull score required for MTF-bullish
ATR_MULT    = 5.0     # wide disaster stop
ATR_N       = 14
COST        = FlatCost(0.0002)
X_SWEEP     = [30,40,45,50,55,60,70]

def reg(df, params):
    lo, hi, eps = params
    return regime_score(df, lo, hi, eps=eps)

d1=load_tf("1d"); h1=load_tf("60m"); m15=load_tf("15m")
b1d,_,_   = reg(d1, FAN["1d"])
b1h,_,_   = reg(h1, FAN["1h"])
b15,c15,_ = reg(m15, FAN["15m"])

# align HTF/MTF onto the 15m clock (no look-ahead: last CLOSED higher-TF bar)
idx=m15.index
bull1d=align(b1d, idx).to_numpy()
bull1h=align(b1h, idx).to_numpy()
bull15=b15.to_numpy(); consol15=c15.to_numpy()

close=m15["close"].to_numpy(); high=m15["high"].to_numpy(); low=m15["low"].to_numpy()
atr=atr_ind(m15["high"], m15["low"], m15["close"], ATR_N).to_numpy()

coil_recent=pd.Series(consol15).rolling(COIL_K).max().to_numpy()>=COIL_LEVEL
years=(idx[-1]-idx[0]).days/365.25; PPY=len(close)/years
start=np.argmax(~np.isnan(bull1d) & ~np.isnan(bull15) & ~np.isnan(atr)) + 1
start=max(start, 600)

exit_sig = bull15 < EXIT_TH

def sim(X, gate_htf, gate_mtf):
    cross = (bull15>=X) & (np.r_[np.nan,bull15[:-1]]<X)
    gate = np.ones(len(close), bool)
    if gate_htf: gate &= bull1d>=HTF_GATE
    if gate_mtf: gate &= bull1h>=MTF_GATE
    entry_sig = cross & coil_recent & gate
    res = run_long_only(close, low, entry_sig, exit_sig, atr,
                        atr_mult=ATR_MULT, cost=COST, start=start)
    rets=res["rets"]; trades=res["trades"]; inmkt=res["in_market"]
    total=metrics.total_return(rets)*100
    cagr=metrics.cagr(rets, PPY)*100
    sh=metrics.sharpe(rets, PPY, start)
    dd=metrics.max_drawdown(rets)*100
    rt=len(trades)
    wr=metrics.win_rate(trades)*100
    return total,cagr,sh,dd,rt,wr,inmkt.mean()*100

configs=[("LTF only",False,False),("+HTF",True,False),("+HTF+MTF",True,True)]
bh=(close[-1]/close[start]-1)*100
print("NQ 15m engine  %s -> %s  (buy&hold %+.0f%%)\n"%(idx[start].date(),idx[-1].date(),bh))
print("%-12s %4s %8s %7s %7s %7s %6s %6s %7s"%("align","X","net%","CAGR%","Sharpe","maxDD%","trips","win%","inmkt%"))
print("-"*72)
best=None
for name,gh,gm in configs:
    for X in X_SWEEP:
        net,cagr,sh,dd,rt,wr,inm=sim(X,gh,gm)
        print("%-12s %4d %+8.0f %+7.1f %7.2f %7.0f %6d %6.0f %7.1f"%(name,X,net,cagr,sh,dd,rt,wr,inm))
        if rt>=20 and (best is None or sh>best[0]): best=(sh,name,X,net,cagr,dd,rt,wr)
    print()
if best:
    print("BEST by Sharpe (>=20 trips): %s  X=%d  -> net %+.0f%%  CAGR %+.1f%%  Sharpe %.2f  DD %.0f%%  trips %d  win %.0f%%"
          %(best[1],best[2],best[3],best[4],best[0],best[5],best[6],best[7]))
