"""Shared data layer for the Runs + Strategies browser tabs.

Pulls fast headline stats from runs/index.json for tables/graphs, and lazily loads full
metrics / equity / config / meta only for the handful of runs being inspected. Both
app/views/runs_browser.py (run-vs-run, one strategy) and strategies_browser.py
(strategy-vs-strategy champions) build on these.
"""
import json
import os

import pandas as pd
import streamlit as st

from algokit import runs, metrics  # noqa: F401  (metrics re-exported for views)

# leaderboard metrics: df column -> (label, higher_is_better, percent?)
METRICS = {
    "net": ("Net return", True, True),
    "cagr": ("CAGR", True, True),
    "sharpe": ("Sharpe", True, False),
    "max_dd": ("Max drawdown", True, True),   # higher (closer to 0) is better
    "win": ("Win rate", True, True),
}

# full-metric rows for the side-by-side compares (ordered)
COMPARE_ROWS = ["total_return", "cagr", "sharpe", "sortino", "calmar", "max_drawdown",
                "annual_vol", "profit_factor", "payoff_ratio", "win_rate", "expectancy",
                "exposure", "round_trips", "max_consec_losses", "total_pnl"]


def index_stamp():
    p = os.path.join(runs.RUNS_DIR, "index.json")
    return os.path.getmtime(p) if os.path.exists(p) else 0


@st.cache_data(show_spinner=False)
def table(_stamp):
    """Unified row per run from the index headline (stamp busts cache when runs change)."""
    rows = []
    for m in runs.list_runs():
        h = m.get("headline", {})
        wfo = m.get("kind") == "wfo"
        g = (lambda k: h.get("oos_" + k)) if wfo else (lambda k: h.get(k))
        pct = lambda v: None if v is None else v * 100
        rows.append(dict(
            run=m["name"], strategy=m["strategy"], type=m.get("backtest_type", "Backtest"),
            date=m.get("date", (m.get("timestamp", "") or "")[:10]),
            net=pct(g("total_return")), cagr=pct(g("cagr")), sharpe=g("sharpe"),
            max_dd=pct(g("max_drawdown")), win=pct(g("win_rate")),
            kind=m.get("kind", "backtest"), path=m["path"],
            basis="OOS" if wfo else "full"))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def full_metrics(path, kind):
    d = os.path.join(runs.RUNS_DIR, path)
    if kind == "wfo":
        return json.load(open(os.path.join(d, "result.json"))).get("oos", {})
    return json.load(open(os.path.join(d, "metrics.json")))


@st.cache_data(show_spinner=False)
def config(path):
    return json.load(open(os.path.join(runs.RUNS_DIR, path, "config.json")))


@st.cache_data(show_spinner=False)
def meta(path):
    return json.load(open(os.path.join(runs.RUNS_DIR, path, "meta.json")))


@st.cache_data(show_spinner=False)
def equity_daily(path):
    """Daily %-return-from-start curve for a backtest run (light enough to overlay)."""
    eq = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "equity.parquet"),
                         columns=["time", "equity"]).set_index("time")
    daily = eq["equity"].resample("1D").last().dropna()
    return daily / daily.iloc[0] * 100 - 100


def fmt_val(v):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def flag(color, text):
    bg = {"good": "#16331f", "warn": "#3a3413", "bad": "#3a1717", "off": "#26272b"}[color]
    bd = {"good": "#26a69a", "warn": "#d6b400", "bad": "#ef5350", "off": "#555"}[color]
    st.markdown(
        f"<div style='background:{bg};border-left:4px solid {bd};padding:0.5rem 0.8rem;"
        f"border-radius:4px;font-size:0.9rem'>{text}</div>", unsafe_allow_html=True)


def metrics_matrix(chosen):
    """rows = COMPARE_ROWS, columns = each run; values formatted via metrics.fmt."""
    cols = {}
    for r in chosen:
        m = full_metrics(r["path"], r["kind"])
        col = r["run"] + (" (OOS)" if r["kind"] == "wfo" else "")
        cols[col] = {k: metrics.fmt(k, m.get(k)) for k in COMPARE_ROWS}
    matrix = pd.DataFrame(cols)
    matrix.insert(0, "what it means", [metrics.EXPLAIN.get(k, "") for k in COMPARE_ROWS])
    matrix.index = list(COMPARE_ROWS)
    return matrix


def equity_overlay(chosen):
    """Overlay daily %-return curves for the backtest runs among `chosen`."""
    curves = {}
    for r in chosen:
        if r["kind"] != "wfo":
            try:
                curves[r["run"]] = equity_daily(r["path"])
            except Exception:
                pass
    if curves:
        st.markdown("**Equity curves** — % return from start (daily)")
        st.line_chart(pd.DataFrame(curves))
    else:
        st.caption("No backtest runs selected to overlay (WFO runs store only stitched "
                   "OOS metrics, no curve).")
