"""
Paint the 9 fractal MAs by REGIME (no signals):
  orange = tier compressed (for an extended stretch)
  green  = MA uptrending
  red    = MA downtrending
HTF mask: while HTF is uptrending, red is suppressed (only green/orange show);
while HTF is downtrending, green is suppressed (only red/orange). Orange always shows.

Thin consumer of algokit.charts.regime_ribbon.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.charts import regime_ribbon

LTF=[10,20,50]; MTF=[100,150,200]; HTF=[300,400,600]
L=10                      # slope lookback
COMP_Q=0.25               # tier "compressed" = spread below this rolling-1yr quantile
COMP_RUN=10               # must stay compressed this many bars = "extended"
START=610                 # after MA600 + slope lookback warm up

df=load_tf("1d")
dt=df.index.normalize()
close=df["close"]

out=os.path.join(OUTPUT_DIR,"nq_regime_ribbon.png")
regime_ribbon(close, dt, LTF, MTF, HTF, slope_L=L, comp_q=COMP_Q,
              comp_run=COMP_RUN, start=START, out_path=out)
print("SAVED nq_regime_ribbon.png")
