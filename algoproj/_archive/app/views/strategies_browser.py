"""Strategies browser — strategy-vs-strategy, "which strategy is best?".

Each strategy is represented by its CHAMPION run — the run that maximizes a metric you
pick live (the champion dropdown). Shows an aggregate leaderboard (one row per strategy)
and compares the champions head to head: metrics + overlaid equity curves. No param-diff
here — comparing different strategies' knobs is meaningless; that lives in the Runs tab.
"""
import altair as alt
import pandas as pd
import streamlit as st

from app.views import runs_data as rd


def _champions(df, metric):
    """Per strategy: the run maximizing `metric` (its champion), as a row dict."""
    champs = {}
    for strat, g in df.groupby("strategy"):
        gg = g.dropna(subset=[metric])
        if not gg.empty:
            champs[strat] = g.loc[gg[metric].idxmax()]
    return champs


def _aggregate(df, metric, champs):
    rows = []
    for strat, g in df.groupby("strategy"):
        ch = champs.get(strat)
        rows.append(dict(
            strategy=strat, runs=len(g),
            champion=ch["run"] if ch is not None else "—",
            champ_net=ch["net"] if ch is not None else None,
            champ_sharpe=ch["sharpe"] if ch is not None else None,
            champ_max_dd=ch["max_dd"] if ch is not None else None,
            best_sharpe=g["sharpe"].max(), median_sharpe=g["sharpe"].median(),
            _sort=(ch[metric] if ch is not None else None)))
    return pd.DataFrame(rows).sort_values("_sort", ascending=False, na_position="last") \
        .drop(columns="_sort").reset_index(drop=True)


def render():
    df = rd.table(rd.index_stamp())
    if df.empty:
        st.info("No runs saved yet. Run a backtest or walk-forward optimization first.")
        return

    c1, _ = st.columns([1.4, 3])
    metric = c1.selectbox("Champion metric", list(rd.METRICS),
                          format_func=lambda k: rd.METRICS[k][0], index=2,
                          help="Each strategy is represented by the run that maximizes this.")
    champs = _champions(df, metric)
    n_strat = df["strategy"].nunique()
    st.caption(f"{n_strat} strateg{'y' if n_strat == 1 else 'ies'} · {len(df)} total runs · "
               f"champion = best {rd.METRICS[metric][0]} run of each")

    # ---- aggregate leaderboard (one row per strategy) ----
    agg = _aggregate(df, metric, champs)
    sty = agg.style.format({"champ_net": "{:+.1f}%", "champ_sharpe": "{:.2f}",
                            "champ_max_dd": "{:.1f}%", "best_sharpe": "{:.2f}",
                            "median_sharpe": "{:.2f}"}, na_rep="—") \
        .highlight_max(subset=["champ_net", "champ_sharpe", "champ_max_dd", "best_sharpe"],
                       color="#16331f")
    st.dataframe(sty, hide_index=True, width="stretch",
                 column_config={"champ_net": st.column_config.TextColumn("net"),
                                "champ_sharpe": st.column_config.TextColumn("sharpe"),
                                "champ_max_dd": st.column_config.TextColumn("max dd")})

    if len(champs) >= 2:
        cdf = pd.DataFrame([{"strategy": s, "champion": ch["run"], "value": ch[metric]}
                            for s, ch in champs.items() if ch[metric] is not None])
        chart = (alt.Chart(cdf).mark_bar(color="#26a69a").encode(
            x=alt.X("value:Q", title=f"Champion {rd.METRICS[metric][0]}"
                                     + (" %" if rd.METRICS[metric][2] else "")),
            y=alt.Y("strategy:N", sort="-x", title=None),
            tooltip=["strategy", "champion", "value"])
            .properties(width="container", height=max(120, 30 * len(cdf))))
        st.altair_chart(chart)

    st.divider()

    # ---- compare champions head to head ----
    st.markdown("**Compare strategy champions**")
    if not champs:
        st.caption("No champions to compare yet.")
        return
    options = {f"{s} · {ch['run']}": ch for s, ch in champs.items()}
    picks = st.multiselect("Champions", list(options), default=list(options))
    if not picks:
        return
    chosen = [options[p] for p in picks]
    st.markdown("**Metrics**")
    st.dataframe(rd.metrics_matrix(chosen), width="stretch",
                 column_config={"what it means": st.column_config.TextColumn(width="large")})
    rd.equity_overlay(chosen)
    if n_strat == 1:
        st.caption("Only one strategy so far — this view comes alive once you add another "
                   "strategy under strategies/ and run it.")
