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
.top{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid var(--ring);flex-wrap:wrap;z-index:10}
.top h1{font-size:15px;margin:0;font-weight:660}.top h1 span{color:var(--mut);font-weight:400}
.top .hint{color:var(--mut);font-size:11.5px}
.sp{margin-left:auto;display:flex;gap:6px}
button{background:var(--panel2);border:1px solid var(--ring);color:var(--ink);font:inherit;font-size:12px;
padding:6px 12px;border-radius:7px;cursor:pointer}button:hover{border-color:#4a9eff}
button.warm{border-color:rgba(246,70,93,.45);color:#f6b3bd}
.stage{position:relative;flex:1;overflow:auto;background:
radial-gradient(circle at 1px 1px,rgba(255,255,255,.045) 1px,transparent 0) 0 0/28px 28px}
.canvas{position:relative;width:2600px;height:1500px}
.empty{position:absolute;top:70px;left:50%;transform:translateX(-50%);color:var(--mut);font-size:13px;text-align:center;pointer-events:none}
svg.edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
svg.edges path.hit{pointer-events:stroke;cursor:pointer}
.node{position:absolute;width:198px;background:var(--panel);border:1px solid var(--ring);border-left:4px solid #888;
border-radius:10px;padding:9px 12px 10px;z-index:2;box-shadow:0 4px 14px rgba(0,0,0,.4);user-select:none}
.node.sel{outline:2px solid #4a9eff;outline-offset:1px}
.node .nh{font-size:12.5px;font-weight:660;cursor:grab;display:flex;align-items:center;gap:6px}
.node .nh .gd{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.node .nx{margin-left:auto;color:var(--mut);cursor:pointer;font-size:15px;line-height:1}.node .nx:hover{color:#f6465d}
.node .ns{color:var(--mut);font-size:11px;margin:2px 0 5px}
.node .nk{font:10px ui-monospace,Menlo,monospace;color:#9fb0c2;background:rgba(255,255,255,.04);
border-radius:4px;padding:2px 5px;word-break:break-word}
.port{position:absolute;width:14px;height:14px;border-radius:50%;background:var(--panel2);border:2px solid #5a6472;
top:calc(50% - 7px);cursor:crosshair;z-index:3}
.port:hover{background:#4a9eff;border-color:#4a9eff}
.port.in{left:-9px}.port.out{right:-9px;border-color:#2ebd85}
/* bottom palette tray */
.palette{border-top:1px solid var(--ring);background:#101319;max-height:210px;overflow-y:auto;padding:10px 14px 14px}
.phead{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.phead b{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--mut)}
.phead span{color:#5b636e;font-size:11px}
.pgroups{display:flex;gap:16px;flex-wrap:wrap}
.pg{min-width:120px}
.pg .pgl{font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;margin-bottom:5px;color:var(--mut);display:flex;align-items:center;gap:5px}
.pg .pgl i{width:9px;height:9px;border-radius:3px}
.chips{display:flex;flex-direction:column;gap:4px}
.chip{display:flex;align-items:center;gap:6px;background:var(--panel);border:1px solid var(--ring);border-left:3px solid #888;
border-radius:7px;padding:4px 9px;font-size:12px;cursor:grab;white-space:nowrap}
.chip:hover{border-color:#4a9eff;background:var(--panel2)}
.chip.placed{opacity:.32;cursor:default;pointer-events:none}
.chip .cdot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
#ghost{position:fixed;z-index:99;pointer-events:none;background:var(--panel);border:1px solid #4a9eff;border-radius:7px;
padding:5px 10px;font-size:12px;box-shadow:0 6px 18px rgba(0,0,0,.5);opacity:.95}
</style></head><body>
<div class="top">
  <h1>simplicity <span>— flow editor</span></h1>
  <span class="hint">drag a piece up from the tray · move it by its title · drag its green port → another's grey port to link · click a line to cut</span>
  <div class="sp">
    <button id="export">⬇ export flow.json</button>
    <button id="import">⬆ import</button>
    <button id="clearEdges" class="warm">clear links</button>
    <button id="reset" class="warm">clear board</button>
    <input id="file" type="file" accept="application/json" style="display:none">
  </div>
</div>
<div class="stage" id="stage"><div class="canvas" id="canvas">
  <div class="empty" id="empty">Empty board — drag pieces up from the tray below and connect them in the order you think the strategy runs.</div>
  <svg class="edges" id="edges"></svg></div></div>
<div class="palette" id="palette">
  <div class="phead"><b>Components</b><span>drag onto the board · your layout auto-saves</span></div>
  <div class="pgroups" id="pgroups"></div>
</div>
<script>
const DEF=__NODES__, GROUPS=__GROUPS__, KEY="simplicity_flow_v2";
const byId={};DEF.forEach(n=>byId[n.id]=n);
const canvas=document.getElementById("canvas"), edgesSvg=document.getElementById("edges"), stage=document.getElementById("stage");
let state=load();

function load(){try{const s=JSON.parse(localStorage.getItem(KEY));if(s&&s.pos)return s;}catch(e){}
  return {pos:{}, edges:[]};}                       // start EMPTY — pull pieces from the tray
function save(){localStorage.setItem(KEY,JSON.stringify(state));}

// ---- palette (bottom tray), grouped ----
function renderPalette(){
  const g=document.getElementById("pgroups");
  g.innerHTML=Object.entries(GROUPS).map(([k,grp])=>{
    const chips=DEF.filter(n=>n.group===k).map(n=>{
      const placed=state.pos[n.id]?" placed":"";
      return `<div class="chip${placed}" data-id="${n.id}" style="border-left-color:${grp.color}">
        <span class="cdot" style="background:${grp.color}"></span>${n.name}</div>`;}).join("");
    return `<div class="pg"><div class="pgl"><i style="background:${grp.color}"></i>${grp.label}</div>
      <div class="chips">${chips}</div></div>`;}).join("");
}

// ---- canvas nodes ----
function renderNodes(){
  [...canvas.querySelectorAll(".node")].forEach(n=>n.remove());
  DEF.forEach(n=>{
    const p=state.pos[n.id]; if(!p)return;
    const col=GROUPS[n.group].color;
    const el=document.createElement("div");
    el.className="node"; el.dataset.id=n.id; el.style.left=p.x+"px"; el.style.top=p.y+"px"; el.style.borderLeftColor=col;
    el.innerHTML=`<div class="nh"><span class="gd" style="background:${col}"></span>${n.name}<span class="nx" data-del="${n.id}">&times;</span></div>
      <div class="ns">${n.sub}</div><div class="nk">${n.knob}</div>
      <div class="port in" data-port="in"></div><div class="port out" data-port="out"></div>`;
    canvas.appendChild(el);
  });
  document.getElementById("empty").style.display=Object.keys(state.pos).length?"none":"block";
  canvas.querySelectorAll("[data-del]").forEach(x=>x.onclick=ev=>{ev.stopPropagation();removeNode(x.dataset.del);});
}
function removeNode(id){state.edges=state.edges.filter(e=>e.from!==id&&e.to!==id);delete state.pos[id];
  if(sel===id)sel=null;save();render();}
function portXY(id,side){const el=canvas.querySelector(`.node[data-id="${id}"]`);if(!el)return null;
  return {x:el.offsetLeft+(side==="out"?el.offsetWidth:0), y:el.offsetTop+el.offsetHeight/2};}
function renderEdges(temp){
  let paths="";
  state.edges.forEach((e,i)=>{const a=portXY(e.from,"out"),b=portXY(e.to,"in");if(!a||!b)return;
    const d=curve(a,b);
    paths+=`<path d="${d}" fill="none" stroke="#4a9eff" stroke-width="2" opacity="0.85"/>`
         + `<path class="hit" d="${d}" fill="none" stroke="transparent" stroke-width="14" data-edge="${i}"/>`;});
  if(temp)paths+=`<path d="${curve(temp.a,temp.b)}" fill="none" stroke="#2ebd85" stroke-width="2" stroke-dasharray="5 4"/>`;
  edgesSvg.innerHTML=paths;
  edgesSvg.querySelectorAll("[data-edge]").forEach(p=>p.onclick=()=>{state.edges.splice(+p.dataset.edge,1);save();renderEdges();});
}
function curve(a,b){const dx=Math.max(40,Math.abs(b.x-a.x)*0.5);
  return `M ${a.x} ${a.y} C ${a.x+dx} ${a.y}, ${b.x-dx} ${b.y}, ${b.x} ${b.y}`;}
function render(){renderNodes();renderEdges();renderPalette();}
render();

// ---- interactions ----
let mode=null, dragId=null, dragOff=null, connFrom=null, sel=null, placeId=null, ghost=null;
function canvasXY(cx,cy){const r=canvas.getBoundingClientRect();return {x:cx-r.left, y:cy-r.top};}

// drag a piece up from the tray
document.getElementById("palette").addEventListener("pointerdown",e=>{
  const chip=e.target.closest(".chip"); if(!chip||chip.classList.contains("placed"))return;
  placeId=chip.dataset.id; mode="place";
  ghost=document.createElement("div");ghost.id="ghost";ghost.textContent=byId[placeId].name;document.body.appendChild(ghost);
  moveGhost(e); e.preventDefault();
});
function moveGhost(e){if(ghost){ghost.style.left=(e.clientX+10)+"px";ghost.style.top=(e.clientY+8)+"px";}}

canvas.addEventListener("pointerdown",e=>{
  const port=e.target.closest(".port"), node=e.target.closest(".node");
  if(port&&node){ if(port.dataset.port==="out"){mode="conn";connFrom=node.dataset.id;e.preventDefault();} return; }
  if(node&&e.target.closest(".nh")&&!e.target.closest(".nx")){
    mode="drag";dragId=node.dataset.id;
    dragOff={x:e.clientX-node.offsetLeft,y:e.clientY-node.offsetTop};
    select(node.dataset.id);e.preventDefault();
  } else if(!node){select(null);}
});
window.addEventListener("pointermove",e=>{
  if(mode==="place"){moveGhost(e);return;}
  if(mode==="drag"&&dragId){
    const x=Math.max(0,e.clientX-dragOff.x), y=Math.max(0,e.clientY-dragOff.y);
    state.pos[dragId]={x,y};
    const el=canvas.querySelector(`.node[data-id="${dragId}"]`);el.style.left=x+"px";el.style.top=y+"px";
    renderEdges();
  } else if(mode==="conn"&&connFrom){
    renderEdges({a:portXY(connFrom,"out"), b:canvasXY(e.clientX,e.clientY)});
  }
});
window.addEventListener("pointerup",e=>{
  if(mode==="place"&&placeId){
    if(ghost){ghost.remove();ghost=null;}
    const pr=document.getElementById("palette").getBoundingClientRect();
    const sr=stage.getBoundingClientRect();
    if(e.clientY<pr.top && e.clientX>sr.left){                 // dropped over the board
      const p=canvasXY(e.clientX,e.clientY);
      state.pos[placeId]={x:Math.max(0,p.x-90),y:Math.max(0,p.y-20)};save();render();
    }
    placeId=null;mode=null;return;
  }
  if(mode==="conn"&&connFrom){
    const node=e.target.closest(".node");
    if(node&&node.dataset.id!==connFrom){const to=node.dataset.id;
      if(!state.edges.some(x=>x.from===connFrom&&x.to===to))state.edges.push({from:connFrom,to});}
    connFrom=null;save();renderEdges();
  }
  if(mode==="drag")save();
  mode=null;dragId=null;
});
function select(id){sel=id;canvas.querySelectorAll(".node").forEach(n=>n.classList.toggle("sel",n.dataset.id===id));}
window.addEventListener("keydown",e=>{
  if((e.key==="Delete"||e.key==="Backspace")&&sel){removeNode(sel);}});

// ---- toolbar ----
document.getElementById("clearEdges").onclick=()=>{if(state.edges.length&&confirm("Remove all links?")){state.edges=[];save();renderEdges();}};
document.getElementById("reset").onclick=()=>{if(confirm("Clear the whole board (pieces + links)?")){state={pos:{},edges:[]};save();render();}};
document.getElementById("export").onclick=()=>{
  const out={nodes:DEF.filter(n=>state.pos[n.id]).map(n=>({id:n.id,name:n.name,group:n.group,pos:state.pos[n.id]})),
    edges:state.edges.map(e=>({from:e.from,to:e.to})), order:orderFromEdges()};
  const blob=new Blob([JSON.stringify(out,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="flow.json";a.click();};
document.getElementById("import").onclick=()=>document.getElementById("file").click();
document.getElementById("file").onchange=function(){const f=this.files[0];if(!f)return;
  const r=new FileReader();r.onload=()=>{try{const j=JSON.parse(r.result);const pos={};
    (j.nodes||[]).forEach(n=>{if(n.pos)pos[n.id]=n.pos;});
    state={pos,edges:(j.edges||[])};save();render();}catch(e){alert("bad json");}};
  r.readAsText(f);this.value="";};
// linear order derived from the links you drew (topological; among placed nodes)
function orderFromEdges(){const P=DEF.filter(n=>state.pos[n.id]).map(n=>n.id);const S=new Set(P);
  const ins={},adj={};P.forEach(id=>{ins[id]=0;adj[id]=[];});
  state.edges.forEach(e=>{if(S.has(e.from)&&S.has(e.to)){adj[e.from].push(e.to);ins[e.to]++;}});
  const q=P.filter(id=>ins[id]===0),out=[];
  while(q.length){const id=q.shift();out.push(id);adj[id].forEach(t=>{if(--ins[t]===0)q.push(t);});}
  return out.length===P.length?out:null;}
</script></body></html>"""


if __name__ == "__main__":
    main()
