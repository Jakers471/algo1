"""Walk-Forward Optimization results — the honest, re-tuned-per-fold view.

Shows: the stitched out-of-sample result (params re-selected on each train window, traded
on the next unseen one) next to the single best-on-full-history config (the overfit
yardstick); the per-fold picks; and how stable each swept parameter was.
"""
import pandas as pd
import streamlit as st

from algokit import metrics

_ROWS = ["total_return", "cagr", "sharpe", "max_drawdown", "exposure",
         "round_trips", "win_rate", "profit_factor"]


def _flag(color, text):
    bg = {"good": "#16331f", "warn": "#3a3413", "bad": "#3a1717", "off": "#26272b"}[color]
    bd = {"good": "#26a69a", "warn": "#d6b400", "bad": "#ef5350", "off": "#555"}[color]
    st.markdown(
        f"<div style='background:{bg};border-left:4px solid {bd};padding:0.5rem 0.8rem;"
        f"border-radius:4px;font-size:0.9rem'>{text}</div>", unsafe_allow_html=True)


def render(res):
    oos, full = res["oos"], res["full_best"]
    win = "Anchored" if res["anchored"] else "Rolling"
    saved = f" &nbsp;|&nbsp; <code>{res['saved_as']}</code>" if res.get("saved_as") else ""
    st.markdown(
        f"<div style='font-size:0.9rem'><b>Walk-Forward Optimization</b> ({win}){saved} &nbsp;|&nbsp; "
        f"optimize on <code>{res['objective']}</code> &nbsp;|&nbsp; "
        f"train {res['train_days']}d / test {res['test_days']}d &nbsp;|&nbsp; "
        f"{res['n_windows']} windows &nbsp;|&nbsp; {res['n_configs']} configs"
        + (f" &nbsp;|&nbsp; range {res['date_range'][0]} -> {res['date_range'][1]}"
           if res.get("date_range") else "")
        + f" &nbsp;|&nbsp; OOS {res['oos_span'][0]} -> {res['oos_span'][1]}</div>",
        unsafe_allow_html=True)
    st.divider()

    # ---- headline: honest OOS vs overfit best-on-full ----
    st.subheader("Walk-forward (honest) vs best-on-full-history (overfit)")
    rows = [(k, metrics.EXPLAIN.get(k, ""), metrics.fmt(k, oos.get(k)),
             metrics.fmt(k, full["metrics"].get(k))) for k in _ROWS]
    st.dataframe(pd.DataFrame(rows, columns=["metric", "what it means",
                                             "walk-forward OOS", "best-on-full"]),
                 hide_index=True, width="stretch",
                 column_config={
                     "metric": st.column_config.TextColumn(width="small"),
                     "what it means": st.column_config.TextColumn(width="large"),
                     "walk-forward OOS": st.column_config.TextColumn(width="small"),
                     "best-on-full": st.column_config.TextColumn(width="small"),
                 })
    oos_r, full_r = oos.get("total_return", 0), full["metrics"].get("total_return", 0)
    gap = full_r - oos_r
    _flag("bad" if oos_r <= 0 else "warn" if gap > 0.10 else "good",
          f"<b>Read:</b> best-on-full shows {full_r*100:+.0f}% but the honest walk-forward "
          f"OOS is {oos_r*100:+.0f}% — a {gap*100:.0f}-pt overfit gap. "
          + ("The OOS result is negative: re-tuning didn't rescue it."
             if oos_r <= 0 else
             "The walk-forward number is what you could realistically expect."))
    st.caption(f"Best-on-full config: `{full['params']}` — the single config that looked "
               "best over the WHOLE history (uses future info; shown only as a yardstick).")

    st.divider()

    # ---- per-fold picks ----
    st.subheader("Per-fold: trained → picked → tested out-of-sample")
    frows = [{
        "fold": s["fold"],
        "train ≤": s["train_to"],
        "picked params": ", ".join(f"{k}={v}" for k, v in s["params"].items()),
        f"train {res['objective']}": f"{s['train_score']:.2f}",
        "test window": f"{s['test_from']} → {s['test_to']}",
        "test net": metrics.fmt("total_return", s["test"].get("total_return")),
        "test sharpe": metrics.fmt("sharpe", s["test"].get("sharpe")),
        "test win": metrics.fmt("win_rate", s["test"].get("win_rate")),
    } for s in res["steps"]]
    st.dataframe(pd.DataFrame(frows), hide_index=True, width="stretch")

    # ---- parameter stability ----
    st.subheader("Parameter stability")
    st.caption("How often each swept value was re-chosen across folds. A param that jumps "
               "around fold-to-fold has no stable optimum — a red flag.")
    cols = st.columns(max(1, len(res["stability"])))
    for col, (p, counts) in zip(cols, res["stability"].items()):
        with col:
            st.markdown(f"**{p}**")
            srows = [{"value": k, "times picked": v}
                     for k, v in sorted(counts.items(), key=lambda x: -x[1])]
            st.dataframe(pd.DataFrame(srows), hide_index=True, width="stretch")
