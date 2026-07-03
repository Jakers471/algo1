"""
run_backtest — the first REAL R measurement. Simulate the target_ladder trades honestly (F24/F25).

Per session (base coil, from base_profile): rest breakout-STOP orders on BOTH coil edges (OCO). When
price breaks a side, ENTER at the CLOSE of that bar (honest fill F1, + slippage). Stop = the other coil
edge (1R). Take-profit = the first target_ladder rung with R:R >= target_r. If stop & target hit in the
same bar, assume STOP (pessimistic). Time-stop after max_hold_bars. Costs = commission both sides +
entry/stop slippage. UNCONDITIONAL -- no setup_arm gating yet; this is the base-rate R distribution the
gates must later beat (add LIFT). No look-ahead: management starts the bar AFTER entry; fills are close/level.

Records per trade; reports total trades, win rate, avg R, total R (expectancy), $ PnL (1 contract), max
drawdown; writes an equity-curve PNG. All rules from strategy_config (ENTRY/EXIT); logged to the ledger.

Run:  python backtest/run_backtest.py   ->  output/equity.png + trades.csv + console stats + ledger row
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.dirname(HERE)
sys.path.insert(0, _SIM)
sys.path.insert(0, os.path.join(_SIM, "research", "setup", "target_ladder"))
sys.path.insert(0, os.path.join(_SIM, "research", "runs"))
import research_config as cfg    # run config: re-exports strategy_config + STARTING_BALANCE / dates
import target_ladder as tl
import runlog

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
RES = os.path.join(_SIM, "research")
SLIP = cfg.SLIPPAGE_TICKS * cfg.TICK
COMM_PTS = 2 * cfg.COMMISSION_PER_SIDE / cfg.POINT_VALUE     # round-trip commission in points
EWIN = cfg.ENTRY["entry_window_bars"]
HOLD = cfg.EXIT["max_hold_bars"]
TRR = cfg.EXIT["target_r"]


def _load_profiles(name, sub):
    return {p["sid"]: p for p in json.load(open(os.path.join(RES, sub, name, "output", name + ".json")))["profiles"]}


def _first_rung(targets):
    for t in targets:
        if t["rr"] >= TRR:
            return t["level"]
    return None


def _report(d, s):
    eq = d["equity"].to_numpy(); cr = d["cumR"].to_numpy(); Rv = d["R"].to_numpy(); n = len(eq)
    peak = np.maximum.accumulate(eq)
    W, H = 1040, 300
    lo = min(eq.min(), cfg.STARTING_BALANCE); hi = max(eq.max(), cfg.STARTING_BALANCE); rng = (hi - lo) or 1
    X = lambda i: (i / (n - 1) * W) if n > 1 else W / 2
    Yq = lambda v: H - (v - lo) / rng * H
    eqp = " ".join(f"{X(i):.1f},{Yq(v):.1f}" for i, v in enumerate(eq))
    pkp = " ".join(f"{X(i):.1f},{Yq(v):.1f}" for i, v in enumerate(peak))
    ddp = eqp + " " + " ".join(f"{X(i):.1f},{Yq(peak[i]):.1f}" for i in range(n - 1, -1, -1))
    ys = Yq(cfg.STARTING_BALANCE); eqcol = "#2ebd85" if eq[-1] >= cfg.STARTING_BALANCE else "#f6465d"
    equity_svg = (f'<svg viewBox="0 0 {W} {H}" class="crv"><polygon points="{ddp}" fill="#f6465d" fill-opacity="0.13"/>'
                  f'<polyline points="{pkp}" fill="none" stroke="#5a6472" stroke-width="1" stroke-dasharray="3 3"/>'
                  f'<line x1="0" y1="{ys:.1f}" x2="{W}" y2="{ys:.1f}" stroke="#8a94a6" stroke-width=".8" stroke-dasharray="2 4"/>'
                  f'<polyline points="{eqp}" fill="none" stroke="{eqcol}" stroke-width="1.7"/></svg>')
    H2 = 120; clo = min(cr.min(), 0); chi = max(cr.max(), 0); crr = (chi - clo) or 1
    Yr = lambda v: H2 - (v - clo) / crr * H2
    crp = " ".join(f"{X(i):.1f},{Yr(v):.1f}" for i, v in enumerate(cr))
    cr_svg = (f'<svg viewBox="0 0 {W} {H2}" class="crv"><line x1="0" y1="{Yr(0):.1f}" x2="{W}" y2="{Yr(0):.1f}" '
              f'stroke="#8a94a6" stroke-width=".8" stroke-dasharray="2 4"/>'
              f'<polyline points="{crp}" fill="none" stroke="#4a9bff" stroke-width="1.4"/></svg>')
    edges = np.arange(-3, 6.01, 0.5); cnt, _ = np.histogram(np.clip(Rv, -2.99, 5.99), bins=edges)
    mx = cnt.max() or 1; HW, HH = 1040, 150; bw = HW / len(cnt); bars = ""
    for i, ct in enumerate(cnt):
        bh = ct / mx * (HH - 16); col = "#2ebd85" if edges[i] >= 0 else "#f6465d"
        bars += (f'<rect x="{i*bw+1:.1f}" y="{HH-16-bh:.1f}" width="{bw-2:.1f}" height="{bh:.1f}" fill="{col}" fill-opacity=".8"/>'
                 f'<text x="{i*bw+bw/2:.1f}" y="{HH-4:.1f}" fill="#8a94a6" font-size="8" text-anchor="middle">{edges[i]:.0f}</text>')
    zx = (3 / 9) * HW
    hist_svg = (f'<svg viewBox="0 0 {HW} {HH}" class="crv">{bars}'
                f'<line x1="{zx:.1f}" y1="0" x2="{zx:.1f}" y2="{HH-16}" stroke="#e6edf3" stroke-width=".8" stroke-dasharray="2 3"/></svg>')
    okc = lambda b: "#2ebd85" if b else "#f6465d"
    tile = lambda lab, val, col="var(--ink)": f'<div class="tile"><div class="tl">{lab}</div><div class="tv" style="color:{col}">{val}</div></div>'
    tiles = (tile("trades", f'{s["n"]:,}') + tile("win rate", f'{s["wr"]:.1f}%')
             + tile("avg R", f'{s["avg_R"]:+.3f}', okc(s["avg_R"] > 0)) + tile("total R", f'{s["tot_R"]:+.1f}', okc(s["tot_R"] > 0))
             + tile("total PnL", f'${s["pnl"]:+,.0f}', okc(s["pnl"] > 0)) + tile("final equity", f'${s["equity"]:,.0f}')
             + tile("max drawdown", f'${s["dd_d"]:,.0f}', "#f6465d") + tile("profit factor", f'{s["pf"]:.2f}', okc(s["pf"] > 1)))
    sess = ""
    for ss in ["asia", "london", "newyork"]:
        z = d[d.session == ss]
        if len(z):
            sess += (f'<div class="br"><span>{ss}</span><b>{len(z)}</b><b>{(z.R>0).mean()*100:.0f}%</b>'
                     f'<b style="color:{okc(z.R.mean()>0)}">{z.R.mean():+.3f}R</b></div>')
    outc = "".join(f'<div class="br"><span>{k}</span><b>{v}</b><b>{v/s["n"]*100:.0f}%</b><b></b></div>' for k, v in s["oc"].items())
    verdict = "POSITIVE" if s["tot_R"] > 0 else "NEGATIVE base rate"
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>backtest — equity</title><style>
:root{{--ink:#e6edf3;--mut:#8a94a6;--bg:#0e1117;--card:#161b22;--bd:#232a33}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:22px}}
h1{{font-size:18px;margin:0 0 2px}}.sub{{color:var(--mut);margin:0 0 16px}}
.badge{{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;border:1px solid;margin-left:8px}}
.tiles{{display:grid;grid-template-columns:repeat(8,1fr);gap:10px;margin-bottom:18px}}
.tile{{background:var(--card);border:1px solid var(--bd);border-radius:9px;padding:10px 12px}}
.tl{{color:var(--mut);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px}}.tv{{font-size:17px;font-weight:650;margin-top:3px;font-variant-numeric:tabular-nums}}
.sec{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;margin-bottom:14px}}
.sh{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px}}
.crv{{display:block;width:100%;height:auto}}
.row{{display:flex;gap:14px}}.row .sec{{flex:1}}
.br{{display:grid;grid-template-columns:1fr auto auto auto;gap:12px;padding:4px 0;border-bottom:1px solid #1c2330}}
.br span{{color:var(--mut)}}.br b{{text-align:right;font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>target_ladder backtest <span class="badge" style="color:{okc(s["tot_R"]>0)};border-color:{okc(s["tot_R"]>0)}">{verdict}</span></h1>
<p class="sub">UNCONDITIONAL — no setup_arm gating (this is the base rate the gates must beat). era ≥ {cfg.ERA_START_YEAR} ·
target ≥ {s["trr"]}R · risk {s["risk_pct"]}%/trade · after commission + slippage · honest fills</p>
<div class="tiles">{tiles}</div>
<div class="sec"><div class="sh">Equity ($) — solid = equity, dashed grey = peak, red = drawdown</div>{equity_svg}</div>
<div class="sec"><div class="sh">Cumulative R</div>{cr_svg}</div>
<div class="sec"><div class="sh">R distribution per trade (−3 … +6, white line = breakeven)</div>{hist_svg}</div>
<div class="row"><div class="sec"><div class="sh">By session — trades · win% · avg R</div>{sess}</div>
  <div class="sec"><div class="sh">By outcome — count · %</div>{outc}</div></div>
</body></html>'''
    open(os.path.join(OUT, "equity.html"), "w", encoding="utf-8").write(html)


def main():
    S = _load_profiles("volume_profile", "structure")
    B = _load_profiles("base_profile", "structure")
    H = _load_profiles("htf_profile", "structure")

    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    yr = df.index.tz_convert(cfg.CLOCK).year
    df = df[yr >= cfg.ERA_START_YEAR]
    t = (df.index.view("int64") // 1_000_000_000).astype("int64")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    n = len(t)

    trades = []
    for b in sorted(B.values(), key=lambda x: x["session_end"]):
        sid = b["sid"]
        lad = tl.ladder({"base": b, "session": S.get(sid), "htf": H.get(sid)})
        if not lad:
            continue
        H_, L_ = b["high"], b["low"]
        if H_ <= L_ or b.get("height_pct", 0) < cfg.ENTRY["min_coil_pct"]:   # skip degenerate / noise coils
            continue
        up_tgt, dn_tgt = _first_rung(lad["up"]["targets"]), _first_rung(lad["down"]["targets"])
        if up_tgt is None and dn_tgt is None:
            continue
        i0 = int(np.searchsorted(t, b["session_end"], "right"))
        if i0 <= 0 or i0 >= n:   # profile's session lies outside the era-filtered bars — not tradeable here
            continue             # (pre-era profiles else map to bar 0 = coil vs a different price regime, ~2500pt fake risk)
        # --- entry phase: first coil breakout within the window (OCO). Stop order fills at the coil edge. ---
        edir = entry = stop = tgt = risk = None
        ei = -1
        for i in range(i0, min(i0 + EWIN, n)):
            up = h[i] >= H_ and up_tgt is not None
            dn = l[i] <= L_ and dn_tgt is not None
            if up and dn:
                edir = "up" if c[i] >= (H_ + L_) / 2 else "down"
            elif up:
                edir = "up"
            elif dn:
                edir = "down"
            if edir:
                if edir == "up":
                    entry = (o[i] if o[i] > H_ else H_) + SLIP     # fill at the level, or the open on a gap
                    stop, tgt = L_, up_tgt; risk = entry - stop
                else:
                    entry = (o[i] if o[i] < L_ else L_) - SLIP
                    stop, tgt = H_, dn_tgt; risk = stop - entry
                ei = i
                break
        if entry is None or risk <= 0:
            continue
        # --- manage from the NEXT bar (no look-ahead within the entry bar) ---
        exit_px = None; outcome = None; exit_i = None
        for i in range(ei + 1, min(ei + HOLD, n)):
            if edir == "up":
                if l[i] <= stop:
                    exit_px, outcome, exit_i = stop - SLIP, "stop", i; break
                if h[i] >= tgt:
                    exit_px, outcome, exit_i = tgt, "target", i; break
            else:
                if h[i] >= stop:
                    exit_px, outcome, exit_i = stop + SLIP, "stop", i; break
                if l[i] <= tgt:
                    exit_px, outcome, exit_i = tgt, "target", i; break
        if exit_px is None:
            exit_i = min(ei + HOLD, n) - 1
            exit_px, outcome = c[exit_i], "time"
        gross = (exit_px - entry) if edir == "up" else (entry - exit_px)
        net = gross - COMM_PTS
        trades.append({"sid": sid, "session": b["session"], "dir": edir, "entry": round(entry, 2),
                       "exit": round(exit_px, 2), "risk_pts": round(risk, 1), "net_pts": round(net, 2),
                       "R": round(net / risk, 3), "outcome": outcome, "t_exit": int(t[exit_i]),
                       # --- geometry for the chart trade-replay (source of truth = this sim) ---
                       "stop": round(stop, 2), "target": round(tgt, 2), "coil_hi": round(H_, 2), "coil_lo": round(L_, 2),
                       "entry_i": int(ei), "exit_i": int(exit_i), "t_entry": int(t[ei])})

    if not trades:
        print("no trades"); return
    d = pd.DataFrame(trades).sort_values("t_exit").reset_index(drop=True)
    d.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    # full per-trade geometry -> the chart trade-replay reads THIS (single source of truth = the sim)
    trades_by_entry = sorted(trades, key=lambda x: x["t_entry"])
    json.dump({"config": {"era_start": cfg.ERA_START_YEAR, "target_r": TRR, "entry_window_bars": EWIN,
                          "max_hold_bars": HOLD, "entry_tf": "5m", "point_value": cfg.POINT_VALUE,
                          "starting_balance": cfg.STARTING_BALANCE, "risk_pct": cfg.RISK["risk_per_trade_pct"]},
               "trades": trades_by_entry},
              open(os.path.join(OUT, "trades.json"), "w"))
    d["cumR"] = d["R"].cumsum()
    risk_d = cfg.STARTING_BALANCE * cfg.RISK["risk_per_trade_pct"] / 100.0   # $ risked per trade (fixed fractional)
    d["pnl"] = d["R"] * risk_d                          # normalized $: each trade risks the same $ (not 1 contract)
    d["equity"] = cfg.STARTING_BALANCE + d["pnl"].cumsum()
    dd_r = (d["cumR"].cummax() - d["cumR"]).max()
    dd_d = (d["equity"].cummax() - d["equity"]).max()
    n_t, wr = len(d), (d["R"] > 0).mean() * 100
    oc = d["outcome"].value_counts().to_dict()

    print(f"BACKTEST -- target_ladder trades, UNCONDITIONAL (no gating), era>={cfg.ERA_START_YEAR}, "
          f"target>={TRR}R, 1 contract")
    print(f"  trades      {n_t:,}   ({oc.get('target',0)} target / {oc.get('stop',0)} stop / {oc.get('time',0)} time)")
    print(f"  win rate    {wr:.1f}%")
    print(f"  avg R       {d['R'].mean():+.3f}   (median {d['R'].median():+.2f})")
    print(f"  total R     {d['R'].sum():+.1f}")
    wins, losses = d[d["pnl"] > 0]["pnl"].sum(), d[d["pnl"] < 0]["pnl"].sum()
    pf = wins / abs(losses) if losses else float("inf")
    print(f"  total PnL   ${d['pnl'].sum():+,.0f}   (risk {cfg.RISK['risk_per_trade_pct']}%/trade)  final equity ${d['equity'].iloc[-1]:,.0f}")
    print(f"  profit fac  {pf:.2f}   max DD {dd_r:.1f}R / ${dd_d:,.0f}")
    print(f"  by session  " + " ".join(f"{s}={d[d.session==s]['R'].mean():+.3f}R(n{len(d[d.session==s])})"
                                        for s in ["asia", "london", "newyork"] if len(d[d.session == s])))
    _report(d, {"n": n_t, "wr": wr, "avg_R": d["R"].mean(), "tot_R": d["R"].sum(),
                "pnl": d["pnl"].sum(), "equity": d["equity"].iloc[-1], "dd_r": dd_r, "dd_d": dd_d,
                "pf": pf, "oc": oc, "risk_pct": cfg.RISK["risk_per_trade_pct"], "trr": TRR})
    print("wrote", os.path.join(OUT, "equity.html"), "+ trades.csv")

    runlog.record("backtest",
                  {"target_r": TRR, "entry_window": EWIN, "max_hold": HOLD, "entry": cfg.ENTRY["type"],
                   "stop": cfg.EXIT["stop"], "target": cfg.EXIT["target"], "conditional": "none (base rate)"},
                  {"trades": n_t, "win_pct": round(float(wr), 1), "avg_R": round(float(d["R"].mean()), 3),
                   "total_R": round(float(d["R"].sum()), 1), "total_pnl": round(float(d["pnl"].sum()), 0),
                   "max_dd_R": round(float(dd_r), 1), "target_pct": round(oc.get("target", 0) / n_t * 100, 1)})


if __name__ == "__main__":
    main()
