"""Equity view — equity curve + drawdown (like NT's equity graph)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def render(R):
    e = R["equity"]
    t = pd.to_datetime(e["time"])
    eq = e["equity"].to_numpy()
    dd = (eq / np.maximum.accumulate(eq) - 1) * 100

    st.subheader("Equity & drawdown")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                        vertical_spacing=0.03)
    fig.add_trace(go.Scatter(x=t, y=eq, line=dict(color="#2dd4bf", width=1.3), name="equity"), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=dd, fill="tozeroy", line=dict(color="#ef5350", width=0.8),
                             name="drawdown %"), 2, 1)
    fig.update_yaxes(type="log", title_text="equity", row=1, col=1)
    fig.update_yaxes(title_text="drawdown %", row=2, col=1)
    fig.update_layout(template="plotly_dark", height=760, showlegend=False,
                      margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="#0b0c0e", plot_bgcolor="#0b0c0e")
    st.plotly_chart(fig, width="stretch")
