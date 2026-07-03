"""
build_flow — an INTERACTIVE flow editor. Drag every component (knobs, data, filters, structure, gates,
trade, risk) around a canvas and CONNECT them in the order you think the strategy should execute. Save
your arrangement (localStorage, auto) + export it to flow.json so it can be reviewed / turned into the
real pipeline.

This is a thinking tool: "start up the strategy, in the order it runs" — you draw the succession yourself
instead of me guessing the wiring. Nodes are seeded from the live config; positions/edges are yours.
Run:  python research/strategy_map/build_flow.py   ->  flow.html   (open it, drag, connect, Export)
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
import strategy_config as cfg
import research_config as rcfg

GROUPS = {  # group -> (color, label)
    "run":       ("#2ebd85", "RUN"),
    "data":      ("#6b8299", "DATA"),
    "when":      ("#e0a94a", "WHEN — filters"),
    "structure": ("#199e70", "WHERE — structure"),
    "quality":   ("#9a7cff", "QUALITY — gates"),
    "setup":     ("#f6465d", "setup_arm"),
    "trade":     ("#f0b000", "THE TRADE"),
    "risk":      ("#8a94a6", "RISK / EXEC"),
    "measure":   ("#4a9eff", "MEASURE"),
}

# id, name, sub, group, knob
NODES = [
    ("active_filter", "active filter", "vol-day variant", "run", "research_config.ACTIVE_FILTER = " + str(rcfg.ACTIVE_FILTER)),
    ("starting_balance", "starting balance", "account size", "run", f"${rcfg.STARTING_BALANCE:,}"),
    ("date_window", "date window", "limit the run", "run", "BACKTEST_START/END"),
    ("replay_size", "replay size", "trades exported", "run", f"MAX_REPLAY_TRADES = {rcfg.MAX_REPLAY_TRADES}"),

    ("data_feed", "data_feed", "clean bars in", "data", "TF_SOURCES · DATA_DIR"),
    ("era", "era cutoff", "drop 2005-2014", "data", f"ERA_START_YEAR = {cfg.ERA_START_YEAR}"),
    ("sessions", "sessions", "ET boundaries", "data", "SESSIONS (4)"),

    ("session_filter", "session filter", "trade chosen sessions", "when", f"FILTER_SESSION ({'on' if cfg.FILTER_SESSION['on'] else 'off'}: {','.join(cfg.FILTER_SESSION['allow'])})"),
    ("hour_filter", "hour filter", "ET hours-of-day", "when", f"FILTER_HOUR ({'on' if cfg.FILTER_HOUR['on'] else 'off'})"),
    ("dayvol_filter", "day-vol regime", "high/med/low day", "when", f"FILTER_DAY_VOL ({'on' if cfg.FILTER_DAY_VOL['on'] else 'off'})"),
    ("news_filter", "news filter", "±30m red-folder news", "when", "F33 — unbuilt"),

    ("base_profile", "base_profile", "the coil (LTF)", "structure", "BASE {band_mult, min_bars}"),
    ("volume_profile", "volume_profile", "session range (MTF)", "structure", "PROFILE {row_size, va_pct}"),
    ("htf_profile", "htf_profile", "week composite", "structure", "HTF {days, bins}"),

    ("shape_filter", "shape_filter", "clean vs foggy", "quality", f"SHAPE.shape_ok = {cfg.SHAPE['shape_ok']}"),
    ("zone_calibration", "zone_calibration", "range dims → R:R + entry TF", "quality", f"ZONE.rr_min = {cfg.ZONE['rr_min']}"),
    ("fib_bias", "fib_bias", "directional lean (in-context)", "quality", "FIB.edges"),
    ("confluence", "confluence", "base ⊂ session ⊂ HTF agree", "quality", "unbuilt"),
    ("target_ladder", "target_ladder", "multi-scale R:R geometry", "quality", f"LADDER {{min_rr={cfg.LADDER['min_rr']}}}"),

    ("setup_arm", "setup_arm", "enabled gates → ARM / skip", "setup", "SETUP {gates, arm_rule} — unbuilt"),

    ("entry", "entry", "resting breakout bracket (OCO)", "trade", f"ENTRY.type = {cfg.ENTRY['type']}"),
    ("stop", "stop", "coil edge = 1R", "trade", "EXIT.stop = coil_edge"),
    ("target", "target", "fixed R | ladder rung", "trade", f"EXIT.target = {cfg.EXIT['target']} (r={cfg.EXIT['target_r']})"),
    ("time_stop", "time stop", "exit if neither hit", "trade", f"EXIT.max_hold_bars = {cfg.EXIT['max_hold_bars']}"),

    ("risk_sizing", "risk sizing", "%/trade to the stop", "risk", f"RISK.risk_per_trade_pct = {cfg.RISK['risk_per_trade_pct']}%"),
    ("costs", "costs", "commission + slippage", "risk", f"${cfg.COMMISSION_PER_SIDE}/side · {cfg.SLIPPAGE_TICKS} tick"),

    ("backtest", "backtest", "honest sim → R per trade", "measure", "run_backtest.py"),
    ("reports", "reports", "equity + full breakdown", "measure", "reports/<run_id>/"),
    ("ledger", "run ledger", "every run's scorecard", "measure", "runs.jsonl"),
]

NODE_JSON = [{"id": n[0], "name": n[1], "sub": n[2], "group": n[3], "knob": n[4]} for n in NODES]
GROUP_JSON = {k: {"color": v[0], "label": v[1]} for k, v in GROUPS.items()}


def main():
    html = TEMPLATE.replace("__NODES__", json.dumps(NODE_JSON)).replace("__GROUPS__", json.dumps(GROUP_JSON))
    out = os.path.join(HERE, "flow.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, "-", len(NODE_JSON), "nodes")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>simplicity — flow editor</title>
<style>
:root{--bg:#0d0d0d;--panel:#161b22;--panel2:#1b2028;--ring:rgba(255,255,255,.12);--ink:#e6edf3;--mut:#8a94a6}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--ink);font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;
display:flex;flex-direction:column;overflow:hidden}
.top{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--ring);flex-wrap:wrap;z-index:10}
.top h1{font-size:15px;margin:0;font-weight:660}.top h1 span{color:var(--mut);font-weight:400}
.top .hint{color:var(--mut);font-size:11.5px}
.sp{margin-left:auto;display:flex;gap:6px}
button{background:var(--panel2);border:1px solid var(--ring);color:var(--ink);font:inherit;font-size:12px;
padding:5px 11px;border-radius:7px;cursor:pointer}button:hover{border-color:#4a9eff}
button.warm{border-color:rgba(246,70,93,.5);color:#f6b3bd}
.legend{display:flex;gap:12px;flex-wrap:wrap;padding:6px 14px;border-bottom:1px solid var(--ring);font-size:11px;color:var(--mut)}
.lg{display:flex;align-items:center;gap:5px}.lg i{width:10px;height:10px;border-radius:3px}
.stage{position:relative;flex:1;overflow:auto;background:
radial-gradient(circle at 1px 1px,rgba(255,255,255,.05) 1px,transparent 0) 0 0/26px 26px}
.canvas{position:relative;width:2600px;height:1600px}
svg.edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
svg.edges path.hit{pointer-events:stroke;cursor:pointer}
.node{position:absolute;width:196px;background:var(--panel);border:1px solid var(--ring);border-left:4px solid #888;
border-radius:9px;padding:8px 11px 9px;z-index:2;box-shadow:0 3px 12px rgba(0,0,0,.35);user-select:none}
.node.sel{outline:2px solid #4a9eff;outline-offset:1px}
.node .nh{font-size:12.5px;font-weight:660;cursor:grab;display:flex;align-items:center;gap:6px}
.node .nh .gd{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.node .ns{color:var(--mut);font-size:11px;margin:2px 0 5px}
.node .nk{font:10px ui-monospace,Menlo,monospace;color:#9fb0c2;background:rgba(255,255,255,.04);
border-radius:4px;padding:2px 5px;word-break:break-word}
.port{position:absolute;width:13px;height:13px;border-radius:50%;background:var(--panel2);border:2px solid #5a6472;
top:calc(50% - 6px);cursor:crosshair;z-index:3}
.port:hover{background:#4a9eff;border-color:#4a9eff}
.port.in{left:-8px}.port.out{right:-8px}
.port.out{border-color:#2ebd85}
#tip{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);background:var(--panel2);border:1px solid var(--ring);
border-radius:8px;padding:6px 12px;font-size:11.5px;color:var(--mut);z-index:20}
</style></head><body>
<div class="top">
  <h1>simplicity <span>— flow editor</span></h1>
  <span class="hint">drag a node by its title · drag the green port → another node's grey port to connect · click a line to cut it</span>
  <div class="sp">
    <button id="export">⬇ export flow.json</button>
    <button id="import">⬆ import</button>
    <button id="tidy">tidy columns</button>
    <button id="clearEdges" class="warm">clear links</button>
    <button id="reset" class="warm">reset</button>
    <input id="file" type="file" accept="application/json" style="display:none">
  </div>
</div>
<div class="legend" id="legend"></div>
<div class="stage" id="stage"><div class="canvas" id="canvas"><svg class="edges" id="edges"></svg></div></div>
<div id="tip">Tip: your layout auto-saves. Export when you want me to look at it.</div>
<script>
const DEF=__NODES__, GROUPS=__GROUPS__, KEY="simplicity_flow_v1";
const canvas=document.getElementById("canvas"), edgesSvg=document.getElementById("edges");
let state=load();

function load(){try{const s=JSON.parse(localStorage.getItem(KEY));if(s&&s.pos)return s;}catch(e){}
  return {pos:tidyPos(), edges:[]};}
function save(){localStorage.setItem(KEY,JSON.stringify(state));}
function tidyPos(){const cols={};let order=Object.keys(GROUPS);const pos={};
  DEF.forEach(n=>{const gi=order.indexOf(n.group);cols[n.group]=(cols[n.group]||0);
    pos[n.id]={x:40+gi*236,y:30+cols[n.group]*104};cols[n.group]++;});return pos;}

document.getElementById("legend").innerHTML=Object.entries(GROUPS).map(([k,g])=>
  `<span class="lg"><i style="background:${g.color}"></i>${g.label}</span>`).join("");

// ---- render nodes ----
function renderNodes(){
  [...canvas.querySelectorAll(".node")].forEach(n=>n.remove());
  DEF.forEach(n=>{
    const p=state.pos[n.id]; if(!p)return;
    const col=GROUPS[n.group].color;
    const el=document.createElement("div");
    el.className="node"; el.dataset.id=n.id; el.style.left=p.x+"px"; el.style.top=p.y+"px"; el.style.borderLeftColor=col;
    el.innerHTML=`<div class="nh"><span class="gd" style="background:${col}"></span>${n.name}</div>
      <div class="ns">${n.sub}</div><div class="nk">${n.knob}</div>
      <div class="port in" data-port="in"></div><div class="port out" data-port="out"></div>`;
    canvas.appendChild(el);
  });
}
function portXY(id,side){const el=canvas.querySelector(`.node[data-id="${id}"]`);if(!el)return null;
  const x=el.offsetLeft+(side==="out"?el.offsetWidth:0), y=el.offsetTop+el.offsetHeight/2;return {x,y};}
function renderEdges(temp){
  let paths="";
  state.edges.forEach((e,i)=>{const a=portXY(e.from,"out"),b=portXY(e.to,"in");if(!a||!b)return;
    const d=curve(a,b);
    paths+=`<path d="${d}" fill="none" stroke="#4a9eff" stroke-width="2" opacity="0.8"/>`
         + `<path class="hit" d="${d}" fill="none" stroke="transparent" stroke-width="12" data-edge="${i}"/>`;});
  if(temp)paths+=`<path d="${curve(temp.a,temp.b)}" fill="none" stroke="#2ebd85" stroke-width="2" stroke-dasharray="5 4"/>`;
  edgesSvg.innerHTML=paths;
  edgesSvg.querySelectorAll("[data-edge]").forEach(p=>p.onclick=()=>{state.edges.splice(+p.dataset.edge,1);save();renderEdges();});
}
function curve(a,b){const dx=Math.max(40,Math.abs(b.x-a.x)*0.5);
  return `M ${a.x} ${a.y} C ${a.x+dx} ${a.y}, ${b.x-dx} ${b.y}, ${b.x} ${b.y}`;}
function render(){renderNodes();renderEdges();}
render();

// ---- interactions: drag node / draw edge / select ----
let mode=null, dragId=null, dragOff=null, connFrom=null, sel=null;
const stage=document.getElementById("stage");
canvas.addEventListener("pointerdown",e=>{
  const port=e.target.closest(".port"), node=e.target.closest(".node");
  if(port&&node){
    if(port.dataset.port==="out"){mode="conn";connFrom=node.dataset.id;e.preventDefault();}
    return;
  }
  if(node&&e.target.closest(".nh")){
    mode="drag";dragId=node.dataset.id;
    dragOff={x:e.clientX-node.offsetLeft,y:e.clientY-node.offsetTop};
    select(node.dataset.id);e.preventDefault();
  } else if(!node){select(null);}
});
window.addEventListener("pointermove",e=>{
  if(mode==="drag"&&dragId){
    const x=Math.max(0,e.clientX-dragOff.x), y=Math.max(0,e.clientY-dragOff.y);
    state.pos[dragId]={x,y};
    const el=canvas.querySelector(`.node[data-id="${dragId}"]`);el.style.left=x+"px";el.style.top=y+"px";
    renderEdges();
  } else if(mode==="conn"&&connFrom){
    const a=portXY(connFrom,"out");
    const r=canvas.getBoundingClientRect();
    renderEdges({a,b:{x:e.clientX-r.left,y:e.clientY-r.top}});
  }
});
window.addEventListener("pointerup",e=>{
  if(mode==="conn"&&connFrom){
    const node=e.target.closest(".node");
    if(node&&node.dataset.id!==connFrom){
      const to=node.dataset.id;
      if(!state.edges.some(x=>x.from===connFrom&&x.to===to)){state.edges.push({from:connFrom,to});}
    }
    connFrom=null;save();renderEdges();
  }
  if(mode==="drag")save();
  mode=null;dragId=null;
});
function select(id){sel=id;canvas.querySelectorAll(".node").forEach(n=>n.classList.toggle("sel",n.dataset.id===id));}
window.addEventListener("keydown",e=>{
  if((e.key==="Delete"||e.key==="Backspace")&&sel){
    state.edges=state.edges.filter(x=>x.from!==sel&&x.to!==sel);
    delete state.pos[sel];sel=null;save();render();
  }});

// ---- toolbar ----
document.getElementById("tidy").onclick=()=>{state.pos=tidyPos();save();render();};
document.getElementById("clearEdges").onclick=()=>{if(confirm("Remove all links?")){state.edges=[];save();renderEdges();}};
document.getElementById("reset").onclick=()=>{if(confirm("Reset layout AND links?")){state={pos:tidyPos(),edges:[]};save();render();}};
document.getElementById("export").onclick=()=>{
  const out={nodes:DEF.map(n=>({id:n.id,name:n.name,group:n.group,pos:state.pos[n.id]||null})),
    edges:state.edges.map(e=>({from:e.from,to:e.to})),
    order:orderFromEdges()};
  const blob=new Blob([JSON.stringify(out,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="flow.json";a.click();};
document.getElementById("import").onclick=()=>document.getElementById("file").click();
document.getElementById("file").onchange=function(){const f=this.files[0];if(!f)return;
  const r=new FileReader();r.onload=()=>{try{const j=JSON.parse(r.result);
    const pos={};(j.nodes||[]).forEach(n=>{if(n.pos)pos[n.id]=n.pos;});
    state={pos:Object.keys(pos).length?pos:tidyPos(),edges:(j.edges||[])};save();render();}catch(e){alert("bad json");}};
  r.readAsText(f);};
// a readable linear order derived from the links (topological-ish; falls back to layout)
function orderFromEdges(){const ins={},adj={};DEF.forEach(n=>{ins[n.id]=0;adj[n.id]=[];});
  state.edges.forEach(e=>{if(adj[e.from]){adj[e.from].push(e.to);ins[e.to]++;}});
  const q=DEF.map(n=>n.id).filter(id=>ins[id]===0),out=[];
  while(q.length){const id=q.shift();out.push(id);(adj[id]||[]).forEach(t=>{if(--ins[t]===0)q.push(t);});}
  return out.length===DEF.length?out:null;}
</script></body></html>"""


if __name__ == "__main__":
    main()
