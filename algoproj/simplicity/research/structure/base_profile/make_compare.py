"""
make_compare — SEE base_profile vs volume_profile side by side, scored by the SAME gates.

For a spread of sessions it draws two mini-charts: WHOLE SESSION (all bars + its profile) next to
BASE ONLY (just the detected consolidation + its profile), and two scorecards (shape_filter +
zone_calibration on each). Picks the sessions where isolating the base changes the read the most --
the trend/impulse days where the whole session is foggy but the coil inside it is clean.

Run:  python research/structure/base_profile/make_compare.py   ->  output/compare.html
"""
import os
import sys
import json
import webbrowser

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, _SIM)
sys.path.insert(0, os.path.join(HERE, "..", "volume_profile"))
sys.path.insert(0, os.path.join(_SIM, "research", "gates", "profile_shape_filter"))
sys.path.insert(0, os.path.join(_SIM, "research", "gates", "zone_calibration"))
import strategy_config as cfg
import shape_filter as sf
import zone_calibration as zc

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
VP = os.path.join(HERE, "..", "volume_profile", "output", "volume_profile.json")
BP = os.path.join(OUT, "base_profile.json")
UP, DN = "#2ebd85", "#f6465d"
CW, CH, CL, CR, CT, CB, VPR, VPW, RS = 300, 240, 30, 196, 12, 224, 292, 92, 2.0


def _svg(prof, bars):
    lo, hi = prof["low"], prof["high"]
    pad = max((hi - lo) * 0.08, 1.0); tp, bp = hi + pad, lo - pad
    def y(p): return CT + (tp - p) / (tp - bp) * (CB - CT)
    barH = max(1.2, (CB - CT) * RS / (tp - bp) - 1)
    e = [f'<rect x="{CL}" y="{y(prof["vah"]):.1f}" width="{VPR-CL}" height="{max(1,y(prof["val"])-y(prof["vah"])):.1f}" fill="#fff" fill-opacity="0.04"/>']
    for p, c, lab in [(prof["poc"], "#e34948", "POC"), (prof["vah"], "#8a94a6", ""), (prof["val"], "#8a94a6", "")]:
        da = "" if lab else ' stroke-dasharray="3 3"'
        e.append(f'<line x1="{CL}" y1="{y(p):.1f}" x2="{VPR}" y2="{y(p):.1f}" stroke="{c}" stroke-width="{1.2 if lab else 1}"{da}/>')
    n = len(bars); step = (CR - CL) / max(n, 1); bw = min(6, step * 0.7)
    for i, (_, r) in enumerate(bars.iterrows()):
        x = CL + (i + 0.5) * step; col = UP if r["close"] >= r["open"] else DN
        e.append(f'<line x1="{x:.1f}" y1="{y(r["high"]):.1f}" x2="{x:.1f}" y2="{y(r["low"]):.1f}" stroke="{col}" stroke-width="0.8"/>')
        yo, yc = y(r["open"]), y(r["close"])
        e.append(f'<rect x="{x-bw/2:.1f}" y="{min(yo,yc):.1f}" width="{bw:.1f}" height="{max(1,abs(yc-yo)):.1f}" fill="{col}"/>')
    mx = max((b["v"] for b in prof["bins"]), default=1)
    for b in prof["bins"]:
        w = b["v"] / mx * VPW
        col = "#e34948" if abs(b["p"] - prof["poc"]) < RS / 2 else ("#3f8cff" if b["p"] <= prof["poc"] else "#e08a3c")
        e.append(f'<rect x="{VPR-w:.1f}" y="{y(b["p"])-barH/2:.1f}" width="{w:.1f}" height="{barH:.1f}" fill="{col}" fill-opacity="{min(0.9,0.3+0.6*(b["v"]/mx)):.2f}"/>')
    return f'<svg viewBox="0 0 {CW} {CH}" width="{CW}" height="{CH}">' + "".join(e) + "</svg>"


def _bars(df, a, b):
    return df.loc[pd.Timestamp(a, unit="s", tz="UTC"):pd.Timestamp(b, unit="s", tz="UTC")]


def _col(title, prof, s, z, base=None):
    r = lambda k, v, c="var(--ink)": f'<div class="r"><span>{k}</span><b style="color:{c}">{v}</b></div>'
    okc = lambda ok: UP if ok else DN
    extra = r("base bars", f'{base["bars"]} of {base["session_bars"]}') if base else r("bars", prof["bars"])
    return (f'<div class="col"><div class="ttl">{title}</div>'
            + r("shape", f'{s["shape_score"]}/100 {"clean" if s["shape_ok"] else "foggy"}', okc(s["shape_ok"]))
            + r("R:R", f'{z["rr"]} {"ok" if z["rr_ok"] else "thin"}', okc(z["rr_ok"]))
            + r("VA % of range", f'{s["va_pct"]}%') + r("prominence", f'{s["prominence"]}x')
            + r("peaks", s["n_peaks"]) + r("height", f'{z["height_pct"]}%') + r("risk 1R", f'{z["risk_pts"]}pt')
            + r("entry tf", z["entry_tf"]) + extra + '</div>')


def main():
    vps = {p["sid"]: p for p in json.load(open(VP))["profiles"]}
    bps = {p["sid"]: p for p in json.load(open(BP))["profiles"]}
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"])); df.index = pd.DatetimeIndex(df.index)

    rows = []
    for sid, bp in bps.items():
        if sid[:4] != "2024" or sid not in vps or bp["bars"] < 10:
            continue
        vpp = vps[sid]
        sv, zv = sf.score(vpp), zc.calibrate(vpp)
        sb, zb = sf.score(bp), zc.calibrate(bp)
        if not (sv and zv and sb and zb):
            continue
        rows.append((sb["shape_score"] - sv["shape_score"], sid, vpp, bp, sv, zv, sb, zb))
    rows.sort(reverse=True)
    picks = rows[:5] + rows[len(rows)//2 - 1:len(rows)//2 + 1]   # biggest base-cleanup + a couple neutral

    cards = []
    for d, sid, vpp, bp, sv, zv, sb, zb in picks:
        sess_bars = _bars(df, vpp["start"], vpp["end"]); base_bars = _bars(df, bp["start"], bp["end"])
        tag = f'base cleaner +{d}' if d > 0 else (f'{d}' if d < 0 else 'same')
        cards.append(f'''<div class="card">
  <div class="head"><b>{sid}</b><span class="mut">shape: session {sv["shape_score"]} &#8594; base {sb["shape_score"]} ({tag})</span></div>
  <div class="body">
    <div class="pane">{_svg(vpp, sess_bars)}<div class="cap">WHOLE SESSION ({vpp["bars"]} bars)</div></div>
    <div class="pane">{_svg(bp, base_bars)}<div class="cap" style="color:#e0a94a">BASE ONLY ({bp["bars"]} bars)</div></div>
    <div class="scores">{_col("session", vpp, sv, zv)}{_col("base", bp, sb, zb, bp)}</div>
  </div></div>''')

    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>base vs session profile</title>
<style>
:root{{--ink:#e6edf3;--mut:#8a94a6;--bg:#0e1117;--card:#161b22;--bd:#232a33}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:20px}}
h1{{font-size:17px;margin:0 0 4px}}.lead{{color:var(--mut);margin:0 0 16px;max-width:940px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:10px;margin:0 0 14px;overflow:hidden}}
.head{{display:flex;gap:10px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--bd)}}
.head b{{font-weight:600}}.mut{{color:var(--mut);margin-left:auto;font-size:12px}}
.body{{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start;padding:6px}}
.pane{{text-align:center}}.cap{{color:var(--mut);font-size:11px;margin-top:-6px}}
.scores{{display:flex;gap:16px;flex:1;min-width:300px;padding:8px 14px}}
.col{{flex:1}}.ttl{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px}}
.r{{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #1c2330}}.r span{{color:var(--mut)}}.r b{{font-weight:600}}
</style></head><body>
<h1>base_profile vs volume_profile &#8212; scored by the same gates</h1>
<p class="lead">LEFT = whole session + its profile; RIGHT = only the detected consolidation BASE + its profile.
Same shape_filter + zone_calibration on both (base emits the same dict). Sorted by where isolating the base
changes the shape score most &#8212; the trend/impulse days where the session reads foggy but the coil inside is clean.</p>
{"".join(cards)}
</body></html>'''
    out = os.path.join(OUT, "compare.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, f"({len(picks)} sessions)")
    webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
