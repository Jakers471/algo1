"""
make_chart — build the fresh TradingView lightweight chart (self-contained).

Reads the cached series + manifest (build_chart_data.py) and writes chart.html with
the data INLINED (file:// can't fetch local JSON) and the lightweight-charts library
referenced locally (offline). PURPOSE: visualize, not measure. Multi-timeframe NQ+ES,
candles + volume, a side menu showing exactly what's loaded + the config, and
dark-themed SHADE overlays so you can SEE what the filter covers:
  * SESSION  — highlights the FILTER_SESSION allowed windows (intraday TFs)
  * VOL DAYS — highlights the ACTIVE_FILTER high-vol days

Run:  python research/chart/make_chart.py   (after build_chart_data.py)
Out:  research/chart/chart.html
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

manifest = json.load(open(os.path.join(DATA, "manifest.json")))
series = {}
for s in manifest["series"]:
    series[s["key"]] = json.load(open(os.path.join(DATA, s["key"] + ".json")))

HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>simplicity chart</title>
<script src="lib/lightweight-charts.standalone.production.js"></script>
<style>
:root{--s:#1a1a19;--pg:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--ring:rgba(255,255,255,.10);
--acc:#3987e5;--up:#199e70;--dn:#e66767}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--pg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:16px;padding:10px 16px;border-bottom:1px solid var(--ring);flex-wrap:wrap}
.top h1{font-size:15px;margin:0;font-weight:650}
.grp{display:flex;gap:4px;align-items:center}.grp .lab{color:var(--mut);font-size:11px;margin-right:4px;text-transform:uppercase;letter-spacing:.05em}
button{background:var(--s);border:1px solid var(--ring);color:var(--ink2);font:inherit;font-size:12.5px;
padding:5px 11px;border-radius:7px;cursor:pointer}button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
button.on.warm{background:var(--dn);border-color:var(--dn)}
button:disabled{opacity:.3;cursor:default}
.main{flex:1;display:flex;min-height:0}
#chart{flex:1;min-width:0}
.side{width:290px;border-left:1px solid var(--ring);padding:14px 16px;overflow:auto;font-size:12.5px}
.side h2{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:16px 0 8px;
border-bottom:1px solid var(--ring);padding-bottom:6px}.side h2:first-child{margin-top:0}
.kv{display:flex;justify-content:space-between;gap:10px;padding:3px 0}
.kv .k{color:var(--mut)}.kv .v{color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:4px;background:rgba(57,135,229,.18);color:var(--acc)}
.on-pill{color:var(--up)}.off-pill{color:var(--mut)}
.cfgbtns{display:flex;gap:5px;margin-bottom:8px}
.cfgbtns button{font-size:11.5px;padding:4px 12px}
.loaded{font-size:12px;color:var(--up);display:flex;align-items:center;gap:7px;font-weight:600}
.loaded .dot{width:8px;height:8px;border-radius:50%;background:var(--up);
box-shadow:0 0 6px var(--up);animation:blink 1.15s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
</style></head><body>
<div class="top">
  <h1>simplicity <span style="color:var(--mut);font-weight:400">chart</span></h1>
  <div class="grp"><span class="lab">inst</span><span id="insts"></span></div>
  <div class="grp"><span class="lab">tf</span><span id="tfs"></span></div>
  <div class="grp"><span class="lab">shade</span><button id="shSess">session</button><button id="shVol">vol days</button></div>
</div>
<div class="main">
  <div id="chart"></div>
  <div class="side">
    <h2>Config</h2><div id="cfgSel" class="cfgbtns"></div><div id="cfgLoaded" class="loaded"></div>
    <h2>Loaded</h2><div id="loaded"></div>
    <h2>When-to-trade filters</h2><div id="filters"></div>
    <h2>Config on chart</h2><div id="cfg"></div>
    <h2>Sessions (ET)</h2><div id="sess"></div>
    <h2>Costs</h2><div id="costs"></div>
  </div>
</div>
<script>
const SERIES=__SERIES__, M=__MANIFEST__, C=M.config;
const TFO=["1m","5m","15m","60m","1d"];
const avail={};M.series.forEach(s=>{(avail[s.instrument]=avail[s.instrument]||{})[s.tf]=s;});
let inst="NQ", tf="1d", shSess=false, shVol=false, cfgSel=M.default_config||"research";

// ET, 12-hour (AM/PM) axis + crosshair -- display only, uses raw times underneath
const _TZ={timeZone:C.clock};
const _t12=t=>new Date(t*1000).toLocaleTimeString("en-US",{..._TZ,hour:"numeric",minute:"2-digit",hour12:true});
const _tick=(t,type)=>{const d=new Date(t*1000);
  if(type>=3)return _t12(t);
  if(type===0)return d.toLocaleDateString("en-US",{..._TZ,year:"numeric"});
  if(type===1)return d.toLocaleDateString("en-US",{..._TZ,month:"short"});
  return d.toLocaleDateString("en-US",{..._TZ,month:"short",day:"numeric"});};
const chart=LightweightCharts.createChart(document.getElementById("chart"),{
  layout:{background:{color:"#1a1a19"},textColor:"#c3c2b7"},
  grid:{vertLines:{color:"#2c2c2a"},horzLines:{color:"#2c2c2a"}},
  rightPriceScale:{borderColor:"#383835"},
  timeScale:{borderColor:"#383835",timeVisible:true,secondsVisible:false,tickMarkFormatter:_tick},
  localization:{timeFormatter:t=>new Date(t*1000).toLocaleString("en-US",
    {..._TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",hour12:true})},
  crosshair:{mode:0}});
// shade sits behind candles (added first), full-height via its own hidden scale
const shade=chart.addHistogramSeries({priceScaleId:"shade",priceLineVisible:false,lastValueVisible:false,base:0});
chart.priceScale("shade").applyOptions({scaleMargins:{top:0,bottom:0},visible:false});
const candle=chart.addCandlestickSeries({upColor:"#199e70",downColor:"#e66767",
  borderUpColor:"#199e70",borderDownColor:"#e66767",wickUpColor:"#199e70",wickDownColor:"#e66767"});
const vol=chart.addHistogramSeries({priceFormat:{type:"volume"},priceScaleId:"vol"});
chart.priceScale("vol").applyOptions({scaleMargins:{top:0.82,bottom:0}});
window.addEventListener("resize",()=>chart.timeScale().fitContent());

const _f=new Intl.DateTimeFormat("en-US",{timeZone:C.clock,hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
function etMin(t){const p=_f.formatToParts(new Date(t*1000));let h=0,m=0;
  for(const x of p){if(x.type=="hour")h=+x.value;if(x.type=="minute")m=+x.value;}return h*60+m;}
function sessionOf(t){const x=etMin(t);
  if(x>=180&&x<570)return"london";if(x>=570&&x<960)return"newyork";if(x>=960&&x<1080)return"close";return"asia";}
function etDate(t){return new Date(t*1000).toLocaleDateString("en-CA",{timeZone:C.clock});}

function updateShade(){
  const cs=SERIES[inst+"_"+tf].candles;
  const allow=new Set(C.filter_session.allow), seld=new Set(M.configs[cfgSel].selected_days);
  const canSess=shSess&&tf!=="1d";  // session shading only meaningful intraday
  const data=cs.map(c=>{let col="rgba(0,0,0,0)";
    if(shVol&&seld.has(etDate(c.time)))col="rgba(230,103,103,0.10)";
    if(canSess&&allow.has(sessionOf(c.time)))col="rgba(57,135,229,0.13)";
    return {time:c.time,value:1,color:col};});
  shade.setData(data);
}
function kv(k,v){return `<div class="kv"><span class="k">${k}</span><span class="v">${v}</span></div>`;}
function load(){
  const s=SERIES[inst+"_"+tf], meta=avail[inst][tf];
  candle.setData(s.candles); vol.setData(s.volume); updateShade();
  chart.timeScale().fitContent();
  document.getElementById("loaded").innerHTML=
    kv("instrument",inst)+kv("timeframe",tf)+kv("bars",meta.bars)+
    kv("from",meta.first.slice(0,10))+kv("to",meta.last.slice(0,10))+kv("max cache",M.max_bars);
  renderTfs();
}
function renderInsts(){document.getElementById("insts").innerHTML=Object.keys(avail).map(i=>
  `<button data-i="${i}" class="${i==inst?'on':''}">${i}</button>`).join("");
  document.querySelectorAll("[data-i]").forEach(b=>b.onclick=()=>{inst=b.dataset.i;
    if(!avail[inst][tf])tf=Object.keys(avail[inst])[0];renderInsts();load();});}
function renderTfs(){document.getElementById("tfs").innerHTML=TFO.map(t=>
  `<button data-t="${t}" class="${t==tf?'on':''}" ${avail[inst][t]?'':'disabled'}>${t}</button>`).join("");
  document.querySelectorAll("[data-t]").forEach(b=>{if(!b.disabled)b.onclick=()=>{tf=b.dataset.t;load();};});}
document.getElementById("shSess").onclick=function(){shSess=!shSess;this.classList.toggle("on",shSess);updateShade();};
document.getElementById("shVol").onclick=function(){shVol=!shVol;this.classList.toggle("on",shVol);this.classList.toggle("warm",shVol);updateShade();};

// sidebar
function onoff(f){return f.on?`<span class="on-pill">ON</span>`:`<span class="off-pill">off</span>`;}
document.getElementById("filters").innerHTML=
  kv("session "+onoff(C.filter_session), C.filter_session.allow.join(", "))+
  kv("hour "+onoff(C.filter_hour), C.filter_hour.on?C.filter_hour.allow.join(","):"—")+
  kv("day_vol "+onoff(C.filter_day_vol), C.filter_day_vol.on?C.filter_day_vol.regimes.join(","):"—");
function renderCfg(){document.getElementById("cfgSel").innerHTML=Object.keys(M.configs).map(k=>
  `<button data-c="${k}" class="${k==cfgSel?'on':''}">${k}</button>`).join("");
  document.querySelectorAll("[data-c]").forEach(b=>b.onclick=()=>{cfgSel=b.dataset.c;renderCfg();renderCfgSidebar();updateShade();});
  document.getElementById("cfgLoaded").innerHTML=`<span class="dot"></span>${cfgSel} attached &amp; loaded`;}
function renderCfgSidebar(){const cc=M.configs[cfgSel];
  document.getElementById("cfg").innerHTML=
    kv("config",`<span class="pill">${cfgSel}</span>`)+kv("&rarr;",cc.label)+
    kv("vol-days",cc.selected_days.length+" d / "+cc.selected_runs.length+" periods")+
    kv("note",cc.note)+kv("era start",C.era_start)+kv("vol metric",C.vol_metric)+
    kv("trail window",C.trail_window+"d")+kv("regime pctiles",C.regime_pctiles.join(" / "));}
renderCfg(); renderCfgSidebar();
document.getElementById("sess").innerHTML=Object.entries(C.sessions).map(([k,v])=>kv(k,v[0]+"–"+v[1])).join("");
document.getElementById("costs").innerHTML=
  kv("point value","$"+C.point_value)+kv("tick",C.tick)+kv("commission","$"+C.commission_per_side+"/side")+
  kv("slippage",C.slippage_ticks+" tick");
renderInsts();load();
</script></body></html>"""

out = HTML.replace("__SERIES__", json.dumps(series)).replace("__MANIFEST__", json.dumps(manifest))
p = os.path.join(HERE, "chart.html")
open(p, "w", encoding="utf-8").write(out)
print("wrote", p, "-", round(len(out) / 1e6, 2), "MB")
