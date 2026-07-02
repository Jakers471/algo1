"""
Render the volume_buckets output into one self-contained dark HTML dashboard:
the four overview charts (year / month / hour / session) up top, then FULL detailed
number tables for every level below (year, quarter, month, day, hour-of-day, session)
so every bucketed figure is readable, not just the chart. Data inlined as JSON so the
file opens straight off disk. Re-run after rebuilding the buckets.
  ->  output/volume_dashboard.html
"""
import os, json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

def _csv(name): return pd.read_csv(os.path.join(OUT, name))

_all = _csv("bucket_all.csv").iloc[0]
year = _csv("bucket_year.csv")
qt = _csv("bucket_quarter.csv")
month = _csv("bucket_month.csv")
day = pd.read_parquet(os.path.join(OUT, "bucket_day.parquet"))
hour = _csv("profile_hour_of_day.csv")
sess = _csv("profile_session.csv")

data = {
    "total": int(_all["volume"]),
    "days": int(_all["trading_days"]),
    "span": str(_all["slice"]),
    "rth_pct": float(sess.loc[sess.session == "newyork", "pct_of_all"].iloc[0]),
    "peak_year": int(year.loc[year.volume.idxmax(), "year"]),
    "year": [{"k": int(r.year), "v": int(r.volume), "p": float(r.pct_of_all),
              "d": int(r.trading_days), "mv": float(r.mean_vol), "hv": float(r.hv),
              "vr": float(r.vol_range), "ar": float(r.avg_range)} for r in year.itertuples()],
    "quarter": [{"k": r.slice, "v": int(r.volume), "p": float(r.pct_of_all),
                 "d": int(r.trading_days), "mv": float(r.mean_vol), "hv": float(r.hv),
                 "vr": float(r.vol_range), "ar": float(r.avg_range)} for r in qt.itertuples()],
    "month": [{"k": r.slice, "v": int(r.volume), "p": float(r.pct_of_all),
               "d": int(r.trading_days), "mv": float(r.mean_vol), "hv": float(r.hv),
               "vr": float(r.vol_range), "ar": float(r.avg_range)} for r in month.itertuples()],
    "day": [{"k": r.date, "dow": r.dow, "v": int(r.volume),
             "mv": float(r.mean_vol), "ar": float(r.avg_range)} for r in day.itertuples()],
    "hour": [{"k": int(r.hour_et), "v": int(r.volume), "p": float(r.pct_of_all),
              "mv": float(r.mean_vol), "hv": float(r.hv), "vr": float(r.vol_range),
              "ar": float(r.avg_range)} for r in hour.itertuples()],
    "sess": [{"k": r.session, "w": r.window_et, "v": int(r.volume), "p": float(r.pct_of_all),
              "mv": float(r.mean_vol), "hv": float(r.hv), "vr": float(r.vol_range),
              "ar": float(r.avg_range)} for r in sess.itertuples()],
}

HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NQ Volume — hierarchical profile</title>
<style>
  :root{
    --surface-1:#1a1a19; --page:#0d0d0d;
    --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --series:#3987e5; --series-soft:#184f95;
    --ring:rgba(255,255,255,0.10);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--page);color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif;padding:28px 32px 64px}
  h1{font-size:20px;font-weight:650;margin:0 0 2px}
  .sub{color:var(--ink-2);font-size:13px;margin:0 0 22px}
  .sec{font-size:13px;font-weight:600;color:var(--ink-2);text-transform:uppercase;
    letter-spacing:.06em;margin:34px 0 14px;border-bottom:1px solid var(--ring);padding-bottom:8px}
  .tiles{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}
  .tile{background:var(--surface-1);border:1px solid var(--ring);border-radius:10px;
    padding:14px 18px;min-width:150px}
  .tile .lab{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
  .tile .val{font-size:24px;font-weight:650;margin-top:4px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px}
  @media(max-width:900px){.grid2{grid-template-columns:1fr}}
  .card{background:var(--surface-1);border:1px solid var(--ring);border-radius:12px;padding:16px 18px 8px}
  .card h2{font-size:14px;font-weight:600;margin:0 0 2px}
  .card .cap{color:var(--muted);font-size:12px;margin:0 0 10px}
  svg{display:block;width:100%;overflow:visible;font-family:inherit}
  .gl{stroke:var(--grid);stroke-width:1}
  .ax{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
  .bar{fill:var(--series)}
  .bar.soft{fill:var(--series-soft)}
  .area{fill:url(#ag)}
  .aline{fill:none;stroke:var(--series);stroke-width:2}
  .tip{position:fixed;pointer-events:none;background:#111;border:1px solid var(--ring);
    border-radius:8px;padding:8px 10px;font-size:12px;color:var(--ink);opacity:0;
    transition:opacity .08s;white-space:nowrap;z-index:9;box-shadow:0 6px 20px rgba(0,0,0,.5)}
  .tip b{color:var(--series)}
  .tip .k{color:var(--muted)}
  .cross{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3;opacity:0}
  .hot{fill:transparent}
  .hot:hover{fill:rgba(255,255,255,.05)}
  /* tables */
  .tcard{background:var(--surface-1);border:1px solid var(--ring);border-radius:12px;
    padding:14px 4px 4px;display:flex;flex-direction:column;min-height:0}
  .tcard h2{font-size:14px;font-weight:600;margin:0 14px 2px}
  .tcard .cap{color:var(--muted);font-size:12px;margin:0 14px 10px}
  .tscroll{overflow:auto;max-height:var(--th,340px)}
  table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
  thead th{position:sticky;top:0;background:#201f1e;color:var(--ink-2);font-weight:600;
    text-align:right;padding:7px 14px;border-bottom:1px solid var(--ring);white-space:nowrap}
  thead th:first-child{text-align:left}
  tbody td{padding:5px 14px;text-align:right;border-bottom:1px solid rgba(255,255,255,.045);color:var(--ink)}
  tbody td:first-child{text-align:left;color:var(--ink-2)}
  tbody tr:hover td{background:rgba(57,135,229,.08)}
  .pct{color:var(--muted)}
  .up{color:#0ca30c} .down{color:#e66767}
</style></head>
<body>
<h1>NQ Volume — 20-year hierarchical profile</h1>
<p class="sub" id="sub"></p>
<div class="tiles" id="tiles"></div>

<div class="sec">Charts</div>
<div class="grid2">
  <div class="card"><h2>By year</h2><p class="cap">real contract volume per calendar year</p><div id="c_year"></div></div>
  <div class="card"><h2>By month</h2><p class="cap">240 months — secular trend &amp; crisis spikes</p><div id="c_month"></div></div>
  <div class="card"><h2>By ET hour-of-day</h2><p class="cap">share of all volume — intraday shape (real; abs. anchored to daily)</p><div id="c_hour"></div></div>
  <div class="card"><h2>By session (ET)</h2><p class="cap">real-scaled volume per session</p><div id="c_sess"></div></div>
</div>

<div class="sec">Volatility over time</div>
<div class="grid2">
  <div class="card"><h2>HV by year</h2><p class="cap">annualized historical volatility — std(log ret)×√252 (%)</p><div id="cv_hv_year"></div></div>
  <div class="card"><h2>Avg daily range by month</h2><p class="cap">mean (High−Low)/Close per day (%)</p><div id="cv_ar_month"></div></div>
</div>

<div class="sec">Volume — every bucketed number</div>
<div class="grid2">
  <div class="tcard"><h2>Year</h2><p class="cap">20 rows</p><div class="tscroll" id="t_year"></div></div>
  <div class="tcard"><h2>Quarter</h2><p class="cap">80 rows</p><div class="tscroll" id="t_quarter"></div></div>
  <div class="tcard"><h2>Month</h2><p class="cap">240 rows</p><div class="tscroll" id="t_month"></div></div>
  <div class="tcard"><h2>Day</h2><p class="cap" id="t_day_cap"></p><div class="tscroll" id="t_day"></div></div>
  <div class="tcard"><h2>Hour of day (ET)</h2><p class="cap">24 rows — aggregate profile</p><div class="tscroll" id="t_hour"></div></div>
  <div class="tcard"><h2>Session (ET)</h2><p class="cap">4 rows — aggregate profile</p><div class="tscroll" id="t_sess"></div></div>
</div>

<div class="sec">Volatility — every bucketed number</div>
<div class="grid2">
  <div class="tcard"><h2>Year</h2><p class="cap">20 rows</p><div class="tscroll" id="tv_year"></div></div>
  <div class="tcard"><h2>Quarter</h2><p class="cap">80 rows</p><div class="tscroll" id="tv_quarter"></div></div>
  <div class="tcard"><h2>Month</h2><p class="cap">240 rows</p><div class="tscroll" id="tv_month"></div></div>
  <div class="tcard"><h2>Day</h2><p class="cap" id="tv_day_cap"></p><div class="tscroll" id="tv_day"></div></div>
  <div class="tcard"><h2>Hour of day (ET)</h2><p class="cap">24 rows — aggregate profile</p><div class="tscroll" id="tv_hour"></div></div>
  <div class="tcard"><h2>Session (ET)</h2><p class="cap">4 rows — aggregate profile</p><div class="tscroll" id="tv_sess"></div></div>
</div>
<div class="tip" id="tip"></div>
<script>
const D = __DATA__;
const NS="http://www.w3.org/2000/svg";
const tip=document.getElementById("tip");
function el(t,a){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}
function fmt(v){const a=Math.abs(v);
  if(a>=1e9)return (v/1e9).toFixed(2)+"B";
  if(a>=1e6)return (v/1e6).toFixed(1)+"M";
  if(a>=1e3)return (v/1e3).toFixed(0)+"k";return ""+v;}
function comma(v){return Math.round(v).toLocaleString();}
function showTip(html,x,y){tip.innerHTML=html;tip.style.opacity=1;
  tip.style.left=(x+14)+"px";tip.style.top=(y-10)+"px";}
function hideTip(){tip.style.opacity=0;}

function barChart(mount,rows,{label,value,pct,soft,dlabEvery,unitPct,axisPct}){
  const W=mount.clientWidth||520,H=250,mL=44,mR=12,mT=14,mB=34;
  const iw=W-mL-mR, ih=H-mT-mB;
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`});
  const yfmt=axisPct?(x=>x.toFixed(1)+"%"):fmt;
  const max=Math.max(...rows.map(value));
  const nice=Math.pow(10,Math.floor(Math.log10(max)));
  const top=Math.ceil(max/nice)*nice;
  for(let i=0;i<=4;i++){const yv=top*i/4, y=mT+ih-ih*i/4;
    svg.appendChild(el("line",{class:"gl",x1:mL,x2:W-mR,y1:y,y2:y}));
    const t=el("text",{class:"ax",x:mL-8,y:y+3,"text-anchor":"end"});t.textContent=yfmt(yv);svg.appendChild(t);}
  const n=rows.length, gap=2, bw=(iw/n)-gap;
  rows.forEach((r,i)=>{
    const v=value(r), h=ih*v/top, x=mL+i*(iw/n)+gap/2, y=mT+ih-h;
    const rc=Math.min(4,bw/2);
    const p=`M${x},${mT+ih} L${x},${y+rc} Q${x},${y} ${x+rc},${y} L${x+bw-rc},${y} Q${x+bw},${y} ${x+bw},${y+rc} L${x+bw},${mT+ih} Z`;
    svg.appendChild(el("path",{d:p,class:"bar"+(soft&&soft(r)?" soft":"")}));
    if(!dlabEvery||i%dlabEvery===0){const t=el("text",{class:"ax",x:x+bw/2,y:H-mB+16,"text-anchor":"middle"});t.textContent=label(r);svg.appendChild(t);}
    const hot=el("rect",{class:"hot",x:mL+i*(iw/n),y:mT,width:iw/n,height:ih});
    hot.addEventListener("mousemove",e=>{
      const val = axisPct? v.toFixed(2)+"%" : (unitPct? (pct(r).toFixed(2)+"% · "+fmt(v)) : fmt(v));
      showTip(`<span class="k">${label(r,true)}</span><br><b>${val}</b>`,e.clientX,e.clientY);});
    hot.addEventListener("mouseleave",hideTip);
    svg.appendChild(hot);
  });
  mount.appendChild(svg);
}

function areaChart(mount,rows,{value,label,axisPct}){
  const W=mount.clientWidth||520,H=250,mL=44,mR=12,mT=14,mB=34;
  const iw=W-mL-mR, ih=H-mT-mB, n=rows.length;
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`});
  const yfmt=axisPct?(x=>x.toFixed(1)+"%"):fmt;
  const max=Math.max(...rows.map(value));
  const nice=Math.pow(10,Math.floor(Math.log10(max)));const top=Math.ceil(max/nice)*nice;
  const defs=el("defs",{});defs.innerHTML=`<linearGradient id="ag" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0" stop-color="#3987e5" stop-opacity="0.42"/>
    <stop offset="1" stop-color="#3987e5" stop-opacity="0.02"/></linearGradient>`;
  svg.appendChild(defs);
  for(let i=0;i<=4;i++){const yv=top*i/4,y=mT+ih-ih*i/4;
    svg.appendChild(el("line",{class:"gl",x1:mL,x2:W-mR,y1:y,y2:y}));
    const t=el("text",{class:"ax",x:mL-8,y:y+3,"text-anchor":"end"});t.textContent=yfmt(yv);svg.appendChild(t);}
  const X=i=>mL+(n<=1?0:iw*i/(n-1));
  const Y=v=>mT+ih-ih*v/top;
  let ln="",ar=`M${X(0)},${mT+ih} `;
  rows.forEach((r,i)=>{const x=X(i),y=Y(value(r));ln+=(i?"L":"M")+x+","+y+" ";ar+="L"+x+","+y+" ";});
  ar+=`L${X(n-1)},${mT+ih} Z`;
  svg.appendChild(el("path",{d:ar,class:"area"}));
  svg.appendChild(el("path",{d:ln,class:"aline"}));
  rows.forEach((r,i)=>{if(String(r.k).endsWith("-01")){const x=X(i);
    const t=el("text",{class:"ax",x:x,y:H-mB+16,"text-anchor":"middle"});t.textContent=String(r.k).slice(0,4);
    if(Number(String(r.k).slice(0,4))%3===0)svg.appendChild(t);}});
  const cross=el("line",{class:"cross",y1:mT,y2:mT+ih});svg.appendChild(cross);
  const dot=el("circle",{r:4,fill:"#3987e5",opacity:0});svg.appendChild(dot);
  const hot=el("rect",{class:"hot",x:mL,y:mT,width:iw,height:ih});
  hot.addEventListener("mousemove",e=>{
    const rb=svg.getBoundingClientRect();const px=(e.clientX-rb.left)/rb.width*W;
    let i=Math.round((px-mL)/(iw/(n-1)));i=Math.max(0,Math.min(n-1,i));
    const r=rows[i],x=X(i),y=Y(value(r));
    cross.setAttribute("x1",x);cross.setAttribute("x2",x);cross.setAttribute("opacity",1);
    dot.setAttribute("cx",x);dot.setAttribute("cy",y);dot.setAttribute("opacity",1);
    const av=axisPct?value(r).toFixed(2)+"%":fmt(value(r));
    showTip(`<span class="k">${label(r)}</span><br><b>${av}</b>`,e.clientX,e.clientY);});
  hot.addEventListener("mouseleave",()=>{hideTip();cross.setAttribute("opacity",0);dot.setAttribute("opacity",0);});
  svg.appendChild(hot);
  mount.appendChild(svg);
}

// generic table builder
function table(mountId,cols,rows){
  const m=document.getElementById(mountId);
  let h="<table><thead><tr>"+cols.map(c=>`<th>${c.h}</th>`).join("")+"</tr></thead><tbody>";
  rows.forEach((r,i)=>{h+="<tr>"+cols.map(c=>{
    const v=c.f?c.f(r,i,rows):r[c.k];const cls=c.cls?` class="${c.cls}"`:"";return `<td${cls}>${v}</td>`;}).join("")+"</tr>";});
  h+="</tbody></table>";m.innerHTML=h;
}

// header
document.getElementById("sub").textContent =
  `${D.span} · ${D.days.toLocaleString()} trading days · every slice = total real contract volume`;
const tiles=[["Total volume",fmt(D.total)],["Trading days",D.days.toLocaleString()],
  ["RTH share",D.rth_pct.toFixed(1)+"%"],["Peak year",D.peak_year]];
document.getElementById("tiles").innerHTML=tiles.map(t=>
  `<div class="tile"><div class="lab">${t[0]}</div><div class="val">${t[1]}</div></div>`).join("");

// charts
barChart(document.getElementById("c_year"),D.year,{
  label:(r,full)=>full?("Year "+r.k):("'"+String(r.k).slice(2)),
  value:r=>r.v,pct:r=>r.p,unitPct:true,dlabEvery:2});
areaChart(document.getElementById("c_month"),D.month,{value:r=>r.v,label:r=>r.k});
barChart(document.getElementById("c_hour"),D.hour,{
  label:(r,full)=>full?(String(r.k).padStart(2,"0")+":00 ET"):(r.k%3===0?String(r.k):""),
  value:r=>r.v,pct:r=>r.p,unitPct:true,
  soft:r=>!(r.k>=9&&r.k<16)});
barChart(document.getElementById("c_sess"),D.sess,{
  label:(r,full)=>full?(r.k+" · "+r.w):r.k,value:r=>r.v,pct:r=>r.p,unitPct:true});

// tables
const C_VOL={h:"Volume",f:r=>comma(r.v)};
const C_PCT={h:"% of all",cls:"pct",f:r=>r.p.toFixed(3)+"%"};
const C_DAYS={h:"Trading days",f:r=>r.d};
// period-over-period change in volume vs the previous slice in the same category
const C_CHG={h:"Δ vs prev",f:(r,i,rows)=>{
  if(i===0||!rows[i-1].v)return '<span class="pct">—</span>';
  const d=(r.v-rows[i-1].v)/rows[i-1].v*100;
  return `<span class="${d>=0?'up':'down'}">${d>=0?'+':''}${d.toFixed(1)}%</span>`;}};
table("t_year",[{h:"Year",f:r=>r.k},C_DAYS,C_VOL,C_PCT,C_CHG],D.year);
table("t_quarter",[{h:"Quarter",f:r=>r.k},C_DAYS,C_VOL,C_PCT,C_CHG],D.quarter);
table("t_month",[{h:"Month",f:r=>r.k},C_DAYS,C_VOL,C_PCT,C_CHG],D.month);
document.getElementById("t_day_cap").textContent=D.day.length.toLocaleString()+" rows — every trading day";
table("t_day",[{h:"Date",f:r=>r.k},{h:"Weekday",f:r=>r.dow},C_VOL,C_CHG],D.day);
table("t_hour",[{h:"Hour ET",f:r=>String(r.k).padStart(2,"0")+":00"},C_VOL,C_PCT,C_CHG],D.hour);
table("t_sess",[{h:"Session",f:r=>r.k},{h:"Window ET",f:r=>r.w},C_VOL,C_PCT,C_CHG],D.sess);

// volatility charts
barChart(document.getElementById("cv_hv_year"),D.year,{
  label:(r,full)=>full?("Year "+r.k):("'"+String(r.k).slice(2)),value:r=>r.hv,axisPct:true,dlabEvery:2});
areaChart(document.getElementById("cv_ar_month"),D.month,{value:r=>r.ar,label:r=>r.k,axisPct:true});

// volatility tables
const P2=x=>x.toFixed(2)+"%";
const C_MV={h:"Mean Vol %",f:r=>P2(r.mv)};
const C_HV={h:"HV %",f:r=>P2(r.hv)};
const C_VR={h:"Vol Range %",f:r=>P2(r.vr)};
const C_AR={h:"Avg Range %",f:r=>P2(r.ar)};
table("tv_year",[{h:"Year",f:r=>r.k},C_MV,C_HV,C_VR,C_AR],D.year);
table("tv_quarter",[{h:"Quarter",f:r=>r.k},C_MV,C_HV,C_VR,C_AR],D.quarter);
table("tv_month",[{h:"Month",f:r=>r.k},C_MV,C_HV,C_VR,C_AR],D.month);
document.getElementById("tv_day_cap").textContent=D.day.length.toLocaleString()+" rows — HV/Vol-Range need >1 day (n/a)";
table("tv_day",[{h:"Date",f:r=>r.k},{h:"Weekday",f:r=>r.dow},C_MV,C_AR],D.day);
table("tv_hour",[{h:"Hour ET",f:r=>String(r.k).padStart(2,"0")+":00"},C_MV,C_HV,C_VR,C_AR],D.hour);
table("tv_sess",[{h:"Session",f:r=>r.k},{h:"Window ET",f:r=>r.w},C_MV,C_HV,C_VR,C_AR],D.sess);
</script></body></html>"""

out_path = os.path.join(OUT, "volume_dashboard.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML.replace("__DATA__", json.dumps(data)))
print("wrote", out_path, "-", round(len(json.dumps(data)) / 1e6, 2), "MB data")
