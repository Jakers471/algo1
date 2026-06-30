"""Candle anatomy — the measurement layer.

A single candle is a lossy, 4-number summary (O/H/L/C) of a hidden intrabar tick
path. These helpers turn any OHLC(V) frame into **scale-free geometric features**
that describe the *shape* of that path — body, wicks, where it closed, how
decisive it was — so a candle in 2005 at 4,700 is directly comparable to one in
2024 at 21,000.

There is no trading opinion in here. This is the vocabulary the conditional
forward-return studies (research/candle_anatomy/) and any future candle-geometry
strategy consume. Volume is intentionally left out of the geometry features — the
volume column in the NQ parquets is not yet vetted (impossible spikes), so anatomy
is built from price alone.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"

# the continuous geometric features anatomy() produces (direction is categorical)
FEATURES = ("body", "range", "body_frac", "close_loc", "upper_wick", "lower_wick")


def anatomy(df: pd.DataFrame) -> pd.DataFrame:
    """OHLC frame -> per-bar scale-free geometry.

    Returns a DataFrame aligned to ``df.index`` with:
      body        signed conviction, (close-open)/open
      range       total range fought, (high-low)/open
      body_frac   decisiveness 0..1, |close-open|/(high-low)  (doji -> ~0)
      close_loc   where it settled 0..1, (close-low)/(high-low)  (0=low, 1=high)
      upper_wick  rejection above, (high-max(o,c))/(high-low), frac of range
      lower_wick  rejection below, (min(o,c)-low)/(high-low), frac of range
      direction   sign of the body, in {-1, 0, +1}

    Zero-range bars (high == low, common in thin overnight minutes) have no
    interior shape: body_frac/wicks -> 0 and close_loc -> 0.5 (neutral).
    """
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float);  c = df["close"].to_numpy(float)
    rng = h - l
    body = c - o
    nz = rng > 0                      # bars that actually have an interior

    close_loc = np.where(nz, (c - l) / np.where(nz, rng, 1.0), 0.5)
    body_frac = np.where(nz, np.abs(body) / np.where(nz, rng, 1.0), 0.0)
    upper = np.where(nz, (h - np.maximum(o, c)) / np.where(nz, rng, 1.0), 0.0)
    lower = np.where(nz, (np.minimum(o, c) - l) / np.where(nz, rng, 1.0), 0.0)

    return pd.DataFrame({
        "body": body / o,
        "range": rng / o,
        "body_frac": body_frac,
        "close_loc": close_loc,
        "upper_wick": upper,
        "lower_wick": lower,
        "direction": np.sign(body),
    }, index=df.index)


# ----------------------------- session helpers -----------------------------
def to_ny(index) -> pd.DatetimeIndex:
    """Return ``index`` as a tz-aware America/New_York DatetimeIndex (DST-correct).

    Accepts tz-aware UTC (raw parquet) or tz-naive UTC (post ``load_tf``).
    """
    idx = pd.DatetimeIndex(index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.tz_convert(NY)


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def session_mask(index, start="09:30", end="16:00", weekdays_only=True) -> np.ndarray:
    """Boolean mask of bars whose timestamp falls in [start, end) New York time.

    Default window is the US equity cash session (09:30–16:00 ET), where NQ shows
    ~2.3x the per-bar range of the overnight session.
    """
    et = to_ny(index)
    mins = et.hour * 60 + et.minute
    m = (mins >= _hm(start)) & (mins < _hm(end))
    if weekdays_only:
        m &= et.weekday < 5
    return np.asarray(m)


def ny_day(index) -> np.ndarray:
    """Calendar ET date for each bar — used to keep forward windows intraday."""
    return to_ny(index).normalize().to_numpy()


# time-of-day buckets within the cash session (minutes from ET midnight)
TOD_BUCKETS = (
    ("open",      570, 600),   # 09:30–10:00  the open auction / first impulse
    ("morning",   600, 690),   # 10:00–11:30  the trend hour(s)
    ("midday",    690, 840),   # 11:30–14:00  lunch chop
    ("afternoon", 840, 930),   # 14:00–15:30  afternoon trend
    ("close",     930, 960),   # 15:30–16:00  the close
)
TOD_ORDER = [b[0] for b in TOD_BUCKETS]


def tod_bucket(index) -> np.ndarray:
    """Label each bar with its cash-session time-of-day bucket ('off' outside)."""
    et = to_ny(index)
    mins = et.hour * 60 + et.minute
    out = np.full(len(mins), "off", dtype=object)
    for name, lo, hi in TOD_BUCKETS:
        out[(mins >= lo) & (mins < hi)] = name
    return out


# ----------------------------- multi-candle structure -----------------------------
# continuous sequence features (computed across consecutive candles)
SEQ_FEATURES = ("mom2", "accel", "run_len", "rng_contract", "gap")


def sequence(df: pd.DataFrame) -> pd.DataFrame:
    """Per-bar features that need the candle's neighbours (structure across candles).

    mom2          2-bar net thrust: body + prior body (frac of price)
    accel         change in body vs the prior bar (impulse building or fading)
    run_len       signed count of consecutive same-direction bodies ending here
    rng_contract  this bar's range / mean range of the prior 3 (coil < 1, expansion > 1)
    gap           open vs prior close (frac of price) — overnight / between-bar gaps
    inside        1 if this bar's range is engulfed by the prior bar's (a coil)
    """
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float);  c = df["close"].to_numpy(float)
    n = len(c)
    body = (c - o) / o
    rng = (h - l) / o
    prev_body = np.r_[np.nan, body[:-1]]
    prev_c = np.r_[np.nan, c[:-1]]
    prev_h = np.r_[np.nan, h[:-1]]; prev_l = np.r_[np.nan, l[:-1]]

    sign = np.sign(c - o)
    run = np.zeros(n)
    for i in range(1, n):
        run[i] = run[i - 1] + sign[i] if sign[i] != 0 and sign[i] == sign[i - 1] else sign[i]

    rng_mean3 = pd.Series(rng).rolling(3).mean().shift(1).to_numpy()
    return pd.DataFrame({
        "mom2": body + prev_body,
        "accel": body - prev_body,
        "run_len": run,
        "rng_contract": rng / np.where(rng_mean3 > 0, rng_mean3, np.nan),
        "gap": (o - prev_c) / prev_c,
        "inside": ((h <= prev_h) & (l >= prev_l)).astype(float),
    }, index=df.index)
