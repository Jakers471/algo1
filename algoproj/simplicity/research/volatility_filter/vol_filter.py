"""
vol_filter — the calendar volatility gate (RESEARCH; promote to engine/ once confirmed).

Given the daily volume/volatility buckets, it:
  1. cuts the low-vol early decade (strategy_config.ERA_START_YEAR),
  2. builds a CAUSAL trailing volatility estimate (mean of the prior TRAIL_WINDOW
     days' VOL_METRIC -- shifted so today's realized range never decides today),
  3. classifies each day low / medium / high by REGIME_PCTILES, and
  4. exposes `passes(date)` -> may the strategy act on this day?

Parameters come from strategy_config (the single source of truth). This is the v0
gate; keep it dumb and honest. When confirmed it gets solidified into engine/.

    from vol_filter import daily_frame, passes, summary
    df = daily_frame()          # every trading day + trail_vol / regime / tradeable
    passes("2020-03-16")        # True/False
    summary()                   # regime counts + thresholds
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
    floor_ok = True if cfg.MIN_TRAIL_VOL is None else (d["trail_vol"] >= cfg.MIN_TRAIL_VOL)
    d["tradeable"] = d["regime"].isin(cfg.TRADEABLE_REGIMES) & floor_ok
    _cache = d
    return d


def passes(date):
    """Would the strategy be allowed to act on `date` (YYYY-MM-DD)? False if unknown."""
    d = daily_frame()
    row = d[d["date"] == str(date)]
    return bool(row["tradeable"].iloc[0]) if len(row) else False


def summary():
    d = daily_frame()
    lo, hi = d.attrs["thresh"]
    print(f"era >= {cfg.ERA_START_YEAR}  |  metric={cfg.VOL_METRIC}  |  trail={cfg.TRAIL_WINDOW}d")
    print(f"regime thresholds (trailing {cfg.VOL_METRIC}): low<{lo}%  medium  {hi}%<=high")
    print(f"tradeable regimes: {cfg.TRADEABLE_REGIMES}"
          + (f"  floor>={cfg.MIN_TRAIL_VOL}%" if cfg.MIN_TRAIL_VOL else ""))
    counts = d["regime"].value_counts()
    tot = len(d)
    for r in ["low", "medium", "high", "warmup"]:
        n = int(counts.get(r, 0))
        print(f"  {r:<7} {n:>5} days  {n/tot*100:5.1f}%")
    trd = int(d["tradeable"].sum())
    print(f"  -> tradeable {trd} days ({trd/tot*100:.1f}% of the era)")


if __name__ == "__main__":
    summary()
