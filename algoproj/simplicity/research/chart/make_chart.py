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
.smodstack{position:absolute;z-index:9;top:52px;right:10px;width:474px;max-height:calc(100% - 62px);
background:rgba(12,13,17,.72);border:1px solid var(--ring);border-radius:12px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 10px 34px rgba(0,0,0,.55)}
.stack-h{display:flex;align-items:center;gap:8px;padding:6px 11px;border-bottom:1px solid var(--ring)}
.stack-h b{font-size:12px}.stack-b{overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:8px}
.smod{background:rgba(20,22,27,.985);border:1px solid var(--ring);border-radius:10px}
.smod-r{margin-left:auto;display:flex;gap:5px}
.smod-h{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--ring);user-select:none}
.smod-h b{font-weight:600}.smod-h .mut{color:var(--mut);font-size:11px}
.smod-tag{font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 7px;border-radius:11px;border:1px solid}
.smod-x{margin-left:auto;cursor:pointer;color:var(--mut);font-size:16px;line-height:1;padding:0 3px}.smod-x:hover{color:var(--ink)}
.smod-svg{padding:6px 8px 2px}.smod-svg svg{display:block;width:100%;height:auto}
.smod-cols{display:flex;gap:14px;padding:4px 14px 9px}
.mcol{flex:1}.mttl{color:var(--mut);font-size:10px;letter-spacing:.4px;text-transform:uppercase;margin-bottom:5px}
.mr{display:flex;justify-content:space-between;gap:6px;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.mr span{color:var(--mut)}.mr b{font-weight:600}
.smod-v{padding:7px 14px;border-top:1px solid var(--ring);color:var(--ink2);font-size:11.5px}
.smod-chat{cursor:pointer;color:var(--acc);font-size:10.5px;border:1px solid var(--acc);border-radius:6px;
padding:2px 8px;background:rgba(57,135,229,.14);white-space:nowrap}.smod-chat:hover{background:var(--acc);color:#fff}
.chatd{position:fixed;top:0;right:0;height:100%;width:376px;background:#141419;border-left:1px solid var(--ring);
z-index:20;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .18s ease;box-shadow:-8px 0 30px rgba(0,0,0,.55)}
.chatd.open{transform:none}
.chatd-h{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--ring)}
.chatd-h b{font-size:13px}.chatd-h .mut{color:var(--mut);font-size:11px}
.chatd-tools{margin-left:auto;display:flex;gap:5px}
.chatd-b{flex:1;overflow:auto;padding:10px 11px;display:flex;flex-direction:column;gap:10px}
.chatd-empty{color:var(--mut);font-size:12px;padding:26px 16px;text-align:center;line-height:1.6}
.centry{border:1px solid var(--ring);border-radius:8px;background:rgba(255,255,255,.02)}
.centry-h{display:flex;align-items:center;gap:7px;padding:7px 9px;border-bottom:1px solid var(--ring)}
.centry-h b{font-weight:600}.centry-h .mut{color:var(--mut);font-size:11px}
.centry-stat{padding:7px 9px;font-size:11px;color:var(--ink2);display:grid;grid-template-columns:1fr 1fr;gap:3px 10px}
.centry-stat span{color:var(--mut)}
.centry textarea{width:100%;border:1px solid var(--ring);background:#0d0d0d;color:var(--ink);border-radius:6px;
font:inherit;font-size:11.5px;padding:6px;resize:vertical;min-height:42px}
.centry-f{display:flex;gap:6px;padding:7px 9px}
.mini2{font-size:11px;padding:3px 9px}
#_toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--up);color:#fff;
padding:7px 14px;border-radius:7px;z-index:50;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.4);opacity:0;transition:opacity .3s}
.rpc{display:flex;align-items:center;gap:5px;padding:7px 12px;border-top:1px solid var(--ring)}
.rpb{background:var(--s);border:1px solid var(--ring);color:var(--ink2);border-radius:6px;font-size:11px;padding:3px 8px;cursor:pointer;min-width:26px}
.rpb:hover{background:var(--acc);color:#fff;border-color:var(--acc)}
.rpc input[type=range]{flex:1;accent-color:var(--acc);min-width:60px}
.rpc select{background:var(--s);border:1px solid var(--ring);color:var(--ink2);border-radius:6px;font-size:11px;padding:2px}
.rpinfo{color:var(--mut);font-size:10.5px;white-space:nowrap;min-width:94px;text-align:right}
</style></head><body>
<div class="top">
  <h1>simplicity <span style="color:var(--mut);font-weight:400">chart</span></h1>
  <div class="grp"><span class="lab">inst</span><span id="insts"></span></div>
  <div class="grp"><span class="lab">tf</span><span id="tfs"></span></div>
  <div class="grp"><span class="lab">shade</span><button id="shSess">session</button><button id="shVol">vol days</button></div>
  <div class="grp" style="margin-left:auto"><button id="chatBtn">chat log (0)</button></div>
</div>
<div class="chatd" id="chatd">
  <div class="chatd-h"><b>Chat log</b><span class="mut" id="chatCount">0 saved</span>
    <div class="chatd-tools"><button class="mini2" id="chatCopyAll">copy all</button>
      <button class="mini2" id="chatDl">json</button><button class="mini2" id="chatClear">clear</button>
      <button class="mini2" id="chatClose">close</button></div></div>
  <div class="chatd-b" id="chatBody"></div>
</div>
<div class="main">
  <div class="chartwrap">
    <div id="chart"></div>
    <svg id="vpsvg" class="vpsvg"></svg>
    <div class="smodstack" id="smodStack">
      <div class="stack-h"><b>modules</b><span class="mut" id="stackSid"></span><span class="smod-x" id="stackX" style="margin-left:auto">&times;</span></div>
      <div class="stack-b" id="stackBody"></div>
    </div>
    <div class="ind" id="ind">
      <div class="ind-h"><b>Indicators</b><button class="mini" id="indMin">&ndash;</button></div>
      <div class="ind-b" id="indBody">
        <div class="ind-row"><span class="ind-lab">anchors</span><button id="ancMaster">off</button><span class="ind-note" id="ancAvail"></span></div>
        <div class="ind-row"><span class="ind-lab">levels</span><button data-lvl="high" class="on">High</button><button data-lvl="low" class="on">Low</button></div>
        <div class="ind-row"><span class="ind-lab">sessions</span><span id="ancSess"></span></div>
        <div class="ind-row"><span class="ind-lab">times</span><button id="timesBtn">off</button><span id="timesSess"></span></div>
        <div class="ind-row"><span class="ind-lab">profile</span><button id="vpBtn">off</button><span id="vpSess"></span></div>
        <div class="ind-row"><span class="ind-lab">fib</span><button id="fibBtn">off</button><span id="fibSess"></span></div>
        <div class="ind-row"><span class="ind-lab">modules</span><button id="modBtn">off</button><span class="ind-note">click a session &rarr; card</span></div>
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
let ancOn=false, ancLvl={high:true,low:true}, ancSess={}, ancLines=[], timesOn=false, timesSess={}, vpOn=false, vpSess={}, fibOn=false, fibSess={};
SESSN.forEach(s=>{ancSess[s]=true; vpSess[s]=true; timesSess[s]=true; fibSess[s]=true;});
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
  if(fibOn) for(const P of (M.profiles||[])){                                  // fib retracement off session hi/lo
    if(!fibSess[P.session])continue;
    const x0=ts.timeToCoordinate(P.start), x1=ts.timeToCoordinate(P.end);
    if(x0==null||x1==null)continue;
    const c=SC[P.session]||"#888", rng=P.high-P.low;
    for(const rr of [0.236,0.382,0.5,0.618,0.786]){
      const y=candle.priceToCoordinate(P.low+rr*rng); if(y==null)continue;
      const mid=rr===0.5;
      vpsvg.appendChild(_ln(x0,y,x1,y,c,mid?1.4:1,mid?0.9:0.5,mid?null:"1 3"));  // 0.5 solid bright, others dotted faint
    }
  }
  if(typeof drawNow==="function")drawNow();   // replay "now" line survives overlay redraws
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
document.getElementById("fibBtn").onclick=function(){fibOn=!fibOn;this.classList.toggle("on",fibOn);this.textContent=fibOn?"on":"off";redraw();};
document.getElementById("fibSess").innerHTML=SESSN.map(s=>
  `<button data-fs="${s}" class="on" style="border-color:${SC[s]}"><span class="sw" style="background:${SC[s]}"></span>${s}</button>`).join("");
document.querySelectorAll("[data-fs]").forEach(b=>b.onclick=function(){fibSess[this.dataset.fs]=!fibSess[this.dataset.fs];this.classList.toggle("on",fibSess[this.dataset.fs]);redraw();});

// ---- per-session MODULE cards (click a session -> crisp profile + timing + scores) ----
let modOn=false, modPt={x:400,y:70};
const smodStack=document.getElementById("smodStack"), stackBody=document.getElementById("stackBody");
document.getElementById("modBtn").onclick=function(){modOn=!modOn;this.classList.toggle("on",modOn);
  this.textContent=modOn?"on":"off";chartEl.style.cursor=modOn?"help":"";if(!modOn)smodStack.style.display="none";};
document.getElementById("stackX").onclick=()=>{smodStack.style.display="none";replayStop();};
function _profAt(t){return (M.profiles||[]).find(P=>t>=P.start&&t<=P.end&&P.bins&&P.bins.length);}
function fmtET(t){return _t12(t)+" "+new Date(t*1000).toLocaleDateString("en-US",{..._TZ,month:"short",day:"numeric"});}
function fmtDur(s){s=Math.max(0,Math.round(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}h ${m}m`:`${m}m`;}
function mrow(k,v,c){return `<div class="mr"><span>${k}</span><b style="${c?`color:${c}`:''}">${v}</b></div>`;}
function moduleSVG(P,cs){
  const CW=588,CH=178, CL=44,CR=356,CT=10,CB=162, VPR=536,VPW=150, rs=2.0;
  const lo=P.low,hi=P.high, pad=Math.max((hi-lo)*0.08,1), tp=hi+pad, bp=lo-pad;
  const rowsz=(P.bins&&P.bins.length>1)?Math.abs(P.bins[1].p-P.bins[0].p):rs;
  const Y=p=>CT+(tp-p)/(tp-bp)*(CB-CT), barH=Math.max(1.2,(CB-CT)*rowsz/(tp-bp)-0.5);
  let e=`<rect x="${CL}" y="${Y(P.vah).toFixed(1)}" width="${VPR-CL}" height="${Math.max(1,Y(P.val)-Y(P.vah)).toFixed(1)}" fill="#fff" fill-opacity="0.04"/>`;
  for(const [p,c,dash,lab] of [[P.high,"#59626e","","H"],[P.low,"#59626e","","L"],[P.vah,"#8a94a6","4 3","VAH"],[P.val,"#8a94a6","4 3","VAL"],[P.poc,"#e34948","","POC"]]){
    const yy=Y(p).toFixed(1);
    e+=`<line x1="${CL}" y1="${yy}" x2="${VPR}" y2="${yy}" stroke="${c}" stroke-width="${lab=="POC"?1.3:1}"${dash?` stroke-dasharray="${dash}"`:""}/>`;
    e+=`<text x="${VPR+4}" y="${(+yy+3).toFixed(1)}" fill="${c}" font-size="9.5">${lab} ${p.toFixed(0)}</text>`;}
  const n=cs.length, step=(CR-CL)/Math.max(n,1), bw=Math.min(8,step*0.7);
  cs.forEach((r,i)=>{const x=CL+(i+0.5)*step, col=r.close>=r.open?"#199e70":"#e66767";
    e+=`<line x1="${x.toFixed(1)}" y1="${Y(r.high).toFixed(1)}" x2="${x.toFixed(1)}" y2="${Y(r.low).toFixed(1)}" stroke="${col}" stroke-width="1"/>`;
    const yo=Y(r.open),yc=Y(r.close);
    e+=`<rect x="${(x-bw/2).toFixed(1)}" y="${Math.min(yo,yc).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1,Math.abs(yc-yo)).toFixed(1)}" fill="${col}"/>`;});
  const mx=Math.max(...P.bins.map(b=>b.v))||1;
  for(const b of P.bins){const w=b.v/mx*VPW, col=Math.abs(b.p-P.poc)<rowsz/2?"#e34948":(b.p<=P.poc?"#3f8cff":"#e08a3c");
    e+=`<rect x="${(VPR-w).toFixed(1)}" y="${(Y(b.p)-barH/2).toFixed(1)}" width="${w.toFixed(1)}" height="${barH.toFixed(1)}" fill="${col}" fill-opacity="${(0.3+0.65*(b.v/mx)).toFixed(2)}"/>`;}
  return `<svg viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="xMidYMid meet">${e}</svg>`;
}
// one card in the stack. kind = "htf" | "session" | "base"; opts = {isReplay, replayControls}
function cardHTML(meta,prof,cs,kind,opts){
  opts=opts||{};
  const s=prof.shape||{}, z=prof.zone||{}, okc=v=>v?"var(--up)":"var(--dn)";
  const gap=meta.next_open!=null?meta.next_open-meta.end:null;
  const timing=mrow("opened",fmtET(meta.start))+mrow("closed",fmtET(meta.end))+mrow("span",fmtDur(meta.duration_sec))
    +(meta.next_session?mrow("next",meta.next_session+" &middot; "+fmtDur(gap)):mrow("next","&mdash;"));
  const shape=(s.shape_score!=null)?(mrow("score",s.shape_score+"/100",okc(s.shape_ok))+mrow("VA % range",s.va_pct+"%")
    +mrow("prominence",s.prominence+"x")+mrow("peaks",s.n_peaks)):mrow("&mdash;","forming");
  const zone=(z.rr!=null)?(mrow("R:R",z.rr,okc(z.rr_ok))+mrow("risk 1R",z.risk_pts+" pt")+mrow("room",z.room_pts+" pt")
    +mrow("entry tf",z.entry_tf)):mrow("&mdash;","forming");
  const acc={htf:"#9a7cff",session:(SC[meta.session]||"#4a9bff"),base:"#e0a94a"}[kind];
  const lab={htf:" &middot; HTF week",session:"",base:" &middot; BASE"}[kind];
  const barsLab=meta.barsLabel||(meta.bars+" x "+tf);
  const rlab=opts.isReplay?' &middot; <b style="color:#f0b000">REPLAY</b>':'';
  const btns=(kind==="session"&&!opts.isReplay)
    ?'<span class="smod-chat" data-act="chat">chat</span><span class="smod-chat" data-act="replay">replay</span>':'';
  return `<div class="smod" data-k="${kind}">
    <div class="smod-h"><span class="smod-tag" style="color:${acc};border-color:${acc}">${meta.session}${lab}</span>
      <b>${meta.date}</b><span class="mut">${barsLab}${rlab}</span><span class="smod-r">${btns}</span></div>
    <div class="smod-svg">${moduleSVG(prof,cs)}</div>
    <div class="smod-cols"><div class="mcol"><div class="mttl">Timing</div>${timing}</div>
      <div class="mcol"><div class="mttl">Shape</div>${shape}</div>
      <div class="mcol"><div class="mttl">Zone &mdash; R:R</div>${zone}</div></div>${opts.replayControls||''}</div>`;
}
function _meta(P,cs,extra){return Object.assign({session:P.session,date:P.date,start:cs[0].time,end:cs[cs.length-1].time,
  duration_sec:cs[cs.length-1].time-cs[0].time,next_session:P.next_session,next_open:P.next_open,bars:cs.length},extra||{});}
// render the whole stack (HTF top -> session -> base). rp = null (static) or {k, ctrls} for replay.
function renderStack(P,rp){
  const sess=SERIES["NQ_5m"].candles.filter(c=>c.time>=P.start&&c.time<=P.end);
  let html="";
  if(P.htf){const h=P.htf, hcs=SERIES["NQ_5m"].candles.filter(c=>c.time>=h.start&&c.time<=h.end);
    const hm={session:P.session,date:P.date,start:h.start,end:h.end,duration_sec:h.end-h.start,
      next_session:P.next_session,next_open:P.next_open,bars:h.htf_bars,barsLabel:h.htf_days+"d week (context)"};
    html+=cardHTML(hm,h,hcs,"htf",{});}                                   // HTF is fixed pre-session context
  const scs=rp?sess.slice(0,rp.k):sess;
  const sp=rp?(computeProfile(scs)||{high:P.high,low:P.low,poc:P.poc,val:P.val,vah:P.vah,bins:[],va_pct_of_range:0,height_pct:0,shape:{},zone:{},bars:scs.length}):P;
  html+=cardHTML(_meta(P,scs),sp,scs,"session",{isReplay:!!rp,replayControls:rp?rp.ctrls:''});
  let bp=null,bcs=null,bm=null;
  if(rp){const bw=computeBase(scs); if(bw&&bw.length>=3){bp=computeProfile(bw); if(bp){bcs=bw;bm=_meta(P,bw);}}}
  else if(P.base){bp=P.base;bcs=sess.filter(c=>c.time>=P.base.start&&c.time<=P.base.end);bm=_meta(P,bcs);}
  if(bp&&bcs&&bcs.length)html+=cardHTML(bm,bp,bcs,"base",{});
  stackBody.innerHTML=html;
  const cb=stackBody.querySelector('[data-act="chat"]');if(cb)cb.onclick=()=>addToChat(P);
  const rb=stackBody.querySelector('[data-act="replay"]');if(rb)rb.onclick=()=>replayStart(P);
  document.getElementById("stackSid").innerHTML=`${P.session} &middot; ${P.date}`;
  smodStack.style.display="flex";
}
function openModule(P){replayStop();renderStack(P,null);}
// ---- causal recompute (JS port of volume_profile / shape_filter / zone_calibration) ----
function computeProfile(bars){
  if(bars.length<2)return null;
  let hi=-1e18,lo=1e18;for(const b of bars){if(b.high>hi)hi=b.high;if(b.low<lo)lo=b.low;}
  if(hi<=lo)return null;
  const ROW=2.0, nb=Math.max(3,Math.round((hi-lo)/ROW)), edges=[];
  for(let i=0;i<=nb;i++)edges.push(lo+(hi-lo)*i/nb);
  const centers=[];for(let i=0;i<nb;i++)centers.push((edges[i]+edges[i+1])/2);
  const vbin=new Array(nb).fill(0);
  for(const b of bars){const idx=[];for(let i=0;i<nb;i++)if(centers[i]>=b.low&&centers[i]<=b.high)idx.push(i);
    if(idx.length===0){let j=Math.floor(((b.low+b.high)/2-lo)/(hi-lo)*nb);j=Math.min(nb-1,Math.max(0,j));vbin[j]+=b.volume;}
    else{const sh=b.volume/idx.length;for(const j of idx)vbin[j]+=sh;}}
  const total=vbin.reduce((a,b)=>a+b,0);if(total<=0)return null;
  let poc=0;for(let i=1;i<nb;i++)if(vbin[i]>vbin[poc])poc=i;
  let li=poc,ui=poc,acc=vbin[poc];const target=total*0.7;
  while(acc<target&&(li>0||ui<nb-1)){const up=ui<nb-1?vbin[ui+1]:-1,dn=li>0?vbin[li-1]:-1;
    if(up>=dn){ui++;acc+=vbin[ui];}else{li--;acc+=vbin[li];}}
  const pocpx=centers[poc],val=edges[li],vah=edges[ui+1],rng=hi-lo,va=vah-val;
  const bins=[];for(let i=0;i<nb;i++)if(vbin[i]>0)bins.push({p:+centers[i].toFixed(2),v:+vbin[i].toFixed(1),va:val<=centers[i]&&centers[i]<=vah});
  const prof={high:+hi.toFixed(2),low:+lo.toFixed(2),poc:+pocpx.toFixed(2),val:+val.toFixed(2),vah:+vah.toFixed(2),
    bins,height_pct:+(rng/lo*100).toFixed(3),va_pct_of_range:+(va/rng*100).toFixed(1),bars:bars.length};
  prof.shape=computeShape(prof);prof.zone=computeZone(prof);return prof;
}
// gate params from config (injected by build_chart_data) so replay/scoring match strategy_config exactly
const GT=(C.gates&&C.gates.SHAPE)||{weights:{tight:.4,peak:.3,single:.2,central:.1},tight_peak:40,tight_hi:85,prom_den:2,single_2:.5,single_else:.15,shape_ok:50};
const GZ=(C.gates&&C.gates.ZONE)||{rr_min:2,tf_bands:[[0.25,"1m"],[0.60,"5m"],[null,"15m"]]};
const GB=(C.gates&&C.gates.BASE)||{band_mult:5,min_bars:8};
function computeShape(p){const bins=p.bins;if(bins.length<3)return{};
  const v=bins.map(b=>b.v),total=v.reduce((a,b)=>a+b,0),pocv=Math.max(...v),meanv=total/v.length;
  const vav=bins.filter(b=>b.va).map(b=>b.v),vam=vav.length?vav.reduce((a,b)=>a+b,0)/vav.length:meanv;
  const prom=vam>0?pocv/vam:0;let peaks=0;
  for(let i=0;i<v.length;i++){const l=i>0?v[i-1]:-1,r=i<v.length-1?v[i+1]:-1;if(v[i]>=l&&v[i]>=r&&v[i]>0.5*pocv)peaks++;}
  const va_pct=p.va_pct_of_range,rng=p.high-p.low,pos=rng>0?(p.poc-p.low)/rng:0.5,bal=Math.abs(pos-0.5),top=pocv/total*100;
  const W=GT.weights,tp=GT.tight_peak,th=GT.tight_hi;
  const tight=(va_pct<=tp)?(va_pct/tp):Math.max(0,1-(va_pct-tp)/(th-tp)),peakc=Math.min(1,Math.max(0,(prom-1)/GT.prom_den)),
    single=peaks<=1?1:(peaks==2?GT.single_2:GT.single_else),central=Math.max(0,1-bal/0.5);
  const score=Math.round(100*(W.tight*tight+W.peak*peakc+W.single*single+W.central*central));
  return{shape_score:score,va_pct:+va_pct.toFixed(1),prominence:+prom.toFixed(2),n_peaks:peaks,poc_pos:+pos.toFixed(2),top_share_pct:+top.toFixed(1),shape_ok:score>=GT.shape_ok};
}
function computeZone(p){const rng=p.high-p.low,va=p.vah-p.val;if(rng<=0||va<=0)return{};
  const rr=+(rng/va).toFixed(2),h=p.height_pct;let etf="15m";for(const b of GZ.tf_bands){if(b[0]==null||h<b[0]){etf=b[1];break;}}
  return{height_pct:+h.toFixed(3),bars:p.bars,risk_pts:+va.toFixed(1),room_pts:+rng.toFixed(1),rr,entry_tf:etf,rr_ok:rr>=GZ.rr_min};
}
// ---- base detector (JS port of base_profile.detect) so the base card recomputes live in replay ----
function computeBase(bars){const mb=GB.min_bars,n=bars.length;if(n<mb)return null;
  const rr=bars.map(b=>b.high-b.low).slice().sort((a,b)=>a-b), med=rr[Math.floor(n/2)], band=GB.band_mult*med;
  let end=n-1,wl=bars[end].low,wh=bars[end].high,start=end;
  for(let i=end-1;i>=0;i--){const nwl=Math.min(wl,bars[i].low),nwh=Math.max(wh,bars[i].high);
    if(nwh-nwl>band)break;wl=nwl;wh=nwh;start=i;}
  return (end-start+1>=mb)?bars.slice(start,end+1):null;}
// ---- REPLAY: step the session bar-by-bar; session + base recompute on bars-so-far, HTF is static context ----
let RP={active:false,P:null,bars:[],k:0,N:0,playing:false,timer:null,speed:1};
function replayStop(){if(RP.timer){clearInterval(RP.timer);RP.timer=null;}RP.active=false;RP.playing=false;drawNow();}
function replayStart(P){const cs=SERIES["NQ_5m"].candles.filter(c=>c.time>=P.start&&c.time<=P.end);
  if(cs.length<3)return;if(RP.timer)clearInterval(RP.timer);
  RP={active:true,P,bars:cs,k:Math.min(cs.length,5),N:cs.length,playing:false,timer:null,speed:RP.speed||1};
  replayRender();}
function replayRender(){const bb=RP.bars[RP.k-1],tlab=bb?_t12(bb.time):"";
  const ctrls=`<div class="rpc">
    <button class="rpb" data-rp="start">|&lt;</button><button class="rpb" data-rp="back">&lt;</button>
    <button class="rpb" id="rpPlay">${RP.playing?"pause":"play"}</button>
    <button class="rpb" data-rp="fwd">&gt;</button><button class="rpb" data-rp="end">&gt;|</button>
    <input type="range" id="rpScrub" min="1" max="${RP.N}" value="${RP.k}">
    <span class="rpinfo">bar ${RP.k}/${RP.N} &middot; ${tlab}</span>
    <select id="rpSpeed"><option value="1">1x</option><option value="2">2x</option><option value="4">4x</option></select></div>`;
  renderStack(RP.P,{k:RP.k,ctrls});
  stackBody.querySelectorAll("[data-rp]").forEach(x=>x.onclick=()=>replayGo(x.dataset.rp));
  const pl=document.getElementById("rpPlay");if(pl)pl.onclick=replayToggle;
  const sc=document.getElementById("rpScrub");if(sc)sc.oninput=()=>{RP.k=+sc.value;replayRender();};
  const sp=document.getElementById("rpSpeed");if(sp){sp.value=RP.speed;sp.onchange=()=>{RP.speed=+sp.value;if(RP.playing){replayPause();replayPlay();}};}
  drawNow();}
function replayGo(cmd){if(cmd==="start")RP.k=Math.min(RP.N,5);else if(cmd==="back")RP.k=Math.max(3,RP.k-1);
  else if(cmd==="fwd")RP.k=Math.min(RP.N,RP.k+1);else if(cmd==="end")RP.k=RP.N;replayRender();}
function replayToggle(){RP.playing?replayPause():replayPlay();}
function replayPlay(){RP.playing=true;RP.timer=setInterval(()=>{if(RP.k>=RP.N){replayPause();return;}RP.k++;replayRender();},700/RP.speed);replayRender();}
function replayPause(){RP.playing=false;if(RP.timer){clearInterval(RP.timer);RP.timer=null;}replayRender();}
function drawNow(){const old=document.getElementById("_nowln");if(old)old.remove();
  if(!RP.active||!RP.bars[RP.k-1])return;const x=chart.timeScale().timeToCoordinate(RP.bars[RP.k-1].time);
  if(x==null)return;const box=chartEl.getBoundingClientRect();const l=_ln(x,0,x,box.height,"#f0b000",1.3,0.9);l.setAttribute("id","_nowln");vpsvg.appendChild(l);}
chart.subscribeClick(p=>{if(!modOn||p.time==null||!(inst==="NQ"&&(tf==="1m"||tf==="5m")))return;
  if(p.point)modPt=p.point;const P=_profAt(p.time);if(P)openModule(P);});
// #demo -> auto-open the latest session card (for screenshots / quick check)
if(location.hash.startsWith("#demo"))window.addEventListener("load",()=>{tf="5m";load();
  const b=document.getElementById("modBtn");modOn=true;b.classList.add("on");b.textContent="on";
  const P=(M.profiles||[]).filter(p=>p.bins&&p.bins.length).slice(-1)[0];
  if(P)setTimeout(()=>{modPt={x:560,y:70};openModule(P);if(location.hash==="#demo2"){addToChat(P);}
    if(location.hash==="#demo3"){replayStart(P);RP.k=Math.max(3,Math.floor(RP.N*0.55));replayRender();}},250);});

// ---- CHAT LOG: "chat about" a session -> save its full snapshot to a persistent per-session drawer ----
const CHKEY="simplicity_chat_v1";
let chatLog=JSON.parse(localStorage.getItem(CHKEY)||"[]");
const chatd=document.getElementById("chatd");
function chatSave(){localStorage.setItem(CHKEY,JSON.stringify(chatLog));updateChatCount();}
function updateChatCount(){document.getElementById("chatBtn").textContent=`chat log (${chatLog.length})`;
  document.getElementById("chatCount").textContent=chatLog.length+" saved";}
function copyText(txt,btn,label){const done=()=>{if(btn){btn.textContent="copied!";setTimeout(()=>btn.textContent=label,1200);}};
  if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(txt).then(done).catch(()=>_fbcopy(txt,done));}
  else _fbcopy(txt,done);}
function _fbcopy(txt,done){const ta=document.createElement("textarea");ta.value=txt;ta.style.cssText="position:fixed;opacity:0";
  document.body.appendChild(ta);ta.select();try{document.execCommand("copy");}catch(e){}document.body.removeChild(ta);done&&done();}
function flash(m){let t=document.getElementById("_toast");if(!t){t=document.createElement("div");t.id="_toast";document.body.appendChild(t);}
  t.textContent=m;t.style.opacity="1";clearTimeout(t._h);t._h=setTimeout(()=>t.style.opacity="0",1500);}
function snapOf(P){const cs=SERIES["NQ_"+tf].candles.filter(c=>c.time>=P.start&&c.time<=P.end);
  return {sid:P.sid,session:P.session,date:P.date,tf,start:P.start,end:P.end,
  duration_sec:P.duration_sec,next_session:P.next_session,next_open:P.next_open,high:P.high,low:P.low,
  poc:P.poc,val:P.val,vah:P.vah,height_pct:P.height_pct,va_pct:P.va_pct_of_range,bars:P.bars,
  shape:P.shape||{},zone:P.zone||{},
  bins:(P.bins||[]).map(b=>({p:b.p,v:b.v})),
  ohlc:cs.map(c=>({t:c.time,o:c.open,h:c.high,l:c.low,c:c.close,v:Math.round(c.volume||0)})),note:""};}
function addToChat(P){
  if(chatLog.some(e=>e.sid===P.sid&&e.tf===tf)){openDrawer();renderDrawer();flash("already in chat log");return;}
  chatLog.push(snapOf(P));chatSave();renderDrawer();openDrawer();flash("saved to chat log");}
function chatMarkdown(e){const s=e.shape||{},z=e.zone||{};
  const nxt=e.next_session?`${e.next_session} in ${fmtDur(e.next_open-e.end)} (opens ${fmtET(e.next_open)})`:"— (last session in data)";
  const hm=t=>new Date(t*1000).toLocaleTimeString("en-US",{..._TZ,hour:"2-digit",minute:"2-digit",hour12:false});
  const topN=(e.bins||[]).slice().sort((a,b)=>b.v-a.v).slice(0,10).map(b=>`  ${b.p}: ${Math.round(b.v)}`).join("\n")||"  (none)";
  const ohlc=(e.ohlc||[]).map(c=>`  ${hm(c.t)}  ${c.o}  ${c.h}  ${c.l}  ${c.c}  ${c.v}`).join("\n")||"  (none)";
  return `## ${e.date} ${e.session}  (NQ ${e.tf})

### Timing (ET)
opened ${fmtET(e.start)} | closed ${fmtET(e.end)} | duration ${fmtDur(e.duration_sec)}
next: ${nxt}

### Range & value area
H ${e.high} / L ${e.low}  (${(e.high-e.low).toFixed(1)} pt, ${e.height_pct}% of price) | ${e.bars} bars
POC ${e.poc} | value area ${e.val}–${e.vah} (${e.va_pct}% of range)

### Shape (clean vs foggy)
score ${s.shape_score}/100 (${s.shape_ok?"clean":"foggy"}) | VA% ${s.va_pct} | prominence ${s.prominence}x | peaks ${s.n_peaks} | POC pos ${s.poc_pos} | top-bin ${s.top_share_pct}%

### Zone — R:R geometry
R:R ${z.rr} (${z.rr_ok?"ok":"thin"}) | risk 1R ${z.risk_pts}pt | room ${z.room_pts}pt | entry tf ${z.entry_tf}

### Top volume nodes (price: volume)
${topN}

### OHLC (${e.tf}, ET) — time  O  H  L  C  Volume
${ohlc}

### My question
${e.note||"(none yet)"}`;}
function renderDrawer(){const b=document.getElementById("chatBody");
  if(!chatLog.length){b.innerHTML=`<div class="chatd-empty">No sessions saved yet.<br>Open a session module and hit <b style="color:var(--acc)">chat about</b> to record it here.</div>`;return;}
  b.innerHTML=chatLog.map((e,i)=>{const col=SC[e.session]||"#888",s=e.shape||{},z=e.zone||{};
    return `<div class="centry"><div class="centry-h">
      <span class="smod-tag" style="color:${col};border-color:${col}">${e.session}</span>
      <b>${e.date}</b><span class="mut">${e.tf}</span><span class="smod-x" data-rm="${i}" style="margin-left:auto">&times;</span></div>
      <div class="centry-stat">
        <div><span>shape</span> ${s.shape_score}/100 ${s.shape_ok?"clean":"foggy"}</div><div><span>R:R</span> ${z.rr} ${z.rr_ok?"ok":"thin"}</div>
        <div><span>POC</span> ${e.poc}</div><div><span>VA%range</span> ${e.va_pct}%</div>
        <div><span>duration</span> ${fmtDur(e.duration_sec)}</div><div><span>entry tf</span> ${z.entry_tf||"-"}</div></div>
      <div style="padding:7px 9px 0"><textarea data-note="${i}" placeholder="your question about this session...">${e.note||""}</textarea></div>
      <div class="centry-f"><button class="mini2" data-copy="${i}">copy for chat</button></div></div>`;}).join("");
  b.querySelectorAll("[data-rm]").forEach(x=>x.onclick=()=>{chatLog.splice(+x.dataset.rm,1);chatSave();renderDrawer();});
  b.querySelectorAll("[data-note]").forEach(t=>t.oninput=()=>{chatLog[+t.dataset.note].note=t.value;chatSave();});
  b.querySelectorAll("[data-copy]").forEach(x=>x.onclick=()=>copyText(chatMarkdown(chatLog[+x.dataset.copy]),x,"copy for chat"));}
function openDrawer(){chatd.classList.add("open");}
document.getElementById("chatBtn").onclick=()=>{chatd.classList.toggle("open");renderDrawer();};
document.getElementById("chatClose").onclick=()=>chatd.classList.remove("open");
document.getElementById("chatClear").onclick=()=>{if(chatLog.length&&confirm("Clear all saved sessions?")){chatLog=[];chatSave();renderDrawer();}};
document.getElementById("chatCopyAll").onclick=function(){if(chatLog.length)copyText(chatLog.map(chatMarkdown).join("\n\n---\n\n"),this,"copy all");};
document.getElementById("chatDl").onclick=()=>{if(!chatLog.length)return;const blob=new Blob([JSON.stringify(chatLog,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="simplicity_chat_log.json";a.click();};
updateChatCount();

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
