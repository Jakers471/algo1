"""
volume_buckets — hierarchical VOLUME + VOLATILITY profile of NQ across every time scale.

The first foundation job of `simplicity`. Take the full ~20 years of NQ and bucket
the timeline top-down:

    all  ->  year  ->  quarter  ->  month  ->  day  ->  hour / session

and for every slice at every level, record:
  * TOTAL VOLUME (real NQ contracts)
  * four VOLATILITY stats (all in %):
      - Avg. Daily Range (%) = mean of (High-Low)/Close*100 per day
      - Mean Volatility (%)  = mean of |ln(Close/PrevClose)|*100  (avg abs daily move)
      - HV (%)               = std(log returns) * sqrt(252) * 100  (annualized hist. vol)
      - Volatility Range (%) = max(daily range %) - min(daily range %) over the slice

------------------------------------------------------------------------------------
DATA-QUALITY REALITY (see NOTES.md "F1 — the volume-data finding")
------------------------------------------------------------------------------------
Only the 1-DAY parquet has trustworthy VOLUME (~381k contracts/day). The intraday
parquets have volume inflated by a random per-day factor, but their PRICES (OHLC) are
fine -- so volatility is computed straight from OHLC at every scale.
  * VOLUME     all/year/quarter/month/day -> real 1d volume; hour/session -> real day
               volume split by winsorized intraday (5m) volume proportions.
  * VOLATILITY all/year/quarter/month/day -> from 1d OHLC (log returns + daily range).
               hour/session               -> from 5m OHLC (each day's per-hour / per-
               session range and open->close return; HV annualized with sqrt(252)
               since each day contributes one observation of that hour/session).

Intraday HV/vol_range at day level are undefined (need >1 observation) -> left blank.
Everything is bucketed on the EASTERN (America/New_York) calendar/clock.

Span: 20 full calendar years 2005-2024 (data runs 2005-01-11..2025-01-10; drop the
10-day 2025 tail, treat 2005 as a full year). 20y -> 80 quarters -> 240 months ->
~5030 trading days.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as _cfg

DATA_DIR = _cfg.DATA_DIR
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

ET = "America/New_York"
Y0, Y1 = 2005, 2024
ANN = np.sqrt(252.0)  # trading days / year, for annualizing HV

SESSIONS = [
    ("asia",    18 * 60),        # 18:00 ET -> 03:00 ET
    ("london",   3 * 60),        # 03:00 ET -> 09:30 ET
    ("newyork",  9 * 60 + 30),   # 09:30 ET -> 16:00 ET  (US RTH)
    ("close",   16 * 60),        # 16:00 ET -> 18:00 ET
]


def _load_et(fname, cols=("volume",)):
    d = pd.read_parquet(os.path.join(DATA_DIR, fname))
    d.index = pd.DatetimeIndex(d.index).tz_convert(ET)
    return d[list(cols)] if cols else d


def _minute_of_day(idx):
    return idx.hour * 60 + idx.minute


def _session_of(idx):
    mod = _minute_of_day(idx)
    lab = np.full(len(idx), "asia", dtype=object)
    lab[(mod >= 3 * 60) & (mod < 9 * 60 + 30)] = "london"
    lab[(mod >= 9 * 60 + 30) & (mod < 16 * 60)] = "newyork"
    lab[(mod >= 16 * 60) & (mod < 18 * 60)] = "close"
    return lab


def _write(df, name):
    path = os.path.join(OUT, name)
    df.to_parquet(path) if name.endswith(".parquet") else df.to_csv(path, index=False)
    return path


def _daily_vol(daily, keys):
    """Volatility stats per group of trading days, from daily range% (rng) and log-ret (lr)."""
    g = daily.groupby(keys)
    out = g.agg(
        avg_range=("rng", "mean"),
        vol_range=("rng", lambda s: s.max() - s.min()),
        mean_vol=("lr", lambda s: s.abs().mean() * 100),
        hv=("lr", lambda s: s.std(ddof=1) * ANN * 100),
    )
    return out.round({"avg_range": 3, "vol_range": 3, "mean_vol": 3, "hv": 2})


def _intraday_vol(bucketed):
    """From per-(day,bucket) hi/lo/op/cl -> volatility profile per bucket.

    bucketed: DataFrame with columns [key, hi, lo, op, cl] (one row per day x bucket).
    Returns per-key: avg_range, vol_range, mean_vol, hv (all %).
    """
    b = bucketed.copy()
    b["rng"] = (b["hi"] - b["lo"]) / b["cl"] * 100
    b["ret"] = np.log(b["cl"] / b["op"])
    g = b.groupby("key")
    out = g.agg(
        avg_range=("rng", "mean"),
        vol_range=("rng", lambda s: s.max() - s.min()),
        mean_vol=("ret", lambda s: s.abs().mean() * 100),
        hv=("ret", lambda s: s.std(ddof=1) * ANN * 100),
    )
    return out.round({"avg_range": 3, "vol_range": 3, "mean_vol": 3, "hv": 2})


def main():
    # ============================================================ DAILY (1d OHLC)
    d1 = _load_et(_cfg.TF_SOURCES["1d"], cols=None)
    d1 = d1[(d1.index.year >= Y0) & (d1.index.year <= Y1)].copy()
    et_date = d1.index.tz_localize(None).normalize()
    daily = pd.DataFrame({
        "date": et_date, "year": et_date.year, "quarter": et_date.quarter,
        "month": et_date.month,
        "volume": d1["volume"].to_numpy(),
        "rng": ((d1["high"] - d1["low"]) / d1["close"] * 100).to_numpy(),
        "lr": np.log(d1["close"] / d1["close"].shift(1)).to_numpy(),
    })
    total_vol = int(daily["volume"].sum())
    print(f"span {Y0}-{Y1}  trading days {len(daily)}  total real volume {total_vol:,}")

    VC = ["mean_vol", "hv", "vol_range", "avg_range"]  # display order

    # ---------------------------------------------------------------- level: ALL
    _all = pd.DataFrame([{
        "slice": f"{Y0}-{Y1}", "trading_days": len(daily),
        "first_day": str(daily["date"].iloc[0].date()),
        "last_day": str(daily["date"].iloc[-1].date()),
        "volume": total_vol,
        "mean_vol": round(daily["lr"].abs().mean() * 100, 3),
        "hv": round(daily["lr"].std(ddof=1) * ANN * 100, 2),
        "vol_range": round(daily["rng"].max() - daily["rng"].min(), 3),
        "avg_range": round(daily["rng"].mean(), 3),
    }])
    _write(_all, "bucket_all.csv")

    # ---------------------------------------------------------------- level: YEAR
    yr = daily.groupby("year").agg(trading_days=("volume", "size"),
                                   volume=("volume", "sum")).reset_index()
    yr["pct_of_all"] = (yr["volume"] / total_vol * 100).round(3)
    yr = yr.merge(_daily_vol(daily, "year").reset_index(), on="year")
    _write(yr[["year", "trading_days", "volume", "pct_of_all"] + VC], "bucket_year.csv")

    # ---------------------------------------------------------------- level: QUARTER
    qt = daily.groupby(["year", "quarter"]).agg(trading_days=("volume", "size"),
                                                volume=("volume", "sum")).reset_index()
    qt["slice"] = qt["year"].astype(str) + "Q" + qt["quarter"].astype(str)
    qt["pct_of_all"] = (qt["volume"] / total_vol * 100).round(4)
    qt = qt.merge(_daily_vol(daily, ["year", "quarter"]).reset_index(), on=["year", "quarter"])
    _write(qt[["slice", "year", "quarter", "trading_days", "volume", "pct_of_all"] + VC],
           "bucket_quarter.csv")

    # ---------------------------------------------------------------- level: MONTH
    mo = daily.groupby(["year", "month"]).agg(trading_days=("volume", "size"),
                                              volume=("volume", "sum")).reset_index()
    mo["slice"] = mo["year"].astype(str) + "-" + mo["month"].astype(str).str.zfill(2)
    mo["pct_of_all"] = (mo["volume"] / total_vol * 100).round(4)
    mo = mo.merge(_daily_vol(daily, ["year", "month"]).reset_index(), on=["year", "month"])
    _write(mo[["slice", "year", "month", "trading_days", "volume", "pct_of_all"] + VC],
           "bucket_month.csv")

    # ---------------------------------------------------------------- level: DAY
    day_out = daily.copy()
    day_out["date"] = day_out["date"].dt.strftime("%Y-%m-%d")
    day_out["dow"] = pd.to_datetime(day_out["date"]).dt.day_name()
    day_out["mean_vol"] = (day_out["lr"].abs() * 100).round(3)   # |that day's return|
    day_out["avg_range"] = day_out["rng"].round(3)               # that day's range
    _write(day_out[["date", "year", "quarter", "month", "dow", "volume", "mean_vol", "avg_range"]],
           "bucket_day.parquet")

    # ============================================================ INTRADAY (5m OHLCV)
    # Volume is now REAL (Up+Down, NOTES F4) -> use 5m volume directly, no anchoring.
    o5 = _load_et(_cfg.TF_SOURCES["5m"], cols=("open", "high", "low", "close", "volume"))
    o5 = o5[(o5.index.year >= Y0) & (o5.index.year <= Y1)]
    idx = o5.index
    base = pd.DataFrame({
        "date": idx.tz_localize(None).normalize(),
        "hour": idx.hour,
        "session": _session_of(idx),
        "open": o5["open"].to_numpy(), "high": o5["high"].to_numpy(),
        "low": o5["low"].to_numpy(), "close": o5["close"].to_numpy(),
        "vol": o5["volume"].to_numpy(dtype="float64"),   # real intraday volume
    })

    def _agg_ohlc(keys):
        return base.groupby(keys).agg(hi=("high", "max"), lo=("low", "min"),
                                      op=("open", "first"), cl=("close", "last")).reset_index()

    # ---------------------------------------------------------------- HOUR / SESSION (per day x bucket)
    hour = base.groupby(["date", "hour"])["vol"].sum().reset_index()
    hour["date"] = hour["date"].dt.strftime("%Y-%m-%d"); hour["vol"] = hour["vol"].round(1)
    _write(hour, "bucket_hour.parquet")
    sess = base.groupby(["date", "session"])["vol"].sum().reset_index()
    sess["date"] = sess["date"].dt.strftime("%Y-%m-%d"); sess["vol"] = sess["vol"].round(1)
    _write(sess, "bucket_session.parquet")

    # ---------------------------------------------------------------- aggregate PROFILES (+ intraday vol)
    hoh = _agg_ohlc(["date", "hour"]).rename(columns={"hour": "key"})
    hv = _intraday_vol(hoh[["key", "hi", "lo", "op", "cl"]])
    hp = base.groupby("hour")["vol"].sum()
    hp = pd.DataFrame({"hour_et": hp.index, "volume": hp.values.round(0).astype("int64"),
                       "pct_of_all": (hp / total_vol * 100).round(3).values}).set_index("hour_et")
    hp = hp.join(hv, how="left").reset_index()
    _write(hp[["hour_et", "volume", "pct_of_all"] + VC], "profile_hour_of_day.csv")

    soh = _agg_ohlc(["date", "session"]).rename(columns={"session": "key"})
    sv = _intraday_vol(soh[["key", "hi", "lo", "op", "cl"]])
    order = [s for s, _ in SESSIONS]
    sp = base.groupby("session")["vol"].sum().reindex(order)
    sp = pd.DataFrame({"session": order,
                       "window_et": ["18:00-03:00", "03:00-09:30", "09:30-16:00", "16:00-18:00"],
                       "volume": sp.values.round(0).astype("int64"),
                       "pct_of_all": (sp / total_vol * 100).round(3).values}).set_index("session")
    sp = sp.join(sv, how="left").reset_index()
    _write(sp[["session", "window_et", "volume", "pct_of_all"] + VC], "profile_session.csv")

    # ---------------------------------------------------------------- console summary
    print("\nYEAR  volume%   avgRange%  meanVol%   HV%   volRange%")
    for _, r in yr.iterrows():
        print(f"  {int(r.year)}  {r.pct_of_all:5.2f}   {r.avg_range:6.3f}   {r.mean_vol:6.3f}  "
              f"{r.hv:6.2f}   {r.vol_range:6.2f}")
    print("\nSESSION   window        volume%   avgRange%  meanVol%   HV%")
    for _, r in sp.iterrows():
        print(f"  {r.session:<8} {r.window_et:<12} {r.pct_of_all:5.2f}   {r.avg_range:6.3f}   "
              f"{r.mean_vol:6.3f}  {r.hv:6.2f}")
    print("\nwrote 9 files to", OUT)


if __name__ == "__main__":
    main()
