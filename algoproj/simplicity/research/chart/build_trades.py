"""
build_trades — attach the 3-scale module readings + per-trade bar slices to the backtest's trades.

The backtest (backtest/run_backtest.py) is the SINGLE SOURCE OF TRUTH: it writes backtest/output/trades.json
with each trade's exact geometry (entry/stop/target/exit times+prices, dir, R, outcome). This script does NOT
re-simulate anything — it only ENRICHES each trade for the chart trade-replay page:
  * the same 3 nested profiles the module stack shows — base ⊂ session ⊂ HTF — scored by the same gates
    (shape_filter / zone_calibration) + the target_ladder, read from the SAME profile jsons the sim used;
  * a compact 5m bar slice covering the setup session through the trade's exit (for the main chart + the
    session/base cards), and a downsampled trailing-week slice (for the HTF card).

Run:  python research/chart/build_trades.py   (after backtest/run_backtest.py)
Out:  research/chart/data/trades_data.json     (consumed by make_trade_replay.py)
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
sys.path.insert(0, os.path.join(SIM, "research", "gates", "profile_shape_filter"))
sys.path.insert(0, os.path.join(SIM, "research", "gates", "zone_calibration"))
sys.path.insert(0, os.path.join(SIM, "research", "setup", "target_ladder"))
import strategy_config as cfg
import research_config as rcfg
import shape_filter as sf
import zone_calibration as zc
import target_ladder as tlm

DATA = os.path.join(HERE, "data"); os.makedirs(DATA, exist_ok=True)
RES = os.path.join(SIM, "research")
BT = os.path.join(SIM, "backtest", "output", "trades.json")

# how many most-recent trades to export -> research_config.MAX_REPLAY_TRADES (the run knob; CLI arg overrides).
PRE_BARS = 12          # a few 5m bars before the setup session opens (context on the main chart)
POST_BARS = 8          # a few bars after exit (see the outcome resolve)
HTF_TARGET = 70        # downsample the trailing-week HTF slice to ~this many bars (keeps file small)


def _load(name, sub):
    return {p["sid"]: p for p in json.load(open(os.path.join(RES, sub, name, "output", name + ".json")))["profiles"]}


def _enrich(p):
    if not p:
        return None
    p = dict(p)
    p.setdefault("bars", p.get("htf_bars", len(p.get("bins", []))))  # htf uses htf_bars; gates want "bars"
    p["shape"] = sf.score(p) or {}
    p["zone"] = zc.calibrate(p) or {}
    p["bins"] = [{"p": round(b["p"], 2), "v": int(b["v"]), "va": bool(b.get("va"))} for b in p.get("bins", [])]
    return p


# bars are compact arrays [t, o, h, l, c, v] (drops repeated JSON keys ~3x); the page unpacks them.
def _slice(t, o, h, l, c, v, t0, t1):
    i0 = int(np.searchsorted(t, t0, "left")); i1 = int(np.searchsorted(t, t1, "right"))
    return [[int(t[i]), round(float(o[i]), 2), round(float(h[i]), 2), round(float(l[i]), 2),
             round(float(c[i]), 2), int(v[i])] for i in range(i0, i1)]


def _downsample(bars, target):
    if len(bars) <= target:
        return bars
    g = int(np.ceil(len(bars) / target)); out = []
    for i in range(0, len(bars), g):
        grp = bars[i:i + g]
        out.append([grp[0][0], grp[0][1], round(max(x[2] for x in grp), 2),
                    round(min(x[3] for x in grp), 2), grp[-1][4], int(sum(x[5] for x in grp))])
    return out


def main():
    bt = json.load(open(BT))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else rcfg.MAX_REPLAY_TRADES
    trades = bt["trades"]                          # sorted by t_entry ascending
    if limit and len(trades) > limit:
        trades = trades[-limit:]                   # most-recent N (most relevant); set limit=0 for all
    print(f"exporting {len(trades)} of {len(bt['trades'])} trades"
          + (f" (most recent {limit})" if limit else " (all)"))
    S = _load("volume_profile", "structure")
    B = _load("base_profile", "structure")
    H = _load("htf_profile", "structure")
    # next-session timing (same as build_chart_data) so the session card's "next" row fills
    order = sorted(S.values(), key=lambda P: P["start"])
    nxt = {}
    for i, P in enumerate(order):
        n = order[i + 1] if i + 1 < len(order) else None
        nxt[P["sid"]] = (n["session"] if n else None, n["start"] if n else None)

    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    t = (df.index.view("int64") // 1_000_000_000).astype("int64")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    v = df["volume"].to_numpy()
    step = 300  # 5m in seconds

    out = []
    skipped = 0
    for tr in trades:
        sid = tr["sid"]
        P = S.get(sid)
        if not P:
            skipped += 1; continue
        P = _enrich(P)
        # module cards are CONFIG-DRIVEN (match the main chart): a larger-dimension card is attached only when
        # that scale is ON in config. session = the always-on base dimension; base/htf appear once wired + enabled.
        # (The trade's entry/stop/target lines come from the sim record, so they stay truthful regardless.)
        base = _enrich(B.get(sid)) if cfg.BASE.get("on") else None
        htf = _enrich(H.get(sid)) if cfg.HTF.get("on") else None
        ns, no = nxt.get(sid, (None, None))
        P["next_session"] = ns; P["next_open"] = no; P["duration_sec"] = int(P["end"] - P["start"])
        lad = tlm.ladder({"base": base, "session": P, "htf": htf})   # None when base is off (needs the coil for 1R)
        # main window: from just before the setup session through the trade's exit
        t0 = min(P["start"], tr["t_entry"]) - PRE_BARS * step
        t1 = max(P["end"], tr["t_exit"]) + POST_BARS * step
        bars = _slice(t, o, h, l, c, v, t0, t1)
        htf_bars = []
        if htf:
            htf_bars = _downsample(_slice(t, o, h, l, c, v, htf["start"], htf["end"]), HTF_TARGET)
        rec = dict(tr)
        rec["date"] = P["date"]
        rec["scales"] = {"session": P, "base": base, "htf": htf, "ladder": lad}
        rec["bars"] = bars
        rec["htf_bars"] = htf_bars
        out.append(rec)

    payload = {"config": bt["config"], "trades": out}
    # emit as a JS global so the page loads it via <script src> (works on file://, unlike fetch)
    p = os.path.join(DATA, "trades_data.js")
    with open(p, "w", encoding="utf-8") as f:
        f.write("window.TRADES_DATA=")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";")
    sz = os.path.getsize(p) / 1e6
    print(f"wrote {len(out)} enriched trades ({skipped} skipped, no profile) -> {p}  ({sz:.1f} MB)")
    if out:
        avg = np.mean([len(r["bars"]) for r in out])
        print(f"  avg main-slice {avg:.0f} bars/trade · htf downsample target {HTF_TARGET}")


if __name__ == "__main__":
    main()
