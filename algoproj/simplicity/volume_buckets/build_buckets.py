"""
volume_buckets — hierarchical volume profile of NQ across every time scale.

The first foundation job of `simplicity`. Take the full ~20 years of NQ and bucket
the timeline top-down:

    all  ->  year  ->  quarter  ->  month  ->  day  ->  hour / session

and for every slice at every level, record the TOTAL VOLUME (in real NQ contracts).

------------------------------------------------------------------------------------
DATA-QUALITY REALITY (see NOTES.md "F1 — the volume-data finding")
------------------------------------------------------------------------------------
Only the 1-DAY parquet has trustworthy volume (~381k contracts/day, matches real NQ).
Every INTRADAY parquet (1m/5m/15m/60m) has volume inflated by a per-day factor that
itself varies 600x-9800x (CV 1.59) -- garbage in absolute terms. BUT the *aggregate
intraday shape* is clean (RTH-concentrated U-curve, 17:00 ET maintenance break ~0).

Therefore:
  * all / year / quarter / month / day  -> REAL volume, straight from the 1d parquet.
  * hour / session                      -> the real DAY volume, SPLIT by the intraday
                                           (5m) volume proportions within that day,
                                           after winsorizing each day's bars at the
                                           99th pct to kill the corrupt spike-bars.
                                           Absolute hour/session totals are therefore
                                           real-contract-SCALED estimates, not raw
                                           intraday volume. Shapes (profiles) are real.

Everything is bucketed on the EASTERN (America/New_York) calendar/clock, because NQ
liquidity follows the US session and every sibling strategy uses ET.

Span: 20 full calendar years 2005-2024 (the data runs 2005-01-11..2025-01-10; we drop
the 10-day 2025 tail and treat 2005 as a full year -- it is short its first ~7 trading
days, immaterial). 20 years -> 80 quarters -> 240 months -> ~5030 trading days.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "NQdata"))
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

ET = "America/New_York"
Y0, Y1 = 2005, 2024  # inclusive, 20 full calendar years

# ET session partition of the 24h day (no gaps, covers all 24h) -- documented in NOTES.
# (start_hour, start_min) inclusive .. next session's start exclusive, wrapping midnight.
SESSIONS = [
    ("asia",    18 * 60),        # 18:00 ET -> 03:00 ET  (Asia / overnight)
    ("london",   3 * 60),        # 03:00 ET -> 09:30 ET  (Europe / pre-open)
    ("newyork",  9 * 60 + 30),   # 09:30 ET -> 16:00 ET  (US RTH cash session)
    ("close",   16 * 60),        # 16:00 ET -> 18:00 ET  (post-close + maint break)
]


def _load_et(fname, cols=("volume",)):
    """Load a parquet, keep tz-aware, convert the index to ET."""
    d = pd.read_parquet(os.path.join(DATA_DIR, fname))
    d.index = pd.DatetimeIndex(d.index).tz_convert(ET)
    return d[list(cols)] if cols else d


def _minute_of_day(idx):
    return idx.hour * 60 + idx.minute


def _session_of(idx):
    """Vectorized session label from an ET DatetimeIndex."""
    mod = _minute_of_day(idx)
    lab = np.full(len(idx), "asia", dtype=object)
    lab[(mod >= 3 * 60) & (mod < 9 * 60 + 30)] = "london"
    lab[(mod >= 9 * 60 + 30) & (mod < 16 * 60)] = "newyork"
    lab[(mod >= 16 * 60) & (mod < 18 * 60)] = "close"
    return lab


def _write(df, name):
    path = os.path.join(OUT, name)
    if name.endswith(".parquet"):
        df.to_parquet(path)
    else:
        df.to_csv(path, index=False)
    return path


def main():
    # ---------------------------------------------------------------- real daily volume
    d1 = _load_et("NQ_1day_clean.parquet", cols=None)
    d1 = d1[(d1.index.year >= Y0) & (d1.index.year <= Y1)].copy()
    et_date = d1.index.tz_localize(None).normalize()  # ET calendar date of each daily bar
    daily = pd.DataFrame({
        "date": et_date,
        "year": et_date.year,
        "quarter": et_date.quarter,
        "month": et_date.month,
        "volume": d1["volume"].to_numpy(),
    })
    total_vol = int(daily["volume"].sum())
    print(f"span {Y0}-{Y1}  trading days {len(daily)}  total real volume {total_vol:,}")

    # ---------------------------------------------------------------- level: ALL
    _all = pd.DataFrame([{
        "slice": f"{Y0}-{Y1}", "trading_days": len(daily),
        "first_day": str(daily["date"].iloc[0].date()),
        "last_day": str(daily["date"].iloc[-1].date()),
        "volume": total_vol,
    }])
    _write(_all, "bucket_all.csv")

    # ---------------------------------------------------------------- level: YEAR
    yr = daily.groupby("year").agg(trading_days=("volume", "size"),
                                   volume=("volume", "sum")).reset_index()
    yr["pct_of_all"] = (yr["volume"] / total_vol * 100).round(3)
    _write(yr, "bucket_year.csv")

    # ---------------------------------------------------------------- level: QUARTER
    qt = daily.groupby(["year", "quarter"]).agg(trading_days=("volume", "size"),
                                                volume=("volume", "sum")).reset_index()
    qt["slice"] = qt["year"].astype(str) + "Q" + qt["quarter"].astype(str)
    qt["pct_of_all"] = (qt["volume"] / total_vol * 100).round(4)
    _write(qt[["slice", "year", "quarter", "trading_days", "volume", "pct_of_all"]],
           "bucket_quarter.csv")

    # ---------------------------------------------------------------- level: MONTH
    mo = daily.groupby(["year", "month"]).agg(trading_days=("volume", "size"),
                                              volume=("volume", "sum")).reset_index()
    mo["slice"] = mo["year"].astype(str) + "-" + mo["month"].astype(str).str.zfill(2)
    mo["pct_of_all"] = (mo["volume"] / total_vol * 100).round(4)
    _write(mo[["slice", "year", "month", "trading_days", "volume", "pct_of_all"]],
           "bucket_month.csv")

    # ---------------------------------------------------------------- level: DAY
    day_out = daily.copy()
    day_out["date"] = day_out["date"].dt.strftime("%Y-%m-%d")
    day_out["dow"] = pd.to_datetime(day_out["date"]).dt.day_name()
    _write(day_out[["date", "year", "quarter", "month", "dow", "volume"]],
           "bucket_day.parquet")

    # ============================================================ INTRADAY (5m shapes)
    # Real daily volume, keyed by ET date, to anchor the intraday splits.
    real_by_date = pd.Series(daily["volume"].to_numpy(),
                             index=pd.to_datetime(daily["date"]))

    v5 = _load_et("NQ_5min_clean.parquet")["volume"]
    v5 = v5[(v5.index.year >= Y0) & (v5.index.year <= Y1)]
    idx = v5.index
    f = pd.DataFrame({
        "date": idx.tz_localize(None).normalize(),
        "hour": idx.hour,
        "session": _session_of(idx),
        "raw": v5.to_numpy(dtype="float64"),
    })
    # winsorize each day's bars at its 99th pct -> kill the corrupt spike-bars
    cap = f.groupby("date")["raw"].transform(lambda s: s.quantile(0.99))
    f["w"] = np.minimum(f["raw"], cap)
    day_intraday = f.groupby("date")["w"].transform("sum")
    f["share"] = np.where(day_intraday > 0, f["w"] / day_intraday, 0.0)
    f["real_day_vol"] = real_by_date.reindex(f["date"].values).to_numpy()
    f["vol"] = f["share"] * f["real_day_vol"]  # real-contract-scaled intraday volume

    # ---------------------------------------------------------------- level: HOUR (per day x hour)
    hour = f.groupby(["date", "hour"])["vol"].sum().reset_index()
    hour["date"] = hour["date"].dt.strftime("%Y-%m-%d")
    hour["vol"] = hour["vol"].round(1)
    _write(hour, "bucket_hour.parquet")

    # ---------------------------------------------------------------- level: SESSION (per day x session)
    sess = f.groupby(["date", "session"])["vol"].sum().reset_index()
    sess["date"] = sess["date"].dt.strftime("%Y-%m-%d")
    sess["vol"] = sess["vol"].round(1)
    _write(sess, "bucket_session.parquet")

    # ---------------------------------------------------------------- aggregate PROFILES
    hp = f.groupby("hour")["vol"].sum()
    hp = pd.DataFrame({"hour_et": hp.index,
                       "volume": hp.values.round(0).astype("int64"),
                       "pct_of_all": (hp / total_vol * 100).round(3).values})
    _write(hp, "profile_hour_of_day.csv")

    sp = f.groupby("session")["vol"].sum().reindex([s for s, _ in SESSIONS])
    sp = pd.DataFrame({"session": sp.index,
                       "window_et": ["18:00-03:00", "03:00-09:30", "09:30-16:00", "16:00-18:00"],
                       "volume": sp.values.round(0).astype("int64"),
                       "pct_of_all": (sp / total_vol * 100).round(3).values})
    _write(sp, "profile_session.csv")

    # ---------------------------------------------------------------- console summary
    print("\nYEAR (real volume, % of 20y):")
    for _, r in yr.iterrows():
        print(f"  {int(r.year)}  {int(r.volume):>13,}  {r.pct_of_all:5.2f}%  ({int(r.trading_days)}d)")
    print("\nSESSION profile (real-scaled):")
    for _, r in sp.iterrows():
        print(f"  {r.session:<8} {r.window_et:<12} {int(r.volume):>15,}  {r.pct_of_all:5.2f}%")
    print("\nwrote 9 files to", OUT)


if __name__ == "__main__":
    main()
