"""
build_map — the WIRING map of the strategy. Built to answer one question: what runs today, what's
built-but-unwired, and where does it plug in?

The story it tells: a SKELETON spine (data -> structure -> trade -> risk -> measurement) already runs
and backtests UNCONDITIONALLY. The GATES (when + quality) are built but bypass `setup_arm`, which
doesn't exist yet -- it's the empty socket every enabled gate plugs into. Building setup_arm = wiring
the gates in as research_config on/off toggles, flipped one at a time to measure lift over the base rate.

Reads live state from strategy_config + research_config so the on/off + knobs are truthful.
Run:  python research/strategy_map/build_map.py   ->  strategy_map.html
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
import strategy_config as cfg
import research_config as rcfg

# status -> (color, label)
ST = {
    "runs":   ("#199e70", "runs today (skeleton / engine)"),
    "built":  ("#4a9bff", "built · NOT wired into the backtest"),
    "geom":   ("#e0a94a", "geometry only (no edge)"),
    "build":  ("#f6465d", "the next build"),
    "locked": ("#8a94a6", "locked"),
    "future": ("#5b636e", "future / unbuilt"),
}


def _onoff(d):
    return ("ON", "#199e70") if d.get("on") else ("off", "#6b7280")


# each node: {name, sub, status, knob, state?, statecol?}
sess_state, sess_col = _onoff(cfg.FILTER_SESSION)
hour_state, hour_col = _onoff(cfg.FILTER_HOUR)
day_state, day_col = _onoff(cfg.FILTER_DAY_VOL)

LAYERS = [
    ("1", "DATA &amp; ERA", "the ground everything stands on", "skeleton", [
        {"name": "data_feed", "sub": "clean NQ+ES bars in", "status": "runs", "knob": "TF_SOURCES · DATA_DIR"},
        {"name": "era filter", "sub": "drop calm 2005-2014", "status": "runs", "knob": f"ERA_START_YEAR = {cfg.ERA_START_YEAR}"},
        {"name": "date window", "sub": "optional run range", "status": "runs", "knob": f"BACKTEST_START/END = {rcfg.BACKTEST_START}/{rcfg.BACKTEST_END}"},
    ]),
    ("2", "WHEN to trade", "timing gates &mdash; plug into setup_arm", "gate", [
        {"name": "session filter", "sub": "trade only in chosen sessions", "status": "built", "knob": "FILTER_SESSION", "state": f"{sess_state}: {','.join(cfg.FILTER_SESSION['allow'])}", "statecol": sess_col},
        {"name": "hour filter", "sub": "ET hours-of-day", "status": "built", "knob": "FILTER_HOUR", "state": hour_state, "statecol": hour_col},
        {"name": "day-vol regime", "sub": "high / med / low day", "status": "built", "knob": "FILTER_DAY_VOL", "state": day_state, "statecol": day_col},
        {"name": "news filter", "sub": "±30m around red-folder news", "status": "future", "knob": "(F33 — unbuilt)"},
    ]),
    ("3", "WHERE — structure", "pick the scale that defines the zone", "skeleton", [
        {"name": "base_profile", "sub": "the coil (LTF) — SKELETON ANCHOR", "status": "runs", "knob": "BASE {band_mult, min_bars}"},
        {"name": "volume_profile", "sub": "session range (MTF)", "status": "runs", "knob": "PROFILE {row_size, va_pct}"},
        {"name": "htf_profile", "sub": "trailing-week composite", "status": "built", "knob": "HTF {days, bins}"},
    ]),
    ("4", "QUALITY", "is the setup good? &mdash; plug into setup_arm", "gate", [
        {"name": "shape_filter", "sub": "clean vs foggy coil", "status": "built", "knob": f"SHAPE.shape_ok = {cfg.SHAPE['shape_ok']}"},
        {"name": "zone_calibration", "sub": "R:R geometry", "status": "built", "knob": f"ZONE.rr_min = {cfg.ZONE['rr_min']}"},
        {"name": "multi-scale confluence", "sub": "base ⊂ session ⊂ HTF agree", "status": "future", "knob": "(scores exist; combiner unbuilt)"},
        {"name": "fib_bias", "sub": "direction — no edge (F11/F13)", "status": "geom", "knob": "FIB.edges"},
    ]),
    ("5", "setup_arm", "the empty SOCKET — every ENABLED gate plugs in here", "socket", [
        {"name": "setup_arm", "sub": "enabled gates → ARM this coil / skip it", "status": "build",
         "knob": "SETUP {gates, arm_rule} · research_config on/off toggles", "wide": True},
    ]),
    ("6", "THE TRADE", "entry / stop / target — built &amp; backtested (runs UNCONDITIONAL today)", "skeleton", [
        {"name": "entry", "sub": "breakout OCO, fill at coil edge", "status": "runs", "knob": f"ENTRY.type = {cfg.ENTRY['type']}"},
        {"name": "stop = 1R", "sub": "the opposite coil edge", "status": "runs", "knob": "EXIT.stop = coil_edge"},
        {"name": "target", "sub": "fixed R (skeleton) | ladder rung (multi-scale)", "status": "runs", "knob": f"EXIT.target = {cfg.EXIT['target']} · target_r = {cfg.EXIT['target_r']}"},
    ]),
    ("7", "RISK &amp; EXECUTION", "sizing + frictions", "skeleton", [
        {"name": "risk sizing", "sub": "fixed-fractional to the 1R stop", "status": "runs", "knob": f"RISK.risk_per_trade_pct = {cfg.RISK['risk_per_trade_pct']}%"},
        {"name": "costs", "sub": "commission + slippage, honest fills", "status": "locked", "knob": f"${cfg.COMMISSION_PER_SIDE}/side · {cfg.SLIPPAGE_TICKS} tick"},
    ]),
    ("8", "MEASUREMENT", "the answer: does gating add lift?", "skeleton", [
        {"name": "backtest", "sub": "honest sim → R per trade", "status": "runs", "knob": "run_backtest.py"},
        {"name": "run ledger", "sub": "every run's scorecard", "status": "runs", "knob": "research/runs/runs.jsonl"},
        {"name": "reports", "sub": "equity + full breakdown", "status": "runs", "knob": "reports/<run_id>/"},
    ]),
]


def card(n):
    col = ST[n["status"]][0]
    wide = ' style="grid-column:1/-1"' if n.get("wide") else ""
    state = ""
    if n.get("state"):
        state = f'<span class="state" style="color:{n.get("statecol","#8a94a6")};border-color:{n.get("statecol","#8a94a6")}">{n["state"]}</span>'
    return f'''<div class="card {n['status']}"{wide}>
      <div class="chead"><span class="dot" style="background:{col}"></span><b>{n['name']}</b>{state}</div>
      <div class="csub">{n['sub']}</div>
      <div class="cknob">{n['knob']}</div>
    </div>'''


def layer(num, title, sub, kind, nodes):
    cards = "".join(card(n) for n in nodes)
    return f'''<div class="layer {kind}">
      <div class="rail"><span class="lnum">{num}</span><div><div class="ltitle">{title}</div><div class="lsub">{sub}</div></div></div>
      <div class="nodes">{cards}</div>
    </div>'''


def main():
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{lab}</span>' for c, lab in ST.values())
    layers = "".join(layer(*L) for L in LAYERS)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>simplicity — wiring map</title>
<style>
:root{{--bg:#0d0d0d;--panel:#161b22;--panel2:#1b2028;--ring:rgba(255,255,255,.10);--ink:#e6edf3;--mut:#8a94a6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;padding:26px 22px 60px}}
.wrap{{max-width:1040px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px;font-weight:680;letter-spacing:-.01em}}
h1 span{{color:var(--mut);font-weight:400}}
.lead{{color:var(--mut);max-width:88ch;margin:0 0 14px;font-size:13.5px}}
.lead b{{color:var(--ink)}}
.callout{{background:linear-gradient(180deg,rgba(246,70,93,.08),rgba(246,70,93,.02));border:1px solid rgba(246,70,93,.35);
border-radius:11px;padding:12px 15px;margin:0 0 18px;font-size:13px;color:#f3d0d5}}
.callout b{{color:#fff}}
.legend{{display:flex;flex-wrap:wrap;gap:8px 16px;margin:0 0 20px;font-size:11.5px;color:var(--mut)}}
.lg{{display:flex;align-items:center;gap:6px}}.lg i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
.layer{{display:grid;grid-template-columns:186px 1fr;gap:14px;padding:14px 0;border-top:1px solid var(--ring);align-items:start}}
.layer:first-of-type{{border-top:none}}
.rail{{display:flex;gap:10px;align-items:flex-start;position:sticky;top:10px}}
.lnum{{flex:0 0 auto;width:26px;height:26px;border-radius:50%;background:var(--panel2);border:1px solid var(--ring);
display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--mut)}}
.ltitle{{font-size:13.5px;font-weight:660;letter-spacing:.02em}}
.lsub{{color:var(--mut);font-size:11.5px;margin-top:1px}}
.nodes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:9px}}
.card{{background:var(--panel);border:1px solid var(--ring);border-left:3px solid var(--ring);border-radius:9px;padding:9px 11px}}
.card.runs{{border-left-color:#199e70}}.card.built{{border-left-color:#4a9bff}}.card.geom{{border-left-color:#e0a94a}}
.card.future{{border-left-color:#5b636e;opacity:.82}}.card.locked{{border-left-color:#8a94a6}}
.card.build{{border-left-color:#f6465d;border-color:rgba(246,70,93,.5);background:linear-gradient(180deg,rgba(246,70,93,.10),rgba(246,70,93,.02));border-style:dashed}}
.chead{{display:flex;align-items:center;gap:7px}}.chead b{{font-size:13px;font-weight:640}}
.dot{{width:8px;height:8px;border-radius:50%;flex:0 0 auto}}
.state{{margin-left:auto;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;
padding:1px 6px;border-radius:10px;border:1px solid}}
.csub{{color:var(--mut);font-size:11.5px;margin:3px 0 6px}}
.cknob{{font:11px ui-monospace,Menlo,monospace;color:#9fb0c2;background:rgba(255,255,255,.03);border-radius:5px;padding:3px 6px;word-break:break-word}}
.layer.gate .rail .lnum{{color:#4a9bff;border-color:rgba(74,158,255,.4)}}
.layer.socket .rail .lnum{{color:#f6465d;border-color:rgba(246,70,93,.5)}}
.foot{{color:var(--mut);font-size:11.5px;margin-top:22px;line-height:1.7;border-top:1px solid var(--ring);padding-top:14px}}
.foot code{{color:#9fb0c2}}
</style></head><body><div class="wrap">
<h1>simplicity <span>— the wiring map</span></h1>
<p class="lead">Built to reason about ONE thing: <b>what runs today, what's built-but-unwired, and where it plugs in.</b>
Read top&#8594;bottom. Green = the <b>skeleton</b> that already runs &amp; backtests. Blue = <b>gates built but bypassed</b>.
Red dashed = <b>the next build</b>.</p>
<div class="callout"><b>Today the skeleton runs UNCONDITIONALLY</b> — layers 1·3·6·7·8 execute every qualifying coil, in every
session, with no quality check. The gates in layers 2 &amp; 4 are <b>built but plug into nothing</b>: <code>setup_arm</code>
(layer 5) is an empty socket. <b>The next build = setup_arm</b> — it ANDs the <i>enabled</i> gates into an ARM/skip decision,
each gate a research_config on/off toggle you flip one at a time to measure lift over the −0.017R base rate.</div>
<div class="legend">{legend}</div>
{layers}
<p class="foot"><b>How the build goes:</b> (1) lock the single-dimension skeleton — anchor on <code>base_profile</code>,
target = <code>fixed_r</code> — and re-confirm the base rate. (2) build <code>setup_arm</code> as an AND-filter over
enabled gates, each an on/off in <code>research_config</code>. (3) flip ONE gate on, re-run, read the lift in the ledger +
report. Repeat. Every knob shown lives in <code>strategy_config</code> (strategy) or <code>research_config</code> (the run
toggles); this map reads their live values so it never drifts.</p>
</div></body></html>'''
    out = os.path.join(HERE, "strategy_map.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
