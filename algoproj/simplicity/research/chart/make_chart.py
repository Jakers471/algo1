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
.smod{position:absolute;z-index:9;top:52px;left:52px;width:604px;background:rgba(20,22,27,.985);
border:1px solid var(--ring);border-radius:10px;box-shadow:0 10px 34px rgba(0,0,0,.6);display:none}
.smod-h{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid var(--ring);cursor:move;user-select:none}
.smod-h b{font-weight:600}.smod-h .mut{color:var(--mut);font-size:11px}
.smod-tag{font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 7px;border-radius:11px;border:1px solid}
.smod-x{margin-left:auto;cursor:pointer;color:var(--mut);font-size:16px;line-height:1;padding:0 3px}.smod-x:hover{color:var(--ink)}
.smod-svg{padding:6px 8px 2px}.smod-svg svg{display:block;width:100%;height:auto}
.smod-cols{display:flex;gap:14px;padding:4px 14px 9px}
.mcol{flex:1}.mttl{color:var(--mut);font-size:10px;letter-spacing:.4px;text-transform:uppercase;margin-bottom:5px}
.mr{display:flex;justify-content:space-between;gap:6px;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.mr span{color:var(--mut)}.mr b{font-weight:600}
.smod-v{padding:7px 14px;border-top:1px solid var(--ring);color:var(--ink2);font-size:11.5px}
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
    <div class="smod" id="smod"></div>
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
const smod=document.getElementById("smod");
document.getElementById("modBtn").onclick=function(){modOn=!modOn;this.classList.toggle("on",modOn);
  this.textContent=modOn?"on":"off";chartEl.style.cursor=modOn?"help":"";if(!modOn)smod.style.display="none";};
function _profAt(t){return (M.profiles||[]).find(P=>t>=P.start&&t<=P.end&&P.bins&&P.bins.length);}
function fmtET(t){return _t12(t)+" "+new Date(t*1000).toLocaleDateString("en-US",{..._TZ,month:"short",day:"numeric"});}
function fmtDur(s){s=Math.max(0,Math.round(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}h ${m}m`:`${m}m`;}
function mrow(k,v,c){return `<div class="mr"><span>${k}</span><b style="${c?`color:${c}`:''}">${v}</b></div>`;}
function moduleSVG(P,cs){
  const CW=588,CH=248, CL=44,CR=356,CT=14,CB=228, VPR=536,VPW=150, rs=2.0;
  const lo=P.low,hi=P.high, pad=Math.max((hi-lo)*0.08,1), tp=hi+pad, bp=lo-pad;
  const Y=p=>CT+(tp-p)/(tp-bp)*(CB-CT), barH=Math.max(1.4,(CB-CT)*rs/(tp-bp)-1);
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
  for(const b of P.bins){const w=b.v/mx*VPW, col=Math.abs(b.p-P.poc)<rs/2?"#e34948":(b.p<=P.poc?"#3f8cff":"#e08a3c");
    e+=`<rect x="${(VPR-w).toFixed(1)}" y="${(Y(b.p)-barH/2).toFixed(1)}" width="${w.toFixed(1)}" height="${barH.toFixed(1)}" fill="${col}" fill-opacity="${(0.3+0.65*(b.v/mx)).toFixed(2)}"/>`;}
  return `<svg viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="xMidYMid meet">${e}</svg>`;
}
function openModule(P){
  const cs=SERIES["NQ_"+tf].candles.filter(c=>c.time>=P.start&&c.time<=P.end);
  const s=P.shape||{}, z=P.zone||{}, col=SC[P.session]||"#888", okc=v=>v?"var(--up)":"var(--dn)";
  const gap=P.next_open!=null?P.next_open-P.end:null;
  const timing=mrow("opened",fmtET(P.start))+mrow("closed",fmtET(P.end))+mrow("duration",fmtDur(P.duration_sec))
    +(P.next_session?mrow("next",P.next_session+" &middot; "+fmtDur(gap))+mrow("opens",fmtET(P.next_open)):mrow("next","&mdash;"));
  const shape=(s.shape_score!=null)?(mrow("score",s.shape_score+"/100",okc(s.shape_ok))+mrow("VA % range",s.va_pct+"%")
    +mrow("prominence",s.prominence+"x")+mrow("peaks",s.n_peaks)+mrow("POC pos",s.poc_pos)):mrow("&mdash;","n/a");
  const zone=(z.rr!=null)?(mrow("R:R",z.rr,okc(z.rr_ok))+mrow("risk 1R",z.risk_pts+" pt")+mrow("room",z.room_pts+" pt")
    +mrow("height",z.height_pct+"%")+mrow("entry tf",z.entry_tf)):mrow("&mdash;","n/a");
  const verdict=(s.shape_ok?"clean single-peak":"scattered / not clean")+" &middot; R:R "+(z.rr!=null?z.rr:"?")
    +(z.rr_ok?" worth it":" too thin")+(z.entry_tf?" &rarr; entry on "+z.entry_tf:"");
  smod.innerHTML=`<div class="smod-h" id="smodH">
      <span class="smod-tag" style="color:${col};border-color:${col}">${P.session}</span>
      <b>${P.date}</b><span class="mut">${P.bars} x ${tf}</span><span class="smod-x" id="smodX">&times;</span></div>
    <div class="smod-svg">${moduleSVG(P,cs)}</div>
    <div class="smod-cols"><div class="mcol"><div class="mttl">Timing (ET)</div>${timing}</div>
      <div class="mcol"><div class="mttl">Shape</div>${shape}</div>
      <div class="mcol"><div class="mttl">Zone &mdash; R:R</div>${zone}</div></div>
    <div class="smod-v">${verdict}</div>`;
  const box=chartEl.getBoundingClientRect();
  smod.style.left=Math.min(Math.max(8,modPt.x-300),Math.max(8,box.width-612))+"px";
  smod.style.top=Math.min(Math.max(8,modPt.y+14),Math.max(8,box.height-330))+"px";
  smod.style.display="block";
  document.getElementById("smodX").onclick=()=>smod.style.display="none";
  _dragify(document.getElementById("smodH"));
}
function _dragify(handle){let sx,sy,ox,oy,drag=false;
  handle.onmousedown=e=>{if(e.target.id==="smodX")return;drag=true;sx=e.clientX;sy=e.clientY;ox=smod.offsetLeft;oy=smod.offsetTop;e.preventDefault();};
  const mv=e=>{if(!drag)return;smod.style.left=(ox+e.clientX-sx)+"px";smod.style.top=(oy+e.clientY-sy)+"px";};
  window.addEventListener("mousemove",mv);window.addEventListener("mouseup",()=>drag=false);}
chart.subscribeClick(p=>{if(!modOn||p.time==null||!(inst==="NQ"&&(tf==="1m"||tf==="5m")))return;
  if(p.point)modPt=p.point;const P=_profAt(p.time);if(P)openModule(P);});
// #demo -> auto-open the latest session card (for screenshots / quick check)
if(location.hash==="#demo")window.addEventListener("load",()=>{tf="5m";load();
  const b=document.getElementById("modBtn");modOn=true;b.classList.add("on");b.textContent="on";
  const P=(M.profiles||[]).filter(p=>p.bins&&p.bins.length).slice(-1)[0];
  if(P)setTimeout(()=>{modPt={x:700,y:70};openModule(P);},250);});

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
