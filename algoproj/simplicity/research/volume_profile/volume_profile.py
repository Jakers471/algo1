"""
volume_profile — one Volume Profile per session, bounded by that session's HIGH<->LOW.
VISION steps 4-6. NY with NY, London with London, Asia with Asia -> one profile each.

For every session instance: bin the price range [session low, session high] and distribute the
session's REAL 5m volume (Up+Down, NOTES F4) across the bins by close price. Then:
  * POC  = price bin with the most volume (the balance point)
  * Value Area (VA_PCT of volume) around the POC -> VAL / VAH (the consolidation zone)
  * measured in %-height and bars (adapts across volatility, per VISION 6)

Only meaningful now that intraday volume is real. Output feeds the chart overlay + later phases.

Run:  python research/volume_profile/volume_profile.py
Out:  output/volume_profile.json  (per-session high/low/poc/val/vah + width% + bars)
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # simplicity/
import strategy_config as cfg

OUT = os.path.join(HERE, "output"); os.makedirs(OUT, exist_ok=True)
N_BINS = 50
VA_PCT = 0.70


def _value_area(vbin, edges):
    """POC + value-area low/high by expanding from POC until VA_PCT of volume."""
    total = vbin.sum()
    if total <= 0:
        return None
    poc = int(vbin.argmax())
    lo = hi = poc
    acc = vbin[poc]
    target = total * VA_PCT
    n = len(vbin)
    while acc < target and (lo > 0 or hi < n - 1):
        up = vbin[hi + 1] if hi < n - 1 else -1.0
        dn = vbin[lo - 1] if lo > 0 else -1.0
        if up >= dn:
            hi += 1; acc += vbin[hi]
        else:
            lo -= 1; acc += vbin[lo]
    poc_px = (edges[poc] + edges[poc + 1]) / 2
    return round(poc_px, 2), round(float(edges[lo]), 2), round(float(edges[hi + 1]), 2)


def main():
    df = pd.read_parquet(os.path.join(cfg.DATA_DIR, cfg.TF_SOURCES["5m"]))
    df.index = pd.DatetimeIndex(df.index)
    et = df.index.tz_convert(cfg.CLOCK)
    mod = et.hour * 60 + et.minute
    sess = np.full(len(et), "asia", dtype=object)
    sess[(mod >= 180) & (mod < 570)] = "london"
    sess[(mod >= 570) & (mod < 960)] = "newyork"
    sess[(mod >= 960) & (mod < 1080)] = "close"
    sdate = pd.Series(et.tz_localize(None).normalize().values)
    sdate[(sess == "asia") & (mod < 180)] -= pd.Timedelta(days=1)

    f = pd.DataFrame({"date": pd.DatetimeIndex(sdate).strftime("%Y-%m-%d"), "session": sess,
                      "high": df["high"].to_numpy(), "low": df["low"].to_numpy(),
                      "close": df["close"].to_numpy(), "vol": df["volume"].to_numpy(dtype="float64"),
                      "ts": (et.view("int64") // 1_000_000_000).astype("int64")})
    f = f[f["session"] != "close"]

    out = []
    for (date, s), g in f.groupby(["date", "session"], sort=False):
        sl, sh = float(g["low"].min()), float(g["high"].max())
        if sh <= sl:
            continue
        edges = np.linspace(sl, sh, N_BINS + 1)
        vbin, _ = np.histogram(g["close"].to_numpy(), bins=edges, weights=g["vol"].to_numpy())
        va = _value_area(vbin, edges)
        if va is None:
            continue
        poc, val, vah = va
        out.append({"date": date, "session": s, "sid": f"{date} {s}",
                    "high": round(sh, 2), "low": round(sl, 2), "poc": poc, "val": val, "vah": vah,
                    "start": int(g["ts"].min()), "end": int(g["ts"].max()), "bars": int(len(g)),
                    "height_pct": round((sh - sl) / sl * 100, 3),
                    "va_pct_of_range": round((vah - val) / (sh - sl) * 100, 1)})

    json.dump({"n_bins": N_BINS, "va_pct": VA_PCT, "profiles": out},
              open(os.path.join(OUT, "volume_profile.json"), "w"))

    d = pd.DataFrame(out)
    print(f"built {len(out):,} session volume profiles ({N_BINS} bins, {int(VA_PCT*100)}% value area)")
    print(f"\n  {'session':<9}{'n':>7}{'median height%':>16}{'median VA/range%':>18}{'POC vs mid':>14}")
    for s in ["asia", "london", "newyork"]:
        ds = d[d.session == s]
        # where POC sits within the range: 0=low, 1=high (is volume balanced or skewed?)
        pocpos = ((ds["poc"] - ds["low"]) / (ds["high"] - ds["low"])).median()
        print(f"  {s:<9}{len(ds):>7}{ds.height_pct.median():>15.3f}%{ds.va_pct_of_range.median():>17.1f}%"
              f"{pocpos:>13.2f}")
    print("\n  (VA/range% = how tight the value area is vs the full session range; POC vs mid ~0.5 = balanced)")
    print("wrote", os.path.join(OUT, "volume_profile.json"))


if __name__ == "__main__":
    main()
