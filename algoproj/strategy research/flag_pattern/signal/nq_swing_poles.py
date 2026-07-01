"""
Approach B — Stage 1: swing-based POLE detection.

Not a template match. We walk the bars, build an ATR zigzag (swing highs/lows), and keep the
legs that stand out as POLES: a directional swing whose size >= POLE_ATR_MULT x ATR (the
"noticeable deviation"). Poles have VARIABLE length — however many bars the swing takes.

Emits findings JSON (poles_<tf>.json) the tv_chart viewer overlays, so we can eyeball whether
the detector catches good poles before adding the consolidation + breakout stages (§7.3/§12).

Run (from algoproj/ root):
  python "strategy research/flag_pattern/signal/nq_swing_poles.py" --save
  python "strategy research/flag_pattern/signal/nq_swing_poles.py" --save --pole-atr 2.5
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj/
sys.path.insert(0, HERE)                                                   # signal_config
from algokit.data import load_tf
import signal_config as cfg

COLS = ["open", "high", "low", "close"]


def _atr(values, n):
    high, low, close = values[:, 1], values[:, 2], values[:, 3]
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    return pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()


def swing_pivots(values, atr, rev_mult):
    """ATR zigzag -> list of (idx, price, 'H'|'L') alternating swing highs/lows."""
    high, low = values[:, 1], values[:, 2]
    n = len(values)
    pivots = []
    direction = 1               # start assuming an up-leg (self-corrects quickly)
    ext_i, ext_p = 0, high[0]
    for i in range(1, n):
        thr = rev_mult * atr[i]
        if direction == 1:                       # up-leg: track the highest high
            if high[i] >= ext_p:
                ext_p, ext_i = high[i], i
            elif ext_p - low[i] >= thr:          # retraced down enough -> confirm swing HIGH
                pivots.append((ext_i, ext_p, "H"))
                direction, ext_p, ext_i = -1, low[i], i
        else:                                    # down-leg: track the lowest low
            if low[i] <= ext_p:
                ext_p, ext_i = low[i], i
            elif high[i] - ext_p >= thr:         # retraced up enough -> confirm swing LOW
                pivots.append((ext_i, ext_p, "L"))
                direction, ext_p, ext_i = 1, high[i], i
    return pivots


def find_poles(values, ts, atr):
    """Legs between consecutive pivots that are big enough (>= POLE_ATR_MULT x ATR) = poles."""
    pivots = swing_pivots(values, atr, cfg.REV_ATR_MULT)
    session = cfg.session_mask(ts)
    poles = []
    for (a_i, a_p, a_k), (b_i, b_p, _) in zip(pivots, pivots[1:]):
        move = abs(b_p - a_p)
        if move < cfg.POLE_ATR_MULT * atr[a_i] or not session[a_i]:
            continue
        up = b_p > a_p                            # up-leg = bull pole, down-leg = bear pole
        seg = values[a_i:b_i + 1]
        poles.append({
            "pattern": "bull_pole" if up else "bear_pole",
            "side": "long" if up else "short",
            "start": int(ts[a_i]), "end": int(ts[b_i]), "entry": int(ts[b_i]),
            "pole_end": int(ts[b_i]),             # whole span is the pole (chart colors it all)
            "pole_lo": round(float(seg[:, 2].min()), 2),
            "pole_hi": round(float(seg[:, 1].max()), 2),
            "bars": int(b_i - a_i),
            "strength": round(float(move / atr[a_i]), 2),   # size in ATRs (higher = stronger)
            "score": round(float(move / atr[a_i]), 2),      # chart reads `score`; here = strength
        })
    return poles


def main(tf, save, pole_atr):
    if pole_atr is not None:
        cfg.POLE_ATR_MULT = pole_atr
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    atr = _atr(values, cfg.ATR_N)
    poles = find_poles(values, ts, atr)
    poles.sort(key=lambda m: -m["strength"])      # strongest first
    for r, m in enumerate(poles, 1):
        m["rank"] = r
    bull = sum(m["side"] == "long" for m in poles)
    print(f"{tf}: {len(df):,} bars | ATR{cfg.ATR_N} rev{cfg.REV_ATR_MULT} pole>={cfg.POLE_ATR_MULT}xATR "
          f"| session {'8AM-2PM ET' if cfg.SESSION_ENABLED else 'all'}")
    print(f"poles: {len(poles)}  ({bull} bull / {len(poles) - bull} bear)  "
          f"median {np.median([m['bars'] for m in poles]):.0f} bars, "
          f"{np.median([m['strength'] for m in poles]):.1f}x ATR")
    if save:
        out = {"tf": tf, "source": "nq_swing_poles", "variable": True,
               "fwd_window": 12, "horizons": [1, 3, 6, 12, 24],
               "atr_n": cfg.ATR_N, "rev_atr_mult": cfg.REV_ATR_MULT, "pole_atr_mult": cfg.POLE_ATR_MULT,
               "session": {"enabled": cfg.SESSION_ENABLED, "tz": cfg.SESSION_TZ,
                           "start_hour": cfg.SESSION_START_HOUR, "end_hour": cfg.SESSION_END_HOUR},
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "matches": poles}
        os.makedirs(cfg.FINDINGS_DIR, exist_ok=True)
        path = os.path.join(cfg.FINDINGS_DIR, f"poles_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> {os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--pole-atr", type=float, default=None, help="override POLE_ATR_MULT")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.save, a.pole_atr)
