"""
Charting helpers.

lightweight_chart : the mod-menu styled lightweight-charts HTML with a stats +
    locked STRATEGY CONFIG panel, folded in from the scratchpad gen_chart.py
    (CSS / panel design preserved, parameterized so any strategy can use it).
fan_plot          : the 32-MA slope-colored fan PNG (from nq_ma_fan.py).
regime_ribbon     : the fractal-MA regime ribbon PNG (from nq_regime_ribbon.py).
"""
import json
import os

import numpy as np
import pandas as pd

GREEN = "#21a121"
RED = "#d62728"
YELLOW = "#f2c800"

# panel accent colors (from gen_chart.py)
_G = "#26a69a"
_R = "#ef5350"
_GOLD = "#f2c800"
_TL = "#2dd4bf"


def _kv(k, v, col="#e6edf3"):
    return f"<tr><td class=k>{k}</td><td class=v style='color:{col}'>{v}</td></tr>"


def _section(title, rows, lock=False):
    lock_html = " <span class=lock>&#128274; LOCKED</span>" if lock else ""
    body = "".join(_kv(k, v, c) if c else _kv(k, v) for k, v, c in rows)
    return f"<div class=sec>{title}{lock_html}</div><table>{body}</table>"


def lightweight_chart(candles, markers, strategy_config, stats, out_path,
                      title="STRATEGY", subtitle="research build",
                      header=None):
    """Write the mod-menu lightweight-charts HTML.

    candles : list of {time, open, high, low, close} dicts.
    markers : list of marker dicts (already sorted is fine; we sort defensively).
    strategy_config : dict of LOCKED config sections. Each value is either a list
        of (label, value) / (label, value, color) rows, OR a flat dict {label: value}.
        Keys become section headers; the first section gets the LOCKED badge.
    stats : dict of stats sections, same shape (e.g. {"PERFORMANCE": {...}, ...}).
    out_path : file to write (utf-8).
    title / subtitle : panel header text.
    header : optional <h3> text (defaults from title).
    """
    markers = sorted(markers, key=lambda m: m["time"])

    def _rows(val):
        if isinstance(val, dict):
            return [(k, v, None) for k, v in val.items()]
        out = []
        for row in val:
            if len(row) == 3:
                out.append((row[0], row[1], row[2]))
            else:
                out.append((row[0], row[1], None))
        return out

    title_html = (f"<div class=title>{title}</div>"
                  f"<div class=sub>{subtitle}</div>")

    cfg_html = ""
    for i, (name, val) in enumerate(strategy_config.items()):
        cfg_html += _section(name, _rows(val), lock=(i == 0))

    stats_html = "".join(_section(name, _rows(val)) for name, val in stats.items())

    panel = title_html + cfg_html + stats_html
    if header is None:
        header = f"{title} — green=BUY red=SELL"

    html = f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
body{{margin:0;background:#0b0c0e;color:#ddd;font-family:'Segoe UI',sans-serif}}
h3{{margin:7px 12px;font-weight:600;font-size:13px;color:#cbd5e1}}
#c{{position:absolute;top:36px;left:0;right:340px;bottom:0}}
#stats{{position:absolute;top:36px;right:0;width:340px;bottom:0;padding:14px 14px 28px;box-sizing:border-box;
 background:linear-gradient(180deg,#15171c,#0c0d10);border-left:2px solid #2dd4bf;
 font:12px/1.55 'Consolas',monospace;overflow:auto;box-shadow:-10px 0 28px #000b}}
.title{{font:800 17px 'Segoe UI',sans-serif;color:#fff;letter-spacing:.5px}}
.sub{{color:#7d8590;font-size:11px;margin-bottom:4px}}
.sec{{display:flex;justify-content:space-between;align-items:center;margin:16px 0 5px;
 font-weight:700;font-size:10px;letter-spacing:1.5px;color:#2dd4bf;text-transform:uppercase;
 border-bottom:1px solid #2dd4bf40;padding-bottom:4px}}
.lock{{color:#f59e0b;font-size:9px;border:1px solid #f59e0b66;border-radius:3px;padding:1px 6px;letter-spacing:.5px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:3px 2px;border-bottom:1px solid #1c1f24}}
td.k{{color:#8b98a5}} td.v{{text-align:right;color:#e6edf3;font-weight:600}}</style></head>
<body><h3>{header}</h3>
<div id=c></div><div id=stats>{panel}</div><script>
const chart=LightweightCharts.createChart(document.getElementById('c'),
 {{layout:{{background:{{color:'#111'}},textColor:'#ddd'}},grid:{{vertLines:{{color:'#222'}},horzLines:{{color:'#222'}}}},
   timeScale:{{timeVisible:true,secondsVisible:false}}}});
const s=chart.addCandlestickSeries();
s.setData({json.dumps(candles)}); s.setMarkers({json.dumps(markers)});
chart.timeScale().fitContent();
window.addEventListener('resize',()=>chart.applyOptions({{}}));
</script></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


# expose panel accent colors for callers building config/stats dicts
COLORS = dict(green=_G, red=_R, gold=_GOLD, teal=_TL)


# ---------------------------------------------------------------- matplotlib

def fan_plot(close, dt, lengths, slope_L=5, eps=0.15, out_path=None,
             title="NQ — 32-MA fan colored by slope  (green=up  red=down  yellow=sideways)",
             dpi=200):
    """Slope-colored 32-MA fan on log price. From nq_ma_fan.py.

    close : pandas Series of closes; dt : tz-naive DatetimeIndex; lengths : MA lengths.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Patch

    x = mdates.date2num(dt.to_pydatetime())
    ma = {n: close.rolling(n).mean() for n in lengths}
    start = max(lengths) + slope_L

    def slope_colors(n):
        sl = (ma[n] / ma[n].shift(slope_L) - 1) * 100
        return np.where(sl > eps, GREEN, np.where(sl < -eps, RED, YELLOW))

    fig, ax = plt.subplots(figsize=(22, 12))
    ax.set_yscale("log")
    ax.plot(x, close, color="black", lw=0.5, alpha=0.20, zorder=1)
    for n in lengths:
        y = ma[n].to_numpy()
        cols = slope_colors(n)
        xs, ys, cs = x[start:], y[start:], cols[start:]
        pts = np.array([xs, ys]).T.reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        ax.add_collection(LineCollection(segs, colors=cs[1:], linewidths=0.9, zorder=3))
    ax.set_xlim(x[start], x[-1])
    ax.set_ylim(close[start:].min() * 0.95, close.max() * 1.05)
    ax.set_title(title)
    ax.legend(handles=[Patch(color=GREEN, label="up"), Patch(color=RED, label="down"),
                       Patch(color=YELLOW, label="sideways")], loc="upper left", fontsize=11)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis_date()
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=dpi)
        plt.close()
    return out_path


def regime_ribbon(close, dt, ltf, mtf, htf, slope_L=10, comp_q=0.25,
                  comp_run=10, start=610, out_path=None, dpi=200):
    """Fractal-MA regime ribbon PNG. From nq_regime_ribbon.py.

    close : Series; dt : tz-naive index; ltf/mtf/htf : MA-length lists.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Patch

    g, orange, r, neutral = "#2ca02c", "#ff8c00", "#d62728", "#d9d9d9"
    all_ma = ltf + mtf + htf
    ma = {n: close.rolling(n).mean() for n in all_ma}
    slope_up = {n: (ma[n] > ma[n].shift(slope_L)).to_numpy() for n in all_ma}

    def tier_compressed(grp):
        s = pd.concat([ma[n] for n in grp], axis=1)
        spread = (s.max(axis=1) - s.min(axis=1)) / close * 100
        comp = spread < spread.rolling(252).quantile(comp_q)
        return comp.rolling(comp_run).min().fillna(0).astype(bool).to_numpy()

    comp = {"L": tier_compressed(ltf), "M": tier_compressed(mtf), "H": tier_compressed(htf)}
    tier_of = {**{n: "L" for n in ltf}, **{n: "M" for n in mtf}, **{n: "H" for n in htf}}

    htf_up = ((ma[htf[0]] > ma[htf[1]]) & (ma[htf[1]] > ma[htf[2]]) & (close > ma[htf[0]])).to_numpy()
    htf_dn = ((ma[htf[0]] < ma[htf[1]]) & (ma[htf[1]] < ma[htf[2]]) & (close < ma[htf[0]])).to_numpy()

    def color_at(n, i):
        if comp[tier_of[n]][i]:
            return orange
        if slope_up[n][i]:
            return neutral if htf_dn[i] else g
        return neutral if htf_up[i] else r

    x = mdates.date2num(dt.to_pydatetime())
    fig, ax = plt.subplots(figsize=(22, 11))
    ax.set_yscale("log")
    ax.plot(x, close, color="black", lw=0.5, alpha=0.25, zorder=1)
    for n in all_ma:
        y = ma[n].to_numpy()
        cols = [color_at(n, i) for i in range(len(close))]
        xs, ys, cs = x[start:], y[start:], cols[start:]
        pts = np.array([xs, ys]).T.reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        lw = 1.0 if tier_of[n] == "L" else (1.6 if tier_of[n] == "M" else 2.4)
        ax.add_collection(LineCollection(segs, colors=cs[1:], linewidths=lw, zorder=3))
    ax.set_xlim(x[start], x[-1])
    ax.set_ylim(close[start:].min() * 0.95, close.max() * 1.05)
    ax.set_title("NQ — fractal MAs painted by regime (HTF thick / MTF med / LTF thin)\n"
                 "orange=compressed  green=uptrend  red=downtrend  (HTF masks the opposite color)")
    ax.legend(handles=[Patch(color=g, label="uptrending"), Patch(color=orange, label="compressed"),
                       Patch(color=r, label="downtrending"), Patch(color=neutral, label="masked / neutral")],
              loc="upper left", fontsize=11)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis_date()
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=dpi)
        plt.close()
    return out_path
