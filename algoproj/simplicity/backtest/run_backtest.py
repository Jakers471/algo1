"""
run_backtest — the first REAL R measurement. Simulate the target_ladder trades honestly (F24/F25).

Per session (base coil, from base_profile): rest breakout-STOP orders on BOTH coil edges (OCO). When
price breaks a side, ENTER at the CLOSE of that bar (honest fill F1, + slippage). Stop = the other coil
edge (1R). Take-profit = the first target_ladder rung with R:R >= target_r. If stop & target hit in the
same bar, assume STOP (pessimistic). Time-stop after max_hold_bars. Costs = commission both sides +
entry/stop slippage. UNCONDITIONAL -- no setup_arm gating yet; this is the base-rate R distribution the
gates must later beat (add LIFT). No look-ahead: management starts the bar AFTER entry; fills are close/level.

Records per trade (incl. MAE/MFE/ETD excursion + bars). All rules from strategy_config (ENTRY/EXIT).
The DETAILED, machine-readable breakdown + its clean HTML view are built by research/runs (make_report),
not here — this stays a lean simulator that emits trades + logs the ledger scorecard.

Run:  python backtest/run_backtest.py   ->  trades.csv/json + console stats + ledger row
      + a full per-run breakdown (analysis.json + report.html) under research/runs/reports/<run_id>/
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
        # excursion over the held bars (MAE adverse / MFE favorable / ETD give-back), as fraction of entry
        seg_hi = float(np.max(h[ei:exit_i + 1])); seg_lo = float(np.min(l[ei:exit_i + 1]))
        if edir == "up":
            mfe = (seg_hi - entry) / entry; mae = (entry - seg_lo) / entry
        else:
            mfe = (entry - seg_lo) / entry; mae = (seg_hi - entry) / entry
        fin = (exit_px - entry) / entry if edir == "up" else (entry - exit_px) / entry
        etd = max(0.0, mfe - fin)
        trades.append({"sid": sid, "session": b["session"], "dir": edir, "entry": round(entry, 2),
                       "exit": round(exit_px, 2), "risk_pts": round(risk, 1), "net_pts": round(net, 2),
                       "R": round(net / risk, 3), "outcome": outcome, "t_exit": int(t[exit_i]),
                       # --- geometry for the chart trade-replay (source of truth = this sim) ---
                       "stop": round(stop, 2), "target": round(tgt, 2), "coil_hi": round(H_, 2), "coil_lo": round(L_, 2),
                       "entry_i": int(ei), "exit_i": int(exit_i), "t_entry": int(t[ei]),
                       # --- excursion + duration for the analytics report ---
                       "mae": round(mae, 5), "mfe": round(mfe, 5), "etd": round(etd, 5), "bars": int(exit_i - ei)})

    if not trades:
        print("no trades"); return
    d = pd.DataFrame(trades).sort_values("t_exit").reset_index(drop=True)
    d.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    # full per-trade geometry -> the chart trade-replay reads THIS (single source of truth = the sim)
    trades_by_entry = sorted(trades, key=lambda x: x["t_entry"])
    ctx = {"era_start": cfg.ERA_START_YEAR, "target_r": TRR, "entry_window_bars": EWIN,
           "max_hold_bars": HOLD, "entry_tf": "5m", "point_value": cfg.POINT_VALUE,
           "starting_balance": cfg.STARTING_BALANCE, "risk_pct": cfg.RISK["risk_per_trade_pct"],
           "n_bars": int(n), "start_ts": int(t[0]), "end_ts": int(t[-1]), "bar_seconds": 300,
           "commission_per_side": cfg.COMMISSION_PER_SIDE, "slippage_ticks": cfg.SLIPPAGE_TICKS, "tick": cfg.TICK}
    json.dump({"config": ctx, "trades": trades_by_entry}, open(os.path.join(OUT, "trades.json"), "w"))
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
    rec = runlog.record("backtest",
                  {"target_r": TRR, "entry_window": EWIN, "max_hold": HOLD, "entry": cfg.ENTRY["type"],
                   "stop": cfg.EXIT["stop"], "target": cfg.EXIT["target"], "conditional": "none (base rate)"},
                  {"trades": n_t, "win_pct": round(float(wr), 1), "avg_R": round(float(d["R"].mean()), 3),
                   "total_R": round(float(d["R"].sum()), 1), "total_pnl": round(float(d["pnl"].sum()), 0),
                   "max_dd_R": round(float(dd_r), 1), "target_pct": round(oc.get("target", 0) / n_t * 100, 1)})
    # the DETAILED, machine-readable per-run breakdown + its clean HTML view live under research/runs (not here)
    import make_report
    ctx["run"] = {"run_id": rec["run_id"], "git": rec["git"], "note": rec["note"], "kind": "backtest"}
    make_report.build(trades_by_entry, ctx)


if __name__ == "__main__":
    main()
