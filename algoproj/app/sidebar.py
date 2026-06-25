"""
Config panel — NinjaTrader-style: Backtest type, Strategy chooser, then parameters.

Layout (top to bottom):
  Backtest type   : "Backtest" (full history) or "Walk-Forward Optimization".
  Strategy        : any module in strategies/ shows up automatically.
  Strategy params : the signal knobs. In WFO mode each numeric one can be swept
                    (min;max;increment), like NT's optimization rows.
  Account & exec  : universal cost/sizing params (algokit.params.UNIVERSAL_PARAMS),
                    collapsed — same machinery for any strategy.
  WFO settings    : objective / folds / window, only in Walk-Forward mode.

Returns a single cfg dict the analyzer routes on (see `mode`).
"""
import importlib
import os
import pkgutil

import streamlit as st

import strategies
from algokit import runs, params, optimize

MODES = ["Backtest", "Walk-Forward Optimization", "Anchored Walk-Forward Optimization"]


def _strategy_names():
    return [m.name for m in pkgutil.iter_modules(strategies.__path__) if not m.name.startswith("_")]


@st.cache_data(show_spinner=False)
def _date_range(ltf_tf):
    """First/last available date for a strategy's lower timeframe (for the Optimize range)."""
    from algokit.data import load_tf
    idx = load_tf(ltf_tf).index
    return idx[0].date(), idx[-1].date()


def _single_input(k, v, key):
    """One plain value input appropriate to the param's type. Returns the value."""
    if isinstance(v, bool):
        return st.checkbox(k, value=v, key=key)
    if isinstance(v, int):
        return int(st.number_input(k, value=int(v), step=1, key=key))
    if isinstance(v, float):
        return float(st.number_input(k, value=float(v), format="%.4f", key=key))
    if k == "sizing":
        opts = ["fixed", "risk_pct"]
        return st.selectbox(k, opts, index=opts.index(v) if v in opts else 0, key=key)
    return v  # str/other: passed through unchanged (not editable here)


def _sweep_row(k, v, key):
    """In WFO mode: a numeric param row that can be swept. Returns (value, spec_or_None).

    Compact NinjaTrader-style `min;max;increment` text field (fits the narrow panel).
    """
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return _single_input(k, v, key + "_s"), None
    sweep = st.checkbox(f"sweep **{k}**", value=False, key=key + "_sw")
    if not sweep:
        return _single_input(k, v, key + "_v"), None
    step_default = 1 if isinstance(v, int) else 0.5
    txt = st.text_input(f"{k}  (min;max;incr)", value=f"{v};{v};{step_default}",
                        key=key + "_mmi")
    spec = optimize.parse_minmax(txt)
    if spec is None:
        st.caption(f"`{k}`: use min;max;incr, e.g. 60;80;10")
        return v, None
    return spec[0], spec


def render():
    st.markdown("**Settings**")
    mode = st.selectbox("Backtest type", MODES, index=0)
    wfo_mode = "Walk-Forward Optimization" in mode
    anchored = mode.startswith("Anchored")

    strategy = st.selectbox("Strategy", _strategy_names(), index=0)
    strat = importlib.import_module(f"strategies.{strategy}")
    default = dict(strat.DEFAULT)
    signal, universal = params.split_params(default)

    st.caption(f"**{default.get('symbol','?')}**  |  HTF {default.get('htf_tf','?')}  "
               f"|  LTF {default.get('ltf_tf','?')}  |  full history")

    overrides, specs = {}, {}
    with st.expander("Strategy parameters", expanded=False):
        for k, v in signal.items():
            if isinstance(v, (str, list, tuple)):
                continue  # symbol / timeframes / fan-lists not edited here
            key = f"{strategy}_{k}"
            if wfo_mode:
                val, spec = _sweep_row(k, v, key)
                overrides[k] = val
                if spec is not None:
                    specs[k] = spec
            else:
                overrides[k] = _single_input(k, v, key)

    with st.expander(params.UNIVERSAL_LABEL, expanded=False):
        for k, v in universal.items():
            overrides[k] = _single_input(k, v, f"{strategy}_u_{k}")

    wfo_cfg = {}
    if wfo_mode:
        from algokit import wfo
        dmin, dmax = _date_range(default.get("ltf_tf", "15m"))
        with st.expander("Optimize", expanded=True):
            wfo_cfg["objective"] = st.selectbox("Optimize on", wfo.OBJECTIVES)
            dc1, dc2 = st.columns(2)
            sd = dc1.date_input("Start date", value=dmin, min_value=dmin, max_value=dmax)
            ed = dc2.date_input("End date", value=dmax, min_value=dmin, max_value=dmax)
            total_days = max(1, (ed - sd).days)
            wfo_cfg["start_date"] = str(sd)
            wfo_cfg["end_date"] = str(ed)
            st.caption(f"Selected timeline: {total_days:,} days ({sd} -> {ed})")

            train_days = int(st.number_input(
                "Optimization period (days)", value=min(1095, max(30, total_days // 3)),
                min_value=30, step=30,
                help="Length of each TRAIN window (the in-sample optimization period)."))
            st.caption(f"= {train_days / total_days * 100:.0f}% of the selected timeline")
            test_days = int(st.number_input(
                "Test period (days)", value=min(365, max(7, total_days // 9)),
                min_value=7, step=7,
                help="Length of each out-of-sample TEST window; the window rolls forward "
                     "by this each step."))
            st.caption(f"= {test_days / total_days * 100:.0f}% of the selected timeline")
            wfo_cfg["train_days"] = train_days
            wfo_cfg["test_days"] = test_days
            if total_days <= train_days:
                st.caption("Optimization period is longer than the selected timeline — "
                           "widen the dates or shorten it.")
            else:
                nwin = max(1, (total_days - train_days) // test_days)
                oos_days = nwin * test_days
                st.caption(f"approx {nwin} walk-forward windows (each: "
                           f"{train_days:,}d train -> {test_days}d test)")
                st.caption(f"in-sample warm-up: first {train_days:,}d "
                           f"({train_days / total_days * 100:.0f}%, never tested OOS)")
                st.caption(f"out-of-sample: {nwin} x {test_days}d = ~{oos_days:,}d tested "
                           f"({oos_days / total_days * 100:.0f}% of timeline)")
        wfo_cfg["anchored"] = anchored
        n_cfg = optimize.grid_size(specs) if specs else 0
        if n_cfg == 0:
            st.warning("Enable sweep on at least one parameter to define the grid.")
        else:
            kind = "anchored" if anchored else "rolling"
            st.caption(f"{n_cfg} configs ({kind})  ·  ~{n_cfg * 2.4:.0f}s estimated")

    label = "Run walk-forward" if wfo_mode else "Run backtest"
    disabled = wfo_mode and not specs
    run_clicked = st.button(label, type="primary", width="stretch", disabled=disabled)

    st.divider()
    bt_runs = runs.list_runs("backtest")
    selected_run = None
    if bt_runs:
        labels = {f"{m['strategy']} / {m['name']}": m["path"] for m in bt_runs}
        choice = st.selectbox("Load saved run", list(labels), index=len(labels) - 1)
        selected_run = labels[choice]

    return dict(mode=mode, strategy=strategy, overrides=overrides, specs=specs,
                run_clicked=run_clicked, selected_run=selected_run, **wfo_cfg)
