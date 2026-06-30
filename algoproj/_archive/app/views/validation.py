"""Validation view — the out-of-sample / walk-forward / significance honesty checks.

Lays out whether an edge SURVIVES on data it was never fitted on. The IS/OOS split is
EDITABLE and recomputed live from the saved run's arrays (drag the fraction / pick a date);
the walk-forward folds, significance and benchmark blocks are read from the saved
`analysis.json`. True walk-forward OPTIMIZATION (re-tuning per window) lives in the sidebar
(Backtest type -> Walk-Forward Optimization).
"""
import json
import os

import pandas as pd
import streamlit as st

from algokit import metrics, runs, validation

# metric rows shown for the in/out-sample and walk-forward blocks, in order
_ROWS = ["total_return", "cagr", "sharpe", "max_drawdown", "exposure",
         "round_trips", "win_rate", "expectancy", "profit_factor"]


def _load_analysis(R):
    p = os.path.join(R["dir"], "analysis.json")
    return json.load(open(p)) if os.path.exists(p) else None


@st.cache_data(show_spinner=False)
def _prep(run_name):
    """Per-bar arrays + bar-indexed trades for live IS/OOS recompute (cached per run)."""
    R = runs.load_run(run_name)
    eq, tr = R["equity"], R["trades"]
    idx = pd.DatetimeIndex(eq["time"])
    rets = eq["ret"].to_numpy(float)
    in_market = eq["in_market"].to_numpy()
    ent_i = idx.searchsorted(pd.DatetimeIndex(tr["entry"]))
    ext_i = idx.searchsorted(pd.DatetimeIndex(tr["exit"]))
    trades = [dict(entry_i=int(ei), exit_i=int(xi), ret=float(r), pnl=float(p))
              for ei, xi, r, p in zip(ent_i, ext_i, tr["ret"], tr["pnl"])]
    days = (idx[-1] - idx[0]).days or 1
    return rets, in_market, idx, len(rets) / (days / 365.25), trades


def _verdict(is_blk, oos_blk):
    is_sh, oos_sh = is_blk.get("sharpe"), oos_blk.get("sharpe")
    if is_sh is None or oos_sh is None:
        return ("off", "Not enough data to judge.")
    if oos_sh < 0:
        return ("bad", "Edge DIES out-of-sample — in-sample Sharpe is positive but OOS is "
                       "negative. Classic overfit signature.")
    if oos_sh < is_sh * 0.5:
        return ("warn", "Edge weakens sharply out-of-sample (OOS Sharpe < half of in-sample). "
                        "Treat the headline with suspicion.")
    return ("good", "Edge holds up reasonably out-of-sample — OOS Sharpe is in the same "
                    "ballpark as in-sample.")


def _flag(color, text):
    bg = {"good": "#16331f", "warn": "#3a3413", "bad": "#3a1717", "off": "#26272b"}[color]
    bd = {"good": "#26a69a", "warn": "#d6b400", "bad": "#ef5350", "off": "#555"}[color]
    st.markdown(
        f"<div style='background:{bg};border-left:4px solid {bd};padding:0.5rem 0.8rem;"
        f"border-radius:4px;font-size:0.9rem'>{text}</div>", unsafe_allow_html=True)


def render(R):
    a = _load_analysis(R)
    if a is None:
        st.info("This run has no `analysis.json` (saved before validation was added). "
                "Re-run the backtest to generate it.")
        return

    # ---- 1. In-sample vs Out-of-sample (editable split, recomputed live) ----
    run_name = R["meta"]["name"]
    rets, in_market, idx, ppy, trades = _prep(run_name)
    d0, d1 = idx[0].date(), idx[-1].date()
    st.subheader("In-sample vs Out-of-sample")
    c1, c2, _ = st.columns([1, 1.4, 2])
    mode = c1.radio("Split by", ["Fraction", "Date"], horizontal=True,
                    key=f"vs_mode_{run_name}")
    if mode == "Fraction":
        split = c2.slider("In-sample fraction", 0.50, 0.95, 0.70, 0.05,
                          key=f"vs_frac_{run_name}")
    else:
        split = c2.date_input("Train up to (exclusive)", value=idx[int(len(idx) * 0.70)].date(),
                              min_value=d0, max_value=d1, key=f"vs_date_{run_name}")
    ios = validation.in_out_sample(rets, trades, in_market, idx, ppy, split=split)
    is_blk, oos_blk = ios["in_sample"], ios["out_of_sample"]
    in_pct = ios["split_bar"] / len(idx) * 100
    st.caption(f"Train on the first **{in_pct:.0f}%** (in-sample), test on the unseen last "
               f"**{100 - in_pct:.0f}%**. Split at **{ios['split_time'][:16]}**. Params were "
               "chosen on in-sample, so out-of-sample is the honest number. Drag to re-split.")
    rows = [(k, metrics.EXPLAIN.get(k, ""), metrics.fmt(k, is_blk.get(k)),
             metrics.fmt(k, oos_blk.get(k))) for k in _ROWS]
    st.dataframe(pd.DataFrame(rows, columns=["metric", "what it means", "in-sample",
                                             "out-of-sample"]),
                 hide_index=True, width="stretch",
                 column_config={
                     "metric": st.column_config.TextColumn(width="small"),
                     "what it means": st.column_config.TextColumn(width="large"),
                     "in-sample": st.column_config.TextColumn(width="small"),
                     "out-of-sample": st.column_config.TextColumn(width="small"),
                 })
    color, msg = _verdict(is_blk, oos_blk)
    _flag(color, "<b>Read:</b> " + msg)

    st.divider()

    # ---- 2. Walk-forward folds ----
    wf = a.get("walk_forward", [])
    st.subheader("Walk-forward (sequential folds)")
    st.caption("History split into equal, non-overlapping time windows, fixed config. A real "
               "edge looks similar fold to fold; an edge in only one fold is noise. "
               "(To RE-OPTIMIZE per fold, use Backtest type -> Walk-Forward Optimization.)")
    if wf:
        wrows = [{
            "fold": int(f.get("fold", 0)),
            "from": str(f.get("from", ""))[:10], "to": str(f.get("to", ""))[:10],
            "net": metrics.fmt("total_return", f.get("total_return")),
            "sharpe": metrics.fmt("sharpe", f.get("sharpe")),
            "win": metrics.fmt("win_rate", f.get("win_rate")),
            "trips": metrics.fmt("round_trips", f.get("round_trips")),
            "profit_factor": metrics.fmt("profit_factor", f.get("profit_factor")),
        } for f in wf]
        st.dataframe(pd.DataFrame(wrows), hide_index=True, width="stretch")
        pos = sum(1 for f in wf if (f.get("sharpe") or 0) > 0)
        _flag("good" if pos == len(wf) else "warn" if pos >= len(wf) / 2 else "bad",
              f"<b>Read:</b> {pos} of {len(wf)} folds had a positive Sharpe. "
              "Consistency across folds separates a stable edge from a lucky window.")
    else:
        st.write("No walk-forward data.")

    st.divider()

    # ---- 3. Significance + benchmark ----
    sig = a.get("significance", {})
    bench = a.get("benchmark", {})
    st.subheader("Significance & benchmark")
    c1, c2 = st.columns(2)

    with c1:
        tt = sig.get("trade_t", {})
        re = sig.get("random_entry", {})
        p_t, p_re = tt.get("p"), re.get("p")
        st.markdown("**Is the edge real, or luck?**")
        st.dataframe(pd.DataFrame([
            ("Per-trade t-stat", metrics.fmt("_", tt.get("t")),
             "Higher = mean trade further from zero"),
            ("Per-trade p-value", "n/a" if p_t is None else f"{p_t:.3f}",
             "<0.05 = trades beat zero significantly"),
            ("# trades", metrics.fmt("round_trips", tt.get("n")), ""),
            ("Random-entry p", "n/a" if p_re is None else f"{p_re:.3f}",
             "<0.05 = your timing beats random dates"),
            ("Deflated Sharpe", metrics.fmt("_", sig.get("deflated_sharpe")),
             "Sharpe haircut for # configs tried; >0.95 survives"),
            ("Configs tried", metrics.fmt("round_trips", sig.get("n_trials")), ""),
        ], columns=["test", "value", "meaning"]), hide_index=True, width="stretch")
        sig_ok = (p_t is not None and p_t < 0.05) and (p_re is not None and p_re < 0.05)
        _flag("good" if sig_ok else "bad",
              "<b>Read:</b> " + ("Trades beat zero AND your entry timing beats random — "
                                 "the signal is contributing." if sig_ok else
                                 "Not statistically convincing: the edge isn't separable "
                                 "from luck / random timing yet."))

    with c2:
        st.markdown("**Strategy vs buy & hold**")
        h = R["meta"]["headline"]
        cmp_rows = [
            ("Net return", metrics.fmt("total_return", h.get("total_return")),
             metrics.fmt("total_return", bench.get("total_return"))),
            ("CAGR", metrics.fmt("cagr", h.get("cagr")), metrics.fmt("cagr", bench.get("cagr"))),
            ("Sharpe", metrics.fmt("_", h.get("sharpe")), metrics.fmt("_", bench.get("sharpe"))),
            ("Max drawdown", metrics.fmt("max_drawdown", h.get("max_drawdown")),
             metrics.fmt("max_drawdown", bench.get("max_drawdown"))),
        ]
        st.dataframe(pd.DataFrame(cmp_rows, columns=["metric", "strategy", "buy & hold"]),
                     hide_index=True, width="stretch")
        s_ret, b_ret = h.get("total_return"), bench.get("total_return")
        if s_ret is not None and b_ret is not None:
            _flag("good" if s_ret > b_ret else "bad",
                  "<b>Read:</b> " + ("Strategy beats buy & hold on net return."
                                     if s_ret > b_ret else
                                     "Buy & hold still wins on net return — the strategy isn't "
                                     "earning its complexity yet."))
