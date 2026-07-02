"""
Interactive 3D CWT scalogram (Plotly "mountain" surface) of the aggregate MTF efficiency score.

Reuses aggregate_score() and cwt_morlet() from mtf_score_cwt.py. Renders period x time x log-power
as a rotatable/zoomable Turbo surface -> interactive HTML.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/mtf_score_cwt_3d.py"
"""
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from algokit.data import load_tf
import mtf_score_cwt as mc

YEARS = 4

base = load_tf("60m").dropna()
end = base.index[-1]
start = end - pd.Timedelta(days=int(365 * YEARS))
warm = start - pd.Timedelta(days=90)
idx = base[base.index >= start].index
sig = mc.aggregate_score(idx, warm)

n = len(sig)
scales = np.geomspace(2, n // 4, 180)
fourier = 4 * np.pi / (mc.W0 + np.sqrt(2 + mc.W0 ** 2))
periods = scales * fourier                              # hours
power = np.abs(mc.cwt_morlet(sig, scales)) ** 2
z = np.log10(power + 1e-9)

stride = max(1, n // 1400)                              # downsample time only
xt = [t.strftime("%Y-%m-%d") for t in idx[::stride]]
zz = z[:, ::stride]

fig = go.Figure(data=[go.Surface(x=xt, y=periods, z=zz, colorscale="Turbo",
                                 colorbar=dict(title="log power"))])
fig.update_layout(
    template="plotly_dark", paper_bgcolor="#080b11",
    title=f"NQ | aggregate MTF efficiency score — 3D CWT scalogram | last {YEARS}yr (drag to rotate, scroll to zoom)",
    scene=dict(xaxis_title="time", yaxis_title="period (hours, log)", zaxis_title="log power",
               yaxis=dict(type="log"), bgcolor="#080b11",
               camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9))),
    margin=dict(l=0, r=0, t=42, b=0))

out = os.path.join(HERE, "output", "mtf_score_cwt_3d.html")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.write_html(out, include_plotlyjs="cdn")
print("saved", out, "| grid", zz.shape[0], "periods x", zz.shape[1], "time cols")
