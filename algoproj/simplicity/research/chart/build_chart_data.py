"""
build_chart_data — cache OHLCV for the fresh tv chart (fast multi-timeframe loads).

Exports the last MAX_BARS bars of each timeframe (NQ + ES) to JSON so the chart loads
instantly and never touches the big parquets at view time. Also writes a manifest with
the strategy_config snapshot + the ACTIVE_FILTER's selected days (for the overlay).

Run:  python research/chart/build_chart_data.py
Out:  research/chart/data/<INST>_<tf>.json  +  manifest.json
"""
import os
import sys
import json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
sys.path.insert(0, os.path.join(SIM, "research", "volatility_filter"))
import strategy_config as cfg
import filter_variants as fvar

DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
MAX_BARS = 2000


def _series(df):
    t = (df.index.view("int64") // 1_000_000_000).tolist()
    o, h, l, c = df["open"].tolist(), df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    v = df["volume"].tolist()
    candles = [{"time": t[i], "open": o[i], "high": h[i], "low": l[i], "close": c[i]} for i in range(len(t))]
    up = "rgba(25,158,112,0.5)"; dn = "rgba(230,103,103,0.5)"
    vol = [{"time": t[i], "value": v[i], "color": up if c[i] >= o[i] else dn} for i in range(len(t))]
    return candles, vol


def main():
    series_meta = []
    for inst, src in (("NQ", cfg.TF_SOURCES), ("ES", cfg.ES_SOURCES)):
        for tf, fname in src.items():
            p = os.path.join(cfg.DATA_DIR, fname)
            if not os.path.exists(p):
                continue
            df = pd.read_parquet(p)
            df.index = pd.DatetimeIndex(df.index)
            df = df.tail(MAX_BARS)
            candles, vol = _series(df)
            key = f"{inst}_{tf}"
            json.dump({"candles": candles, "volume": vol},
                      open(os.path.join(DATA, key + ".json"), "w"))
            series_meta.append({"key": key, "instrument": inst, "tf": tf, "bars": len(df),
                                "first": str(df.index[0]), "last": str(df.index[-1])})

    # ACTIVE_FILTER selected days (for the overlay) -- NQ daily-derived
    sel = fvar.select(cfg.ACTIVE_FILTER)
    selected_days = sel.loc[sel["selected"], "date"].tolist()
    # contiguous runs (period start/end) for overlay markers
    runs, run = [], None
    for r in sel.itertuples():
        if r.selected:
            run = run or {"start": r.date, "end": r.date}
            run["end"] = r.date
        elif run:
            runs.append(run); run = None
    if run:
        runs.append(run)

    manifest = {
        "max_bars": MAX_BARS,
        "series": series_meta,
        "config": {
            "instrument": cfg.INSTRUMENT, "clock": cfg.CLOCK,
            "era_start": cfg.ERA_START_YEAR, "vol_metric": cfg.VOL_METRIC,
            "trail_window": cfg.TRAIL_WINDOW, "regime_pctiles": list(cfg.REGIME_PCTILES),
            "active_filter": cfg.ACTIVE_FILTER, "tradeable_regimes": list(cfg.TRADEABLE_REGIMES),
            "sessions": {k: list(v) for k, v in cfg.SESSIONS.items()},
            "filter_session": cfg.FILTER_SESSION, "filter_hour": cfg.FILTER_HOUR,
            "filter_day_vol": cfg.FILTER_DAY_VOL,
            "point_value": cfg.POINT_VALUE, "tick": cfg.TICK,
            "commission_per_side": cfg.COMMISSION_PER_SIDE, "slippage_ticks": cfg.SLIPPAGE_TICKS,
        },
        "active_filter": cfg.ACTIVE_FILTER,
        "selected_days": selected_days,
        "selected_runs": runs,
    }
    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"))
    print(f"wrote {len(series_meta)} series + manifest to {DATA}")
    for s in series_meta:
        print(f"  {s['key']:<8} {s['bars']:>5} bars  {s['first'][:10]}..{s['last'][:10]}")
    print(f"  active_filter={cfg.ACTIVE_FILTER}  selected_days={len(selected_days)}")


if __name__ == "__main__":
    main()
