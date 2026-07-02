"""
engine/data_feed — load clean market data. FIRST solidified engine piece.

Confirmed & promoted from research 2026-07-01. Loads the clean parquets (real
volume = Up+Down) for NQ and ES, any timeframe, straight from strategy_config paths.
Hard, fast, dependency-light -- the bars-in stage every other engine piece reads.

    from data_feed import load, available, check
    df = load("5m")               # NQ 5-minute  (tz-aware UTC)
    df = load("1d", "ES")         # ES daily (n/a yet), etc.
    check()                       # -> "NQ 5/5, ES 4/4 parquets present"
"""
import os
import sys
import pandas as pd

# --- engine path bootstrap: flat imports work from any engine/ subfolder ---
_E = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_E) != "engine":
    _E = os.path.dirname(_E)
for _d in [_E, os.path.dirname(_E)] + [os.path.join(_E, x) for x in os.listdir(_E) if os.path.isdir(os.path.join(_E, x))]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import strategy_config as cfg

DESCRIBE = "loads NQ/ES clean parquets (tz-aware UTC) from strategy_config paths"
_cache = {}


def _sources(instrument):
    return cfg.TF_SOURCES if instrument.upper() == "NQ" else cfg.ES_SOURCES


def path(tf, instrument="NQ"):
    src = _sources(instrument)
    if tf not in src:
        raise KeyError(f"{instrument} has no timeframe '{tf}'. options: {list(src)}")
    return os.path.join(cfg.DATA_DIR, src[tf])


def load(tf, instrument="NQ", tz=None, use_cache=True):
    """Clean OHLCV for (instrument, tf). Index tz-aware UTC; pass tz to convert (e.g. cfg.CLOCK)."""
    key = (instrument.upper(), tf)
    if use_cache and key in _cache:
        df = _cache[key]
    else:
        p = path(tf, instrument)
        if not os.path.exists(p):
            raise FileNotFoundError(f"{p} missing -- run data/build_data.py")
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(df.index)
        if use_cache:
            _cache[key] = df
    return df.tz_convert(tz) if tz else df


def available():
    """{instrument: {tf: bool present}} across NQ + ES."""
    out = {}
    for inst in ("NQ", "ES"):
        out[inst] = {tf: os.path.exists(path(tf, inst)) for tf in _sources(inst)}
    return out


def check():
    a = available()
    parts = [f"{inst} {sum(v.values())}/{len(v)}" for inst, v in a.items()]
    missing = [f"{inst}:{tf}" for inst, v in a.items() for tf, ok in v.items() if not ok]
    s = ", ".join(parts) + " parquets present"
    return s if not missing else s + f"  (missing: {', '.join(missing)})"


if __name__ == "__main__":
    print(check())
    for inst, tfs in available().items():
        print(f"  {inst}: {tfs}")
