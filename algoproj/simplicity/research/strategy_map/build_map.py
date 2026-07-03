"""
build_map — the CONTROL PANEL: every dial in strategy_config + research_config, on one page.

Shows all the filters / gates / settings that can be tuned, enabled or disabled, grouped by pipeline
stage, with each knob's config path, current value, and a badge for whether the BACKTEST actually uses
it right now:
  LIVE       the backtest reads & applies this today
  NOT WIRED  configured, but the backtest ignores it (a gate waiting on setup_arm to apply it)
  REFERENCE  a bias / geometry input, validated in-context (not a standalone signal)
  FUTURE     not built yet
  LOCKED     fixed frictions

The point: the amber NOT-WIRED dials are the wiring to-do list. Building setup_arm turns each into an
on/off you flip one at a time. Reads the live config values so it never drifts.
Run:  python research/strategy_map/build_map.py   ->  strategy_map.html
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
import strategy_config as cfg
import research_config as rcfg

BADGE = {
    "live":      ("#199e70", "LIVE", "the backtest applies this now"),
    "notwired":  ("#e0a94a", "NOT WIRED", "configured, but the backtest ignores it — waits on setup_arm"),
    "reference": ("#4a9bff", "REFERENCE", "bias / geometry input, validated in-context"),
    "future":    ("#5b636e", "FUTURE", "not built yet"),
    "locked":    ("#8a94a6", "LOCKED", "fixed frictions"),
}


def _tog(on):
    return ("ON", "#199e70") if on else ("OFF", "#6b7280")


# item: {name, does, path, value, badge, toggle?(bool)}
SESS = ",".join(cfg.FILTER_SESSION["allow"])
PANEL = [
    ("RUN knobs", "research_config — how THIS run is set up (not the strategy)", [
        {"name": "active filter", "does": "vol-day variant for overlays / A-B", "path": "research_config.ACTIVE_FILTER", "value": rcfg.ACTIVE_FILTER, "badge": "reference"},
        {"name": "starting balance", "does": "account size for the equity curve", "path": "research_config.STARTING_BALANCE", "value": f"${rcfg.STARTING_BALANCE:,}", "badge": "live"},
        {"name": "date window", "does": "limit the backtest to a range", "path": "research_config.BACKTEST_START / _END", "value": f"{rcfg.BACKTEST_START} → {rcfg.BACKTEST_END}", "badge": "live"},
        {"name": "replay size", "does": "how many trades the replay page exports", "path": "research_config.MAX_REPLAY_TRADES", "value": rcfg.MAX_REPLAY_TRADES, "badge": "live"},
    ]),
    ("DATA &amp; ERA", "the ground — what data, which years", [
        {"name": "instrument", "does": "which market", "path": "strategy_config.INSTRUMENT", "value": cfg.INSTRUMENT, "badge": "locked"},
        {"name": "era cutoff", "does": "drop the calm 2005-2014 decade", "path": "strategy_config.ERA_START_YEAR", "value": cfg.ERA_START_YEAR, "badge": "live"},
        {"name": "sessions", "does": "ET session boundaries (asia/london/ny/close)", "path": "strategy_config.SESSIONS", "value": "4 sessions, ET", "badge": "live"},
    ]),
    ("WHEN to trade — filters", "timing gates · each ENABLE/DISABLE · none applied by the backtest yet", [
        {"name": "session filter", "does": "only trade chosen sessions", "path": "strategy_config.FILTER_SESSION", "value": f"allow = {SESS}", "badge": "notwired", "toggle": cfg.FILTER_SESSION["on"]},
        {"name": "hour filter", "does": "only trade chosen ET hours", "path": "strategy_config.FILTER_HOUR", "value": "9-15 ET", "badge": "notwired", "toggle": cfg.FILTER_HOUR["on"]},
        {"name": "day-vol regime", "does": "only trade high/med/low-vol days", "path": "strategy_config.FILTER_DAY_VOL", "value": ",".join(cfg.FILTER_DAY_VOL["regimes"]), "badge": "notwired", "toggle": cfg.FILTER_DAY_VOL["on"]},
        {"name": "news filter", "does": "block ±30m around red-folder news", "path": "(F33 — unbuilt)", "value": "—", "badge": "future"},
    ]),
    ("WHERE — structure", "the profilers that build the zone · tunable", [
        {"name": "base_profile", "does": "detect the coil (LTF) — the skeleton anchor", "path": "strategy_config.BASE", "value": f"band_mult={cfg.BASE['band_mult']}, min_bars={cfg.BASE['min_bars']}", "badge": "live"},
        {"name": "volume_profile", "does": "session range → POC / value area", "path": "strategy_config.PROFILE", "value": f"row={cfg.PROFILE['row_size']}, va={cfg.PROFILE['va_pct']}", "badge": "live"},
        {"name": "htf_profile", "does": "trailing-week composite (ladder source)", "path": "strategy_config.HTF", "value": f"days={cfg.HTF['days']}, bins={cfg.HTF['bins']}", "badge": "live"},
    ]),
    ("QUALITY — gates", "is the setup good? · tunable · become ON/OFF toggles when setup_arm exists", [
        {"name": "shape_filter", "does": "clean vs foggy coil (reject scattered)", "path": "strategy_config.SHAPE.shape_ok", "value": f"{cfg.SHAPE['shape_ok']} / 100", "badge": "notwired"},
        {"name": "zone_calibration", "does": "range dimensions → R:R + entry TF", "path": "strategy_config.ZONE.rr_min", "value": f"rr_min={cfg.ZONE['rr_min']}", "badge": "notwired"},
        {"name": "fib_bias", "does": "directional LEAN for the zone (VISION 12) — in-context, not standalone", "path": "strategy_config.FIB", "value": f"{len(cfg.FIB['edges'])-1} zones", "badge": "reference"},
        {"name": "confluence", "does": "base ⊂ session ⊂ HTF agree = A+ setup", "path": "(scores exist; combiner unbuilt)", "value": "—", "badge": "future"},
        {"name": "target ladder", "does": "multi-scale R:R geometry (target source)", "path": "strategy_config.LADDER", "value": f"min_rr={cfg.LADDER['min_rr']}, {'+'.join(cfg.LADDER['sources'])}", "badge": "live"},
    ]),
    ("setup_arm — THE SOCKET", "where the ENABLED gates converge into an ARM / skip decision", [
        {"name": "setup_arm", "does": "stack enabled gates → arm this coil or skip it — THE NEXT BUILD", "path": "strategy_config.SETUP {gates, arm_rule, invalidate}", "value": "None (unbuilt)", "badge": "future", "wide": True},
    ]),
    ("THE TRADE — entry / stop / target", "the geometry · tunable · backtested UNCONDITIONALLY today", [
        {"name": "entry", "does": "resting breakout bracket, OCO both edges", "path": "strategy_config.ENTRY", "value": f"{cfg.ENTRY['type']}, tf={cfg.ENTRY['entry_tf']}, min_coil={cfg.ENTRY['min_coil_pct']}%", "badge": "live"},
        {"name": "stop", "does": "opposite coil edge = 1R", "path": "strategy_config.EXIT.stop", "value": cfg.EXIT["stop"], "badge": "live"},
        {"name": "target", "does": "fixed R (single-dim) | ladder rung (multi-scale)", "path": "strategy_config.EXIT.target", "value": f"{cfg.EXIT['target']} · target_r={cfg.EXIT['target_r']}", "badge": "live"},
        {"name": "time stop", "does": "exit if neither hit", "path": "strategy_config.EXIT.max_hold_bars", "value": f"{cfg.EXIT['max_hold_bars']} bars", "badge": "live"},
    ]),
    ("RISK &amp; EXECUTION", "sizing + frictions", [
        {"name": "risk sizing", "does": "fixed-fractional to the 1R stop", "path": "strategy_config.RISK.risk_per_trade_pct", "value": f"{cfg.RISK['risk_per_trade_pct']}%/trade", "badge": "live"},
        {"name": "position limits", "does": "max contracts / concurrent", "path": "strategy_config.RISK", "value": "None (unset)", "badge": "future"},
        {"name": "costs", "does": "commission + slippage, honest fills", "path": "strategy_config (costs)", "value": f"${cfg.COMMISSION_PER_SIDE}/side · {cfg.SLIPPAGE_TICKS} tick", "badge": "locked"},
    ]),
]


def item(it):
    bcol, blab, _ = BADGE[it["badge"]]
    wide = ' style="grid-column:1/-1"' if it.get("wide") else ""
    tog = ""
    if "toggle" in it:
        t, tc = _tog(it["toggle"])
        tog = f'<span class="tog" style="color:{tc};border-color:{tc}">{t}</span>'
    return f'''<div class="item {it['badge']}"{wide}>
      <div class="ihead"><b>{it['name']}</b>{tog}<span class="badge" style="color:{bcol};border-color:{bcol}">{blab}</span></div>
      <div class="idoes">{it['does']}</div>
      <div class="irow"><span class="ipath">{it['path']}</span><span class="ival">{it['value']}</span></div>
    </div>'''


def section(title, note, items):
    return f'''<section><div class="shead"><h2>{title}</h2><span class="snote">{note}</span></div>
      <div class="items">{"".join(item(i) for i in items)}</div></section>'''


def main():
    legend = "".join(
        f'<span class="lg"><i style="background:{c}"></i><b>{lab}</b> — {desc}</span>' for c, lab, desc in BADGE.values())
    body = "".join(section(*s) for s in PANEL)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>simplicity — control panel</title>
<style>
:root{{--bg:#0d0d0d;--panel:#161b22;--panel2:#1b2028;--ring:rgba(255,255,255,.10);--ink:#e6edf3;--mut:#8a94a6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;padding:26px 22px 60px}}
.wrap{{max-width:1060px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px;font-weight:680;letter-spacing:-.01em}}h1 span{{color:var(--mut);font-weight:400}}
.lead{{color:var(--mut);max-width:92ch;margin:0 0 14px;font-size:13.5px}}.lead b{{color:var(--ink)}}
.callout{{background:linear-gradient(180deg,rgba(224,169,74,.09),rgba(224,169,74,.02));border:1px solid rgba(224,169,74,.4);
border-radius:11px;padding:12px 15px;margin:0 0 16px;font-size:13px;color:#f0dcbf}}.callout b{{color:#fff}}
.legend{{display:grid;grid-template-columns:1fr 1fr;gap:5px 18px;margin:0 0 22px;font-size:11.5px;color:var(--mut)}}
.lg{{display:flex;align-items:center;gap:7px}}.lg i{{width:11px;height:11px;border-radius:3px;flex:0 0 auto}}.lg b{{color:var(--ink);font-weight:640}}
section{{margin:0 0 18px}}
.shead{{display:flex;align-items:baseline;gap:11px;padding-bottom:8px;border-bottom:1px solid var(--ring);margin-bottom:11px}}
.shead h2{{font-size:14px;margin:0;font-weight:670;letter-spacing:.01em}}
.snote{{color:var(--mut);font-size:11.5px}}
.items{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:9px}}
.item{{background:var(--panel);border:1px solid var(--ring);border-left:3px solid var(--ring);border-radius:9px;padding:9px 12px}}
.item.live{{border-left-color:#199e70}}.item.notwired{{border-left-color:#e0a94a;background:linear-gradient(180deg,rgba(224,169,74,.05),transparent)}}
.item.reference{{border-left-color:#4a9bff}}.item.future{{border-left-color:#5b636e;opacity:.85}}.item.locked{{border-left-color:#8a94a6}}
.ihead{{display:flex;align-items:center;gap:8px}}.ihead b{{font-size:13px;font-weight:645}}
.badge{{margin-left:auto;font-size:9px;font-weight:800;letter-spacing:.5px;padding:1px 6px;border-radius:10px;border:1px solid}}
.tog{{font-size:9px;font-weight:800;letter-spacing:.5px;padding:1px 6px;border-radius:10px;border:1px solid}}
.idoes{{color:var(--mut);font-size:11.5px;margin:3px 0 7px}}
.irow{{display:flex;justify-content:space-between;gap:10px;align-items:center;font:11px ui-monospace,Menlo,monospace;
background:rgba(255,255,255,.03);border-radius:5px;padding:4px 7px}}
.ipath{{color:#7f8b99;word-break:break-word}}.ival{{color:#cfe0ef;font-weight:600;text-align:right;flex:0 0 auto}}
.foot{{color:var(--mut);font-size:11.5px;margin-top:20px;line-height:1.7;border-top:1px solid var(--ring);padding-top:14px}}
.foot code{{color:#9fb0c2}}
</style></head><body><div class="wrap">
<h1>simplicity <span>— the control panel</span></h1>
<p class="lead">Every dial in <b>strategy_config</b> + <b>research_config</b>, grouped by stage. Each shows its config
path, current value, and whether the backtest <b>uses it now</b>.</p>
<div class="callout"><b>The amber "NOT WIRED" dials are the to-do list.</b> Today the backtest runs UNCONDITIONALLY —
it applies the green (LIVE) dials (data/structure/trade/risk/costs) but <b>ignores every gate/filter</b>. Building
<code>setup_arm</code> is what turns each amber dial into an <b>ON/OFF toggle</b> you flip one at a time, re-running to
measure the lift over the −0.017R base rate.</div>
<div class="legend">{legend}</div>
{body}
<p class="foot"><b>Read it as a to-do list:</b> green already runs; amber (<code>FILTER_SESSION</code>, <code>SHAPE</code>,
<code>ZONE</code>) is built but bypassed until <code>setup_arm</code> applies it; blue (<code>fib_bias</code>) is a
directional-bias input judged in-context (the F11 isolated test was invalid — F13); grey is unbuilt. Live values are read
straight from the configs, so this panel never drifts from the code.</p>
</div></body></html>'''
    out = os.path.join(HERE, "strategy_map.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
