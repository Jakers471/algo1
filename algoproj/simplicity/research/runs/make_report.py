"""
make_report — the clean HTML VIEW of a run's machine-readable analysis (research/runs owns both).

build(trades, ctx):  analytics.analyze -> reports/<run_id>/analysis.json  (machine-readable, source of truth)
                     -> reports/<run_id>/report.html  (professional view: ECharts equity/drawdown +
                        headline cards + ALL/LONG/SHORT tables, NinjaTrader-style)  -> reports/index.html
The equity chart uses the vendored ECharts (lib/echarts.min.js) referenced offline. Nothing here re-computes
metrics — it renders analysis.json. Run indirectly via backtest/run_backtest.py, or rebuild a report from an
existing analysis.json with:  python research/chart/... (or import make_report; make_report.render(dir)).
"""
import os
import json
import math

import analytics

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, "reports")
LEDGER = os.path.join(HERE, "runs.jsonl")


# ---------- number formatting ----------
def _f(v):  # finite guard
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None


def pct(v, sign=True):
    v = _f(v)
    return "&mdash;" if v is None else (f"{v*100:+.2f}%" if sign else f"{v*100:.2f}%")


def money(v):
    v = _f(v)
    return "&mdash;" if v is None else (f"&minus;${abs(v):,.0f}" if v < 0 else f"${v:,.0f}")


def ratio(v):
    v = _f(v)
    if v is None:
        return "&infin;"
    return f"{v:.2f}"


def rr(v):
    v = _f(v)
    return "&mdash;" if v is None else f"{v:+.3f}R"


def num(v, d=0):
    v = _f(v)
    return "&mdash;" if v is None else f"{v:,.{d}f}"


def _cls(v, mode):
    v = _f(v)
    if v is None or mode is None:
        return ""
    if mode == "sign":
        return "up" if v >= 0 else "dn"
    if mode == "gt1":
        return "up" if v > 1 else "dn"
    if mode == "neg":
        return "dn"
    if mode == "up":
        return "up"
    if mode == "dn":
        return "dn"
    return ""


# section spec: (row label, group-section, field, formatter, color-mode)
SECTIONS = [
    ("Performance", "performance", [
        ("Total net profit", "total_net_profit", money, "sign"),
        ("Gross profit", "gross_profit", money, "up"),
        ("Gross loss", "gross_loss", money, "dn"),
        ("Commission", "commission", money, None),
        ("Total slippage", "total_slippage", money, None),
        ("Profit factor", "profit_factor", ratio, "gt1"),
        ("Total return", "total_return", pct, "sign"),
        ("CAGR", "cagr", pct, "sign"),
        ("Max. drawdown (%)", "max_dd_pct", pct, "neg"),
        ("Max. drawdown ($)", "max_dd_dollar", money, "dn"),
        ("Sharpe ratio", "sharpe", ratio, "sign"),
        ("Sortino ratio", "sortino", ratio, "sign"),
        ("Calmar ratio", "calmar", ratio, "sign"),
        ("Ulcer index", "ulcer_index", ratio, None),
    ]),
    ("Trades", "trades", [
        ("Total # of trades", "total", num, None),
        ("Percent profitable", "pct_profitable", lambda v: pct(v, False), None),
        ("# of winning trades", "n_win", num, None),
        ("# of losing trades", "n_loss", num, None),
        ("# of even trades", "n_even", num, None),
        ("Expectancy / trade", "expectancy", pct, "sign"),
        ("Avg. trade", "avg_trade", money, "sign"),
        ("Avg. R / trade", "avg_R", rr, "sign"),
        ("Avg. winning trade", "avg_win", pct, "up"),
        ("Avg. losing trade", "avg_loss", pct, "dn"),
        ("Ratio avg win / avg loss", "payoff", ratio, None),
        ("Max consecutive winners", "max_consec_win", num, None),
        ("Max consecutive losers", "max_consec_loss", num, None),
        ("Largest winning trade", "largest_win", pct, "up"),
        ("Largest losing trade", "largest_loss", pct, "dn"),
    ]),
    ("Excursion (per trade)", "excursion", [
        ("Avg MAE (adverse)", "avg_mae", lambda v: pct(v, False), "dn"),
        ("Avg MFE (favorable)", "avg_mfe", lambda v: pct(v, False), "up"),
        ("Avg ETD (give-back)", "avg_etd", lambda v: pct(v, False), None),
    ]),
    ("Risk of ruin (Monte Carlo, reshuffled)", "risk_of_ruin", [
        ("Median drawdown", "median_dd", pct, "dn"),
        ("Worst-5% drawdown", "worst5_dd", pct, "dn"),
        ("Prob. drawdown &lt; -20%", "p_dd_lt_20", lambda v: pct(v, False), None),
        ("Prob. drawdown &lt; -50%", "p_dd_lt_50", lambda v: pct(v, False), None),
    ]),
    ("Time &amp; exposure", "time_exposure", [
        ("Avg # of trades per day", "avg_trades_per_day", lambda v: num(v, 2), None),
        ("Time in market", "time_in_market", lambda v: pct(v, False), None),
        ("Avg bars in trade", "avg_bars_in_trade", lambda v: num(v, 1), None),
        ("Profit per month", "profit_per_month", money, "sign"),
        ("Max time to recover", "max_time_to_recover_days", lambda v: num(v) + "d", None),
        ("Longest flat period", "longest_flat_days", lambda v: num(v) + "d", None),
    ]),
]

HEADLINE = [
    ("Net return", "net_return", pct, "sign"),
    ("CAGR", "cagr", pct, "sign"),
    ("Sharpe", "sharpe", ratio, "sign"),
    ("Max drawdown", "max_dd", pct, "neg"),
    ("Win rate", "win_rate", lambda v: pct(v, False), None),
    ("Exposure", "exposure", lambda v: pct(v, False), None),
    ("Total P&amp;L", "total_pnl", money, "sign"),
    ("Profit factor", "profit_factor", ratio, "gt1"),
]


def _gval(groups, section, field):
    g = groups.get("all") or {}
    vals = []
    for k in ("all", "long", "short"):
        gg = groups.get(k)
        vals.append(gg[section].get(field) if gg and section in gg else None)
    return vals


def _tables(A):
    groups = A["groups"]
    out = ""
    for title, section, rows in SECTIONS:
        body = ""
        for label, field, fmt, mode in rows:
            va, vl, vs = _gval(groups, section, field)
            cell = lambda v: f'<td class="v {_cls(v, mode)}">{fmt(v)}</td>'
            body += f'<tr><td class="k">{label}</td>{cell(va)}{cell(vl)}{cell(vs)}</tr>'
        out += (f'<div class="sec"><table><thead><tr><th class="k">{title}</th>'
                f'<th class="v">ALL</th><th class="v">LONG</th><th class="v">SHORT</th></tr></thead>'
                f'<tbody>{body}</tbody></table></div>')
    return out


def _cards(A):
    h = A["headline"]
    out = ""
    for label, field, fmt, mode in HEADLINE:
        v = h.get(field)
        out += (f'<div class="card"><div class="cl">{label}</div>'
                f'<div class="cv {_cls(v, mode)}">{fmt(v)}</div></div>')
    return out


def _html(A):
    run = A.get("run", {}); p = A["period"]; cfg = A.get("config", {})
    eq = A["equity"]
    meta = (f'{run.get("run_id","?")} &nbsp;&middot;&nbsp; <span class="tag">backtest</span> &nbsp;&middot;&nbsp; '
            f'{run.get("note") or "&mdash;"} &nbsp;&middot;&nbsp; git {run.get("git","?")}')
    period = (f'<div class="sec"><table><tbody>'
              f'<tr><td class="k">Start date</td><td class="v">{p["start"]}</td></tr>'
              f'<tr><td class="k">End date</td><td class="v">{p["end"]}</td></tr>'
              f'<tr><td class="k">Trading days</td><td class="v">{p["trading_days"]:,}</td></tr>'
              f'<tr><td class="k">Era &middot; target</td><td class="v">&ge;{cfg.get("era_start","?")} &middot; &ge;{cfg.get("target_r","?")}R</td></tr>'
              f'<tr><td class="k">Start balance</td><td class="v">${cfg.get("starting_balance",0):,.0f}</td></tr>'
              f'<tr><td class="k">Risk / trade</td><td class="v">{cfg.get("risk_pct","?")}%</td></tr>'
              f'</tbody></table></div>')
    start_bal = cfg.get("starting_balance", 0)
    pos = bool(eq["equity"] and eq["equity"][-1] >= start_bal)   # net result -> equity curve color
    chart_data = json.dumps({"dates": eq["dates"], "equity": eq["equity"], "dd": eq["drawdown_pct"],
                             "start": start_bal, "pos": pos})
    rid = run.get("run_id", "run")
    return TEMPLATE.replace("__META__", meta).replace("__CARDS__", _cards(A)) \
                   .replace("__PERIOD__", period).replace("__TABLES__", _tables(A)) \
                   .replace("__CHART__", chart_data) \
                   .replace("__TITLERUN__", rid).replace("__TITLE__", rid + " — performance")


def build(trades, ctx):
    A = analytics.analyze(trades, ctx)
    run = ctx.get("run", {})
    run_id = run.get("run_id", "adhoc"); source = run.get("source", "research")   # runs separated by config source
    d = os.path.join(REPORTS, source, run_id); os.makedirs(d, exist_ok=True)
    json.dump(A, open(os.path.join(d, "analysis.json"), "w"), indent=1)
    open(os.path.join(d, "report.html"), "w", encoding="utf-8").write(_html(A))
    build_index()
    print(f"[report] research/runs/reports/{source}/{run_id}/report.html  (+ analysis.json) · index updated")
    return A


def build_index():
    rows = ""
    runs = [json.loads(l) for l in open(LEDGER, encoding="utf-8")] if os.path.exists(LEDGER) else []
    bt = [r for r in runs if r.get("kind") == "backtest"][::-1]
    scol = {"strategy": "#9a7cff", "research": "#4a9eff"}
    for r in bt:
        rid = r["run_id"]; m = r.get("metrics", {}); source = m.get("config_source", "research")
        has = os.path.exists(os.path.join(REPORTS, source, rid, "report.html"))
        link = f'<a href="{source}/{rid}/report.html">open &rarr;</a>' if has else '<span class="mut">no report</span>'
        avgR = m.get("avg_R"); totR = m.get("total_R"); sc = scol.get(source, "#8a94a6")
        rows += (f'<tr><td>{rid}</td>'
                 f'<td><span class="tag" style="color:{sc};border:1px solid {sc};border-radius:5px;padding:1px 7px;font-size:11px">{source}</span></td>'
                 f'<td>{r.get("note") or "&mdash;"}</td>'
                 f'<td class="num">{m.get("trades","&mdash;"):,}</td><td class="num">{m.get("win_pct","&mdash;")}%</td>'
                 f'<td class="num {"up" if (avgR or 0)>=0 else "dn"}">{avgR:+.3f}R</td>'
                 f'<td class="num {"up" if (totR or 0)>=0 else "dn"}">{totR:+.1f}R</td>'
                 f'<td class="num">${m.get("total_pnl",0):,.0f}</td><td class="mut">git {r.get("git","?")}</td>'
                 f'<td>{link}</td></tr>')
    html = INDEX_TEMPLATE.replace("__ROWS__", rows or '<tr><td colspan="10" class="mut">no backtest runs yet</td></tr>')
    os.makedirs(REPORTS, exist_ok=True)
    open(os.path.join(REPORTS, "index.html"), "w", encoding="utf-8").write(html)


# ---------- templates ----------
_CSS = """
:root{--bg:#0a0d13;--panel:#11151d;--panel2:#151b25;--bd:#1d2430;--ink:#e6edf3;--ink2:#c3ccd6;
--mut:#79838f;--up:#2ebd85;--dn:#f6465d;--acc:#4a9eff}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--ink);font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
padding:26px 30px 60px}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.mono,.num,.v,.cv{font-variant-numeric:tabular-nums}
h1{font-size:26px;font-weight:680;margin:0 0 3px;letter-spacing:-.01em}
.crumb{color:var(--mut);font-size:12px;float:right;margin-top:12px}
.meta{color:var(--ink2);font-size:12.5px;margin:8px 0 20px}
.tag{background:rgba(74,158,255,.16);color:var(--acc);border-radius:5px;padding:1px 7px;font-size:11px;font-weight:600}
.mut{color:var(--mut)}.up{color:var(--up)}.dn{color:var(--dn)}
.cards{display:grid;grid-template-columns:repeat(8,1fr);gap:11px;margin-bottom:20px}
@media(max-width:1180px){.cards{grid-template-columns:repeat(4,1fr)}}
.card{background:var(--panel);border:1px solid var(--bd);border-radius:11px;padding:13px 15px}
.cl{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.4px}
.cv{font-size:24px;font-weight:640;margin-top:5px;letter-spacing:-.01em}
.chartwrap{background:var(--panel);border:1px solid var(--bd);border-radius:12px;padding:14px 16px;margin-bottom:20px}
.chartwrap h2{font-size:13px;font-weight:640;margin:0 0 6px}
#eq{width:100%;height:420px}
.cols{columns:3;column-gap:16px}
@media(max-width:1180px){.cols{columns:2}}@media(max-width:760px){.cols{columns:1}}
.sec{background:var(--panel);border:1px solid var(--bd);border-radius:11px;padding:4px 14px 8px;
margin:0 0 16px;break-inside:avoid;display:inline-block;width:100%}
table{width:100%;border-collapse:collapse}
thead th{color:var(--mut);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;font-weight:600;
text-align:right;padding:9px 0 7px;border-bottom:1px solid var(--bd)}
thead th.k{text-align:left;color:var(--ink2);font-size:12px;text-transform:none;letter-spacing:0;font-weight:650}
td{padding:4px 0;border-bottom:1px solid rgba(255,255,255,.045);font-size:12.5px}
td.k{color:var(--ink2)}td.v{text-align:right;padding-left:14px;min-width:82px}
tbody tr:last-child td{border-bottom:none}
.foot{color:var(--mut);font-size:11.5px;margin-top:12px}
"""

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<script src="../../../lib/echarts.min.js"></script>
<style>__CSS__</style></head><body>
<div class="crumb"><a href="../../index.html">&lt; all runs</a> &nbsp; Performance / __TITLERUN__</div>
<h1>Performance</h1>
<div class="meta">__META__</div>
<div class="cards">__CARDS__</div>
<div class="chartwrap"><h2>Equity &amp; drawdown</h2><div id="eq"></div></div>
<div class="cols">__TABLES__ __PERIOD__</div>
<div class="foot">Machine-readable source: <span class="mono">analysis.json</span> (same folder). $ = fixed-fractional
on the starting balance (matches the sim). LONG = up-breakouts, SHORT = down-breakouts.</div>
<script>
const D=__CHART__;
const EQC=D.pos?"#2ebd85":"#f6465d";                       // equity curve reflects the net result
const EQG0=D.pos?"rgba(46,189,133,.35)":"rgba(246,70,93,.28)";
const EQG1=D.pos?"rgba(46,189,133,.02)":"rgba(246,70,93,.02)";
const ch=echarts.init(document.getElementById("eq"),null,{renderer:"canvas"});
ch.setOption({
  backgroundColor:"transparent",
  animation:false,
  color:[EQC,"#f6465d"],
  grid:[{left:18,right:66,top:14,height:250},{left:18,right:66,top:300,height:96}],
  axisPointer:{link:[{xAxisIndex:"all"}],lineStyle:{color:"#3a4452"}},
  tooltip:{trigger:"axis",backgroundColor:"#11151d",borderColor:"#1d2430",textStyle:{color:"#e6edf3",fontSize:12},
    formatter:p=>{const d=p[0].axisValue;let s=`<b>${d}</b>`;p.forEach(x=>{const v=x.value;
      s+=`<br>${x.marker}${x.seriesName}: `+(x.seriesIndex===0?("$"+Number(v).toLocaleString(undefined,{maximumFractionDigits:0})):(Number(v).toFixed(2)+"%"));});return s;}},
  xAxis:[
    {type:"category",data:D.dates,boundaryGap:false,gridIndex:0,axisLabel:{show:false},
      axisLine:{lineStyle:{color:"#2a3340"}},axisTick:{show:false}},
    {type:"category",data:D.dates,boundaryGap:false,gridIndex:1,
      axisLabel:{color:"#79838f",fontSize:11,hideOverlap:true},axisLine:{lineStyle:{color:"#2a3340"}},axisTick:{show:false}}],
  yAxis:[
    {scale:true,gridIndex:0,position:"right",splitLine:{lineStyle:{color:"rgba(255,255,255,.05)"}},
      axisLabel:{color:"#79838f",fontSize:11,formatter:v=>"$"+(v/1000).toFixed(0)+"k"}},
    {scale:true,gridIndex:1,position:"right",max:0,splitLine:{lineStyle:{color:"rgba(255,255,255,.05)"}},
      axisLabel:{color:"#79838f",fontSize:11,formatter:v=>v.toFixed(0)+"%"}}],
  series:[
    {name:"Equity",type:"line",data:D.equity,xAxisIndex:0,yAxisIndex:0,showSymbol:false,lineStyle:{width:1.6,color:EQC},
      areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:EQG0},{offset:1,color:EQG1}])},
      markLine:{silent:true,symbol:"none",lineStyle:{color:"#5a6472",type:"dashed",width:1},
        data:[{yAxis:D.start,label:{show:false}}]}},
    {name:"Drawdown",type:"line",data:D.dd,xAxisIndex:1,yAxisIndex:1,showSymbol:false,lineStyle:{width:1,color:"#f6465d"},
      areaStyle:{color:"rgba(246,70,93,.18)"}}]
});
new ResizeObserver(()=>ch.resize()).observe(document.getElementById("eq"));
</script></body></html>"""

INDEX_TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>runs — backtests</title>
<style>__CSS__
table.runs{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--bd);border-radius:12px;overflow:hidden}
table.runs th{color:var(--mut);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;text-align:left;padding:11px 14px;border-bottom:1px solid var(--bd)}
table.runs td{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.045);font-size:12.5px}
table.runs td.num{text-align:right;font-variant-numeric:tabular-nums}
table.runs tr:last-child td{border-bottom:none}table.runs tbody tr:hover{background:rgba(74,158,255,.05)}
</style></head><body>
<h1>Backtest runs</h1>
<div class="meta">Every run's detailed breakdown lives under <span class="mono">reports/&lt;run_id&gt;/</span>
(machine-readable <span class="mono">analysis.json</span> + this HTML view). Newest first.</div>
<table class="runs"><thead><tr><th>Run</th><th>Config</th><th>Note</th><th style="text-align:right">Trades</th>
<th style="text-align:right">Win%</th><th style="text-align:right">Avg R</th><th style="text-align:right">Total R</th>
<th style="text-align:right">P&amp;L</th><th>Commit</th><th></th></tr></thead><tbody>__ROWS__</tbody></table>
</body></html>"""

TEMPLATE = TEMPLATE.replace("__CSS__", _CSS)
INDEX_TEMPLATE = INDEX_TEMPLATE.replace("__CSS__", _CSS)


if __name__ == "__main__":
    build_index()
    print("rebuilt reports/index.html")
