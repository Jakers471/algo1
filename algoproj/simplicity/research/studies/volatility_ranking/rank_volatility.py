"""
rank_volatility — structured output on the MOST vs LEAST volatile periods.

Reads the volume_buckets volatility tables and, for each level (year / quarter /
month / day), ranks the slices by volatility (HV for multi-day levels, avg range for
days), most -> least, tags each with a High/Medium/Low regime (terciles within the
kept era), and writes sorted files. It also prints the EARLY-vs-RECENT era comparison
that motivates the cutoff (filter_config.ERA_START_YEAR), so the "the early decade is
calmer and would skew us" claim is shown, not assumed.

Run:  python simplicity/filters/rank_volatility.py
Out:  filters/output/rank_<level>.csv  +  era_comparison.csv  +  console report
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # simplicity/
import strategy_config as cfg

BK = cfg.BUCKETS_OUT
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
E = cfg.ERA_START_YEAR


def _regime_col(s):
    """Tercile High/Medium/Low by value within s."""
    lo, hi = np.percentile(s, [33.0, 66.0])
    return s.map(lambda x: "low" if x < lo else ("high" if x >= hi else "medium")), (round(lo, 3), round(hi, 3))


def _rank(df, key, sort_metric, keep_cols, name):
    """Sort a level's slices most->least volatile, tag regime, write CSV, return it."""
    d = df.copy()
    d["regime"], (lo, hi) = _regime_col(d[sort_metric])
    d = d.sort_values(sort_metric, ascending=False).reset_index(drop=True)
    d.insert(0, "rank", np.arange(1, len(d) + 1))
    cols = ["rank", key, sort_metric, "regime"] + [c for c in keep_cols if c != sort_metric]
    d[cols].to_csv(os.path.join(OUT, f"rank_{name}.csv"), index=False)
    return d[cols], (lo, hi)


def main():
    yr = pd.read_csv(os.path.join(BK, "bucket_year.csv"))
    qt = pd.read_csv(os.path.join(BK, "bucket_quarter.csv"))
    mo = pd.read_csv(os.path.join(BK, "bucket_month.csv"))
    day = pd.read_parquet(os.path.join(BK, "bucket_day.parquet"))

    # ---------------------------------------------------------- ERA comparison (year table)
    early = yr[yr.year < E]
    recent = yr[yr.year >= E]
    cmp = pd.DataFrame([
        {"era": f"full 2005-{yr.year.max()}", "years": len(yr),
         "mean_HV": round(yr.hv.mean(), 2), "mean_avg_range": round(yr.avg_range.mean(), 3),
         "mean_mean_vol": round(yr.mean_vol.mean(), 3)},
        {"era": f"early 2005-{E-1}", "years": len(early),
         "mean_HV": round(early.hv.mean(), 2), "mean_avg_range": round(early.avg_range.mean(), 3),
         "mean_mean_vol": round(early.mean_vol.mean(), 3)},
        {"era": f"recent {E}-{yr.year.max()}", "years": len(recent),
         "mean_HV": round(recent.hv.mean(), 2), "mean_avg_range": round(recent.avg_range.mean(), 3),
         "mean_mean_vol": round(recent.mean_vol.mean(), 3)},
    ])
    cmp.to_csv(os.path.join(OUT, "era_comparison.csv"), index=False)

    # ---------------------------------------------------------- keep only the era, then rank
    yrE = yr[yr.year >= E]
    qtE = qt[qt.year >= E]
    moE = mo[mo.year >= E]
    dayE = day[day.year >= E].copy()

    r_year, _ = _rank(yrE, "year", "hv", ["hv", "avg_range", "mean_vol", "vol_range", "volume"], "year")
    r_qt, _ = _rank(qtE, "slice", "hv", ["hv", "avg_range", "mean_vol", "vol_range", "volume"], "quarter")
    r_mo, thr_mo = _rank(moE, "slice", "hv", ["hv", "avg_range", "mean_vol", "vol_range", "volume"], "month")
    r_day, _ = _rank(dayE, "date", "avg_range", ["avg_range", "mean_vol", "volume"], "day")

    # ---------------------------------------------------------- console report
    def _blk(title, d, key, metric, unit="%"):
        print(f"\n{title}")
        print("  MOST volatile:")
        for _, r in d.head(5).iterrows():
            print(f"    {r[key]!s:<9} {r[metric]:>7.2f}{unit}  [{r.regime}]")
        print("  LEAST volatile:")
        for _, r in d.tail(5).iloc[::-1].iterrows():
            print(f"    {r[key]!s:<9} {r[metric]:>7.2f}{unit}  [{r.regime}]")

    print("=" * 68)
    print("ERA COMPARISON  (why cut the early decade)")
    print("=" * 68)
    for _, r in cmp.iterrows():
        print(f"  {r.era:<18} {int(r.years):>2}y   HV {r.mean_HV:6.2f}%   "
              f"avgRange {r.mean_avg_range:5.3f}%   meanVol {r.mean_mean_vol:5.3f}%")
    if len(early) and early.hv.mean() > 0:
        print(f"  -> recent-era HV is {recent.hv.mean()/early.hv.mean():.2f}x the early decade "
              f"=> keeping years >= {E}")

    print("\n" + "=" * 68)
    print(f"MOST vs LEAST VOLATILE  (kept era {E}-{int(yr.year.max())}, ranked by HV / day avg-range)")
    print("=" * 68)
    _blk("YEARS (by HV)", r_year, "year", "hv")
    _blk("QUARTERS (by HV)", r_qt, "slice", "hv")
    _blk("MONTHS (by HV)", r_mo, "slice", "hv")
    _blk("DAYS (by avg daily range)", r_day, "date", "avg_range")

    # regime split summary on months
    hi = r_mo[r_mo.regime == "high"]
    lo = r_mo[r_mo.regime == "low"]
    print(f"\nMONTH regime split (terciles, thresh HV {thr_mo[0]}/{thr_mo[1]}%):")
    print(f"  HIGH {len(hi):>3} months  mean HV {hi.hv.mean():5.2f}%  mean vol {hi.volume.mean():,.0f}")
    print(f"  LOW  {len(lo):>3} months  mean HV {lo.hv.mean():5.2f}%  mean vol {lo.volume.mean():,.0f}")

    print("\nwrote 6 files to", OUT)


if __name__ == "__main__":
    main()
