"""
make_selection_report — SEE what each filter actually selected.

For every variant (high = most volatile ... low = least volatile, + complements) it
finds the contiguous runs of selected trading days -- i.e. the actual PERIODS the
filter picks -- and lays them out next to the most/least-volatile rankings, so you
can eyeball the selections and decide what to promote.

Run:  python research/volatility_filter/make_selection_report.py
Out:  output/filter_selections.html   (dark, self-contained; open it)
"""
import os
import sys
import json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vol_filter as vf
import filter_variants as fvar

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
RANK = os.path.join(HERE, "..", "..", "studies", "volatility_ranking", "output")


def _runs(df):
    """Contiguous runs of selected==True trading days -> list of period dicts."""
    out = []
    run = None
    for r in df.itertuples():
        if r.selected:
            if run is None:
                run = {"s": r.date, "e": r.date, "n": 1, "rsum": r.avg_range, "vsum": r.volume}
            else:
                run["e"] = r.date; run["n"] += 1; run["rsum"] += r.avg_range; run["vsum"] += r.volume
        elif run is not None:
            out.append(run); run = None
    if run is not None:
        out.append(run)
    for x in out:
        x["r"] = round(x.pop("rsum") / x["n"], 3)
        x["vol"] = int(x.pop("vsum"))
    return out


def _rank_rows(fname, key, n=10):
    d = pd.read_csv(os.path.join(RANK, fname))
    most = d.head(n)[[key, "hv", "regime"]].values.tolist()
    least = d.tail(n)[[key, "hv", "regime"]].iloc[::-1].values.tolist()
    return most, least


def main():
    base = vf.daily_frame()
    total = len(base)
    variants = {}
    for mode in fvar.PRESETS:
        d = fvar.select(mode)
        sel = d[d["selected"]]
        runs = sorted(_runs(d), key=lambda x: x["n"], reverse=True)
        yc = sel.groupby("year").size().to_dict()
        variants[mode] = {
            "days": int(len(sel)), "pct": round(len(sel) / total * 100, 1),
            "n_runs": len(runs), "runs": runs[:40],
            "year_counts": {int(k): int(v) for k, v in yc.items()},
        }
    m_most, m_least = _rank_rows("rank_month.csv", "slice")
    y_most, y_least = _rank_rows("rank_year.csv", "year")
    data = {"era": vf.cfg.ERA_START_YEAR, "metric": vf.cfg.VOL_METRIC, "total": total,
            "variants": variants, "month_most": m_most, "month_least": m_least,
            "year_most": y_most, "year_least": y_least}

    html = _HTML.replace("__DATA__", json.dumps(data))
    p = os.path.join(OUT, "filter_selections.html")
    open(p, "w", encoding="utf-8").write(html)
    print("wrote", p)
    print(f"variants: " + ", ".join(f"{k}={v['days']}d/{v['n_runs']}runs" for k, v in variants.items()))


_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Filter selections</title>
<style>
:root{--s:#1a1a19;--pg:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--ring:rgba(255,255,255,.10);
--acc:#3987e5;--hi:#e66767;--lo:#199e70}
*{box-sizing:border-box}body{margin:0;background:var(--pg);color:var(--ink);
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;padding:26px 30px 60px}
h1{font-size:19px;margin:0 0 2px}.sub{color:var(--ink2);font-size:13px;margin:0 0 20px}
.sec{font-size:12px;font-weight:600;color:var(--ink2);text-transform:uppercase;letter-spacing:.06em;
margin:26px 0 12px;border-bottom:1px solid var(--ring);padding-bottom:7px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:800px){.row{grid-template-columns:1fr}}
.card{background:var(--s);border:1px solid var(--ring);border-radius:11px;padding:14px 16px}
.card h3{margin:0 0 8px;font-size:13px}.card h3.hi{color:var(--hi)}.card h3.lo{color:var(--lo)}
table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th{color:var(--mut);text-align:right;font-weight:600;padding:5px 10px;border-bottom:1px solid var(--ring)}
th:first-child,td:first-child{text-align:left}
td{padding:4px 10px;text-align:right;border-bottom:1px solid rgba(255,255,255,.05)}
tbody tr:hover td{background:rgba(57,135,229,.08)}
.btns{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.btns button{background:var(--s);border:1px solid var(--ring);color:var(--ink2);font:inherit;font-size:12.5px;
padding:6px 13px;border-radius:8px;cursor:pointer}.btns button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.stat{color:var(--ink2);font-size:13px;margin:0 0 12px}.stat b{color:var(--ink)}
.ybar{display:flex;align-items:center;gap:8px;font-size:12px;margin:3px 0}
.ybar .y{width:38px;color:var(--mut);font-variant-numeric:tabular-nums}
.ybar .bar{height:11px;background:var(--acc);border-radius:3px}.ybar .n{color:var(--ink2);font-variant-numeric:tabular-nums}
.pill{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:4px}
.pill.high{background:rgba(230,103,103,.18);color:var(--hi)}.pill.low{background:rgba(25,158,112,.18);color:var(--lo)}
.pill.medium{background:rgba(201,133,0,.18);color:#eda100}
</style></head><body>
<h1>Volatility filter — what each variant selected</h1>
<p class="sub" id="sub"></p>

<div class="sec">Most vs least volatile periods (ranking)</div>
<div class="row">
  <div class="card"><h3 class="hi">Most volatile months</h3><div id="m_most"></div></div>
  <div class="card"><h3 class="lo">Least volatile months</h3><div id="m_least"></div></div>
  <div class="card"><h3 class="hi">Most volatile years</h3><div id="y_most"></div></div>
  <div class="card"><h3 class="lo">Least volatile years</h3><div id="y_least"></div></div>
</div>

<div class="sec">What the filter selected — periods (contiguous runs of selected days)</div>
<div class="btns" id="btns"></div>
<p class="stat" id="vstat"></p>
<div class="row">
  <div class="card"><h3>Selected days per year</h3><div id="ybars"></div></div>
  <div class="card"><h3>Selected periods (longest first)</h3><div id="runs"></div></div>
</div>

<script>
const D=__DATA__;
document.getElementById("sub").textContent=
 `era >= ${D.era} · metric ${D.metric} · ${D.total} trading days · high = most volatile, low = least`;
function pill(r){return `<span class="pill ${r}">${r}</span>`;}
function rankTbl(id,rows,unit="%"){document.getElementById(id).innerHTML=
 "<table><tbody>"+rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1].toFixed(2)}${unit}</td><td>${pill(r[2])}</td></tr>`).join("")+"</tbody></table>";}
rankTbl("m_most",D.month_most);rankTbl("m_least",D.month_least);
rankTbl("y_most",D.year_most);rankTbl("y_least",D.year_least);

const modes=Object.keys(D.variants);let cur="high";
const btns=document.getElementById("btns");
btns.innerHTML=modes.map(m=>`<button data-m="${m}" class="${m==cur?'on':''}">${m}</button>`).join("");
btns.querySelectorAll("button").forEach(b=>b.onclick=()=>{cur=b.dataset.m;
 btns.querySelectorAll("button").forEach(x=>x.classList.toggle("on",x.dataset.m==cur));draw();});

function draw(){
 const v=D.variants[cur];
 document.getElementById("vstat").innerHTML=
  `<b>${cur}</b> — selected <b>${v.days}</b> days (${v.pct}% of era) across <b>${v.n_runs}</b> periods`;
 const yrs=Object.keys(v.year_counts).map(Number).sort();
 const mx=Math.max(1,...Object.values(v.year_counts));
 document.getElementById("ybars").innerHTML=yrs.map(y=>{
  const n=v.year_counts[y];return `<div class="ybar"><span class="y">${y}</span>
   <span class="bar" style="width:${n/mx*220}px"></span><span class="n">${n}</span></div>`;}).join("")||"<span class='n'>none</span>";
 document.getElementById("runs").innerHTML="<table><thead><tr><th>#</th><th>start</th><th>end</th>"
  +"<th>days</th><th>mean range</th></tr></thead><tbody>"
  +v.runs.map((r,i)=>`<tr><td>${i+1}</td><td>${r.s}</td><td>${r.e}</td><td>${r.n}</td><td>${r.r.toFixed(2)}%</td></tr>`).join("")
  +"</tbody></table>"+(v.n_runs>v.runs.length?`<p class="stat">showing top ${v.runs.length} of ${v.n_runs} periods</p>`:"");
}
draw();
</script></body></html>"""


if __name__ == "__main__":
    main()
