"""
session_anchors — session high/low levels + FORWARD BREACH TRACKING (VISION step 3 / 13).

For every ET session (Asia / London / NY / Close) it fixes the session HIGH and LOW at
session end, then scans FORWARD: when does a later bar CLOSE through the level (close >
high, or close < low)? Each level is recorded as:
  * hit      -> price closed through it  (drawn SOLID, from formation to the breach)
  * ongoing  -> not breached as of the latest data (drawn DASHED, extends to now)
plus WHEN/WHERE it was hit, and how long it took (bars + seconds).

Breach is CLOSE-based on the 5m series. Forward scan is capped at MAX_FWD_BARS for speed;
a level not breached within the cap but whose window hits end-of-data = ongoing, else
'unbreached_cap' (only affects deep-history levels, never the recent chart window).

Run:  python research/session_anchors/session_anchors.py
Out:  output/session_anchors.json  (machine-readable; the chart inlines the in-window subset)
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
import strategy_config as cfg

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# the three real trading sessions (NOT "close" 16:00-18:00 = post-close + maintenance break)
COLORS = {"asia": "#a68cff", "london": "#1fc98d", "newyork": "#4a9bff"}  # brighter / more saturated
MAX_FWD_BARS = 4000  # ~14 trading days of 5m; cap on the forward breach scan


def main():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    close = df["close"].to_numpy()
    ts = (et.view("int64") // 1_000_000_000).astype("int64")   # unix sec per 5m bar
    n = len(close)
    data_end = int(ts[-1])
    pos = {int(t): i for i, t in enumerate(ts)}

    mod = et.hour * 60 + et.minute
    sess = np.full(n, "asia", dtype=object)
    sess[(mod >= 180) & (mod < 570)] = "london"
    sess[(mod >= 570) & (mod < 960)] = "newyork"
    sess[(mod >= 960) & (mod < 1080)] = "close"
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    early = (sess == "asia") & (mod < 180)
    sdate[early] = sdate[early] - pd.Timedelta(days=1)

    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
                      "ts": ts})
    f = f[f["session"] != "close"].reset_index(drop=True)  # anchors: real sessions only
    grp = f.groupby(["date", "session"], sort=False)
    hi = f.loc[grp["high"].idxmax()][["date", "session", "high", "ts"]].rename(columns={"ts": "high_ts"})
    lo = f.loc[grp["low"].idxmin()][["date", "session", "low", "ts"]].rename(columns={"ts": "low_ts"})
    ends = grp["ts"].max().reset_index().rename(columns={"ts": "end"})
    g = ends.merge(hi, on=["date", "session"]).merge(lo, on=["date", "session"]).sort_values("end")

    def breach(level, formed_ts, direction):
        """direction 'up' (close>level) or 'down' (close<level). -> dict."""
        fi = pos[int(formed_ts)]
        lo, hi = fi + 1, min(fi + 1 + MAX_FWD_BARS, n)
        win = close[lo:hi]
        hits = (win > level) if direction == "up" else (win < level)
        if hits.any():
            bi = lo + int(hits.argmax())
            return {"hit": True, "status": "hit", "breach_ts": int(ts[bi]),
                    "breach_price": round(float(close[bi]), 2),
                    "duration_bars": int(bi - fi), "duration_sec": int(ts[bi] - formed_ts),
                    "stop": int(ts[bi])}
        ongoing = hi >= n
        return {"hit": False, "status": "ongoing" if ongoing else "unbreached_cap",
                "breach_ts": None, "breach_price": None, "duration_bars": None,
                "duration_sec": None, "stop": data_end}

    levels = []
    for r in g.itertuples():
        # start = the timestamp the extreme was actually made (so the line touches the wick);
        # breach is scanned from session END (the level becomes S/R after the session closes).
        for typ, lvl, ext_ts, direction in (("high", r.high, r.high_ts, "up"),
                                            ("low", r.low, r.low_ts, "down")):
            b = breach(lvl, r.end, direction)
            levels.append({"date": r.date, "session": r.session, "sid": f"{r.date} {r.session}",
                           "type": typ, "level": round(float(lvl), 2), "start": int(ext_ts),
                           "formed": int(r.end), **b})

    # per-session boundaries (for the vertical open/close lines on the chart)
    opens, closes = grp["ts"].min(), grp["ts"].max()
    sessions = [{"date": d, "session": s, "sid": f"{d} {s}", "open": int(o), "close": int(closes[(d, s)])}
                for (d, s), o in opens.items()]

    out = {"colors": COLORS, "data_end": data_end, "max_fwd_bars": MAX_FWD_BARS,
           "levels": levels, "sessions": sessions}
    json.dump(out, open(os.path.join(OUT, "session_anchors.json"), "w"))

    n_hit = sum(1 for x in levels if x["hit"])
    n_ong = sum(1 for x in levels if x["status"] == "ongoing")
    dur = [x["duration_bars"] for x in levels if x["hit"]]
    print(f"wrote {len(levels):,} session levels to {OUT}")
    print(f"  hit {n_hit:,} ({n_hit/len(levels)*100:.1f}%) | ongoing {n_ong:,} | "
          f"capped {len(levels)-n_hit-n_ong:,}")
    if dur:
        med = int(np.median(dur))
        print(f"  median bars-to-breach {med} (~{med*5/60:.1f}h on 5m)")


if __name__ == "__main__":
    main()
