"""
Fractal flag matcher on NQ. Matches the SETUP (pole+flag), measures the forward outcome,
and filters by time of day. Signal defined in signal_config.py.

Two axes of adaptiveness:
  • --norm free   magnitude-free (matches the shape at any move SIZE)
  • --scales      bar-LENGTH variance: the 9-bar template is interpolated to each length,
                  so the same shape is searched at 9, 18, 36 bars... (the pole:flag ratio
                  and fwd window scale with it). Each scale -> its own findings file.

Each saved match carries its outcome (directional close returns + MFE/MAE). Only patterns
inside the configured session (US Eastern) are kept.

Run (from algoproj/ root):
  python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save
  python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save --norm free
  python "strategy research/flag_pattern/signal/nq_fractal_match.py" --save --norm free --scales 9,18,36
"""
import argparse
import datetime as dt
import json
import os
import sys
from collections import namedtuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj/
sys.path.insert(0, HERE)                                                   # for signal_config
from algokit.data import load_tf
from algokit import patterns
import signal_config as cfg

FINDINGS_DIR = cfg.FINDINGS_DIR      # centralized in the control panel (signal_config)
COLS = ["open", "high", "low", "close"]

# geometry for one bar-length scale (window = bar count)
Geom = namedtuple("Geom", "window pole_bars fwd_window horizons min_gap setup")


def _interp(tmpl, length):
    """Stretch a (W,4) template to (length,4) by interpolating each column (same shape, more bars)."""
    sx = np.linspace(0.0, 1.0, tmpl.shape[0])
    dx = np.linspace(0.0, 1.0, length)
    return np.stack([np.interp(dx, sx, tmpl[:, c]) for c in range(tmpl.shape[1])], axis=1)


def geom_for(length):
    """Build the geometry for a given setup length, scaling everything from the base config."""
    if length == cfg.WINDOW:
        return Geom(cfg.WINDOW, cfg.POLE_BARS, cfg.FWD_WINDOW, list(cfg.HORIZONS), cfg.MIN_GAP, cfg.SETUP)
    s = length / cfg.WINDOW
    setup = {name: (d, side, _interp(t, length)) for name, (d, side, t) in cfg.SETUP.items()}
    horizons = sorted({max(1, round(h * s)) for h in cfg.HORIZONS})
    return Geom(length, max(1, round(cfg.POLE_BARS * s)), max(1, round(cfg.FWD_WINDOW * s)),
                horizons, max(1, round(cfg.MIN_GAP * s)), setup)


def _load(tf, start):
    df = load_tf(tf)[COLS].dropna()
    if start:
        df = df[df.index >= start]
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    return df, df.values, ts


def _forward(values, close, entry, direction, g):
    """Outcome from the entry (flag-end) bar: directional close returns + MFE/MAE (%)."""
    n = len(close)
    fwd = {str(h): round(direction * (close[entry + h] / close[entry] - 1.0) * 100, 4)
           for h in g.horizons if entry + h < n}
    base = close[entry]
    end = min(n, entry + 1 + g.fwd_window)
    seg_hi, seg_lo = values[entry + 1:end, 1], values[entry + 1:end, 2]
    if len(seg_hi):
        up = seg_hi.max() / base - 1.0
        dn = seg_lo.min() / base - 1.0
        mfe, mae = (up, dn) if direction > 0 else (-dn, -up)
        return fwd, round(mfe * 100, 4), round(mae * 100, 4)
    return fwd, None, None


def _fib(values, i, direction, g):
    """Fib retracement of the flag into the pole (CLOSING basis), + the pole's low/high prices.
    retrace 0 = no pullback, 0.5 = held the midpoint, 1 = full 100% retrace of the pole."""
    pole = values[i:i + g.pole_bars]
    flag = values[i + g.pole_bars:i + g.window]
    pole_hi = float(pole[:, 1].max())
    pole_lo = float(pole[:, 2].min())
    rng = pole_hi - pole_lo
    if rng <= 0 or len(flag) == 0:
        return None, pole_lo, pole_hi
    if direction > 0:
        retrace = (pole_hi - flag[:, 3].min()) / rng      # lowest flag close vs pole top
    else:
        retrace = (flag[:, 3].max() - pole_lo) / rng      # highest flag close vs pole bottom
    return round(float(retrace), 4), pole_lo, pole_hi


def _matches(values, ts, tmpl, pct, use_session, norm, g):
    """Closest-first non-overlapping window-starts under the pct threshold, session-masked."""
    scorer = patterns.scan_free if norm == "free" else patterns.scan
    scores = scorer(values, tmpl, g.window)
    thr = float(np.percentile(scores, pct))            # threshold on ALL windows = global "good flag"
    s = scores
    if use_session:
        s = scores.copy()
        s[~cfg.session_mask(ts[:len(scores)])] = np.inf   # never pick out-of-session windows
    return patterns.matches_under(s, thr, g.min_gap), scores, thr


def _out_path(tf, norm, g):
    parts = []
    if g.window != cfg.WINDOW:
        parts.append(f"w{g.window}")
    if norm != "level":
        parts.append(norm)
    suffix = ("_" + "_".join(parts)) if parts else ""
    return os.path.join(FINDINGS_DIR, f"flag_{tf}{suffix}.json")


def report(tf, start, pct, use_session, norm, g):
    df, values, ts = _load(tf, start)
    close = values[:, 3]
    hz = g.horizons[min(2, len(g.horizons) - 1)]   # representative horizon (~6 at base scale)
    print(f"{cfg.describe()}  |  norm={norm} window={g.window}" + ("" if use_session else "  [session off]"))
    for name, (direction, side, tmpl) in g.setup.items():
        idxs, _, thr = _matches(values, ts, tmpl, pct, use_session, norm, g)
        f = np.array([v for v in (_forward(values, close, i + g.window - 1, direction, g)[0].get(str(hz))
                                  for i in idxs) if v is not None])
        print(f"  {name:>10}: {len(idxs):>4} matches (score<{thr:.4f})  "
              f"fwd{hz} mean {f.mean():+.3f}%  win {(f > 0).mean() * 100:.0f}%")


def save_findings(tf, start, pct, use_session, norm, g, max_retrace):
    df, values, ts = _load(tf, start)
    close = values[:, 3]
    out = {"tf": tf, "window": g.window, "pole_bars": g.pole_bars, "fwd_window": g.fwd_window,
           "horizons": g.horizons, "selector": f"score < p{pct}", "norm": norm,
           "max_retrace": max_retrace,
           "session": {"enabled": use_session, "tz": cfg.SESSION_TZ,
                       "start_hour": cfg.SESSION_START_HOUR, "end_hour": cfg.SESSION_END_HOUR},
           "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
           "source": "nq_fractal_match", "matches": []}
    for name, (direction, side, tmpl) in g.setup.items():
        idxs, scores, thr = _matches(values, ts, tmpl, pct, use_session, norm, g)
        kept = 0
        for rank, i in enumerate(idxs, 1):
            retrace, pole_lo, pole_hi = _fib(values, i, direction, g)
            if max_retrace is not None and retrace is not None and retrace > max_retrace:
                continue
            entry = i + g.window - 1
            fwd, mfe, mae = _forward(values, close, entry, direction, g)
            out["matches"].append({
                "pattern": name, "side": side, "rank": rank,
                "start": int(ts[i]), "end": int(ts[entry]), "entry": int(ts[entry]),
                "score": round(float(scores[i]), 5), "fwd": fwd, "mfe": mfe, "mae": mae,
                "retrace": retrace, "pole_lo": round(pole_lo, 2), "pole_hi": round(pole_hi, 2)})
            kept += 1
        print(f"  {name}: {kept} matches (score < {thr:.4f})")
    os.makedirs(FINDINGS_DIR, exist_ok=True)
    path = _out_path(tf, norm, g)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  -> {len(out['matches'])} matches saved to {os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--start", default=cfg.HISTORY_START)
    ap.add_argument("--pct", type=float, default=cfg.MATCH_PCT)
    ap.add_argument("--norm", choices=["level", "free"], default="level",
                    help="level = % from open (current); free = magnitude-free (shape only)")
    ap.add_argument("--scales", default=str(cfg.WINDOW),
                    help="comma-separated setup bar-lengths, e.g. 9,18,36")
    ap.add_argument("--max-retrace", type=float, default=cfg.MAX_RETRACE,
                    help="keep only consolidations whose fib retrace <= this (e.g. 0.5)")
    ap.add_argument("--no-session", action="store_true", help="ignore the time-of-day filter")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    session = not a.no_session and cfg.SESSION_ENABLED
    for length in [int(x) for x in a.scales.split(",")]:
        g = geom_for(length)
        print(f"=== window {g.window} bars (pole {g.pole_bars} / flag {g.window - g.pole_bars}, "
              f"fwd {g.fwd_window}) ===")
        if a.save:
            save_findings(a.tf, a.start, a.pct, session, a.norm, g, a.max_retrace)
        else:
            report(a.tf, a.start, a.pct, session, a.norm, g)
