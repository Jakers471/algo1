"""
Strategy Analyzer — a NinjaTrader-style single-window backtest runner.

Layout: wide views on the LEFT, config panel on the RIGHT (like NT). The config panel's
"Backtest type" selects the mode:
  Backtest                  -> run once, save a numbered run, browse Summary | Trades |
                               Equity | Chart | Validation.
  Walk-Forward Optimization -> sweep params, re-optimize per fold, show the honest
                               out-of-sample result (app/views/wfopt.py).
Reuses the algokit engine + the versioned run registry. Launch:
    python -m streamlit run app/analyzer.py   (or run_analyzer.bat)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/

import streamlit as st

from algokit import runs, wfo
from app import sidebar
from app.views import (summary, trades, equity, chart, validation, wfopt,
                       runs_browser, strategies_browser)

st.set_page_config(page_title="Strategy Analyzer", layout="wide")
st.markdown(
    "<style>.block-container{padding-top:2.4rem;padding-bottom:0.4rem;}"
    ".stProgress > div > div > div > div{background-color:#26a69a;}</style>",
    unsafe_allow_html=True)

VIEWS = {"Summary": summary, "Trades": trades, "Equity": equity, "Chart": chart,
         "Validation": validation}


@st.cache_data(show_spinner=False)
def _load(run_name):
    """Load a run once and cache it — flipping between views won't re-read the data."""
    return runs.load_run(run_name)


@st.cache_data(show_spinner=False)
def _run_arrays(strategy, items):
    """Run one config's full backtest and return its causal arrays (cached per config)."""
    strat = importlib.import_module(f"strategies.{strategy}")
    return wfo.arrays_from_result(strat.run(**dict(items)))


def _render_backtest(cfg):
    """Backtest mode: run-or-load a single run, then the Display switcher over the views."""
    current = None
    if cfg["run_clicked"]:
        strat = importlib.import_module(f"strategies.{cfg['strategy']}")
        prog = st.progress(0.25, text="Running backtest (~3s estimated)...")
        result = strat.run(**cfg["overrides"])
        prog.progress(0.85, text="Saving run...")
        run_dir, meta = runs.save_run(result, cfg["strategy"])
        prog.progress(1.0, text="Done")
        prog.empty()
        current = meta.get("path", meta["name"])
        st.session_state["current"] = current
        st.toast(("Unchanged - reused " if meta.get("unchanged") else "Saved ") + meta["name"])
    else:
        current = cfg["selected_run"] or st.session_state.get("current")

    if not current:
        st.info("No runs yet - set parameters on the right and click **Run backtest**.")
        return
    R = _load(current)
    m = R["meta"]
    diff = m.get("config_diff")
    changed = ""
    if diff and diff.get("changed"):
        changed = " | changed: " + ", ".join(f"{k} {v[0]}->{v[1]}" for k, v in diff["changed"].items())
    st.markdown(
        f"<div style='font-size:0.9rem;line-height:1.3'><b>Strategy Analyzer</b> &nbsp;&nbsp; "
        f"<code>{m['name']}</code> &nbsp;|&nbsp; {m['strategy']} &nbsp;|&nbsp; {m['timestamp']} "
        f"&nbsp;|&nbsp; parent {m['parent']}{changed}</div>", unsafe_allow_html=True)
    view = st.radio("Display", list(VIEWS), horizontal=True, label_visibility="collapsed")
    VIEWS[view].render(R)


def _render_wfo(cfg):
    """Walk-Forward Optimization mode: sweep the grid, re-optimize per fold, show OOS."""
    if cfg["run_clicked"] and cfg["specs"]:
        import time
        from algokit import optimize as _opt
        n_cfg = _opt.grid_size(cfg["specs"])
        prog = st.progress(0.0, text=f"Starting {n_cfg} configs (~{n_cfg * 2.4:.0f}s estimated)...")
        t0 = time.time()

        def cb(i, n, ov):
            el = time.time() - t0
            rem = (el / i) * (n - i) if i else 0
            prog.progress(i / n, text=f"Config {i}/{n}  ·  elapsed {el:.0f}s  ·  "
                                      f"remaining ~{rem:.0f}s")

        strat = importlib.import_module(f"strategies.{cfg['strategy']}")
        base = {**strat.DEFAULT, **cfg["overrides"]}
        run_fn = lambda ov: _run_arrays(cfg["strategy"], tuple(sorted({**cfg["overrides"], **ov}.items())))
        res = wfo.optimize(run_fn, cfg["specs"], objective=cfg["objective"],
                           train_days=cfg["train_days"], test_days=cfg["test_days"],
                           anchored=cfg["anchored"], start_date=cfg.get("start_date"),
                           end_date=cfg.get("end_date"), progress=cb)
        prog.empty()
        settings = {"specs": cfg["specs"], "objective": cfg["objective"],
                    "train_days": cfg["train_days"], "test_days": cfg["test_days"],
                    "anchored": cfg["anchored"], "backtest_type": cfg["mode"],
                    "start_date": cfg.get("start_date"), "end_date": cfg.get("end_date")}
        run_dir, meta = runs.save_wfo(res, cfg["strategy"], base, settings)
        res["saved_as"] = meta["name"]
        st.session_state["wfo_result"] = res
        st.toast("Saved " + meta["name"])

    res = st.session_state.get("wfo_result")
    if res is None:
        st.info("Enable **sweep** on a parameter, then **Run walk-forward**.")
    else:
        wfopt.render(res)


# top-level page nav: Analyzer (run/optimize), Strategies (cross-strategy), Runs (one strategy)
nav = st.radio("nav", ["Analyzer", "Strategies", "Runs"], horizontal=True,
               label_visibility="collapsed")
if nav == "Runs":
    runs_browser.render()
elif nav == "Strategies":
    strategies_browser.render()
else:
    # wide main area on the left, slim config panel on the right
    main_col, cfg_col = st.columns([6.5, 1.4], gap="medium")
    with cfg_col:
        cfg = sidebar.render()
    with main_col:
        if "Walk-Forward Optimization" in cfg["mode"]:
            _render_wfo(cfg)
        else:
            _render_backtest(cfg)
