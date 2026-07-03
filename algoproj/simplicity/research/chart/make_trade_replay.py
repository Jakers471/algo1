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
.statepanel{position:absolute;top:10px;left:10px;z-index:4;background:rgba(13,13,13,.9);border:1px solid var(--ring);border-radius:9px;padding:9px 11px;font-size:11.5px;min-width:186px;pointer-events:none;font-variant-numeric:tabular-nums}
.statepanel .stage{font-weight:700;letter-spacing:.3px;margin-bottom:6px}
.statepanel .sh{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--mut);margin:6px 0 3px}
.statepanel .sr{display:flex;justify-content:space-between;gap:10px;padding:1.5px 0}
.statepanel .sr span{color:var(--mut)}.statepanel .sr b{font-weight:600}
.gpill{display:inline-block;padding:1px 6px;border-radius:9px;font-size:10px;font-weight:700;margin:1px 3px 0 0;border:1px solid}
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
    <div class="statepanel" id="statepanel"></div>
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
let filtered=TR.map((_,i)=>i), fpos=0, priceLines=[], outcomeFilter="all", CUR=null;
const RP={bars:[],k:0,e0:0,e1:0,entryK:0,exitK:0,armK:0,playing:false,timer:null,speed:1};

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
// ---- causal recompute (JS port of volume_profile / shape_filter / zone_calibration) so the module cards EVOLVE bar-by-bar ----
const GT=(CFG.gates&&CFG.gates.SHAPE)||{weights:{tight:.4,peak:.3,single:.2,central:.1},tight_peak:40,tight_hi:85,prom_den:2,single_2:.5,single_else:.15,shape_ok:50};
const GZ=(CFG.gates&&CFG.gates.ZONE)||{rr_min:2,tf_bands:[[0.25,"1m"],[0.60,"5m"],[null,"15m"]]};
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
  return{shape_score:score,va_pct:+va_pct.toFixed(1),prominence:+prom.toFixed(2),n_peaks:peaks,poc_pos:+pos.toFixed(2),top_share_pct:+top.toFixed(1),shape_ok:score>=GT.shape_ok};}
function computeZone(p){const rng=p.high-p.low,va=p.vah-p.val;if(rng<=0||va<=0)return{};
  const rr=+(rng/va).toFixed(2),h=p.height_pct;let etf="15m";for(const b of GZ.tf_bands){if(b[0]==null||h<b[0]){etf=b[1];break;}}
  return{height_pct:+h.toFixed(3),bars:p.bars,risk_pts:+va.toFixed(1),room_pts:+rng.toFixed(1),rr,entry_tf:etf,rr_ok:rr>=GZ.rr_min};}
function computeProfile(bars){
  if(bars.length<2)return null;
  let hi=-1e18,lo=1e18;for(const b of bars){if(b.high>hi)hi=b.high;if(b.low<lo)lo=b.low;}
  if(hi<=lo)return null;
  const ROW=2.0, nb=Math.max(3,Math.round((hi-lo)/ROW)), edges=[];
  for(let i=0;i<=nb;i++)edges.push(lo+(hi-lo)*i/nb);
  const centers=[];for(let i=0;i<nb;i++)centers.push((edges[i]+edges[i+1])/2);
  const vbin=new Array(nb).fill(0);
  for(const b of bars){const idx=[];for(let i=0;i<nb;i++)if(centers[i]>=b.low&&centers[i]<=b.high)idx.push(i);
    if(idx.length===0){let j=Math.floor(((b.low+b.high)/2-lo)/(hi-lo)*nb);j=Math.min(nb-1,Math.max(0,j));vbin[j]+=b.value;}
    else{const sh=b.value/idx.length;for(const j of idx)vbin[j]+=sh;}}
  const total=vbin.reduce((a,b)=>a+b,0);if(total<=0)return null;
  let poc=0;for(let i=1;i<nb;i++)if(vbin[i]>vbin[poc])poc=i;
  let li=poc,ui=poc,acc=vbin[poc];const target=total*0.7;
  while(acc<target&&(li>0||ui<nb-1)){const up=ui<nb-1?vbin[ui+1]:-1,dn=li>0?vbin[li-1]:-1;
    if(up>=dn){ui++;acc+=vbin[ui];}else{li--;acc+=vbin[li];}}
  const pocpx=centers[poc],val=edges[li],vah=edges[ui+1],rng=hi-lo,va=vah-val;
  const bins=[];for(let i=0;i<nb;i++)if(vbin[i]>0)bins.push({p:+centers[i].toFixed(2),v:+vbin[i].toFixed(1),va:val<=centers[i]&&centers[i]<=vah});
  const prof={high:+hi.toFixed(2),low:+lo.toFixed(2),poc:+pocpx.toFixed(2),val:+val.toFixed(2),vah:+vah.toFixed(2),
    bins,height_pct:+(rng/lo*100).toFixed(3),va_pct_of_range:+(va/rng*100).toFixed(1),bars:bars.length};
  prof.shape=computeShape(prof);prof.zone=computeZone(prof);return prof;}

function renderStack(tr,nowT){
  const sc=tr.scales, allbars=tr.bars.map(B), stack=document.getElementById("stack");
  const inRange=(s,e)=>allbars.filter(c=>c.time>=s&&c.time<=e);
  let html="";
  if(sc.htf){const h=sc.htf, hcs=tr.htf_bars.map(B);
    html+=cardHTML({session:tr.session,date:tr.date,start:h.start,end:h.end,duration_sec:h.end-h.start,
      barsLabel:(h.htf_days||"")+"d week (context)"},h,hcs,"htf");}
  // SESSION card — while the session is still FORMING (nowT within it), recompute the profile + scores on bars-so-far
  const P=sc.session; let sp=P, scs=inRange(P.start,P.end), sEnd=P.end, sDur=P.duration_sec, bl=null;
  const forming=(nowT!=null && nowT<P.end);
  if(forming){ scs=inRange(P.start,nowT); const rp=computeProfile(scs);
    if(rp)sp=Object.assign({},P,rp); sEnd=nowT; sDur=nowT-P.start; bl=scs.length+" bars · forming"; }
  html+=cardHTML({session:tr.session,date:tr.date,start:P.start,end:sEnd,duration_sec:sDur,
    next_session:P.next_session,next_open:P.next_open,barsLabel:bl},sp,scs,"session");
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

// ---- entry/stop/target axis lines + R-ladder bands (option 03) + entry/exit markers ----
function fmtR(r){return Math.abs(r-Math.round(r))<0.05?Math.round(r):r.toFixed(1);}
function drawTrade(tr){    // markers only (entry/exit arrows); the price LINES are drawn phase-aware in renderNow
  CUR=tr; const up=tr.dir==="up";
  candle.setMarkers([
    {time:tr.t_entry,position:up?"belowBar":"aboveBar",color:"#f0b000",shape:up?"arrowUp":"arrowDown",text:"ENTRY"},
    {time:tr.t_exit,position:up?"aboveBar":"belowBar",
     color:tr.outcome==="target"?"#199e70":tr.outcome==="stop"?"#e66767":"#8a94a6",
     shape:"circle",text:tr.outcome.toUpperCase()+" "+(tr.R>=0?"+":"")+tr.R+"R"}]);
}
function drawTradeLines(tr){    // entry/stop/target appear ONLY after the fill — before that the trade hasn't triggered
  clearLines();
  if(RP.k<RP.entryK)return;
  const Rr=Math.abs(tr.target-tr.entry)/(tr.risk_pts||1);
  line(tr.entry,"#f0b000",0,"entry "+tr.entry);
  line(tr.stop,"#e66767",2,"stop -1R (initial)");
  if(tr.method==="trailing") line(tr.target,"#2ebd85",2,"exit "+tr.target);
  else line(tr.target,"#199e70",2,"target +"+fmtR(Rr)+"R");
}

// ---- auto-lock the view onto the setup (coil -> exit), not the whole slice ----
function lockView(tr){
  const b=tr.scales.base||tr.scales.session;
  const from=(b?b.start:tr.t_entry)-6*300, to=tr.t_exit+8*300;   // a few bars of coil context .. a few past exit
  RP.viewFrom=from; RP.viewTo=to;
  try{chart.timeScale().setVisibleRange({from,to});}catch(e){chart.timeScale().fitContent();}
}
// ---- select a trade ----
function selectTrade(pos){
  fpos=(pos+filtered.length)%filtered.length;
  const tr=TR[filtered[fpos]];
  candle.setData(tr.bars.map(B));
  vol.setData(tr.bars.map(a=>({time:a[0],value:a[5],color:a[4]>=a[1]?"rgba(25,158,112,.4)":"rgba(230,103,103,.4)"})));
  drawTrade(tr); renderStat(tr);
  lockView(tr);
  document.getElementById("tIdx").textContent=`${fpos+1} / ${filtered.length}`;
  document.getElementById("tScrub").max=filtered.length-1;
  document.getElementById("tScrub").value=fpos;
  // replay range = the SETUP SESSION START (watch it FORM) .. EXIT. entry/exit are markers within the range.
  RP.bars=tr.bars; RP.tr=tr;
  RP.entryK=tr.bars.findIndex(a=>a[0]===tr.t_entry); if(RP.entryK<0)RP.entryK=0;
  RP.exitK=tr.bars.findIndex(a=>a[0]===tr.t_exit); if(RP.exitK<0)RP.exitK=tr.bars.length-1;
  let s0=tr.bars.findIndex(a=>a[0]>=tr.scales.session.start); if(s0<0)s0=0;
  RP.e0=s0; RP.e1=RP.exitK;
  // ARM moment = session close (that's when setup_arm evaluated the coil + placed the resting orders in the sim)
  let ak=tr.bars.findIndex(a=>a[0]>tr.scales.session.end); if(ak<0)ak=RP.entryK; RP.armK=Math.max(RP.e0,Math.min(ak,RP.entryK));
  RP.k=RP.exitK;   // open laid-out at the outcome; press |< (or play) to replay from the forming phase
  replayPause(); document.getElementById("rpScrub").min=RP.e0;
  document.getElementById("rpScrub").max=RP.e1; renderNow();
}

// ---- bar-by-bar "now" line + running mark-to-market R ----
function renderNow(){
  const sc=document.getElementById("rpScrub"); sc.value=RP.k;
  const tr=RP.tr, bar=RP.bars[RP.k]; if(!bar){document.getElementById("rpInfo").textContent="–";return;}
  // REVEAL the candles bar-by-bar: show only bars up to "now" (at exit, show the full slice incl. the post-exit pad)
  const upto=RP.k>=RP.exitK?RP.bars.length-1:RP.k, shown=RP.bars.slice(0,upto+1);
  candle.setData(shown.map(B));
  vol.setData(shown.map(a=>({time:a[0],value:a[5],color:a[4]>=a[1]?"rgba(25,158,112,.4)":"rgba(230,103,103,.4)"})));
  try{chart.timeScale().setVisibleRange({from:RP.viewFrom,to:RP.bars[upto][0]+8*300});}catch(e){}
  renderStack(tr, bar[0]);    // recompute the module cards on bars-so-far (the "numbers changing in the module screen")
  drawTradeLines(tr);         // entry/stop/target only after the fill
  redrawOverlay();
  const px=bar[4], risk=tr.risk_pts||1;
  const preEntry=RP.k<RP.entryK, atExit=RP.k>=RP.exitK, forming=bar[0]<tr.scales.session.end;
  const mtm=(tr.dir==="up"?(px-tr.entry):(tr.entry-px))/risk;
  const rShow=atExit?tr.R:+mtm.toFixed(2), col=rShow>=0?"#2ebd85":"#e66767";
  const stage=preEntry?(forming?"forming":"resting"):atExit?tr.outcome.toUpperCase():"in trade";
  document.getElementById("rpInfo").innerHTML=
    `bar ${RP.k-RP.e0+1}/${RP.e1-RP.e0+1} &middot; ${_t12(bar[0])} &middot; `
    + (preEntry?"":`<b style="color:${col}">${rShow>=0?"+":""}${rShow}R</b> &middot; `) + stage;
  updateState(tr);   // the live arm-state / trailing / R panel
}
const nowsvg=document.getElementById("nowsvg"), chartEl=document.getElementById("chart");
function _sv(tag,a){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const k in a)e.setAttribute(k,a[k]);return e;}
function redrawOverlay(){
  while(nowsvg.firstChild)nowsvg.removeChild(nowsvg.firstChild);
  const box=chartEl.getBoundingClientRect();
  nowsvg.setAttribute("viewBox",`0 0 ${box.width} ${box.height}`);
  if(CUR){drawResting(CUR,box); if(RP.k>=RP.entryK){drawBands(CUR,box); drawTrail(CUR,box);}}
  drawNowLine(box);
}
// option 03 — R-multiple ladder: green reward bands (opacity grows per R) + a red 1R risk band. both directions.
function drawBands(tr,box){
  const ts=chart.timeScale(), plotW=(ts.width&&ts.width())||box.width;
  const risk=tr.risk_pts||1, sgn=tr.dir==="up"?1:-1, E=tr.entry, yOf=p=>candle.priceToCoordinate(p);
  let x0=ts.timeToCoordinate(tr.t_entry); if(x0==null||x0<0)x0=0;   // bands live from ENTRY -> right only (not over the setup)
  const bw=Math.max(0,plotW-x0), lx=x0+5;
  const Rr=Math.abs(tr.target-E)/risk, nB=Math.min(8,Math.max(3,Math.ceil(Rr-1e-6)));  // cap bands; target line still marks true R
  for(let k=1;k<=nB;k++){                                   // reward bands stacked away from entry
    const yt=yOf(E+sgn*k*risk), yb=yOf(E+sgn*(k-1)*risk); if(yt==null||yb==null)continue;
    nowsvg.appendChild(_sv("rect",{x:x0,y:Math.min(yt,yb),width:bw,height:Math.abs(yb-yt),fill:"#199e70","fill-opacity":(0.05+0.035*Math.min(k,4)).toFixed(3)}));
    nowsvg.appendChild(_sv("line",{x1:x0,y1:yt,x2:plotW,y2:yt,stroke:"#199e70","stroke-width":0.8,"stroke-dasharray":"3 4","stroke-opacity":0.5}));
    const t=_sv("text",{x:lx,y:(yt+11).toFixed(1),fill:"#199e70","font-size":10,"font-family":"ui-monospace,Menlo,monospace","fill-opacity":0.85});t.textContent=k+"R";nowsvg.appendChild(t);
  }
  const ys=yOf(tr.stop), ye=yOf(E);                         // 1R risk band entry->stop
  if(ys!=null&&ye!=null){
    nowsvg.appendChild(_sv("rect",{x:x0,y:Math.min(ys,ye),width:bw,height:Math.abs(ys-ye),fill:"#e66767","fill-opacity":0.11}));
    const t=_sv("text",{x:lx,y:((ys+ye)/2+3.5).toFixed(1),fill:"#e66767","font-size":10,"font-family":"ui-monospace,Menlo,monospace","fill-opacity":0.85});t.textContent="−1R";nowsvg.appendChild(t);
  }
}
function drawNowLine(box){const bar=RP.bars[RP.k];if(!bar)return;
  const x=chart.timeScale().timeToCoordinate(bar[0]);if(x==null)return;
  nowsvg.appendChild(_sv("line",{x1:x,y1:0,x2:x,y2:box.height,stroke:"#f0b000","stroke-width":1.3,"stroke-opacity":0.9}));}

// ---- LIVE: resting orders (pre-entry) + the trailing-stop staircase + the state panel (all from the sim) ----
function pathStopAt(tr,t){if(!tr.path)return null;let s=null;for(const p of tr.path){if(p[0]<=t)s=p;else break;}return s;}
function drawResting(tr,box){    // the two resting breakout-STOP orders — placed at the ARM moment (session close), not during forming
  if(RP.k<RP.armK)return;
  const preEntry=RP.k<RP.entryK, up=tr.dir==="up";
  const b=tr.scales.base||tr.scales.session; let x0=chart.timeScale().timeToCoordinate(b?b.start:tr.t_entry); if(x0==null||x0<0)x0=0;
  const rest=(price,col,lab,live)=>{const y=candle.priceToCoordinate(price);if(y==null)return;
    nowsvg.appendChild(_sv("line",{x1:x0,y1:y,x2:box.width,y2:y,stroke:col,"stroke-width":1.1,"stroke-dasharray":"6 4","stroke-opacity":live?0.9:0.16}));
    const tx=_sv("text",{x:x0+5,y:(y-4).toFixed(1),fill:col,"font-size":10,"font-family":"ui-monospace,monospace","fill-opacity":live?0.9:0.3});tx.textContent=lab;nowsvg.appendChild(tx);};
  rest(tr.coil_hi,"#2ebd85","buy-stop ↑ "+tr.coil_hi, preEntry|| up);   // after entry, only the triggered side stays bright
  rest(tr.coil_lo,"#e66767","sell-stop ↓ "+tr.coil_lo, preEntry|| !up);
}
function drawTrail(tr,box){      // the LIVE trailing stop as a stepped staircase, up to "now"
  if(!tr.path||!tr.path.length)return;
  const now=RP.bars[RP.k][0], pts=[];
  for(const p of tr.path){if(p[0]>now)break;const x=chart.timeScale().timeToCoordinate(p[0]),y=candle.priceToCoordinate(p[1]);if(x!=null&&y!=null)pts.push([x,y]);}
  if(!pts.length)return;
  let d="M "+pts[0][0].toFixed(1)+" "+pts[0][1].toFixed(1);
  for(let i=1;i<pts.length;i++)d+=" L "+pts[i][0].toFixed(1)+" "+pts[i-1][1].toFixed(1)+" L "+pts[i][0].toFixed(1)+" "+pts[i][1].toFixed(1);
  nowsvg.appendChild(_sv("path",{d,fill:"none",stroke:"#e66767","stroke-width":1.7,"stroke-opacity":0.95}));
  const last=pts[pts.length-1], st=pathStopAt(tr,now);
  nowsvg.appendChild(_sv("line",{x1:last[0],y1:last[1],x2:box.width,y2:last[1],stroke:"#e66767","stroke-width":1,"stroke-dasharray":"2 3","stroke-opacity":0.6}));
  if(st){const tx=_sv("text",{x:last[0]+4,y:(last[1]-4).toFixed(1),fill:"#e66767","font-size":10,"font-family":"ui-monospace,monospace"});tx.textContent="trail "+st[1];nowsvg.appendChild(tx);}
}
function updateState(tr){
  const sp=document.getElementById("statepanel"), bar=RP.bars[RP.k]; if(!bar||!tr){sp.innerHTML="";return;}
  const now=bar[0], px=bar[4], risk=tr.risk_pts||1, up=tr.dir==="up";
  // phases keyed to the sim: FORMING (coil building) -> ARMED/RESTING (session close: gates checked, orders placed) -> IN TRADE -> EXIT
  const forming=RP.k<RP.armK, resting=RP.k>=RP.armK&&RP.k<RP.entryK, atExit=RP.k>=RP.exitK, inTrade=!forming&&!resting&&!atExit;
  const st=pathStopAt(tr,now), armedTrail=st?!!st[2]:false;
  const liveStop=inTrade?(st?st[1]:tr.stop):null;
  const mtm=atExit?tr.R:+(((up?(px-tr.entry):(tr.entry-px))/risk)).toFixed(2);
  const isTrail=tr.method==="trailing";
  const stage=forming?"FORMING · coil building"
    :resting?"ARMED · orders resting"
    :atExit?(tr.outcome.toUpperCase()+" · "+(tr.R>=0?"+":"")+tr.R+"R")
    :(isTrail?(armedTrail?"IN TRADE · trailing":"IN TRADE · pre-arm"):"IN TRADE");
  const stageCol=forming?"#4a9bff":resting?"#e0a94a":atExit?(tr.R>=0?"#2ebd85":"#e66767"):"#f0b000";
  const g=tr.arm||{}, pill=(ok,lab)=>`<span class="gpill" style="color:${ok?'#2ebd85':'#e66767'};border-color:${ok?'#2ebd85':'#e66767'}">${lab}</span>`;
  let gates=""; if(tr.arm){gates=(('session'in g)?pill(g.session,'session'):'')+pill(g.shape,'shape '+(tr.arm_shape??''))+pill(g.rr,'rr '+(tr.arm_rr??''));}
  const method=isTrail?`trailing · arm ${CFG.trail_arm_r} / gap ${CFG.trail_gap_r}`:`${tr.method} · ${CFG.target_r}R`;
  let body;
  if(forming){
    body=`<div class="sh">what's happening</div><div class="sr"><span>the coil is</span><b>still forming</b></div>`
      +`<div class="sr"><span>bars so far</span><b>${RP.k-RP.e0+1}</b></div>`
      +`<div class="sr"><span>waiting for</span><b>session close → arm</b></div>`;
  } else if(resting){                       // THE CAUSE: the gates that armed it, + the resting orders now live
    body=(tr.arm?`<div class="sh">why it ARMED (setup_arm)</div><div>${gates}</div>`
                :`<div class="sh">unconditional (no gate)</div>`)
      +`<div class="sh">resting orders (OCO)</div>`
      +`<div class="sr"><span>buy-stop ↑</span><b style="color:#2ebd85">${tr.coil_hi}</b></div>`
      +`<div class="sr"><span>sell-stop ↓</span><b style="color:#e66767">${tr.coil_lo}</b></div>`;
  } else {                                  // in trade / exit
    body=`<div class="sh">take-profit</div><div class="sr"><span>method</span><b>${method}</b></div>`
      +`<div class="sh">live</div><div class="sr"><span>mark-to-mkt</span><b style="color:${mtm>=0?'#2ebd85':'#e66767'}">${mtm>=0?'+':''}${mtm}R</b></div>`
      +`<div class="sr"><span>live stop</span><b>${liveStop!=null?liveStop:'—'}</b></div>`
      +`<div class="sr"><span>R to stop</span><b>${(liveStop!=null)?(((up?(px-liveStop):(liveStop-px))/risk)).toFixed(2):'—'}</b></div>`;
  }
  sp.innerHTML=`<div class="stage" style="color:${stageCol}">${stage}</div>`+body;
}
chart.timeScale().subscribeVisibleLogicalRangeChange(redrawOverlay);
new ResizeObserver(redrawOverlay).observe(chartEl);

function rpGo(cmd){if(cmd==="start")RP.k=RP.e0;else if(cmd==="back")RP.k=Math.max(RP.e0,RP.k-1);
  else if(cmd==="fwd")RP.k=Math.min(RP.e1,RP.k+1);else if(cmd==="end")RP.k=RP.e1;renderNow();}
function replayPlay(){RP.playing=true;document.getElementById("rpPlay").textContent="pause";
  if(RP.k>=RP.e1)RP.k=RP.e0;   // at the end -> restart the replay from the FORMING phase
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
const _tp=CFG.tp_method==="trailing"?`trailing arm${CFG.trail_arm_r}/gap${CFG.trail_gap_r}`:`${CFG.tp_method||"ladder"} ${CFG.target_r}R`;
document.getElementById("cfgNote").textContent=
  `${TR.length} trades · ${_tp} · ${CFG.setup_on?"setup_arm ON":"unconditional"}`;

selectTrade(filtered.length-1);   // open the most-recent trade
</script></body></html>"""

out = HTML
p = os.path.join(HERE, "trade_replay.html")
open(p, "w", encoding="utf-8").write(out)
print("wrote", p, "-", round(len(out) / 1e3, 1), "KB (data loads from data/trades_data.js)")
