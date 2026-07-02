"""
session_anchors — per-session high / low / open anchors (VISION step 3).

For every ET session of every day (Asia / London / New York / Close) computes the
session's HIGH, LOW, OPEN and its time span. These are the reference levels the Volume
Profile (Phase 3) gets built between, and the color-coded levels drawn on the chart.

Asia wraps midnight (18:00 -> 03:00 ET): its 00:00-03:00 bars are folded back onto the
prior day's session so each session is one contiguous span.

Run:  python research/session_anchors/session_anchors.py
Out:  output/session_anchors.json  ({colors, anchors:[{date,session,high,low,open,start,end}]})
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as cfg

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# color-coded per session (distinct, dark-theme friendly)
COLORS = {"asia": "#9085e9", "london": "#199e70", "newyork": "#3987e5", "close": "#d95926"}


def main():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    mod = et.hour * 60 + et.minute

    sess = np.full(len(et), "asia", dtype=object)
    sess[(mod >= 180) & (mod < 570)] = "london"
    sess[(mod >= 570) & (mod < 960)] = "newyork"
    sess[(mod >= 960) & (mod < 1080)] = "close"

    sdate = pd.Series(et.tz_localize(None).normalize().values)
    asia_early = (sess == "asia") & (mod < 180)          # 00:00-03:00 -> prior day's Asia session
    sdate[asia_early] = sdate[asia_early] - pd.Timedelta(days=1)

    f = pd.DataFrame({
        "date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"),
        "session": sess,
        "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
        "open": df["open"].to_numpy(),
        "ts": (et.view("int64") // 1_000_000_000),      # unix seconds (absolute)
    })
    g = f.groupby(["date", "session"], sort=False)
    a = g.agg(high=("high", "max"), low=("low", "min"), open=("open", "first"),
              start=("ts", "min"), end=("ts", "max")).reset_index()
    a = a.sort_values("start")

    anchors = [{"date": r.date, "session": r.session,
                "high": round(float(r.high), 2), "low": round(float(r.low), 2),
                "open": round(float(r.open), 2), "start": int(r.start), "end": int(r.end)}
               for r in a.itertuples()]
    json.dump({"colors": COLORS, "anchors": anchors},
              open(os.path.join(OUT, "session_anchors.json"), "w"))

    print(f"wrote {len(anchors):,} session anchors to {OUT}")
    counts = a["session"].value_counts()
    for s in ["asia", "london", "newyork", "close"]:
        print(f"  {s:<8} {int(counts.get(s, 0)):>6} sessions   color {COLORS[s]}")


if __name__ == "__main__":
    main()
