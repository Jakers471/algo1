"""
make_examples — SEE what shape_filter + zone_calibration score, against real NQ price.

Picks a spread of example sessions (clean / foggy / big-RR / poor-RR), and for each renders:
  - the session's 5m candles (the real OHLC of that range)
  - its volume profile (horizontal two-tone histogram) + POC / value-area / hi-lo lines
  - a SCORECARD: shape metrics + zone-calibration geometry, so you can match number->picture

Run:  python research/profile_shape_filter/make_examples.py
Out:  output/examples.html  (opens in browser)
"""
import os
import sys
import json
import webbrowser

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # simplicity/
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine", "feed"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "zone_calibration"))
import data_feed
import shape_filter
import zone_calibration as zc

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
VP = os.path.join(HERE, "..", "volume_profile", "output", "volume_profile.json")

# --- geometry ---
CW, CH = 640, 266                          # svg canvas
CL, CR, CT, CB = 48, 402, 18, 248          # candle area (left,right,top,bottom)
VPR, VPW = 598, 150                         # volume-profile right edge + max bar width
# --- colors (match the main chart) ---
UP, DN = "#2ebd85", "#f6465d"
VP_LO, VP_HI, POC_C = "#4a9bff", "#e0863c", "#ff5b5b"
VA_C, HL_C = "#8a94a6", "#59626e"


def _bars_for(df, prof):
    a = pd.Timestamp(prof["start"], unit="s", tz="UTC")
    b = pd.Timestamp(prof["end"], unit="s", tz="UTC")
    return df.loc[a:b]


def _svg(prof, bars, row_size):
    lo, hi = prof["low"], prof["high"]
    pad = max((hi - lo) * 0.08, 1.0)
    top_p, bot_p = hi + pad, lo - pad
    def y(p): return CT + (top_p - p) / (top_p - bot_p) * (CB - CT)
    barH = max(1.4, (CB - CT) * row_size / (top_p - bot_p) - 1)

    e = []
    # value area band + hi/lo/poc/va lines (span full width)
    e.append(f'<rect x="{CL}" y="{y(prof["vah"]):.1f}" width="{VPR-CL}" '
             f'height="{max(1,y(prof["val"])-y(prof["vah"])):.1f}" fill="#ffffff" fill-opacity="0.04"/>')
    for p, c, dash, lab in [(prof["high"], HL_C, "", "H"), (prof["low"], HL_C, "", "L"),
                            (prof["vah"], VA_C, "4 3", "VAH"), (prof["val"], VA_C, "4 3", "VAL"),
                            (prof["poc"], POC_C, "", "POC")]:
        yy = y(p)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        e.append(f'<line x1="{CL}" y1="{yy:.1f}" x2="{VPR}" y2="{yy:.1f}" stroke="{c}" '
                 f'stroke-width="{1.4 if lab=="POC" else 1}"{da}/>')
        e.append(f'<text x="{VPR+4}" y="{yy+3.5:.1f}" fill="{c}" font-size="10">{lab} {p:.0f}</text>')

    # candles
    n = len(bars)
    step = (CR - CL) / max(n, 1)
    bw = min(9, step * 0.7)
    for i, (_, r) in enumerate(bars.iterrows()):
        x = CL + (i + 0.5) * step
        col = UP if r["close"] >= r["open"] else DN
        e.append(f'<line x1="{x:.1f}" y1="{y(r["high"]):.1f}" x2="{x:.1f}" y2="{y(r["low"]):.1f}" '
                 f'stroke="{col}" stroke-width="1"/>')
        yo, yc = y(r["open"]), y(r["close"])
        e.append(f'<rect x="{x-bw/2:.1f}" y="{min(yo,yc):.1f}" width="{bw:.1f}" '
                 f'height="{max(1,abs(yc-yo)):.1f}" fill="{col}"/>')

    # volume profile (horizontal bars grow left from VPR)
    mx = max((b["v"] for b in prof["bins"]), default=1)
    for b in prof["bins"]:
        w = b["v"] / mx * VPW
        col = POC_C if abs(b["p"] - prof["poc"]) < row_size / 2 else (VP_LO if b["p"] <= prof["poc"] else VP_HI)
        op = 0.30 + 0.65 * (b["v"] / mx)
        e.append(f'<rect x="{VPR-w:.1f}" y="{y(b["p"])-barH/2:.1f}" width="{w:.1f}" height="{barH:.1f}" '
                 f'fill="{col}" fill-opacity="{op:.2f}"/>')

    return f'<svg viewBox="0 0 {CW} {CH}" width="{CW}" height="{CH}">' + "".join(e) + "</svg>"


def _card(prof, s, z, tag, tagcol, bars, row_size):
    shp_c = UP if s["shape_ok"] else DN
    rr_c = UP if z["rr_ok"] else DN
    single = "yes" if s["n_peaks"] <= 1 else f"no ({s['n_peaks']} peaks)"
    verdict = []
    verdict.append("clean single-peak" if s["shape_ok"] else "scattered / not clean")
    verdict.append(f"R:R {z['rr']} " + ("worth it" if z["rr_ok"] else "too thin") + f" -> entry on {z['entry_tf']}")
    def row(k, v, c="var(--ink)"):
        return f'<div class="r"><span>{k}</span><b style="color:{c}">{v}</b></div>'
    shape_rows = (row("shape score", f'{s["shape_score"]}/100', shp_c)
                  + row("VA width % of range", f'{s["va_pct"]}%')
                  + row("POC prominence", f'{s["prominence"]}x')
                  + row("single-peak", single)
                  + row("POC position", f'{s["poc_pos"]} (0=lo,1=hi)')
                  + row("top-bin share", f'{s["top_share_pct"]}%'))
    zone_rows = (row("R:R", f'{z["rr"]}', rr_c)
                 + row("risk (1R = VA edge)", f'{z["risk_pts"]} pt')
                 + row("room (range)", f'{z["room_pts"]} pt')
                 + row("range height", f'{z["height_pct"]*100:.2f}%')
                 + row("duration", f'{z["bars"]} bars')
                 + row("entry timeframe", z["entry_tf"]))
    return f'''<div class="card">
  <div class="head"><span class="tag" style="background:{tagcol}22;color:{tagcol};border-color:{tagcol}55">{tag}</span>
    <span class="sid">{prof["sid"]}</span><span class="mut">{len(bars)} x 5m bars</span></div>
  <div class="body">
    <div class="chart">{_svg(prof, bars, row_size)}</div>
    <div class="score">
      <div class="col"><div class="ttl">SHAPE — clean vs foggy</div>{shape_rows}</div>
      <div class="col"><div class="ttl">ZONE — R:R geometry</div>{zone_rows}</div>
    </div>
  </div>
  <div class="verdict">{" · ".join(verdict)}</div>
</div>'''


def main():
    vp = json.load(open(VP))
    profiles, row_size = vp["profiles"], vp["row_size"]
    df5 = data_feed.load("5m")

    cand = []
    for p in profiles:
        if p["date"][:4] != "2024" or p["bars"] < 24:
            continue
        s, z = shape_filter.score(p), zc.calibrate(p)
        if s and z:
            cand.append((p, s, z))
    by_shape = sorted(cand, key=lambda x: x[1]["shape_score"])
    by_rr = sorted(cand, key=lambda x: x[2]["rr"])

    picks, seen = [], set()
    def take(items, tag, col):
        for p, s, z in items:
            if p["sid"] in seen:
                continue
            seen.add(p["sid"]); picks.append((p, s, z, tag, col)); return
    take(by_shape[::-1], "CLEAN", UP); take(by_shape[::-1][1:], "CLEAN", UP)
    take(by_shape, "FOGGY", DN); take(by_shape[1:], "FOGGY", DN)
    take(by_rr[::-1], "BIG R:R", "#4a9bff"); take(by_rr[::-1][1:], "BIG R:R", "#4a9bff")
    take(by_rr, "POOR R:R", "#e0863c"); take(by_rr[1:], "POOR R:R", "#e0863c")

    cards = "".join(_card(p, s, z, tag, col, _bars_for(df5, p), row_size)
                    for p, s, z, tag, col in picks)
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>shape + zone — examples</title>
<style>
:root{{--ink:#e6edf3;--mut:#8a94a6;--bg:#0e1117;--card:#161b22;--bd:#232a33}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
  font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:22px}}
h1{{font-size:17px;margin:0 0 4px}} .lead{{color:var(--mut);margin:0 0 18px;max-width:820px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:10px;margin:0 0 16px;overflow:hidden}}
.head{{display:flex;align-items:center;gap:10px;padding:9px 12px;border-bottom:1px solid var(--bd)}}
.tag{{font-size:11px;font-weight:700;letter-spacing:.5px;padding:2px 8px;border-radius:20px;border:1px solid}}
.sid{{font-weight:600}} .mut{{color:var(--mut);margin-left:auto;font-size:12px}}
.body{{display:flex;gap:6px;align-items:stretch;flex-wrap:wrap}}
.chart{{padding:6px 4px 6px 8px}} svg{{display:block}}
.score{{display:flex;gap:22px;padding:12px 16px;flex:1;min-width:360px}}
.col{{flex:1}} .ttl{{color:var(--mut);font-size:11px;letter-spacing:.4px;text-transform:uppercase;margin-bottom:7px}}
.r{{display:flex;justify-content:space-between;padding:2.5px 0;border-bottom:1px solid #1c2330}}
.r span{{color:var(--mut)}} .r b{{font-weight:600}}
.verdict{{padding:8px 14px;border-top:1px solid var(--bd);color:var(--mut);font-size:12px}}
</style></head><body>
<h1>shape_filter + zone_calibration — what the computer scores, on real NQ sessions</h1>
<p class="lead">Each card: the session's real 5m candles + its volume profile (blue below POC / orange above,
POC red, value area shaded), and the derived scores. <b>PROVISIONAL</b> metrics — eyeball them against the
picture, then we refine the thresholds/weights. shape_ok = score ≥ 50; rr_ok = R:R ≥ 2.</p>
{cards}
</body></html>'''
    out = os.path.join(OUT, "examples.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out}  ({len(picks)} example sessions)")
    webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
