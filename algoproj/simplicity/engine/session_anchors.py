"""
engine/session_anchors — session high/low levels + breach tracking. Promoted 2026-07-02.

Solidified from research/session_anchors. Self-contained (reads engine/data_feed, not research
artifacts). For each real session (Asia/London/NY) it fixes the high/low at session end and scans
forward to the first CLOSE through it (hit) else ongoing. Returns machine-usable level records the
strategy consumes; the breach data itself carries NO directional edge (research verdict) -- these
levels are structure/anchors for the Volume Profile, not a signal.

    from session_anchors import compute, check
    compute()            # all levels over the full 5m history
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

DESCRIBE = "session high/low levels + forward breach tracking (Asia/London/NY)"
MAX_FWD_BARS = 4000


def _sessions(et):
    mod = et.hour * 60 + et.minute
    lab = np.full(len(et), "asia", dtype=object)
    lab[(mod >= 180) & (mod < 570)] = "london"
    lab[(mod >= 570) & (mod < 960)] = "newyork"
    lab[(mod >= 960) & (mod < 1080)] = "close"
    return lab


def compute(df=None, tail=None):
    """List of session-level dicts: {date,session,sid,type,level,start,formed,hit,breach_ts,stop,duration_bars}."""
    if df is None:
        df = data_feed.load("5m")
    if tail:
        df = df.tail(tail)
    et = df.index.tz_convert(cfg.CLOCK)
    close = df["close"].to_numpy()
    ts = (et.view("int64") // 1_000_000_000).astype("int64")
    n = len(close)
    pos = {int(t): i for i, t in enumerate(ts)}
    mod = et.hour * 60 + et.minute
    sess = _sessions(et)
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)

    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(), "ts": ts})
    f = f[f["session"] != "close"]
    grp = f.groupby(["date", "session"], sort=False)
    hi = f.loc[grp["high"].idxmax()][["date", "session", "high", "ts"]].rename(columns={"ts": "high_ts"})
    lo = f.loc[grp["low"].idxmin()][["date", "session", "low", "ts"]].rename(columns={"ts": "low_ts"})
    ends = grp["ts"].max().reset_index().rename(columns={"ts": "end"})
    g = ends.merge(hi, on=["date", "session"]).merge(lo, on=["date", "session"]).sort_values("end")

    def breach(level, formed, direction):
        fi = pos[int(formed)]
        a, b = fi + 1, min(fi + 1 + MAX_FWD_BARS, n)
        win = close[a:b]
        hits = (win > level) if direction == "up" else (win < level)
        if hits.any():
            bi = a + int(hits.argmax())
            return {"hit": True, "breach_ts": int(ts[bi]), "stop": int(ts[bi]), "duration_bars": int(bi - fi)}
        return {"hit": False, "breach_ts": None, "stop": int(ts[-1]), "duration_bars": None}

    out = []
    for r in g.itertuples():
        for typ, lvl, ext, dr in (("high", r.high, r.high_ts, "up"), ("low", r.low, r.low_ts, "down")):
            out.append({"date": r.date, "session": r.session, "sid": f"{r.date} {r.session}",
                        "type": typ, "level": round(float(lvl), 2), "start": int(ext),
                        "formed": int(r.end), **breach(lvl, r.end, dr)})
    return out


def sessions(df=None, tail=None):
    """Per-session boundaries: {date, session, sid, open, close, high, low} (Asia/London/NY)."""
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
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    f = f[f["session"] != "close"]
    g = f.groupby(["date", "session"], sort=False).agg(
        open=("ts", "min"), close=("ts", "max"), high=("high", "max"), low=("low", "min")).reset_index()
    return [{"date": r.date, "session": r.session, "sid": f"{r.date} {r.session}",
             "open": int(r.open), "close": int(r.close), "high": round(float(r.high), 2),
             "low": round(float(r.low), 2)} for r in g.itertuples()]


def check():
    lv = compute(tail=20000)                      # recent ~2 months, fast readiness check
    hit = sum(1 for x in lv if x["hit"])
    pct = hit / len(lv) * 100 if lv else 0
    return f"{len(lv)} recent session levels ({pct:.0f}% hit); Asia/London/NY hi/lo + breach"


if __name__ == "__main__":
    print(check())
