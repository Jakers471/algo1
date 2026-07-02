"""
engine/session_state — the session STATE MACHINE (the spine). Built 2026-07-02.

The foundation every downstream component reads. Event-driven / causal: given bars, it produces,
FOR EACH BAR, the live session context using only that bar and the ones before it (running values):

  session        current session (asia / london / newyork / close)  -- close = 16:00-18:00 gap
  sid            session-instance id  "<date> <session>"  (Asia's 00:00-03:00 folds to the prior day)
  session_open   ts the current session opened      time_in_sec    seconds elapsed in-session
  session_high   LIVE high so far this session       high_ts       when that high was made
  session_low    LIVE low  so far this session        low_ts        when that low was made
  next_session   the next session                    next_open      ts it opens
  time_until_sec seconds until the next open

Because every value is a running/cumulative computation over bars-so-far, a backtest that replays
bars (and only ever passes bars <= now) gets exactly what live would -- no look-ahead is possible.

    from session_state import frame, state_at, check
    f = frame()                 # per-bar state over the full 5m history (DataFrame)
    state_at()                  # dict for the latest bar (the "now" state)
    check()                     # readiness summary for the engine runner
"""
import os
import sys

import numpy as np
import pandas as pd

# --- engine path bootstrap: flat imports work from any engine/ subfolder ---
_E = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_E) != "engine":
    _E = os.path.dirname(_E)
for _d in [_E, os.path.dirname(_E)] + [os.path.join(_E, x) for x in os.listdir(_E) if os.path.isdir(os.path.join(_E, x))]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import strategy_config as cfg
import data_feed

DESCRIBE = "session state machine -- current/next session, live hi/lo, time-in/until (causal)"
TRADING = ("asia", "london", "newyork")        # 'close' (16:00-18:00) is a non-trading gap


def _sessions(et):
    mod = et.hour * 60 + et.minute
    lab = np.full(len(et), "asia", dtype=object)
    lab[(mod >= 180) & (mod < 570)] = "london"
    lab[(mod >= 570) & (mod < 960)] = "newyork"
    lab[(mod >= 960) & (mod < 1080)] = "close"
    return lab, mod


def frame(df=None, tail=None):
    """Per-bar session state (causal, running values). Returns a DataFrame indexed like `df`."""
    if df is None:
        df = data_feed.load("5m")
    if tail:
        df = df.tail(tail)
    et = df.index.tz_convert(cfg.CLOCK)
    sess, mod = _sessions(et)
    # session-instance date (Asia's 00:00-03:00 belongs to the prior day's Asia session)
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)
    sid = pd.Series(pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), index=df.index) + " " + pd.Series(sess, index=df.index)

    ts = pd.Series((et.view("int64") // 1_000_000_000).astype("int64"), index=df.index)
    hi = pd.Series(df["high"].to_numpy(), index=df.index)
    lo = pd.Series(df["low"].to_numpy(), index=df.index)
    g = sid.groupby(sid)  # for transforms keyed by session instance

    run_hi = hi.groupby(sid).cummax()
    run_lo = lo.groupby(sid).cummin()
    high_ts = ts.where(hi >= run_hi).groupby(sid).ffill()   # ts of the most recent running-high bar
    low_ts = ts.where(lo <= run_lo).groupby(sid).ffill()
    session_open = ts.groupby(sid).transform("min")

    # next session instance (ordered by open time) -> next_open / next_session per bar
    inst = pd.DataFrame({"sid": sid.values, "ts": ts.values, "session": sess}) \
        .groupby("sid", sort=False).agg(open=("ts", "min"), session=("session", "first")).reset_index() \
        .sort_values("open")
    inst["next_open"] = inst["open"].shift(-1)
    inst["next_session"] = inst["session"].shift(-1)
    nxt = inst.set_index("sid")[["next_open", "next_session"]]

    out = pd.DataFrame({
        "ts": ts, "session": sess, "sid": sid.values,
        "session_open": session_open.astype("int64"), "time_in_sec": (ts - session_open).astype("int64"),
        "session_high": run_hi.round(2), "session_low": run_lo.round(2),
        "high_ts": high_ts.astype("Int64"), "low_ts": low_ts.astype("Int64"),
        "next_open": sid.map(nxt["next_open"]).astype("Int64"),
        "next_session": sid.map(nxt["next_session"]),
    }, index=df.index)
    out["time_until_sec"] = (out["next_open"] - out["ts"]).astype("Int64")
    out["tradeable_session"] = out["session"].isin(TRADING)
    return out


def state_at(df=None):
    """Dict for the latest bar -- the 'now' state the engine acts on."""
    f = frame(df if df is not None else data_feed.load("5m").tail(2000))
    r = f.iloc[-1]
    return {k: (int(r[k]) if isinstance(r[k], (int, np.integer)) or (hasattr(r[k], "dtype")) else r[k])
            for k in f.columns}


def check():
    r = frame(data_feed.load("5m").tail(2000)).iloc[-1]
    tin = int(r["time_in_sec"]) // 60
    nx = r["next_session"] if pd.notna(r["next_session"]) else "(end of data)"
    tu = f"{int(r['time_until_sec']) // 60}m" if pd.notna(r["time_until_sec"]) else "n/a"
    return f"state machine live: in {r['session']} ({tin}m elapsed), next {nx} in {tu}; hi/lo + timing tracked"


if __name__ == "__main__":
    print(check())
