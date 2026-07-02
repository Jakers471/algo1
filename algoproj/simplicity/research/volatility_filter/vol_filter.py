"""
vol_filter — the WHEN-TO-TRADE gate (RESEARCH; promote to engine/ once confirmed).

Filters intraday timestamps by SESSION and/or HOUR (the core -- trade inside
high-activity windows), with an optional DAILY vol-regime gate. Each filter toggles
independently in strategy_config (FILTER_SESSION / FILTER_HOUR / FILTER_DAY_VOL); a
bar is tradeable only if ALL *enabled* filters pass.

  * session/hour  -> pure ET clock (no look-ahead).
  * day_vol       -> causal trailing-vol regime (mean of prior TRAIL_WINDOW days'
                     VOL_METRIC, era-cut, low/med/high by REGIME_PCTILES).

    from vol_filter import mask, passes, daily_frame, summary
    mask(df.index)              # boolean Series over an intraday index
    passes("2020-03-16 10:30")  # single timestamp -> bool
    daily_frame()               # per-day regime table (for filter_variants / day_vol)
    summary()                   # which filters are on + % of NQ 5m bars tradeable
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as cfg

DAY_FILE = os.path.join(cfg.BUCKETS_OUT, "bucket_day.parquet")
_cache = None


def daily_frame():
    """All trading days from ERA_START_YEAR on, with causal trailing vol + regime label."""
    global _cache
    if _cache is not None:
        return _cache
    d = pd.read_parquet(DAY_FILE)
    d = d[d["year"] >= cfg.ERA_START_YEAR].reset_index(drop=True)
    v = d[cfg.VOL_METRIC].astype(float)
    d["trail_vol"] = v.rolling(cfg.TRAIL_WINDOW).mean().shift(1).round(3)  # causal (prior window)

    lo, hi = np.percentile(d["trail_vol"].dropna(), cfg.REGIME_PCTILES)
    d.attrs["thresh"] = (round(float(lo), 3), round(float(hi), 3))

    def _regime(x):
        if pd.isna(x):
            return "warmup"
        if x < lo:
            return "low"
        return "high" if x >= hi else "medium"

    d["regime"] = d["trail_vol"].map(_regime)
    _cache = d
    return d  # regime table; the actual gate is mask() (session/hour/day_vol)


# ---- intraday gate: session AND hour AND (optional) day-vol, each toggled in config ----
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
    d = daily_frame()
    return dict(zip(d["date"], d["regime"]))


def mask(index):
    """Boolean Series over an intraday DatetimeIndex: which bars are tradeable per the
    config toggles (session AND hour AND day-vol -- only the ones with on=True)."""
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
    """Single-timestamp convenience -> bool. Bare (naive) timestamps are read as ET wall-time."""
    t = pd.Timestamp(ts)
    if t.tz is None:
        t = t.tz_localize(cfg.CLOCK)
    return bool(mask(pd.DatetimeIndex([t])).iloc[0])


def summary():
    on = []
    if cfg.FILTER_SESSION["on"]:
        on.append(f"session={cfg.FILTER_SESSION['allow']}")
    if cfg.FILTER_HOUR["on"]:
        on.append(f"hour={cfg.FILTER_HOUR['allow']}")
    if cfg.FILTER_DAY_VOL["on"]:
        d = daily_frame(); lo, hi = d.attrs["thresh"]
        on.append(f"day_vol={cfg.FILTER_DAY_VOL['regimes']} (era>={cfg.ERA_START_YEAR}, "
                  f"{cfg.VOL_METRIC}, low<{lo}%/{hi}%<=high)")
    print("WHEN-TO-TRADE gate (enabled filters, ANDed):")
    print("  " + ("  |  ".join(on) if on else "(none enabled -> trades everything)"))
    # demonstrate the effect on real NQ 5m
    p = os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"])
    if os.path.exists(p):
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(df.index)
        df = df[df.index.year >= cfg.ERA_START_YEAR]
        m = mask(df.index)
        print(f"  -> {int(m.sum()):,} / {len(m):,} NQ 5m bars tradeable ({m.mean()*100:.1f}%)")


if __name__ == "__main__":
    summary()
