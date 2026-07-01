"""
Hybrid flag detector (NOTES §15): template SETUP + variable-length consolidation watch.

Two stages:
  1. SETUP — the same magnitude-free template match finds a clean pole+flag setup (the part the
     `free` version already did well). This locates the pole and confirms a flag is forming.
  2. WATCH — instead of a fixed forward window, we watch the consolidation FORWARD from the setup
     until it resolves:
        • FAIL   — a close crosses back past the 0.5 fib of the pole (cancel; rolls into a bigger
                   consolidation), or the initial flag already broke it.
        • BREAKOUT — a close beyond the consolidation range in the pole's direction, OR a bar that
                   moves >= BREAKOUT_ATR_MULT x ATR that way. This is the continuation.
        • TIMEOUT — never resolved within CONSOL_MAX_WATCH bars.
  Only BREAKOUTS are kept as valid patterns. The flag is variable length (pole_end..breakout) and
  the outcome (fwd / MFE / MAE) is measured FROM the breakout bar (where you'd enter).

Run (from algoproj/ root):
  python "strategy research/flag_pattern/signal/nq_flag_breakout.py" --save
  python "strategy research/flag_pattern/signal/nq_flag_breakout.py" --save --pct 0.25
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
from algokit import patterns
import signal_config as cfg

COLS = ["open", "high", "low", "close"]
O, H, L, C = 0, 1, 2, 3


def _atr(values, n):
    prev = np.concatenate([[values[0, C]], values[:-1, C]])
    tr = np.maximum(values[:, H] - values[:, L],
                    np.maximum(np.abs(values[:, H] - prev), np.abs(values[:, L] - prev)))
    return pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()


def _forward(values, close, entry, direction):
    n = len(close)
    fwd = {str(h): round(direction * (close[entry + h] / close[entry] - 1.0) * 100, 4)
           for h in cfg.HORIZONS if entry + h < n}
    base = close[entry]
    end = min(n, entry + 1 + cfg.FWD_WINDOW)
    seg_hi, seg_lo = values[entry + 1:end, H], values[entry + 1:end, L]
    if len(seg_hi):
        up, dn = seg_hi.max() / base - 1.0, seg_lo.min() / base - 1.0
        mfe, mae = (up, dn) if direction > 0 else (-dn, -up)
        return fwd, round(mfe * 100, 4), round(mae * 100, 4)
    return fwd, None, None


def _watch(values, close, atr, i, direction):
    """Watch the flag forward from setup start i. Returns (outcome, resolve_idx, pole_lo, pole_hi)."""
    P, W, n = cfg.POLE_BARS, cfg.WINDOW, len(close)
    pole = values[i:i + P]
    pole_hi, pole_lo = float(pole[:, H].max()), float(pole[:, L].min())
    rng = pole_hi - pole_lo
    if rng <= 0:
        return "skip", i, pole_lo, pole_hi
    mid = pole_lo + cfg.FIB_HOLD * rng           # the 0.5 fib (hold line)
    buf = cfg.BREAK_BUFFER * rng
    fstart, wstart = i + P, i + W                 # flag bars start; watch starts after the setup window
    flag_hi = float(values[fstart:wstart, H].max())
    flag_lo = float(values[fstart:wstart, L].min())
    # already failed inside the initial flag?
    if direction > 0 and close[fstart:wstart].min() < mid - buf:
        return "failed", wstart - 1, pole_lo, pole_hi
    if direction < 0 and close[fstart:wstart].max() > mid + buf:
        return "failed", wstart - 1, pole_lo, pole_hi
    for j in range(wstart, min(n, wstart + cfg.CONSOL_MAX_WATCH)):
        c = close[j]
        spike = (c - values[j, O]) if direction > 0 else (values[j, O] - c)
        if direction > 0:
            if c < mid - buf:
                return "failed", j, pole_lo, pole_hi
            if c > flag_hi or spike >= cfg.BREAKOUT_ATR_MULT * atr[j]:
                return "broke_out", j, pole_lo, pole_hi
        else:
            if c > mid + buf:
                return "failed", j, pole_lo, pole_hi
            if c < flag_lo or spike >= cfg.BREAKOUT_ATR_MULT * atr[j]:
                return "broke_out", j, pole_lo, pole_hi
        flag_hi = max(flag_hi, float(values[j, H]))
        flag_lo = min(flag_lo, float(values[j, L]))
    return "timeout", min(n - 1, wstart + cfg.CONSOL_MAX_WATCH - 1), pole_lo, pole_hi


def _retrace(values, close, i, brk, direction, pole_lo, pole_hi):
    """Deepest flag retrace into the pole (closing basis) over the whole variable flag."""
    rng = pole_hi - pole_lo
    flag_c = close[i + cfg.POLE_BARS:brk]
    if rng <= 0 or len(flag_c) == 0:
        return None
    r = (pole_hi - flag_c.min()) / rng if direction > 0 else (flag_c.max() - pole_lo) / rng
    return round(float(r), 4)


def main(tf, pct, save):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    close = values[:, C]
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    atr = _atr(values, cfg.ATR_N)

    matches, counts = [], {"broke_out": 0, "failed": 0, "timeout": 0, "skip": 0}
    for name, (direction, side, tmpl) in cfg.SETUP.items():
        scores = patterns.scan_free(values, tmpl, cfg.WINDOW)          # magnitude-free SETUP match
        thr = float(np.percentile(scores, pct))
        s = scores.copy()
        s[~cfg.session_mask(ts[:len(scores)])] = np.inf
        for i in patterns.matches_under(s, thr, cfg.MIN_GAP):
            outcome, brk, pole_lo, pole_hi = _watch(values, close, atr, i, direction)
            counts[outcome] = counts.get(outcome, 0) + 1
            if outcome != "broke_out":
                continue
            fwd, mfe, mae = _forward(values, close, brk, direction)
            matches.append({
                "pattern": name, "side": side,
                "start": int(ts[i]), "pole_end": int(ts[i + cfg.POLE_BARS - 1]),
                "end": int(ts[brk]), "entry": int(ts[brk]),
                "score": round(float(scores[i]), 5),
                "retrace": _retrace(values, close, i, brk, direction, pole_lo, pole_hi),
                "flag_bars": int(brk - (i + cfg.POLE_BARS)),
                "pole_lo": round(pole_lo, 2), "pole_hi": round(pole_hi, 2),
                "fwd": fwd, "mfe": mfe, "mae": mae})

    matches.sort(key=lambda m: (m["pattern"], m["score"]))
    for r, m in enumerate([m for m in matches], 1):
        m["rank"] = r
    tried = sum(counts.values())
    br = counts["broke_out"]
    print(f"{tf}: {len(df):,} bars | setup p{pct} free | session {'8-2 ET' if cfg.SESSION_ENABLED else 'all'}")
    print(f"setups watched: {tried}  ->  broke_out {br} ({br/max(tried,1)*100:.0f}%)  "
          f"failed {counts['failed']}  timeout {counts['timeout']}")
    if matches:
        import statistics as st
        f6 = [m["fwd"].get("6") for m in matches if m["fwd"].get("6") is not None]
        med_bars = st.median([m["flag_bars"] for m in matches])
        print(f"kept {len(matches)} breakouts | median flag {med_bars:.0f} bars | "
              f"fwd6 mean {st.mean(f6):+.3f}%  win {sum(x>0 for x in f6)/len(f6)*100:.0f}%")
    if save:
        out = {"tf": tf, "source": "nq_flag_breakout", "variable": True,
               "pole_bars": cfg.POLE_BARS, "fwd_window": cfg.FWD_WINDOW, "horizons": cfg.HORIZONS,
               "fib_hold": cfg.FIB_HOLD, "breakout_atr_mult": cfg.BREAKOUT_ATR_MULT,
               "max_watch": cfg.CONSOL_MAX_WATCH, "selector": f"score < p{pct}, norm=free",
               "session": {"enabled": cfg.SESSION_ENABLED, "tz": cfg.SESSION_TZ,
                           "start_hour": cfg.SESSION_START_HOUR, "end_hour": cfg.SESSION_END_HOUR},
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "matches": matches}
        os.makedirs(cfg.FINDINGS_DIR, exist_ok=True)
        path = os.path.join(cfg.FINDINGS_DIR, f"flag_breakout_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> {os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--pct", type=float, default=cfg.MATCH_PCT)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.pct, a.save)
