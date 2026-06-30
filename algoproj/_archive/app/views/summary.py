"""Summary view — the full performance & risk stats (like NT's Summary tab)."""
import pandas as pd
import streamlit as st

from algokit import metrics


def render(R):
    m = R["metrics"]
    st.subheader("Performance & risk")
    df = pd.DataFrame([(k, metrics.fmt(k, v), metrics.EXPLAIN.get(k, "")) for k, v in m.items()],
                      columns=["metric", "value", "what it means"])
    st.dataframe(
        df, width="stretch", hide_index=True, height=760,
        column_config={
            "metric": st.column_config.TextColumn(width="small"),
            "value": st.column_config.TextColumn(width="small"),
            "what it means": st.column_config.TextColumn(width="large"),  # full, never cut off
        },
    )
    st.caption("Strategy is long-only, so All trades = Long trades (Short = none).")
