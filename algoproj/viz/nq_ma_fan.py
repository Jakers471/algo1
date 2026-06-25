"""
Giant MA fan on NQ daily: 32 moving averages, each colored by its own slope.
  green  = sloping up
  red    = sloping down
  yellow = sideways (slope within +/- EPS)

Thin consumer of algokit.charts.fan_plot.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.indicators import geom_lengths
from algokit.charts import fan_plot

L=5            # slope lookback (bars)
EPS=0.15       # +/- % over L bars that counts as "sideways"

df=load_tf("1d")
dt=df.index.normalize()
close=df["close"]
lengths=geom_lengths(5,500,32)   # ~32 MAs, fan spacing

out=os.path.join(OUTPUT_DIR,"nq_ma_fan.png")
fan_plot(close, dt, lengths, slope_L=L, eps=EPS, out_path=out)
print("MAs:",len(lengths),"->",lengths)
print("SAVED nq_ma_fan.png")
