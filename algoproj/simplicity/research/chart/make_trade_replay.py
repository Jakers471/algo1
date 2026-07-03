"""
make_trade_replay — the trade-by-trade replay page (sibling of make_chart, same look + module stack).

Reads research/chart/data/trades_data.js (built by build_trades.py from the backtest's trades.json — the
SINGLE SOURCE OF TRUTH) and writes trade_replay.html: a self-contained page that lets you STEP THROUGH each
backtest trade and its outcome on a candle chart, with the SAME 3 nested module cards (base ⊂ session ⊂ HTF)
+ target ladder the main chart shows, and the trade's entry / stop / target / exit drawn exactly as simulated.

  * Trade browser  — prev/next, jump, scrubber, filter by outcome (target/stop/time); trade stats panel.
  * On the chart   — entry (gold), stop (red), target (green), coil edges (faint) price lines; entry & exit
                     arrows; a gold "now" line you scrub bar-by-bar from entry to exit.
  * Running R      — mark-to-market R at the current bar; the FINAL R/outcome is the sim's (authoritative).
  * Module stack   — the setup's 3 profiles + ladder (static context that armed the trade), scored by the gates.

Run:  python research/chart/make_trade_replay.py   (after build_trades.py)
Out:  research/chart/trade_replay.html
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>simplicity — trade replay</title>
<script src="lib/lightweight-charts.standalone.production.js"></script>
<script src="data/trades_data.js"></script>
<style>
:root{--s:#1a1a19;--pg:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--ring:rgba(255,255,255,.10);
--acc:#3987e5;--up:#199e70;--dn:#e66767;--gold:#f0b000}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--pg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:14px;padding:9px 15px;border-bottom:1px solid var(--ring);flex-wrap:wrap}
.top h1{font-size:15px;margin:0;font-weight:650}.top h1 span{color:var(--mut);font-weight:400}
.grp{display:flex;gap:5px;align-items:center}.grp .lab{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
button{background:var(--s);border:1px solid var(--ring);color:var(--ink2);font:inherit;font-size:12.5px;padding:5px 10px;border-radius:7px;cursor:pointer}
button.on{background:var(--acc);color:#fff;border-color:var(--acc)}button:disabled{opacity:.3;cursor:default}
button:hover:not(:disabled):not(.on){border-color:var(--acc)}
.nav{display:flex;align-items:center;gap:6px}
.idx{font-variant-numeric:tabular-nums;min-width:104px;text-align:center;font-size:12.5px}
#tScrub{width:220px;accent-color:var(--acc)}
.main{flex:1;display:flex;min-height:0;min-width:0}
.chartwrap{flex:1 1 auto;min-width:0;position:relative;display:flex;flex-direction:column}
#chart{flex:1;position:relative;min-height:0}
.nowsvg{position:absolute;inset:0;pointer-events:none;z-index:3}
.rpc{display:flex;align-items:center;gap:6px;padding:7px 12px;border-top:1px solid var(--ring);background:rgba(20,22,27,.6)}
.rpb{background:var(--s);border:1px solid var(--ring);color:var(--ink2);border-radius:6px;font-size:12px;padding:4px 9px;cursor:pointer;min-width:30px}
.rpb:hover{background:var(--acc);color:#fff;border-color:var(--acc)}
.rpc input[type=range]{flex:1;accent-color:var(--gold);min-width:80px}
.rpc select{background:var(--s);border:1px solid var(--ring);color:var(--ink2);border-radius:6px;font-size:11px;padding:3px}
.rpinfo{color:var(--ink2);font-size:11.5px;white-space:nowrap;font-variant-numeric:tabular-nums;min-width:150px;text-align:right}
.side{flex:0 0 500px;border-left:1px solid var(--ring);overflow:auto;display:flex;flex-direction:column}
@media(max-width:1100px){.side{flex-basis:380px}}
.tstat{padding:12px 15px;border-bottom:1px solid var(--ring)}
.tstat-h{display:flex;align-items:center;gap:9px;margin-bottom:9px}
.tstat-h .date{font-size:14px;font-weight:650}
.tag{font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 8px;border-radius:11px;border:1px solid}
.badge{font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;border:1px solid;margin-left:auto}
.tgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.tcell{background:var(--s);border:1px solid var(--ring);border-radius:8px;padding:7px 9px}
.tcell .l{color:var(--mut);font-size:10px;text-transform:uppercase;letter-spacing:.3px}
.tcell .v{font-size:14px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
.stack{padding:9px;display:flex;flex-direction:column;gap:8px}
.smod{background:rgba(20,22,27,.985);border:1px solid var(--ring);border-radius:10px}
.smod-h{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--ring)}
.smod-tag{font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 7px;border-radius:11px;border:1px solid}
.smod-h b{font-weight:600}.smod-h .mut{color:var(--mut);font-size:11px;margin-left:auto}
.smod-svg{padding:6px 8px 2px}.smod-svg svg{display:block;width:100%;height:auto}
.smod-cols{display:flex;gap:14px;padding:4px 14px 9px}
.mcol{flex:1}.mttl{color:var(--mut);font-size:10px;letter-spacing:.4px;text-transform:uppercase;margin-bottom:5px}
.mr{display:flex;justify-content:space-between;gap:6px;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.mr span{color:var(--mut)}.mr b{font-weight:600}
.lgrid{display:flex;gap:12px;padding:8px 12px}.lcol{flex:1}
.lttl{font-size:11px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:5px}
.lr{display:flex;justify-content:space-between;gap:6px;padding:2px 0;border-bottom:1px solid #1c2330;font-size:11.5px}
.lr span{color:var(--mut)}.lr .rr{color:var(--ink2);min-width:46px;text-align:right;font-weight:600}
</style></head><body>
<div class="top">
  <h1>simplicity <span>trade replay</span></h1>
  <div class="nav">
    <button class="rpb" id="tFirst">|&lt;</button><button class="rpb" id="tPrev">&lt; trade</button>
    <span class="idx" id="tIdx">– / –</span>
    <button class="rpb" id="tNext">trade &gt;</button><button class="rpb" id="tLast">&gt;|</button>
  </div>
  <input type="range" id="tScrub" min="0" value="0">
  <div class="grp"><span class="lab">outcome</span><span id="filt"></span></div>
  <div class="grp" style="margin-left:auto"><span class="lab" id="cfgNote"></span></div>
</div>
<div class="main">
  <div class="chartwrap">
    <div id="chart"></div>
    <svg id="nowsvg" class="nowsvg"></svg>
    <div class="rpc">
      <button class="rpb" data-rp="start">|&lt;</button><button class="rpb" data-rp="back">&lt;</button>
      <button class="rpb" id="rpPlay">play</button>
      <button class="rpb" data-rp="fwd">&gt;</button><button class="rpb" data-rp="end">&gt;|</button>
      <input type="range" id="rpScrub" min="0" value="0">
      <span class="rpinfo" id="rpInfo">–</span>
      <select id="rpSpeed"><option value="1">1x</option><option value="2">2x</option><option value="4">4x</option></select>
    </div>
  </div>
  <div class="side">
    <div class="tstat" id="tstat"></div>
    <div class="stack" id="stack"></div>
  </div>
</div>
<script>
const TD=window.TRADES_DATA, TR=TD.trades, CFG=TD.config, CLOCK="America/New_York";
const SC={asia:"#e0a94a",london:"#4a9bff",newyork:"#9a7cff",close:"#8a94a6"};
const _TZ={timeZone:CLOCK};
const _t12=t=>new Date(t*1000).toLocaleTimeString("en-US",{..._TZ,hour:"numeric",minute:"2-digit",hour12:true});
function fmtET(t){return _t12(t)+" "+new Date(t*1000).toLocaleDateString("en-US",{..._TZ,month:"short",day:"numeric"});}
function fmtDur(s){s=Math.max(0,Math.round(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}h ${m}m`:`${m}m`;}
const B=a=>({time:a[0],open:a[1],high:a[2],low:a[3],close:a[4],value:a[5]});   // unpack [t,o,h,l,c,v]
const okc=v=>v?"var(--up)":"var(--dn)";
const _tick=(t,type)=>{const d=new Date(t*1000);if(type>=3)return _t12(t);
  return d.toLocaleDateString("en-US",{..._TZ,month:"short",day:"numeric"});};

const chart=LightweightCharts.createChart(document.getElementById("chart"),{
  autoSize:true,layout:{background:{color:"#1a1a19"},textColor:"#c3c2b7"},
  grid:{vertLines:{visible:false},horzLines:{visible:false}},
  rightPriceScale:{borderColor:"#383835"},
  timeScale:{borderColor:"#383835",timeVisible:true,secondsVisible:false,tickMarkFormatter:_tick},
  localization:{timeFormatter:t=>new Date(t*1000).toLocaleString("en-US",
    {..._TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",hour12:true})},
  crosshair:{mode:0}});
const candle=chart.addCandlestickSeries({upColor:"#199e70",downColor:"#e66767",
  borderUpColor:"#199e70",borderDownColor:"#e66767",wickUpColor:"#199e70",wickDownColor:"#e66767"});
const vol=chart.addHistogramSeries({priceFormat:{type:"volume"},priceScaleId:"vol",
  color:"rgba(120,120,120,.4)"});
chart.priceScale("vol").applyOptions({scaleMargins:{top:0.85,bottom:0}});

// ---- state ----
let filtered=TR.map((_,i)=>i), fpos=0, priceLines=[], outcomeFilter="all";
const RP={bars:[],k:0,e0:0,e1:0,playing:false,timer:null,speed:1};

// ---- price lines (entry/stop/target/coil), redrawn per trade ----
function clearLines(){priceLines.forEach(pl=>candle.removePriceLine(pl));priceLines=[];}
function line(price,color,style,title){priceLines.push(candle.createPriceLine(
  {price,color,lineWidth:1,lineStyle:style,axisLabelVisible:true,title}));}

// ---- module cards (ported from make_chart; render from the stored profile dicts) ----
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
  if(P.bins&&P.bins.length){const mx=Math.max(...P.bins.map(b=>b.v))||1;
    for(const b of P.bins){const w=b.v/mx*VPW, col=Math.abs(b.p-P.poc)<rowsz/2?"#e34948":(b.p<=P.poc?"#3f8cff":"#e08a3c");
      e+=`<rect x="${(VPR-w).toFixed(1)}" y="${(Y(b.p)-barH/2).toFixed(1)}" width="${w.toFixed(1)}" height="${barH.toFixed(1)}" fill="${col}" fill-opacity="${(0.3+0.65*(b.v/mx)).toFixed(2)}"/>`;}}
  return `<svg viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="xMidYMid meet">${e}</svg>`;
}
function cardHTML(meta,prof,cs,kind){
  const s=prof.shape||{}, z=prof.zone||{};
  const gap=meta.next_open!=null?meta.next_open-meta.end:null;
  const timing=mrow("opened",fmtET(meta.start))+mrow("closed",fmtET(meta.end))+mrow("span",fmtDur(meta.duration_sec))
    +(meta.next_session?mrow("next",meta.next_session+" &middot; "+fmtDur(gap)):mrow("next","&mdash;"));
  const shape=(s.shape_score!=null)?(mrow("score",s.shape_score+"/100",okc(s.shape_ok))+mrow("VA % range",s.va_pct+"%")
    +mrow("prominence",s.prominence+"x")+mrow("peaks",s.n_peaks)):mrow("&mdash;","forming");
  const zone=(z.rr!=null)?(mrow("R:R",z.rr,okc(z.rr_ok))+mrow("risk 1R",z.risk_pts+" pt")+mrow("room",z.room_pts+" pt")
    +mrow("entry tf",z.entry_tf)):mrow("&mdash;","forming");
  const acc={htf:"#9a7cff",session:(SC[meta.session]||"#4a9bff"),base:"#e0a94a"}[kind];
  const lab={htf:" &middot; HTF week",session:"",base:" &middot; BASE"}[kind];
  return `<div class="smod"><div class="smod-h">
    <span class="smod-tag" style="color:${acc};border-color:${acc}">${meta.session}${lab}</span>
    <b>${meta.date}</b><span class="mut">${meta.barsLabel||(cs.length+" bars")}</span></div>
    <div class="smod-svg">${moduleSVG(prof,cs)}</div>
    <div class="smod-cols"><div class="mcol"><div class="mttl">Timing</div>${timing}</div>
      <div class="mcol"><div class="mttl">Shape</div>${shape}</div>
      <div class="mcol"><div class="mttl">Zone &mdash; R:R</div>${zone}</div></div></div>`;
}
function ladderCard(L){
  const rung=t=>`<div class="lr"><span>${t.src}</span><b>${t.level}</b><b class="rr">${t.rr}R</b></div>`;
  const side=(d,col,lab)=>`<div class="lcol"><div class="lttl" style="color:${col}">${lab} &middot; stop ${d.stop}</div>`
    +(d.targets.length?d.targets.map(rung).join(""):'<div class="lr"><span>no rung</span><b></b></div>')+'</div>';
  return `<div class="smod"><div class="smod-h">
    <span class="smod-tag" style="color:#c3c2b7;border-color:#c3c2b7">TARGET LADDER</span>
    <b>1R = ${L.risk_pts} pt</b><span class="mut">base = stop &middot; larger scales = targets</span></div>
    <div class="lgrid">${side(L.up,"#2ebd85","UP break")}${side(L.down,"#f6465d","DOWN break")}</div></div>`;
}
function renderStack(tr){
  const sc=tr.scales, allbars=tr.bars.map(B), stack=document.getElementById("stack");
  const inRange=(s,e)=>allbars.filter(c=>c.time>=s&&c.time<=e);
  let html="";
  if(sc.htf){const h=sc.htf, hcs=tr.htf_bars.map(B);
    html+=cardHTML({session:tr.session,date:tr.date,start:h.start,end:h.end,duration_sec:h.end-h.start,
      barsLabel:(h.htf_days||"")+"d week (context)"},h,hcs,"htf");}
  const P=sc.session, scs=inRange(P.start,P.end);
  html+=cardHTML({session:tr.session,date:tr.date,start:P.start,end:P.end,duration_sec:P.duration_sec,
    next_session:P.next_session,next_open:P.next_open},P,scs,"session");
  if(sc.base){const b=sc.base, bcs=inRange(b.start,b.end);
    html+=cardHTML({session:tr.session,date:tr.date,start:b.start,end:b.end,duration_sec:b.end-b.start},b,bcs,"base");}
  if(sc.ladder)html+=ladderCard(sc.ladder);
  stack.innerHTML=html;
}

// ---- trade stats panel ----
function renderStat(tr){
  const dirCol=tr.dir==="up"?"var(--up)":"var(--dn)", oc=tr.outcome;
  const ocCol=oc==="target"?"var(--up)":oc==="stop"?"var(--dn)":"var(--mut)";
  const rCol=tr.R>=0?"var(--up)":"var(--dn)";
  const cell=(l,v,c)=>`<div class="tcell"><div class="l">${l}</div><div class="v" style="${c?`color:${c}`:''}">${v}</div></div>`;
  document.getElementById("tstat").innerHTML=
   `<div class="tstat-h"><span class="tag" style="color:${SC[tr.session]||'#888'};border-color:${SC[tr.session]||'#888'}">${tr.session}</span>
      <span class="date">${tr.date}</span>
      <span class="tag" style="color:${dirCol};border-color:${dirCol}">${tr.dir==="up"?"LONG break":"SHORT break"}</span>
      <span class="badge" style="color:${ocCol};border-color:${ocCol}">${oc.toUpperCase()} &middot; ${tr.R>=0?"+":""}${tr.R}R</span></div>
    <div class="tgrid">
      ${cell("entry",tr.entry,"var(--gold)")}${cell("stop (1R)",tr.stop,"var(--dn)")}
      ${cell("target",tr.target,"var(--up)")}${cell("risk",tr.risk_pts+" pt")}
      ${cell("outcome",oc,ocCol)}${cell("result",(tr.R>=0?"+":"")+tr.R+" R",rCol)}
      ${cell("net",(tr.net_pts>=0?"+":"")+tr.net_pts+" pt",rCol)}${cell("entry ET",_t12(tr.t_entry))}</div>`;
}

// ---- draw entry/stop/target/coil price lines + entry/exit markers ----
function drawTrade(tr){
  clearLines();
  line(tr.entry,"#f0b000",0,"entry "+tr.entry);
  line(tr.stop,"#e66767",2,"stop "+tr.stop);
  line(tr.target,"#2ebd85",2,"target "+tr.target);
  line(tr.coil_hi,"rgba(240,176,0,.5)",3,"coil hi");
  line(tr.coil_lo,"rgba(240,176,0,.5)",3,"coil lo");
  const up=tr.dir==="up";
  candle.setMarkers([
    {time:tr.t_entry,position:up?"belowBar":"aboveBar",color:"#f0b000",shape:up?"arrowUp":"arrowDown",text:"ENTRY"},
    {time:tr.t_exit,position:up?"aboveBar":"belowBar",
     color:tr.outcome==="target"?"#2ebd85":tr.outcome==="stop"?"#e66767":"#8a94a6",
     shape:"circle",text:tr.outcome.toUpperCase()+" "+(tr.R>=0?"+":"")+tr.R+"R"}]);
}

// ---- select a trade ----
function selectTrade(pos){
  fpos=(pos+filtered.length)%filtered.length;
  const tr=TR[filtered[fpos]];
  candle.setData(tr.bars.map(B));
  vol.setData(tr.bars.map(a=>({time:a[0],value:a[5],color:a[4]>=a[1]?"rgba(25,158,112,.4)":"rgba(230,103,103,.4)"})));
  drawTrade(tr); renderStat(tr); renderStack(tr);
  chart.timeScale().fitContent();
  document.getElementById("tIdx").textContent=`${fpos+1} / ${filtered.length}`;
  document.getElementById("tScrub").max=filtered.length-1;
  document.getElementById("tScrub").value=fpos;
  // set up bar stepping between entry and exit
  RP.bars=tr.bars; RP.e0=tr.bars.findIndex(a=>a[0]===tr.t_entry);
  RP.e1=tr.bars.findIndex(a=>a[0]===tr.t_exit); if(RP.e1<0)RP.e1=tr.bars.length-1;
  if(RP.e0<0)RP.e0=0;
  RP.k=RP.e0; RP.tr=tr; replayPause(); document.getElementById("rpScrub").min=RP.e0;
  document.getElementById("rpScrub").max=RP.e1; renderNow();
}

// ---- bar-by-bar "now" line + running mark-to-market R ----
function renderNow(){
  const sc=document.getElementById("rpScrub"); sc.value=RP.k;
  drawNow();
  const tr=RP.tr, bar=RP.bars[RP.k]; if(!bar){document.getElementById("rpInfo").textContent="–";return;}
  const px=bar[4], risk=tr.risk_pts||1;
  const mtm=(tr.dir==="up"?(px-tr.entry):(tr.entry-px))/risk;   // mark-to-market R at this bar's close
  const atExit=RP.k>=RP.e1;
  const rShow=atExit?tr.R:+mtm.toFixed(2);
  const col=rShow>=0?"#2ebd85":"#e66767";
  const stage=RP.k<RP.e0?"pre-entry":atExit?tr.outcome.toUpperCase():"in trade";
  document.getElementById("rpInfo").innerHTML=
    `bar ${RP.k-RP.e0+1}/${RP.e1-RP.e0+1} &middot; ${_t12(bar[0])} &middot; <b style="color:${col}">${rShow>=0?"+":""}${rShow}R</b> &middot; ${stage}`;
}
const nowsvg=document.getElementById("nowsvg"), chartEl=document.getElementById("chart");
function drawNow(){while(nowsvg.firstChild)nowsvg.removeChild(nowsvg.firstChild);
  const bar=RP.bars[RP.k]; if(!bar)return;
  const x=chart.timeScale().timeToCoordinate(bar[0]); if(x==null)return;
  const box=chartEl.getBoundingClientRect(); nowsvg.setAttribute("viewBox",`0 0 ${box.width} ${box.height}`);
  const l=document.createElementNS("http://www.w3.org/2000/svg","line");
  l.setAttribute("x1",x);l.setAttribute("y1",0);l.setAttribute("x2",x);l.setAttribute("y2",box.height);
  l.setAttribute("stroke","#f0b000");l.setAttribute("stroke-width","1.3");l.setAttribute("stroke-opacity",".9");nowsvg.appendChild(l);}
chart.timeScale().subscribeVisibleLogicalRangeChange(drawNow);
new ResizeObserver(drawNow).observe(chartEl);

function rpGo(cmd){if(cmd==="start")RP.k=RP.e0;else if(cmd==="back")RP.k=Math.max(0,RP.k-1);
  else if(cmd==="fwd")RP.k=Math.min(RP.bars.length-1,RP.k+1);else if(cmd==="end")RP.k=RP.e1;renderNow();}
function replayPlay(){RP.playing=true;document.getElementById("rpPlay").textContent="pause";
  RP.timer=setInterval(()=>{if(RP.k>=RP.e1){replayPause();return;}RP.k++;renderNow();},600/RP.speed);}
function replayPause(){RP.playing=false;document.getElementById("rpPlay").textContent="play";
  if(RP.timer){clearInterval(RP.timer);RP.timer=null;}}
document.getElementById("rpPlay").onclick=()=>RP.playing?replayPause():replayPlay();
document.querySelectorAll("[data-rp]").forEach(b=>b.onclick=()=>rpGo(b.dataset.rp));
document.getElementById("rpScrub").oninput=function(){RP.k=+this.value;renderNow();};
document.getElementById("rpSpeed").onchange=function(){RP.speed=+this.value;if(RP.playing){replayPause();replayPlay();}};

// ---- trade navigation + outcome filter ----
document.getElementById("tPrev").onclick=()=>selectTrade(fpos-1);
document.getElementById("tNext").onclick=()=>selectTrade(fpos+1);
document.getElementById("tFirst").onclick=()=>selectTrade(0);
document.getElementById("tLast").onclick=()=>selectTrade(filtered.length-1);
document.getElementById("tScrub").oninput=function(){selectTrade(+this.value);};
function applyFilter(f){outcomeFilter=f;
  filtered=TR.map((t,i)=>i).filter(i=>f==="all"||TR[i].outcome===f);
  if(!filtered.length)filtered=TR.map((_,i)=>i);
  document.querySelectorAll("[data-f]").forEach(b=>b.classList.toggle("on",b.dataset.f===f));
  selectTrade(0);}
const counts={all:TR.length,target:0,stop:0,time:0};TR.forEach(t=>counts[t.outcome]++);
document.getElementById("filt").innerHTML=["all","target","stop","time"].map(f=>
  `<button data-f="${f}" class="${f==='all'?'on':''}">${f} (${counts[f]})</button>`).join("");
document.querySelectorAll("[data-f]").forEach(b=>b.onclick=()=>applyFilter(b.dataset.f));
document.getElementById("cfgNote").textContent=
  `${TR.length} trades · era≥${CFG.era_start} · target≥${CFG.target_r}R · UNCONDITIONAL (base rate)`;

selectTrade(filtered.length-1);   // open the most-recent trade
</script></body></html>"""

out = HTML
p = os.path.join(HERE, "trade_replay.html")
open(p, "w", encoding="utf-8").write(out)
print("wrote", p, "-", round(len(out) / 1e3, 1), "KB (data loads from data/trades_data.js)")
