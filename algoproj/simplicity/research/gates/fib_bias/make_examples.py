"""
make_examples — SEE what the fib_bias edge test is actually looking at, on real NQ candles.

For a spread of example sessions it draws: the session's candles + the fib retracement lines off its
own high<->low, a marker at the CLOSE (the `fpos` the code computes) showing which fib zone it lands
in, THEN the NEXT session's candles (green/red by its open->close direction) — because "does the fib
zone predict the next session's direction?" is exactly the number the test measures. A scorecard spells
out fpos -> zone -> next direction. (Per F11 there's no edge: watch how next-dir ignores the zone.)

Run:  python research/gates/fib_bias/make_examples.py
Out:  output/fib_examples.html
"""
import os
import sys
import json
import webbrowser

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
sys.path.insert(0, HERE)
import strategy_config as cfg
from fib_bias import EDGES, LABELS, _sessions, TRADING

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
FIBS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
UP, DN = "#2ebd85", "#f6465d"


def zone_of(fp):
    for i in range(len(EDGES) - 1):
        if EDGES[i] <= fp < EDGES[i + 1]:
            return LABELS[i]
    return LABELS[-1]


def build():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    keep = et.year >= 2024                         # recent, relatable window for the gallery
    df, et = df[keep], et[keep]
    sess, mod = _sessions(et)
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)
    ts = (et.view("int64") // 1_000_000_000).astype("int64")
    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "open": df["open"].to_numpy(), "high": df["high"].to_numpy(),
                      "low": df["low"].to_numpy(), "close": df["close"].to_numpy(), "ts": np.asarray(ts)})
    f = f[np.isin(f["session"], TRADING)]
    inst = []
    for (date, s), g in f.groupby(["date", "session"], sort=False):
        lo, hi = float(g["low"].min()), float(g["high"].max())
        if hi <= lo:
            continue
        inst.append({"sid": f"{date} {s}", "date": date, "session": s,
                     "start": int(g["ts"].min()), "end": int(g["ts"].max()),
                     "low": lo, "high": hi, "open": float(g["open"].iloc[0]), "close": float(g["close"].iloc[-1]),
                     "fpos": (float(g["close"].iloc[-1]) - lo) / (hi - lo)})
    inst.sort(key=lambda r: r["start"])
    for i, r in enumerate(inst):
        nx = inst[i + 1] if i + 1 < len(inst) else None
        r["next"] = nx
        r["next_dir"] = (1 if nx["close"] >= nx["open"] else 0) if nx else None
    return df, [r for r in inst if r["next"]]


def _svg(df, r):
    CW, CH, CT, CB = 620, 250, 14, 232
    L, MID, R = 44, 400, 596
    a = pd.Timestamp(r["start"], unit="s", tz="UTC"); b = pd.Timestamp(r["end"], unit="s", tz="UTC")
    nx = r["next"]; na = pd.Timestamp(nx["start"], unit="s", tz="UTC"); nb = pd.Timestamp(nx["end"], unit="s", tz="UTC")
    cur = df.loc[a:b]; nxt = df.loc[na:nb]
    allLo = min(r["low"], nx["low"]); allHi = max(r["high"], nx["high"])
    pad = max((allHi - allLo) * 0.06, 1); tp, bp = allHi + pad, allLo - pad
    Y = lambda p: CT + (tp - p) / (tp - bp) * (CB - CT)
    e = []
    # fib lines off THIS session's range (left region only)
    for fr in FIBS:
        price = r["low"] + fr * (r["high"] - r["low"]); y = Y(price)
        gold = fr in (0.618, 0.786); mid = fr == 0.5
        col = "#e0a94a" if gold else ("#c3c2b7" if mid else "#6b7280")
        e.append(f'<line x1="{L}" y1="{y:.1f}" x2="{MID}" y2="{y:.1f}" stroke="{col}" stroke-width="{1.2 if mid or gold else 0.8}" stroke-dasharray="{"" if mid else "3 3"}"/>')
        e.append(f'<text x="{L-2:.1f}" y="{y-1.5:.1f}" fill="{col}" font-size="8.5" text-anchor="end">{fr*100:.1f}</text>')
    # candles helper
    def candles(bars, x0, x1, tint=None):
        n = len(bars); step = (x1 - x0) / max(n, 1); bw = min(7, step * 0.7)
        for i, (_, k) in enumerate(bars.iterrows()):
            x = x0 + (i + 0.5) * step; col = tint or (UP if k["close"] >= k["open"] else DN)
            e.append(f'<line x1="{x:.1f}" y1="{Y(k["high"]):.1f}" x2="{x:.1f}" y2="{Y(k["low"]):.1f}" stroke="{col}" stroke-width="0.9"/>')
            yo, yc = Y(k["open"]), Y(k["close"])
            e.append(f'<rect x="{x-bw/2:.1f}" y="{min(yo,yc):.1f}" width="{bw:.1f}" height="{max(1,abs(yc-yo)):.1f}" fill="{col}"/>')
    candles(cur, L, MID)
    # close marker (the fpos the code reads)
    yc = Y(r["close"])
    e.append(f'<circle cx="{MID:.1f}" cy="{yc:.1f}" r="3.5" fill="#fff"/>')
    e.append(f'<text x="{MID-6:.1f}" y="{yc-5:.1f}" fill="#fff" font-size="9" text-anchor="end">close &#8594; fpos {r["fpos"]:.2f}</text>')
    # divider + next session (tinted by its direction = the outcome measured)
    e.append(f'<line x1="{MID+8}" y1="{CT}" x2="{MID+8}" y2="{CB}" stroke="#3a3a38" stroke-width="1" stroke-dasharray="2 3"/>')
    ntint = UP if r["next_dir"] else DN
    candles(nxt, MID + 14, R, tint=ntint)
    e.append(f'<text x="{(MID+14+R)/2:.1f}" y="{CT+10:.1f}" fill="{ntint}" font-size="10" text-anchor="middle">NEXT: {"UP" if r["next_dir"] else "DOWN"}</text>')
    e.append(f'<text x="{(L+MID)/2:.1f}" y="{CT+10:.1f}" fill="#8a8781" font-size="9.5" text-anchor="middle">this session + fib</text>')
    return f'<svg viewBox="0 0 {CW} {CH}" width="{CW}" height="{CH}">' + "".join(e) + "</svg>"


def main():
    df, inst = build()
    inst.sort(key=lambda r: r["fpos"])
    # a spread across the range: 2 deep-low, 2 middle, 2 deep-high closes
    n = len(inst); picks = inst[:2] + inst[n//2-1:n//2+1] + inst[-2:]
    cards = []
    for r in picks:
        z = zone_of(r["fpos"]); tdir = "UP" if r["close"] >= r["open"] else "DOWN"
        ndir = "UP" if r["next_dir"] else "DOWN"; ncol = UP if r["next_dir"] else DN
        cards.append(f'''<div class="card">
  <div class="head"><span class="tag">{r["session"]}</span><b>{r["date"]}</b>
    <span class="mut">fib zone: {z}</span></div>
  <div class="body"><div class="chart">{_svg(df, r)}</div>
    <div class="score">
      <div class="r"><span>close position (fpos)</span><b>{r["fpos"]:.3f}</b></div>
      <div class="r"><span>&#8594; fib zone</span><b>{z}</b></div>
      <div class="r"><span>this session dir</span><b>{tdir}</b></div>
      <div class="r"><span>NEXT session dir</span><b style="color:{ncol}">{ndir}</b></div>
      <div class="note">the test asks: does the zone (left) predict NEXT dir (right)?<br>across 7,764 sessions it does not (F11) &#8212; fib = geometry, not direction.</div>
    </div></div></div>''')
    html = f'''<!doctype html><html><head><meta charset="utf-8"><title>fib_bias — what the test sees</title>
<style>
:root{{--ink:#e6edf3;--mut:#8a94a6;--bg:#0e1117;--card:#161b22;--bd:#232a33}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:22px}}
h1{{font-size:17px;margin:0 0 4px}}.lead{{color:var(--mut);margin:0 0 18px;max-width:900px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:10px;margin:0 0 15px;overflow:hidden}}
.head{{display:flex;gap:10px;align-items:center;padding:9px 12px;border-bottom:1px solid var(--bd)}}
.tag{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;border:1px solid var(--bd);color:var(--mut)}}
.mut{{color:var(--mut);margin-left:auto;font-size:12px}}.body{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.chart{{padding:6px 4px 6px 8px}}svg{{display:block}}
.score{{flex:1;min-width:280px;padding:12px 16px}}
.r{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1c2330}}.r span{{color:var(--mut)}}.r b{{font-weight:600}}
.note{{color:var(--mut);font-size:11px;margin-top:9px;line-height:1.5}}
</style></head><body>
<h1>fib_bias &#8212; exactly what the edge test sees</h1>
<p class="lead">LEFT of each chart = the session with its own fib retracement lines (golden zone 61.8/78.6 in amber, 50 in white);
the white dot is the <b>close</b> &#8212; where it lands gives <code>fpos</code> and the fib zone. RIGHT = the NEXT session's
candles, tinted by its open&#8594;close direction. The test buckets by the left zone and asks whether the right direction follows.
It doesn't (base 54.3%, all zones 51.8&#8211;56.4%, F11) &#8212; so fib stays as chart geometry, not a signal.</p>
{"".join(cards)}
</body></html>'''
    out = os.path.join(OUT, "fib_examples.html")
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, f"({len(picks)} examples)")
    webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
