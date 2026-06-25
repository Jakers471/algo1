"""
Data loading helpers. Extracted from the repeated ``load()`` functions in the
research/ and viz/ scripts.

All loaders convert the tz-aware UTC DatetimeIndex to tz-naive (``tz_convert(None)``)
so downstream rolling / alignment math matches the original scripts exactly.
"""
import os
import pandas as pd

from config import DATA_DIR, VIX_CSV  # algoproj root must be on sys.path

# timeframe -> parquet filename
TF = {
    "1d":  "NQ_1day_clean.parquet",
    "60m": "NQ_60min_clean.parquet",
    "15m": "NQ_15min_clean.parquet",
    "5m":  "NQ_5min_clean.parquet",
    "1m":  "NQ_1min_clean.parquet",
}

_cache = {}


def load_tf(tf, use_cache=True):
    """Load a timeframe parquet from DATA_DIR -> OHLCV DataFrame with a tz-naive index.

    ``tf`` may be a key of TF (e.g. "15m") or a raw parquet filename / path.
    """
    if tf in TF:
        path = os.path.join(DATA_DIR, TF[tf])
    elif os.path.isabs(tf) or os.path.sep in tf:
        path = tf
    else:
        path = os.path.join(DATA_DIR, tf)
    if use_cache and path in _cache:
        return _cache[path]
    d = pd.read_parquet(path)
    d.index = pd.DatetimeIndex(d.index).tz_convert(None)
    if use_cache:
        _cache[path] = d
    return d


def align(series, target_index):
    """No-look-ahead higher-TF alignment: reindex onto target_index, forward-filled.

    Carries the last CLOSED higher-timeframe value onto the lower-timeframe clock.
    """
    return series.reindex(target_index, method="ffill")


def integrity_report(df, gap_sigma=8.0):
    """Data-quality / continuous-contract guard. Call before trusting a series.

    The NQ parquets here are a BACK-ADJUSTED continuous contract (verified: roll-
    window overnight gaps are no larger than ordinary overnight gaps, so there are
    no un-adjusted roll seams to fake out the indicators). This function keeps that
    honest going forward by flagging anything that would corrupt a backtest:
    duplicate/unsorted timestamps, NaNs, non-positive prices, OHLC inconsistencies,
    and bar-to-bar return jumps beyond `gap_sigma` standard deviations (a roll seam
    or bad print would show up here).

    Returns a dict; an empty `issues` list means the data is clean.
    """
    import numpy as np
    issues = []
    idx = pd.DatetimeIndex(df.index)
    if not idx.is_monotonic_increasing:
        issues.append("index not sorted ascending")
    if idx.duplicated().any():
        issues.append(f"{int(idx.duplicated().sum())} duplicate timestamps")
    for col in ("open", "high", "low", "close"):
        if col in df and df[col].isna().any():
            issues.append(f"{int(df[col].isna().sum())} NaNs in {col}")
        if col in df and (df[col] <= 0).any():
            issues.append(f"{int((df[col] <= 0).sum())} non-positive {col}")
    if {"high", "low"} <= set(df.columns) and (df["high"] < df["low"]).any():
        issues.append(f"{int((df['high'] < df['low']).sum())} bars with high < low")
    r = df["close"].pct_change().dropna() if "close" in df else pd.Series(dtype=float)
    jumps = 0
    if len(r) and r.std() > 0:
        jumps = int((r.abs() > gap_sigma * r.std()).sum())
        if jumps:
            issues.append(f"{jumps} bar return(s) > {gap_sigma}sigma (possible roll/bad print)")
    return {"rows": len(df), "first": str(idx[0]) if len(idx) else None,
            "last": str(idx[-1]) if len(idx) else None,
            "extreme_jumps": jumps, "issues": issues, "clean": not issues}


def load_vix():
    """Load the VIX history CSV -> Series of closes indexed by tz-naive date."""
    vraw = pd.read_csv(VIX_CSV)
    vraw["DATE"] = pd.to_datetime(vraw["DATE"])
    return vraw.set_index("DATE")["CLOSE"]
