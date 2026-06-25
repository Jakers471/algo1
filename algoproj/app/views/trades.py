"""Trades view — the trade-by-trade grid (like NT's Trades tab)."""
import streamlit as st

# hover help for each column (shown as an info tooltip on the header)
_HELP = {
    "#": "Trade number, in chronological order.",
    "entry": "Timestamp the position was opened (UTC bar time).",
    "exit": "Timestamp the position was closed.",
    "entry_px": "Entry fill price, in index points.",
    "exit_px": "Exit fill price, in index points.",
    "ret_%": "Gross price return of the trade, in percent (before $ sizing).",
    "result": "WIN if the trade made money, otherwise LOSS.",
    "reason": "Why the trade exited (signal exit vs protective stop).",
    "hold_bars": "How many bars the position was held (15m bars).",
    "hour_et": "Hour of day in US/Eastern the trade was entered (0-23).",
    "dow": "Day of week entered: 0=Mon, 1=Tue, ... 4=Fri.",
    "bull15": "15m bull regime score at entry (0-100; higher = more bullish).",
    "consol15": "15m consolidation score at entry (0-100; higher = more coiled).",
    "bull1d": "Daily (HTF) bull regime score at entry (0-100; the bias gate).",
}


def render(R):
    tr = R["trades"].copy()
    tr.insert(0, "#", range(1, len(tr) + 1))
    tr["ret_%"] = (tr["ret"] * 100).round(3)
    tr["result"] = tr["ret"].apply(lambda v: "WIN" if v > 0 else "LOSS")
    cols = ["#", "entry", "exit", "entry_px", "exit_px", "ret_%", "result",
            "reason", "hold_bars", "hour_et", "dow", "bull15", "consol15", "bull1d"]
    disp = tr[cols].copy()
    num = disp.select_dtypes("number").columns
    disp[num] = disp[num].round(2)

    st.subheader(f"Trades ({len(tr)})")
    st.caption("Hover any column header for what it means.")
    sty = disp.style.map(
        lambda v: f"color:{'#26a69a' if v > 0 else '#ef5350'}", subset=["ret_%"])
    st.dataframe(sty, width="stretch", hide_index=True, height=800,
                 column_config={c: st.column_config.Column(help=_HELP[c]) for c in cols})
