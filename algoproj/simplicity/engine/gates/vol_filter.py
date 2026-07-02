"""
engine/vol_filter — the WHEN-TO-TRADE gate. Confirmed & promoted 2026-07-01.

Solidified from research/volatility_filter. Self-contained and live-ready: session &
hour from the pure ET clock (no data, no look-ahead); the optional daily vol-regime is
computed straight from engine/data_feed (raw daily OHLC), not any research artifact.
All toggles come from strategy_config (FILTER_SESSION / FILTER_HOUR / FILTER_DAY_VOL).
A bar is tradeable only if ALL enabled filters pass.

    from vol_filter import mask, passes, check
    mask(df.index)                 # boolean Series over an intraday index
    passes("2020-03-16 10:30")     # single bar (bare = ET wall-time) -> bool
    check()                        # -> "session=['newyork'] | hour=off | day_vol=off"
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

DESCRIBE = "when-to-trade gate: session/hour + optional daily vol-regime"
_regime_cache = None


def _et(index):
    idx = pd.DatetimeIndex(index)
    return idx.tz_convert(cfg.CLOCK) if idx.tz is not None else idx.tz_localize("UTC").tz_convert(cfg.CLOCK)


def _sessions(et_idx):
    mod = et_idx.hour * 60 + et_idx.minute
    lab = np.full(len(et_idx), "asia", dtype=object)
    lab[(mod >= 3 * 60) & (mod < 9 * 60 + 30)] = "london"
    lab[(mod >= 9 * 60 + 30) & (mod < 16 * 60)] = "newyork"
    lab[(mod >= 16 * 60) & (mod < 18 * 60)] = "close"
    return lab


def _regime_by_date():
    """date(YYYY-MM-DD) -> low/medium/high, from raw daily OHLC (causal trailing vol, era-cut)."""
    global _regime_cache
    if _regime_cache is not None:
        return _regime_cache
    d = data_feed.load("1d")
    et = _et(d.index)
    keep = et.year >= cfg.ERA_START_YEAR
    d, et = d[keep], et[keep]
    if cfg.VOL_METRIC == "mean_vol":
        metric = np.log(d["close"] / d["close"].shift(1)).abs() * 100
    else:
        metric = (d["high"] - d["low"]) / d["close"] * 100
    trail = metric.rolling(cfg.TRAIL_WINDOW).mean().shift(1)   # causal
    lo, hi = np.percentile(trail.dropna(), cfg.REGIME_PCTILES)

    def reg(x):
        if pd.isna(x):
            return "warmup"
        return "low" if x < lo else ("high" if x >= hi else "medium")

    dates = et.tz_localize(None).normalize().strftime("%Y-%m-%d")
    _regime_cache = dict(zip(dates, [reg(x) for x in trail]))
    return _regime_cache


def mask(index):
    """Boolean Series over an intraday DatetimeIndex: tradeable per the enabled config toggles."""
    et = _et(index)
    keep = np.ones(len(et), dtype=bool)
    if cfg.FILTER_SESSION["on"]:
        keep &= np.isin(_sessions(et), cfg.FILTER_SESSION["allow"])
    if cfg.FILTER_HOUR["on"]:
        keep &= np.isin(np.asarray(et.hour), cfg.FILTER_HOUR["allow"])
    if cfg.FILTER_DAY_VOL["on"]:
        reg = _regime_by_date()
        dates = et.tz_localize(None).normalize().strftime("%Y-%m-%d")
        rr = pd.Series(dates).map(reg).fillna("warmup").to_numpy()
        keep &= np.isin(rr, cfg.FILTER_DAY_VOL["regimes"])
    return pd.Series(keep, index=pd.DatetimeIndex(index))


def passes(ts):
    """Single-timestamp -> bool. Bare (naive) timestamps are read as ET wall-time."""
    t = pd.Timestamp(ts)
    if t.tz is None:
        t = t.tz_localize(cfg.CLOCK)
    return bool(mask(pd.DatetimeIndex([t])).iloc[0])


def check():
    s = f"session={cfg.FILTER_SESSION['allow']}" if cfg.FILTER_SESSION["on"] else "session=off"
    h = f"hour={cfg.FILTER_HOUR['allow']}" if cfg.FILTER_HOUR["on"] else "hour=off"
    dv = f"day_vol={cfg.FILTER_DAY_VOL['regimes']}" if cfg.FILTER_DAY_VOL["on"] else "day_vol=off"
    return f"{s} | {h} | {dv}"


if __name__ == "__main__":
    print(check())
    df = data_feed.load("5m")
    df = df[_et(df.index).year >= cfg.ERA_START_YEAR]
    m = mask(df.index)
    print(f"NQ 5m tradeable: {int(m.sum()):,}/{len(m):,} ({m.mean()*100:.1f}%)")
