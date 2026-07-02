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
.main{flex:1;display:flex;min-height:0;min-width:0}
.chartwrap{flex:1 1 auto;min-width:0;position:relative}
#chart{position:absolute;inset:0}
.vpsvg{position:absolute;inset:0;pointer-events:none;z-index:3}
.ind{position:absolute;top:8px;left:8px;z-index:5;background:rgba(26,26,25,.94);border:1px solid var(--ring);
border-radius:8px;font-size:11.5px;min-width:150px;box-shadow:0 4px 14px rgba(0,0,0,.45)}
.ind-h{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:6px 9px;border-bottom:1px solid var(--ring)}
.ind-h b{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}
.ind-b{padding:8px 9px;display:flex;flex-direction:column;gap:7px}
.ind-b.min{display:none}
.ind-row{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
.ind-lab{color:var(--mut);width:54px;font-size:11px}
.ind button{font-size:11px;padding:2px 8px}
.sw{width:9px;height:9px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:middle}
.ind-note{color:var(--mut);font-size:10px}
.side{flex:0 0 290px;border-left:1px solid var(--ring);padding:14px 16px;overflow:auto;font-size:12.5px}
@media(max-width:860px){.side{flex-basis:230px}}
@media(max-width:640px){.side{flex-basis:190px;font-size:11.5px}}
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
  <div class="chartwrap">
    <div id="chart"></div>
    <svg id="vpsvg" class="vpsvg"></svg>
    <div class="ind" id="ind">
      <div class="ind-h"><b>Indicators</b><button class="mini" id="indMin">&ndash;</button></div>
      <div class="ind-b" id="indBody">
        <div class="ind-row"><span class="ind-lab">anchors</span><button id="ancMaster">off</button><span class="ind-note" id="ancAvail"></span></div>
        <div class="ind-row"><span class="ind-lab">levels</span><button data-lvl="high" class="on">High</button><button data-lvl="low" class="on">Low</button></div>
        <div class="ind-row"><span class="ind-lab">sessions</span><span id="ancSess"></span></div>
        <div class="ind-row"><span class="ind-lab">times</span><button id="timesBtn">off</button><span id="timesSess"></span></div>
        <div class="ind-row"><span class="ind-lab">profile</span><button id="vpBtn">off</button><span id="vpSess"></span></div>
        <div class="ind-note">solid = hit &middot; dashed = ongoing &middot; labels: NY/Lo/As + H/L</div>
      </div>
    </div>
  </div>
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
  autoSize:true,
  layout:{background:{color:"#1a1a19"},textColor:"#c3c2b7"},
  grid:{vertLines:{visible:false},horzLines:{visible:false}},
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
  candle.setData(s.candles); vol.setData(s.volume); updateShade(); updateAnchors(); redraw();
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

// ---- session anchors (minimizable Indicators module) ----
const SC=M.session_colors||{}, SESSN=Object.keys(SC), CODE={asia:"As",london:"Lo",newyork:"NY"};
let ancOn=false, ancLvl={high:true,low:true}, ancSess={}, ancLines=[], timesOn=false, timesSess={}, vpOn=false, vpSess={};
SESSN.forEach(s=>{ancSess[s]=true; vpSess[s]=true; timesSess[s]=true;});
function clearAnchors(){ancLines.forEach(s=>chart.removeSeries(s));ancLines=[];}
function updateAnchors(){
  clearAnchors();
  const avail=ancOn&&inst==="NQ"&&(tf==="1m"||tf==="5m");
  document.getElementById("ancAvail").textContent=ancOn?(avail?"":"1m/5m NQ only"):"";
  if(!avail)return;
  const cs=SERIES[inst+"_"+tf].candles, tmin=cs[0].time, tmax=cs[cs.length-1].time;
  for(const L of M.levels){
    if(!ancSess[L.session]||!ancLvl[L.type]||L.stop<tmin||L.start>tmax)continue;
    const s=chart.addLineSeries({color:SC[L.session]||"#888",lineWidth:1,priceLineVisible:false,
      lastValueVisible:false,crosshairMarkerVisible:false,lineStyle:L.hit?0:2});  // solid=hit, dashed=ongoing
    s.setData([{time:Math.max(L.start,tmin),value:L.level},{time:(L.hit?L.stop:tmax),value:L.level}]);
    s.setMarkers([{time:Math.max(L.start,tmin),position:L.type==="high"?"aboveBar":"belowBar",
      color:SC[L.session]||"#888",shape:"circle",text:CODE[L.session]+" "+(L.type==="high"?"H":"L")}]);
    ancLines.push(s);
  }
}
// SVG overlay: vertical session lines (times) + per-session volume-profile histogram
const NSV="http://www.w3.org/2000/svg", vpsvg=document.getElementById("vpsvg"), chartEl=document.getElementById("chart");
function clearVP(){while(vpsvg.firstChild)vpsvg.removeChild(vpsvg.firstChild);}
function _ln(x1,y1,x2,y2,c,w,op,dash){const l=document.createElementNS(NSV,"line");
  l.setAttribute("x1",x1);l.setAttribute("y1",y1);l.setAttribute("x2",x2);l.setAttribute("y2",y2);
  l.setAttribute("stroke",c);l.setAttribute("stroke-width",w);l.setAttribute("stroke-opacity",op);
  if(dash)l.setAttribute("stroke-dasharray",dash);return l;}
function redraw(){
  clearVP();
  if(!(inst==="NQ"&&(tf==="1m"||tf==="5m")))return;
  const ts=chart.timeScale(), box=chartEl.getBoundingClientRect(), H=box.height;
  vpsvg.setAttribute("viewBox",`0 0 ${box.width} ${H}`);
  let nT=0, nTvis=0;
  if(timesOn) for(const S of (M.sessions||[])){if(!timesSess[S.session])continue;const c=SC[S.session]||"#888";
    for(const sp of [[S.open,0.75],[S.close,0.42]]){nT++;const x=ts.timeToCoordinate(sp[0]);
      if(x!=null){nTvis++;vpsvg.appendChild(_ln(x,0,x,H,c,1,sp[1],"3 3"));}}}
  if(timesOn)console.log(`%c[times] sessions=${(M.sessions||[]).length} candidates=${nT} drawn=${nTvis} tf=${tf} inst=${inst}`,"color:#4a9bff");
  if(vpOn) for(const P of (M.profiles||[])){
    if(!vpSess[P.session]||!P.bins||!P.bins.length)continue;
    const x0=ts.timeToCoordinate(P.start), x1=ts.timeToCoordinate(P.end);
    if(x0==null||x1==null)continue;
    const w=Math.max(8,x1-x0), c=SC[P.session]||"#888", mx=Math.max(...P.bins.map(b=>b.v))||1;
    const y0=candle.priceToCoordinate(P.bins[0].p), y1=P.bins.length>1?candle.priceToCoordinate(P.bins[1].p):null;
    const step=(y0!=null&&y1!=null)?Math.max(1,Math.abs(y0-y1)):3;
    const xr=Math.round(x0), hh=Math.max(1,Math.round(step)-1);  // pixel-snapped + 1px row gap = crisp
    for(const b of P.bins){const y=candle.priceToCoordinate(b.p);if(y==null)continue;
      const r=document.createElementNS(NSV,"rect");
      r.setAttribute("x",xr);r.setAttribute("y",Math.round(y-step/2));
      r.setAttribute("width",Math.max(1,Math.round(b.v/mx*w)));r.setAttribute("height",hh);
      r.setAttribute("fill", b.p<=P.poc?"#3f8cff":"#e08a3c");                 // C: blue below POC, orange above
      r.setAttribute("fill-opacity",Math.min(0.9,0.14+0.78*(b.v/mx)));        // fade by volume -> stays clean when spread
      vpsvg.appendChild(r);}
    const yp=candle.priceToCoordinate(P.poc);
    if(yp!=null)vpsvg.appendChild(_ln(x0,yp,x1,yp,"#e34948",1.2,0.95));        // POC line (red)
  }
}
chart.timeScale().subscribeVisibleLogicalRangeChange(redraw);
new ResizeObserver(redraw).observe(chartEl);
document.getElementById("indMin").onclick=function(){const m=document.getElementById("indBody").classList.toggle("min");this.textContent=m?"+":"–";};
document.getElementById("ancMaster").onclick=function(){ancOn=!ancOn;this.classList.toggle("on",ancOn);this.textContent=ancOn?"on":"off";updateAnchors();};
document.querySelectorAll("[data-lvl]").forEach(b=>b.onclick=function(){ancLvl[this.dataset.lvl]=!ancLvl[this.dataset.lvl];this.classList.toggle("on",ancLvl[this.dataset.lvl]);updateAnchors();});
document.getElementById("ancSess").innerHTML=SESSN.map(s=>
  `<button data-s="${s}" class="on" style="border-color:${SC[s]}"><span class="sw" style="background:${SC[s]}"></span>${s}</button>`).join("");
document.querySelectorAll("[data-s]").forEach(b=>b.onclick=function(){ancSess[this.dataset.s]=!ancSess[this.dataset.s];this.classList.toggle("on",ancSess[this.dataset.s]);updateAnchors();});
document.getElementById("timesBtn").onclick=function(){timesOn=!timesOn;this.classList.toggle("on",timesOn);this.textContent=timesOn?"on":"off";redraw();};
document.getElementById("timesSess").innerHTML=SESSN.map(s=>
  `<button data-ts="${s}" class="on" style="border-color:${SC[s]}"><span class="sw" style="background:${SC[s]}"></span>${s}</button>`).join("");
document.querySelectorAll("[data-ts]").forEach(b=>b.onclick=function(){timesSess[this.dataset.ts]=!timesSess[this.dataset.ts];this.classList.toggle("on",timesSess[this.dataset.ts]);redraw();});
document.getElementById("vpBtn").onclick=function(){vpOn=!vpOn;this.classList.toggle("on",vpOn);this.textContent=vpOn?"on":"off";redraw();};
document.getElementById("vpSess").innerHTML=SESSN.map(s=>
  `<button data-vs="${s}" class="on" style="border-color:${SC[s]}"><span class="sw" style="background:${SC[s]}"></span>${s}</button>`).join("");
document.querySelectorAll("[data-vs]").forEach(b=>b.onclick=function(){vpSess[this.dataset.vs]=!vpSess[this.dataset.vs];this.classList.toggle("on",vpSess[this.dataset.vs]);redraw();});

// sidebar
function onoff(f){return f.on?`<span class="on-pill">ON</span>`:`<span class="off-pill">off</span>`;}
document.getElementById("filters").innerHTML=
  kv("session "+onoff(C.filter_session), C.filter_session.allow.join(", "))+
  kv("hour "+onoff(C.filter_hour), C.filter_hour.on?C.filter_hour.allow.join(","):"—")+
  kv("day_vol "+onoff(C.filter_day_vol), C.filter_day_vol.on?C.filter_day_vol.regimes.join(","):"—");
function renderCfg(){document.getElementById("cfgSel").innerHTML=Object.keys(M.configs).map(k=>
  `<button data-c="${k}" class="${k==cfgSel?'on':''}">${k}</button>`).join("");
  document.querySelectorAll("[data-c]").forEach(b=>b.onclick=()=>{cfgSel=b.dataset.c;renderCfg();renderCfgSidebar();updateShade();logConfig();});
  document.getElementById("cfgLoaded").innerHTML=`<span class="dot"></span>${cfgSel} attached &amp; loaded`;}
function logConfig(){const cc=M.configs[cfgSel];
  console.log(`%c[simplicity] CONFIG LOADED -> ${cfgSel}`,"color:#199e70;font-weight:bold;font-size:13px");
  console.table({
    source:cc.label, note:cc.note,
    "vol-day overlay (days)":cc.selected_days.length, "vol-day overlay (periods)":cc.selected_runs.length,
    "session filter":C.filter_session.on?C.filter_session.allow.join(","):"off",
    "hour filter":C.filter_hour.on?C.filter_hour.allow.join(","):"off",
    "day_vol filter":C.filter_day_vol.on?C.filter_day_vol.regimes.join(","):"off",
    era_start:C.era_start, vol_metric:C.vol_metric, trail_window:C.trail_window+"d",
    instrument:inst, timeframe:tf});
  console.log("  first selected days:",cc.selected_days.slice(0,8),`... (${cc.selected_days.length} total)`);}
function renderCfgSidebar(){const cc=M.configs[cfgSel];
  document.getElementById("cfg").innerHTML=
    kv("config",`<span class="pill">${cfgSel}</span>`)+kv("&rarr;",cc.label)+
    kv("vol-days",cc.selected_days.length+" d / "+cc.selected_runs.length+" periods")+
    kv("note",cc.note)+kv("era start",C.era_start)+kv("vol metric",C.vol_metric)+
    kv("trail window",C.trail_window+"d")+kv("regime pctiles",C.regime_pctiles.join(" / "));}
renderCfg(); renderCfgSidebar(); logConfig();
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
