"""
structure_detection — swing high/low structure detector (3 grains).

Walks the bars tracking the running extreme in the current direction. In an up-leg it follows the
highest high; when price retraces from it by >= grain x ATR, that high is locked in as a SWING HIGH
and we flip to a down-leg (and vice versa). The confirmed swings alternate H, L, H, L... — connect
the H's and the L's and you get the stair-stepping structure lines. Run at LTF / MTF / HTF grains.

Emits findings JSON (structure_<tf>.json): per grain, the ordered swing points {t, p, k}.

Run (from algoproj/ root):
  python "strategy research/structure_detection/signal/structure.py" --save
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
FINDINGS_DIR = os.path.join(HERE, "..", "findings")


def _atr(values, n):
    high, low, close = values[:, 1], values[:, 2], values[:, 3]
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    return pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()


def swings(values, atr, grain_mult):
    """ATR-threshold swing tracker -> ordered list of (idx, price, 'H'|'L')."""
    high, low = values[:, 1], values[:, 2]
    n = len(values)
    out = []
    direction = 1                    # start assuming an up-leg (self-corrects)
    ext, ext_i = high[0], 0
    for i in range(1, n):
        thr = grain_mult * atr[i]
        if direction == 1:                          # up-leg: follow the highest high
            if high[i] >= ext:
                ext, ext_i = high[i], i
            elif ext - low[i] >= thr:               # retrace confirms a SWING HIGH
                out.append((ext_i, float(ext), "H"))
                direction, ext, ext_i = -1, low[i], i
        else:                                       # down-leg: follow the lowest low
            if low[i] <= ext:
                ext, ext_i = low[i], i
            elif high[i] - ext >= thr:              # rally confirms a SWING LOW
                out.append((ext_i, float(ext), "L"))
                direction, ext, ext_i = 1, high[i], i
    return out


def main(tf, save):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    atr = _atr(values, cfg.ATR_N)
    print(f"{tf}: {len(df):,} bars  {df.index[0].date()} -> {df.index[-1].date()}")

    grains = []
    for name, gm in cfg.GRAINS.items():
        sw = swings(values, atr, gm)
        pts = [{"t": int(ts[i]), "p": round(p, 2), "k": k} for i, p, k in sw]
        grains.append({"name": name, "grain": gm, "swings": pts})
        h = sum(1 for _, _, k in sw if k == "H")
        print(f"  {name:>4} (grain {gm}x ATR): {len(sw)} swings ({h} highs / {len(sw) - h} lows)")

    if save:
        out = {"tf": tf, "source": "structure_detection",
               "start": int(ts[0]), "end": int(ts[-1]), "atr_n": cfg.ATR_N,
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "grains": grains}
        os.makedirs(FINDINGS_DIR, exist_ok=True)
        path = os.path.join(FINDINGS_DIR, f"structure_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> {os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.save)
