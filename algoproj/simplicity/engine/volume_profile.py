"""
engine/volume_profile — per-session Volume Profile (POC + Value Area). Promoted 2026-07-02.

Solidified from research/volume_profile. Self-contained via engine/data_feed. One profile per
session (Asia/London/NY), bounded by that session's high<->low, real Up+Down volume binned by
close at ROW_SIZE points/row -> POC (balance) + Value Area (VAL/VAH, VA_PCT of volume). Returns
machine-usable records the strategy consumes; the chart is just a view of these numbers.

    from volume_profile import compute, check
    compute()            # all sessions over the full 5m history
    compute(tail=20000)  # recent slice (fast)
    check()              # readiness summary for the engine runner
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # engine/  (data_feed)
sys.path.insert(0, os.path.dirname(HERE))      # simplicity/  (strategy_config)
import strategy_config as cfg
import data_feed

DESCRIBE = "per-session volume profile: POC + value area (VAL/VAH)"
ROW_SIZE = 2.0
VA_PCT = 0.70


def _sessions(et):
    mod = et.hour * 60 + et.minute
    lab = np.full(len(et), "asia", dtype=object)
    lab[(mod >= 180) & (mod < 570)] = "london"
    lab[(mod >= 570) & (mod < 960)] = "newyork"
    lab[(mod >= 960) & (mod < 1080)] = "close"
    return lab


def _value_area(vbin, edges):
    total = vbin.sum()
    if total <= 0:
        return None
    poc = int(vbin.argmax())
    lo = hi = poc
    acc = vbin[poc]
    n = len(vbin)
    while acc < total * VA_PCT and (lo > 0 or hi < n - 1):
        up = vbin[hi + 1] if hi < n - 1 else -1.0
        dn = vbin[lo - 1] if lo > 0 else -1.0
        if up >= dn:
            hi += 1; acc += vbin[hi]
        else:
            lo -= 1; acc += vbin[lo]
    return round((edges[poc] + edges[poc + 1]) / 2, 2), round(float(edges[lo]), 2), round(float(edges[hi + 1]), 2)


def compute(df=None, tail=None):
    if df is None:
        df = data_feed.load("5m")
    if tail:
        df = df.tail(tail)
    et = df.index.tz_convert(cfg.CLOCK)
    mod = et.hour * 60 + et.minute
    sess = _sessions(et)
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)
    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
                      "close": df["close"].to_numpy(), "vol": df["volume"].to_numpy(dtype="float64"),
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    f = f[f["session"] != "close"]

    out = []
    for (date, s), g in f.groupby(["date", "session"], sort=False):
        sl, sh = float(g["low"].min()), float(g["high"].max())
        if sh <= sl:
            continue
        nb = max(3, int(round((sh - sl) / ROW_SIZE)))
        edges = np.linspace(sl, sh, nb + 1)
        vbin, _ = np.histogram(g["close"].to_numpy(), bins=edges, weights=g["vol"].to_numpy())
        va = _value_area(vbin, edges)
        if va is None:
            continue
        poc, val, vah = va
        centers = (edges[:-1] + edges[1:]) / 2
        bins = [{"p": round(float(centers[i]), 2), "v": round(float(vbin[i]), 1),
                 "va": bool(val <= centers[i] <= vah)} for i in range(nb) if vbin[i] > 0]
        out.append({"date": date, "session": s, "sid": f"{date} {s}", "high": round(sh, 2),
                    "low": round(sl, 2), "poc": poc, "val": val, "vah": vah,
                    "start": int(g["ts"].min()), "end": int(g["ts"].max()), "bars": int(len(g)),
                    "height_pct": round((sh - sl) / sl * 100, 3),
                    "va_pct_of_range": round((vah - val) / (sh - sl) * 100, 1), "bins": bins})
    return out


def check():
    p = compute(tail=20000)
    if not p:
        return "no profiles"
    va = np.median([x["va_pct_of_range"] for x in p])
    return f"{len(p)} recent session profiles; median VA {va:.0f}% of range; POC + value area ready"


if __name__ == "__main__":
    print(check())
