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
sys.path.insert(0, os.path.join(_SIM, "research", "setup", "setup_arm"))
sys.path.insert(0, os.path.join(_SIM, "research", "runs"))
# default: run off research_config (the experimental truth). `--real` runs off strategy_config (the graduated one).
if "--real" in sys.argv:
    import strategy_config as cfg
else:
    import research_config as cfg    # re-exports strategy_config + STARTING_BALANCE / dates
import target_ladder as tl
import setup_arm
import runlog

# setup_arm gating: env SIMP_ARM forces it (1=on, 0=off) else cfg.SETUP["on"]. OFF = unconditional base rate.
_arm_env = os.environ.get("SIMP_ARM")
ARM_ON = (_arm_env == "1") if _arm_env is not None else bool(getattr(cfg, "SETUP", {}).get("on"))
ARM_GATES = getattr(cfg, "SETUP", {}).get("gates", [])

STARTING_BALANCE = getattr(cfg, "STARTING_BALANCE", 100_000)   # research-only knob; default when running --real

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
RES = os.path.join(_SIM, "research")
SLIP = cfg.SLIPPAGE_TICKS * cfg.TICK
COMM_PTS = 2 * cfg.COMMISSION_PER_SIDE / cfg.POINT_VALUE     # round-trip commission in points
EWIN = cfg.ENTRY["entry_window_bars"]
HOLD = cfg.EXIT["max_hold_bars"]
TRR = cfg.EXIT["target_r"]
METHOD = cfg.EXIT.get("target", "ladder_rung")          # TP engine: "fixed_rr" | "ladder_rung" | "trailing"
TRAIL_ARM = cfg.EXIT.get("trail_arm_r", 1.0)            # trailing: arm once +arm_r in profit
TRAIL_GAP = cfg.EXIT.get("trail_gap_r", 1.5)            # trailing: hold stop this many R behind best


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
    _data_first, _data_last = str(df.index[0])[:10], str(df.index[-1])[:10]   # raw range, for a clear empty-window message
    # date window (env override from the chart > research_config knob). An explicit START OVERRIDES the era
    # floor, so you can run FULL history back to the data start; with no explicit start, ERA_START_YEAR is the floor.
    bstart = os.environ.get("SIMP_BT_START") or getattr(cfg, "BACKTEST_START", None)
    bend = os.environ.get("SIMP_BT_END") or getattr(cfg, "BACKTEST_END", None)
    if bstart:
        df = df[df.index >= pd.Timestamp(bstart, tz=cfg.CLOCK)]
    else:
        yr = df.index.tz_convert(cfg.CLOCK).year
        df = df[yr >= cfg.ERA_START_YEAR]
    if bend:
        df = df[df.index <= pd.Timestamp(bend, tz=cfg.CLOCK)]
    t = (df.index.view("int64") // 1_000_000_000).astype("int64")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    n = len(t)

    trades = []
    n_disarmed = 0
    for b in sorted(B.values(), key=lambda x: x["session_end"]):
        sid = b["sid"]
        htf_scale = H.get(sid) if cfg.HTF.get("on") else None   # HTF toggle is REAL: off -> not fed to the ladder
        lad = tl.ladder({"base": b, "session": S.get(sid), "htf": htf_scale})
        H_, L_ = b["high"], b["low"]
        if H_ <= L_ or b.get("height_pct", 0) < cfg.ENTRY["min_coil_pct"]:   # skip degenerate / noise coils
            continue
        # target availability + per-side tradeability depend on the TP METHOD
        if METHOD == "ladder_rung":
            if not lad:
                continue
            up_tgt, dn_tgt = _first_rung(lad["up"]["targets"]), _first_rung(lad["down"]["targets"])
            if up_tgt is None and dn_tgt is None:
                continue
            up_ok, dn_ok = up_tgt is not None, dn_tgt is not None
        else:                                    # fixed_rr / trailing: target derived at fill; both sides tradeable
            up_tgt = dn_tgt = None
            up_ok = dn_ok = True
        i0 = int(np.searchsorted(t, b["session_end"], "right"))
        if i0 <= 0 or i0 >= n:   # profile's session lies outside the era-filtered bars — not tradeable here
            continue             # (pre-era profiles else map to bar 0 = coil vs a different price regime, ~2500pt fake risk)
        # --- setup_arm gate: ARM this coil only if the confluence stack passes (else the base rate) ---
        # compute the gates ALWAYS (so the trade-replay state panel can show them); gate only when ARM_ON.
        arm_pass, arm_info = setup_arm.decide(b, S.get(sid), H.get(sid), cfg=cfg)
        if ARM_ON and not arm_pass:
            n_disarmed += 1
            continue
        # --- entry phase: first coil breakout within the window (OCO). Stop order fills at the coil edge. ---
        edir = entry = stop = tgt = risk = None
        ei = -1
        for i in range(i0, min(i0 + EWIN, n)):
            up = h[i] >= H_ and up_ok
            dn = l[i] <= L_ and dn_ok
            if up and dn:
                edir = "up" if c[i] >= (H_ + L_) / 2 else "down"
            elif up:
                edir = "up"
            elif dn:
                edir = "down"
            if edir:
                if edir == "up":
                    entry = (o[i] if o[i] > H_ else H_) + SLIP     # fill at the level, or the open on a gap
                    stop = L_; risk = entry - stop
                else:
                    entry = (o[i] if o[i] < L_ else L_) - SLIP
                    stop = H_; risk = stop - entry
                if risk > 0:                                       # TAKE-PROFIT target per the configured method
                    if METHOD == "fixed_rr":
                        tgt = entry + TRR * risk if edir == "up" else entry - TRR * risk
                    elif METHOD == "ladder_rung":
                        tgt = up_tgt if edir == "up" else dn_tgt
                    else:                                          # trailing: no fixed TP
                        tgt = None
                ei = i
                break
        if entry is None or risk <= 0:
            continue
        # --- manage from the NEXT bar (no look-ahead within the entry bar) ---
        exit_px = None; outcome = None; exit_i = None
        path = []                                                  # per-bar LIVE stop (the trailing ratchet) -> the replay renders it
        if METHOD == "trailing":
            best = entry; trail = stop; armed = False
            for i in range(ei + 1, min(ei + HOLD, n)):
                path.append([int(t[i]), round(trail, 2), 1 if armed else 0])   # [t, live stop, armed] coming into this bar
                if edir == "up":
                    if l[i] <= trail:      # trailed out: a WIN if the stop was ratcheted into profit, else a base-stop loss
                        exit_px, outcome, exit_i = trail - SLIP, ("target" if armed else "stop"), i; break
                    best = max(best, h[i])
                    if not armed and (best - entry) >= TRAIL_ARM * risk:
                        armed = True
                    if armed:
                        trail = max(trail, best - TRAIL_GAP * risk)
                else:
                    if h[i] >= trail:
                        exit_px, outcome, exit_i = trail + SLIP, ("target" if armed else "stop"), i; break
                    best = min(best, l[i])
                    if not armed and (entry - best) >= TRAIL_ARM * risk:
                        armed = True
                    if armed:
                        trail = min(trail, best + TRAIL_GAP * risk)
        else:                                                      # fixed_rr / ladder_rung: fixed target vs stop
            for i in range(ei + 1, min(ei + HOLD, n)):
                path.append([int(t[i]), round(stop, 2), 1])        # stop is constant for fixed methods
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
                       "stop": round(stop, 2), "target": round(tgt if tgt is not None else exit_px, 2), "coil_hi": round(H_, 2), "coil_lo": round(L_, 2),
                       "entry_i": int(ei), "exit_i": int(exit_i), "t_entry": int(t[ei]),
                       # --- LIVE replay: per-bar trailing-stop path + the setup_arm gate states that armed it ---
                       "method": METHOD, "path": path,
                       "arm": (arm_info.get("gates") if arm_info else None),
                       "arm_shape": (arm_info.get("shape_score") if arm_info else None),
                       "arm_rr": (arm_info.get("rr") if arm_info else None),
                       "armed": bool(ARM_ON),
                       # --- excursion + duration for the analytics report ---
                       "mae": round(mae, 5), "mfe": round(mfe, 5), "etd": round(etd, 5), "bars": int(exit_i - ei)})

    if not trades:
        print(f"no trades -- window {bstart or 'era-start'}..{bend or 'latest'} matched {n} bars "
              f"(data available {_data_first}..{_data_last}). Pick a window inside the data range."); return
    d = pd.DataFrame(trades).sort_values("t_exit").reset_index(drop=True)
    d.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    # full per-trade geometry -> the chart trade-replay reads THIS (single source of truth = the sim)
    trades_by_entry = sorted(trades, key=lambda x: x["t_entry"])
    ctx = {"era_start": cfg.ERA_START_YEAR, "target_r": TRR, "entry_window_bars": EWIN,
           "max_hold_bars": HOLD, "entry_tf": "5m", "point_value": cfg.POINT_VALUE,
           "starting_balance": STARTING_BALANCE, "risk_pct": cfg.RISK["risk_per_trade_pct"],
           "n_bars": int(n), "start_ts": int(t[0]), "end_ts": int(t[-1]), "bar_seconds": 300,
           "commission_per_side": cfg.COMMISSION_PER_SIDE, "slippage_ticks": cfg.SLIPPAGE_TICKS, "tick": cfg.TICK,
           # --- take-profit / gating config, so the trade-replay state panel reflects the actual strategy ---
           "tp_method": METHOD, "trail_arm_r": TRAIL_ARM, "trail_gap_r": TRAIL_GAP,
           "setup_on": ARM_ON, "arm_gates": ARM_GATES,
           # gate params so the replay can RECOMPUTE the module cards live (bars-so-far), matching the config
           "gates": {"SHAPE": cfg.SHAPE, "ZONE": cfg.ZONE, "BASE": cfg.BASE, "LADDER": cfg.LADDER}}
    json.dump({"config": ctx, "trades": trades_by_entry}, open(os.path.join(OUT, "trades.json"), "w"))
    d["cumR"] = d["R"].cumsum()
    risk_d = STARTING_BALANCE * cfg.RISK["risk_per_trade_pct"] / 100.0   # $ risked per trade (fixed fractional)
    d["pnl"] = d["R"] * risk_d                          # normalized $: each trade risks the same $ (not 1 contract)
    d["equity"] = STARTING_BALANCE + d["pnl"].cumsum()
    dd_r = (d["cumR"].cummax() - d["cumR"]).max()
    dd_d = (d["equity"].cummax() - d["equity"]).max()
    n_t, wr = len(d), (d["R"] > 0).mean() * 100
    oc = d["outcome"].value_counts().to_dict()

    _cond = ("setup_arm ON [" + "+".join(ARM_GATES) + f"] — disarmed {n_disarmed} coils") if ARM_ON \
        else "UNCONDITIONAL (no gating — base rate)"
    _tp = {"fixed_rr": f"TP fixed 1:{TRR}", "ladder_rung": f"TP ladder>={TRR}R",
           "trailing": f"TP trail arm{TRAIL_ARM}/gap{TRAIL_GAP}"}.get(METHOD, METHOD)
    _htf = "htf-on" if cfg.HTF.get("on") else "htf-off"
    _rng = (f"from {bstart}" if bstart else f"era>={cfg.ERA_START_YEAR}") + (f"..{bend}" if bend else "")
    print(f"BACKTEST -- coil breakout, {_cond}, {_tp} ({_htf}), {_rng}, 1 contract")
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
    source = getattr(cfg, "CONFIG_SOURCE", "research")   # which config produced this run -> runs saved separated by it
    rec = runlog.record("backtest",
                  {"target_r": TRR, "entry_window": EWIN, "max_hold": HOLD, "entry": cfg.ENTRY["type"],
                   "stop": cfg.EXIT["stop"], "tp_method": METHOD, "htf_on": bool(cfg.HTF.get("on")),
                   "trail": f"{TRAIL_ARM}/{TRAIL_GAP}" if METHOD == "trailing" else None,
                   "conditional": ("+".join(ARM_GATES) if ARM_ON else "none (base rate)")},
                  {"trades": n_t, "win_pct": round(float(wr), 1), "avg_R": round(float(d["R"].mean()), 3),
                   "total_R": round(float(d["R"].sum()), 1), "total_pnl": round(float(d["pnl"].sum()), 0),
                   "max_dd_R": round(float(dd_r), 1), "target_pct": round(oc.get("target", 0) / n_t * 100, 1),
                   "config_source": source})
    # the DETAILED, machine-readable per-run breakdown + its clean HTML view live under research/runs (not here)
    import make_report
    ctx["run"] = {"run_id": rec["run_id"], "git": rec["git"], "note": rec["note"], "kind": "backtest", "source": source}
    ctx["config_snapshot"] = rec.get("config", {})   # the FULL strategy_config that produced this run -> into analysis.json
    make_report.build(trades_by_entry, ctx)
    print(f"RESULT {rec['run_id']} {source}")   # machine-readable line the chart server (serve.py) parses


if __name__ == "__main__":
    main()
