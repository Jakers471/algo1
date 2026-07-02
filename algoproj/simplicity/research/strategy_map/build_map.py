"""
build_map — a decision-tree / neural-net style MAP of the whole strategy, to SEE how the gates,
structure and execution connect and what's built vs planned. Self-contained HTML (offline).

Layers (top -> bottom): context -> feed -> state (spine) -> structure -> GATES (confluence) ->
setup_arm (ARM/DISARM) -> execution chain. Nodes are colored by status; edges show the flow;
the gates converge into setup_arm (the confluence engine). Regenerate whenever wiring changes.

Run:  python research/strategy_map/build_map.py   ->  strategy_map.html
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1060, 700

# status -> (color, label)
ST = {"wired": ("#199e70", "WIRED (engine)"), "research": ("#4a9bff", "in research"),
      "geometry": ("#e0a94a", "geometry only"), "planned": ("#6b7280", "planned")}

# id: (label, sublabel, cx, cy, w, status)
N = {
 "regime":          ("regime / context", "chained-session bias (FUTURE)", 530, 54, 260, "planned"),
 "data_feed":       ("data_feed", "bars in", 360, 150, 160, "wired"),
 "session_state":   ("session_state", "the spine: live session clock + hi/lo", 710, 150, 220, "wired"),
 "session_anchors": ("session_anchors", "session hi/lo + breach", 360, 250, 190, "wired"),
 "volume_profile":  ("volume_profile", "POC + value area (the zone)", 710, 250, 210, "wired"),
 "vol_filter":      ("vol_filter", "WHEN gate", 150, 362, 150, "wired"),
 "shape_filter":    ("shape_filter", "clean vs foggy", 375, 362, 160, "research"),
 "zone_calibration":("zone_calibration", "R:R geometry", 610, 362, 170, "research"),
 "fib_bias":        ("fib_bias", "geometry only (F11/F13)", 850, 362, 180, "geometry"),
 "setup_arm":       ("setup_arm", "stack the gates -> ARM / DISARM resting orders", 530, 474, 300, "planned"),
 "entry":           ("entry", "resting breakout / edge orders", 235, 592, 190, "planned"),
 "risk":            ("risk", "position sizing", 455, 592, 150, "planned"),
 "execution":       ("execution", "fills, commission, slippage", 660, 592, 190, "planned"),
 "trailing_stop":   ("trailing_stop", "breakeven + aggressive trail", 875, 592, 190, "planned"),
}
NH = 56
E = [  # (from, to, dashed?)
 ("data_feed", "session_state", 0), ("session_state", "session_anchors", 0),
 ("session_state", "volume_profile", 0), ("data_feed", "vol_filter", 0),
 ("volume_profile", "shape_filter", 0), ("volume_profile", "zone_calibration", 0),
 ("volume_profile", "fib_bias", 0), ("session_anchors", "zone_calibration", 0),
 ("vol_filter", "setup_arm", 0), ("shape_filter", "setup_arm", 0),
 ("zone_calibration", "setup_arm", 0), ("fib_bias", "setup_arm", 0),
 ("regime", "setup_arm", 1),
 ("setup_arm", "entry", 0), ("entry", "risk", 0), ("risk", "execution", 0), ("execution", "trailing_stop", 0),
]


def edge(a, b, dashed):
    (_, _, ax, ay, aw, _) = N[a]; (_, _, bx, by, bw, _) = N[b]
    if a == "regime":  # route down the left margin so it doesn't cross the middle nodes
        return f'<path d="M {ax-aw/2} {ay} C 70 120, 70 460, {bx-bw/2} {by}" fill="none" stroke="#7a6a3a" stroke-width="1.4" stroke-dasharray="6 4" marker-end="url(#ar)"/>'
    sy, ty = ay + NH / 2, by - NH / 2
    my = (sy + ty) / 2
    dash = ' stroke-dasharray="6 4"' if dashed else ''
    return f'<path d="M {ax} {sy} C {ax} {my}, {bx} {my}, {bx} {ty}" fill="none" stroke="#39424e" stroke-width="1.4"{dash} marker-end="url(#ar)"/>'


def node(nid):
    label, sub, cx, cy, w, status = N[nid]
    col = ST[status][0]
    x, y = cx - w / 2, cy - NH / 2
    return f'''<g>
  <rect x="{x}" y="{y}" width="{w}" height="{NH}" rx="10" fill="#161b22" stroke="{col}" stroke-width="1.6"/>
  <circle cx="{x+13}" cy="{y+14}" r="4" fill="{col}"/>
  <text x="{cx}" y="{cy-4}" text-anchor="middle" fill="#e6edf3" font-size="14" font-weight="600">{label}</text>
  <text x="{cx}" y="{cy+13}" text-anchor="middle" fill="#8a94a6" font-size="10.5">{sub}</text>
</g>'''


def main():
    edges = "".join(edge(a, b, d) for a, b, d in E)
    nodes = "".join(node(n) for n in N)
    legend = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{lab}</span>' for c, lab in ST.values())
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>simplicity — strategy map</title>
<style>
body{{margin:0;background:#0e1117;color:#e6edf3;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;padding:20px}}
h1{{font-size:17px;margin:0 0 3px}}.lead{{color:#8a94a6;margin:0 0 8px;max-width:900px}}
.legend{{display:flex;gap:16px;margin:6px 0 12px;font-size:12px;color:#c3c2b7}}
.lg{{display:flex;align-items:center;gap:6px}}.lg i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
svg{{display:block;background:#0e1117;border:1px solid #232a33;border-radius:12px}}
.note{{color:#8a94a6;font-size:11.5px;margin-top:10px;max-width:940px;line-height:1.6}}
</style></head><body>
<h1>simplicity — strategy map <span style="color:#8a94a6;font-weight:400">(the decision tree)</span></h1>
<p class="lead">Flow top&#8594;bottom. The <b>gates converge into <code>setup_arm</code></b> (the confluence engine) which ARMs/DISARMs
resting orders; execution manages the trade. Edge = feeds-into. Dashed = the future context/bias layer.</p>
<div class="legend">{legend}</div>
<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs><marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
    <path d="M0,0 L7,3 L0,6 Z" fill="#5a6472"/></marker></defs>
  {edges}{nodes}
</svg>
<p class="note"><b>Reading it:</b> the edge is confluence + R:R geometry, not prediction. <code>fib_bias</code> is amber
(geometry only — no directional edge in isolation, NOTES F11/F13). <code>shape_filter</code> / <code>zone_calibration</code>
are provisional in research (blue). The <b>dashed regime/context node</b> is the big future idea — a top-of-tree
bias built by chaining session buckets (NOTES F14) — it would color which setups arm and their R:R, NOT call direction.</p>
</body></html>'''
    out = os.path.join(HERE, "strategy_map.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
