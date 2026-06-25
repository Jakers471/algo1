"""Chart view — the lightweight-charts candles + order markers, embedded in-window."""
import os

import streamlit as st
import streamlit.components.v1 as components


def render(R):
    st.subheader("Chart - candles + orders")
    p = os.path.join(R["dir"], "chart.html")
    if not os.path.exists(p):
        st.info("No chart for this run.")
        return
    html = open(p, encoding="utf-8").read()
    components.html(html, height=820, scrolling=False)
