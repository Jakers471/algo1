"""Runs browser — registry-level view across ALL saved runs.

Browse, filter, rank (worst->best on any metric), and compare every backtest / walk-forward
run the registry has saved. Pulls the fast headline stats from runs/index.json for the
tables + graphs, and only loads full metrics / equity curves for the handful of runs you
pick to compare side by side.
"""
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

from algokit import runs, metrics, params

# leaderboard metrics: df column -> (label, higher_is_better, percent?)
_METRICS = {
    "net": ("Net return", True, True),
    "cagr": ("CAGR", True, True),
    "sharpe": ("Sharpe", True, False),
    "max_dd": ("Max drawdown", True, True),   # higher (closer to 0) is better
    "win": ("Win rate", True, True),
}

# full-metric rows for the side-by-side compare (ordered)
_COMPARE_ROWS = ["total_return", "cagr", "sharpe", "sortino", "calmar", "max_drawdown",
                 "annual_vol", "profit_factor", "payoff_ratio", "win_rate", "expectancy",
                 "exposure", "round_trips", "max_consec_losses", "total_pnl"]


@st.cache_data(show_spinner=False)
def _table(_stamp):
    """Unified row per run from the index headline (stamp busts cache when runs change)."""
    rows = []
    for m in runs.list_runs():
        h = m.get("headline", {})
        wfo = m.get("kind") == "wfo"
        g = (lambda k: h.get("oos_" + k)) if wfo else (lambda k: h.get(k))
        net = g("total_return")
        rows.append(dict(
            run=m["name"], strategy=m["strategy"], type=m.get("backtest_type", "Backtest"),
            date=m.get("date", (m.get("timestamp", "") or "")[:10]),
            net=None if net is None else net * 100,
            cagr=(lambda v: None if v is None else v * 100)(g("cagr")),
            sharpe=g("sharpe"),
            max_dd=(lambda v: None if v is None else v * 100)(g("max_drawdown")),
            win=(lambda v: None if v is None else v * 100)(g("win_rate")),
            kind=m.get("kind", "backtest"), path=m["path"],
            basis="OOS" if wfo else "full"))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _full_metrics(path, kind):
    d = os.path.join(runs.RUNS_DIR, path)
    if kind == "wfo":
        return json.load(open(os.path.join(d, "result.json"))).get("oos", {})
    return json.load(open(os.path.join(d, "metrics.json")))


@st.cache_data(show_spinner=False)
def _config(path):
    return json.load(open(os.path.join(runs.RUNS_DIR, path, "config.json")))


@st.cache_data(show_spinner=False)
def _meta(path):
    return json.load(open(os.path.join(runs.RUNS_DIR, path, "meta.json")))


@st.cache_data(show_spinner=False)
def _equity_daily(path):
    """Daily % -return-from-start curve for a backtest run (light enough to overlay)."""
    eq = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "equity.parquet"),
                         columns=["time", "equity"]).set_index("time")
    daily = eq["equity"].resample("1D").last().dropna()
    return daily / daily.iloc[0] * 100 - 100


def _cards(df):
    """Best-of metric callouts over the (filtered) set."""
    if df.empty:
        return
    c1, c2, c3, c4 = st.columns(4)
    def best(col, fn="idxmax"):
        s = df[col].dropna()
        if s.empty:
            return None
        i = getattr(s, fn)()
        return df.loc[i]
    for col, fn, label, card in (("net", "idxmax", "Best net return", c1),
                                 ("sharpe", "idxmax", "Best Sharpe", c2),
                                 ("max_dd", "idxmax", "Smallest drawdown", c3),
                                 ("cagr", "idxmax", "Best CAGR", c4)):
        r = best(col, fn)
        with card:
            if r is None:
                st.metric(label, "—")
            else:
                unit = "" if col == "sharpe" else "%"
                st.metric(label, f"{r[col]:+.2f}{unit}" if col == "sharpe" else f"{r[col]:+.1f}{unit}")
                st.caption(f"{r['run']} · {r['strategy']}")


def _leaderboard(df, sort_col, ascending):
    disp = df[["run", "type", "strategy", "basis", "date", "net", "cagr", "sharpe",
               "max_dd", "win"]].sort_values(sort_col, ascending=ascending, na_position="last")
    sty = disp.style.format({"net": "{:+.1f}%", "cagr": "{:+.1f}%", "sharpe": "{:.2f}",
                             "max_dd": "{:.1f}%", "win": "{:.0f}%"}, na_rep="—")
    sty = sty.highlight_max(subset=["net", "cagr", "sharpe", "max_dd", "win"],
                            color="#16331f", props=None)
    st.dataframe(sty, hide_index=True, width="stretch",
                 column_config={"basis": st.column_config.TextColumn(
                     "basis", help="full = whole-history backtest; OOS = walk-forward out-of-sample")})


def _ranking_chart(df, sort_col, ascending):
    label = _METRICS[sort_col][0]
    d = df.dropna(subset=[sort_col]).copy()
    if d.empty:
        return
    order = "ascending" if ascending else "descending"
    chart = (alt.Chart(d).mark_bar().encode(
        x=alt.X(f"{sort_col}:Q", title=label + (" %" if _METRICS[sort_col][2] else "")),
        y=alt.Y("run:N", sort=alt.SortField(sort_col, order=order), title=None),
        color=alt.Color("strategy:N", legend=alt.Legend(orient="bottom")),
        tooltip=["run", "strategy", "type", "net", "sharpe", "max_dd", "win"])
        .properties(width="container", height=max(120, 26 * len(d))))
    st.altair_chart(chart)


def _scatter(df):
    d = df.dropna(subset=["max_dd", "net"]).copy()
    if d.empty:
        st.caption("No runs with drawdown data yet for the risk/reward map.")
        return
    d["drawdown"] = -d["max_dd"]                       # plot as positive pain
    chart = (alt.Chart(d).mark_circle(size=160, opacity=0.8).encode(
        x=alt.X("drawdown:Q", title="Max drawdown % (pain →)"),
        y=alt.Y("net:Q", title="Net return % (← reward)"),
        color=alt.Color("type:N", legend=alt.Legend(orient="bottom")),
        tooltip=["run", "strategy", "type", "net", "sharpe", "max_dd", "win"])
        .properties(width="container", height=340))
    st.altair_chart(chart)


def _per_strategy(df):
    if df.empty:
        return
    g = df.groupby("strategy").agg(
        runs=("run", "count"),
        best_net=("net", "max"), best_sharpe=("sharpe", "max"),
        median_sharpe=("sharpe", "median"), best_dd=("max_dd", "max")).reset_index()
    sty = g.style.format({"best_net": "{:+.1f}%", "best_sharpe": "{:.2f}",
                          "median_sharpe": "{:.2f}", "best_dd": "{:.1f}%"}, na_rep="—")
    st.dataframe(sty, hide_index=True, width="stretch")


def _fmt_val(v):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _params_compare(chosen):
    """Side-by-side config of the selected runs: timeframe, optimize settings, param diffs."""
    cfgs = {r["run"]: _config(r["path"]) for r in chosen}

    # per-run context line: strategy, instrument, timeframes, and (WFO) the window settings
    for r in chosen:
        c = cfgs[r["run"]]
        base = (f"**{r['run']}** · {r['strategy']} · {c.get('symbol', '?')} · "
                f"HTF {c.get('htf_tf', '?')} / LTF {c.get('ltf_tf', '?')}")
        if r["kind"] == "wfo":
            m = _meta(r["path"])
            win = "anchored" if m.get("anchored") else "rolling"
            dr = m.get("date_range") or ["?", "?"]
            base += (f" · optimize **{m.get('objective')}** · train {m.get('train_days')}d / "
                     f"test {m.get('test_days')}d ({win}) · range {dr[0]} → {dr[1]} · "
                     f"swept {', '.join(m.get('swept_params', {}) or {}) or '—'}")
        st.markdown(base)

    # union of keys, signal params first then account/execution
    allkeys = list(dict.fromkeys(k for c in cfgs.values() for k in c))
    sig, uni = params.split_params({k: None for k in allkeys})
    ordered = [k for k in allkeys if k in sig] + [k for k in allkeys if k in uni]

    def _same(k):
        seen = {json.dumps(c.get(k), default=str, sort_keys=True) for c in cfgs.values()}
        return len(seen) == 1
    diff_keys = [k for k in ordered if not _same(k)]

    only_diff = st.checkbox("Show only changed params", value=True)
    rows = diff_keys if only_diff else ordered
    if not rows:
        st.caption("All parameters are identical across the selected runs.")
        return
    table = pd.DataFrame(
        {run: [_fmt_val(cfgs[run].get(k)) for k in rows] for run in cfgs}, index=rows)
    table.insert(0, "group", ["signal" if k in sig else "account/exec" for k in rows])

    def _hl(row):
        bad = row.name in diff_keys
        return ["background-color:#3a3413" if bad and col != "group" else "" for col in row.index]
    st.dataframe(table.style.apply(_hl, axis=1), width="stretch",
                 column_config={"group": st.column_config.TextColumn(width="small")})
    st.caption(f"{len(diff_keys)} of {len(ordered)} parameters differ "
               "(highlighted). Missing in a run shows as —, i.e. added/removed.")


def _compare(df):
    labels = {f"{r['strategy']} / {r['run']}": r for _, r in df.iterrows()}
    default = list(labels)[:2]
    picks = st.multiselect("Pick runs to compare", list(labels), default=default)
    if len(picks) < 1:
        return
    chosen = [labels[p] for p in picks]

    # metric matrix: rows = metric, columns = each run
    cols = {}
    for r in chosen:
        m = _full_metrics(r["path"], r["kind"])
        col = r["run"] + (" (OOS)" if r["kind"] == "wfo" else "")
        cols[col] = {k: metrics.fmt(k, m.get(k)) for k in _COMPARE_ROWS}
    matrix = pd.DataFrame(cols)
    matrix.insert(0, "what it means", [metrics.EXPLAIN.get(k, "") for k in _COMPARE_ROWS])
    matrix.index = [k for k in _COMPARE_ROWS]
    st.dataframe(matrix, width="stretch",
                 column_config={"what it means": st.column_config.TextColumn(width="large")})

    # equity overlay (backtest runs only)
    curves = {}
    for r in chosen:
        if r["kind"] != "wfo":
            try:
                curves[r["run"]] = _equity_daily(r["path"])
            except Exception:
                pass
    if curves:
        st.markdown("**Equity curves** — % return from start (daily)")
        st.line_chart(pd.DataFrame(curves))
    else:
        st.caption("Select backtest runs to overlay equity curves (WFO runs store only "
                   "stitched OOS metrics, no curve).")

    st.divider()
    st.markdown("**Parameters & settings**")
    _params_compare(chosen)


def render():
    st.subheader("Runs registry")
    df = _table(os.path.getmtime(os.path.join(runs.RUNS_DIR, "index.json"))
                if os.path.exists(os.path.join(runs.RUNS_DIR, "index.json")) else 0)
    if df.empty:
        st.info("No runs saved yet. Run a backtest or walk-forward optimization first.")
        return

    # ---- filters + sort ----
    f1, f2, f3, f4 = st.columns([1.4, 1.4, 1.4, 1])
    strats = sorted(df["strategy"].unique())
    types = sorted(df["type"].unique())
    strat_sel = f1.multiselect("Strategy", strats, default=strats)
    type_sel = f2.multiselect("Type", types, default=types)
    sort_col = f3.selectbox("Sort by", list(_METRICS),
                            format_func=lambda k: _METRICS[k][0], index=2)
    order = f4.radio("Order", ["Worst→Best", "Best→Worst"], index=1)
    ascending = order == "Worst→Best"

    fdf = df[df["strategy"].isin(strat_sel) & df["type"].isin(type_sel)].reset_index(drop=True)
    if fdf.empty:
        st.warning("No runs match the filters.")
        return

    _cards(fdf)
    st.divider()

    st.markdown(f"**Leaderboard** — {len(fdf)} runs, sorted by {_METRICS[sort_col][0]} "
                f"({order.lower()})")
    _leaderboard(fdf, sort_col, ascending)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown(f"**Ranked by {_METRICS[sort_col][0]}**")
        _ranking_chart(fdf, sort_col, ascending)
    with g2:
        st.markdown("**Risk / reward map**")
        _scatter(fdf)

    st.divider()
    st.markdown("**Per-strategy summary**")
    _per_strategy(fdf)

    st.divider()
    st.markdown("**Compare runs side by side**")
    _compare(fdf)
