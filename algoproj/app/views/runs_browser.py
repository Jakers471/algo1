"""Runs browser — run-vs-run, scoped to ONE strategy.

Pick a strategy, then browse / filter / rank its runs and compare any of them side by side:
full metrics, overlaid equity curves, and a parameter DIFF (which knobs changed, what was
added/removed). Param-diff only makes sense within a strategy (shared param schema), so this
tab is single-strategy; cross-strategy comparison lives in the Strategies tab.
"""
import altair as alt
import pandas as pd
import streamlit as st

from algokit import metrics, params
from app.views import runs_data as rd


def _cards(df):
    if df.empty:
        return
    cols = st.columns(4)
    for (col, label), card in zip(
            [("net", "Best net return"), ("sharpe", "Best Sharpe"),
             ("max_dd", "Smallest drawdown"), ("cagr", "Best CAGR")], cols):
        s = df[col].dropna()
        with card:
            if s.empty:
                st.metric(label, "—")
                continue
            r = df.loc[s.idxmax()]
            st.metric(label, f"{r[col]:+.2f}" if col == "sharpe" else f"{r[col]:+.1f}%")
            st.caption(r["run"])


def _leaderboard(df, sort_col, ascending):
    disp = df[["run", "type", "basis", "date", "net", "cagr", "sharpe", "max_dd", "win"]] \
        .sort_values(sort_col, ascending=ascending, na_position="last")
    sty = disp.style.format({"net": "{:+.1f}%", "cagr": "{:+.1f}%", "sharpe": "{:.2f}",
                             "max_dd": "{:.1f}%", "win": "{:.0f}%"}, na_rep="—") \
        .highlight_max(subset=["net", "cagr", "sharpe", "max_dd", "win"], color="#16331f")
    st.dataframe(sty, hide_index=True, width="stretch",
                 column_config={"basis": st.column_config.TextColumn(
                     "basis", help="full = whole-history backtest; OOS = walk-forward")})


def _ranking_chart(df, sort_col, ascending):
    d = df.dropna(subset=[sort_col])
    if d.empty:
        return
    order = "ascending" if ascending else "descending"
    label = rd.METRICS[sort_col][0]
    chart = (alt.Chart(d).mark_bar(color="#26a69a").encode(
        x=alt.X(f"{sort_col}:Q", title=label + (" %" if rd.METRICS[sort_col][2] else "")),
        y=alt.Y("run:N", sort=alt.SortField(sort_col, order=order), title=None),
        tooltip=["run", "type", "net", "sharpe", "max_dd", "win"])
        .properties(width="container", height=max(120, 26 * len(d))))
    st.altair_chart(chart)


def _scatter(df):
    d = df.dropna(subset=["max_dd", "net"]).copy()
    if d.empty:
        st.caption("No runs with drawdown data yet for the risk/reward map.")
        return
    d["drawdown"] = -d["max_dd"]
    chart = (alt.Chart(d).mark_circle(size=160, opacity=0.8).encode(
        x=alt.X("drawdown:Q", title="Max drawdown % (pain →)"),
        y=alt.Y("net:Q", title="Net return % (← reward)"),
        color=alt.Color("type:N", legend=alt.Legend(orient="bottom")),
        tooltip=["run", "type", "net", "sharpe", "max_dd", "win"])
        .properties(width="container", height=340))
    st.altair_chart(chart)


def _params_compare(chosen):
    cfgs = {r["run"]: rd.config(r["path"]) for r in chosen}
    for r in chosen:
        c = cfgs[r["run"]]
        line = (f"**{r['run']}** · {c.get('symbol', '?')} · "
                f"HTF {c.get('htf_tf', '?')} / LTF {c.get('ltf_tf', '?')}")
        if r["kind"] == "wfo":
            m = rd.meta(r["path"])
            win = "anchored" if m.get("anchored") else "rolling"
            dr = m.get("date_range") or ["?", "?"]
            line += (f" · optimize **{m.get('objective')}** · train {m.get('train_days')}d / "
                     f"test {m.get('test_days')}d ({win}) · range {dr[0]} → {dr[1]} · "
                     f"swept {', '.join(m.get('swept_params', {}) or {}) or '—'}")
        st.markdown(line)

    allkeys = list(dict.fromkeys(k for c in cfgs.values() for k in c))
    sig, _ = params.split_params({k: None for k in allkeys})
    ordered = [k for k in allkeys if k in sig] + [k for k in allkeys if k not in sig]
    import json
    diff_keys = [k for k in ordered
                 if len({json.dumps(c.get(k), default=str, sort_keys=True)
                         for c in cfgs.values()}) > 1]

    only_diff = st.checkbox("Show only changed params", value=True)
    rows = diff_keys if only_diff else ordered
    if not rows:
        st.caption("All parameters are identical across the selected runs.")
        return
    table = pd.DataFrame({run: [rd.fmt_val(cfgs[run].get(k)) for k in rows] for run in cfgs},
                         index=rows)
    table.insert(0, "group", ["signal" if k in sig else "account/exec" for k in rows])

    def _hl(row):
        bad = row.name in diff_keys
        return ["background-color:#3a3413" if bad and col != "group" else "" for col in row.index]
    st.dataframe(table.style.apply(_hl, axis=1), width="stretch",
                 column_config={"group": st.column_config.TextColumn(width="small")})
    st.caption(f"{len(diff_keys)} of {len(ordered)} parameters differ (highlighted). "
               "Missing in a run shows as — (added/removed).")


def _compare(df):
    labels = {f"{r['run']}": r for _, r in df.iterrows()}
    picks = st.multiselect("Pick runs to compare", list(labels), default=list(labels)[:2])
    if not picks:
        return
    chosen = [labels[p] for p in picks]

    st.markdown("**Metrics**")
    matrix = rd.metrics_matrix(chosen)
    st.dataframe(matrix, width="stretch",
                 column_config={"what it means": st.column_config.TextColumn(width="large")})

    rd.equity_overlay(chosen)

    st.divider()
    st.markdown("**Parameters & settings**")
    _params_compare(chosen)


def render():
    df = rd.table(rd.index_stamp())
    if df.empty:
        st.info("No runs saved yet. Run a backtest or walk-forward optimization first.")
        return

    strategy = st.selectbox("Strategy", sorted(df["strategy"].unique()))
    sdf = df[df["strategy"] == strategy].reset_index(drop=True)

    f1, f2, f3 = st.columns([1.4, 1.4, 1])
    types = sorted(sdf["type"].unique())
    type_sel = f1.multiselect("Type", types, default=types)
    sort_col = f2.selectbox("Sort by", list(rd.METRICS),
                            format_func=lambda k: rd.METRICS[k][0], index=2)
    order = f3.radio("Order", ["Worst→Best", "Best→Worst"], index=1)
    ascending = order == "Worst→Best"

    fdf = sdf[sdf["type"].isin(type_sel)].reset_index(drop=True)
    if fdf.empty:
        st.warning("No runs match the filters.")
        return

    _cards(fdf)
    st.divider()
    st.markdown(f"**{strategy}** — {len(fdf)} runs, sorted by {rd.METRICS[sort_col][0]} "
                f"({order.lower()})")
    _leaderboard(fdf, sort_col, ascending)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown(f"**Ranked by {rd.METRICS[sort_col][0]}**")
        _ranking_chart(fdf, sort_col, ascending)
    with g2:
        st.markdown("**Risk / reward map**")
        _scatter(fdf)

    st.divider()
    st.markdown("**Compare runs side by side**")
    _compare(fdf)
