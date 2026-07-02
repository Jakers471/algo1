"""
flag_triangle — sideways consolidation finder (rectangles, triangles, channels, pennants).

Pipeline:
  1. SWINGS   — ATR-threshold swing tracker (same as structure_detection) gives alternating
                swing highs / lows.
  2. WINDOWS  — slide over the swing sequence; for each start swing grow the window to the
                largest span that stays a consolidation (enough pivots, price contained within
                the trendlines fitted to the highs and to the lows, duration in range).
  3. CLASSIFY — from the two fitted slopes + whether the channel is converging:
                  rectangle | sym_triangle | asc_triangle | desc_triangle
                  | channel_up | channel_down | pennant
  4. OUTCOME  — treat the end of the consolidation as the breakout bar; record forward returns,
                MFE / MAE in the continuation direction (prior move, else shape bias).

Emits findings JSON (flag_triangle_<tf>.json) in the same "matches" schema the tv_chart viewer
uses, so it renders immediately (band = consolidation span, arrow = breakout bar, fwd stats).

Run (from algoproj/ root):
  python "strategy research/flag_triangle/signal/flag_triangle.py" --save
  python "strategy research/flag_triangle/signal/flag_triangle.py" --save --tf 15m
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
O, H, L, C = 0, 1, 2, 3
FINDINGS_DIR = os.path.join(HERE, "..", "findings")


def _atr(values, n):
    prev = np.concatenate([[values[0, C]], values[:-1, C]])
    tr = np.maximum(values[:, H] - values[:, L],
                    np.maximum(np.abs(values[:, H] - prev), np.abs(values[:, L] - prev)))
    return pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()


def swings(values, atr, grain_mult):
    """ATR-threshold swing tracker -> ordered list of (idx, price, 'H'|'L')."""
    high, low, n = values[:, H], values[:, L], len(values)
    out = []
    direction, ext, ext_i = 1, high[0], 0
    for i in range(1, n):
        thr = grain_mult * atr[i]
        if direction == 1:
            if high[i] >= ext:
                ext, ext_i = high[i], i
            elif ext - low[i] >= thr:
                out.append((ext_i, float(ext), "H"))
                direction, ext, ext_i = -1, low[i], i
        else:
            if low[i] <= ext:
                ext, ext_i = low[i], i
            elif high[i] - ext >= thr:
                out.append((ext_i, float(ext), "L"))
                direction, ext, ext_i = 1, high[i], i
    return out


def _fit(xs, ys):
    """Least-squares line -> (slope, intercept, rms residual)."""
    slope, intercept = np.polyfit(xs, ys, 1)
    resid = ys - (slope * xs + intercept)
    return slope, intercept, float(np.sqrt(np.mean(resid ** 2)))


def _forward(values, close, entry, direction):
    """Forward returns per horizon + MFE/MAE over FWD_WINDOW, in the trade direction."""
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


def _classify(rh, rl, converging, broadening):
    """Shape from normalized bound slopes (rh/rl = line move over window / avg width)."""
    if broadening:
        return None
    flat_h, flat_l = abs(rh) < cfg.FLAT, abs(rl) < cfg.FLAT
    up_h, dn_h = rh > cfg.FLAT, rh < -cfg.FLAT
    up_l, dn_l = rl > cfg.FLAT, rl < -cfg.FLAT
    if converging:
        if dn_h and up_l:
            return "sym_triangle"
        if flat_h and up_l:
            return "asc_triangle"
        if dn_h and flat_l:
            return "desc_triangle"
        return "triangle"
    if flat_h and flat_l:
        return "rectangle"
    if up_h and up_l:
        return "channel_up"
    if dn_h and dn_l:
        return "channel_down"
    return None   # mixed / not a clean consolidation


def _evaluate(values, atr, sw, i, j):
    """Fit + qualify the region spanning swings[i..j]. Returns a match dict or None."""
    a, b = sw[i][0], sw[j][0]                 # start / end BAR indices
    dur = b - a
    if dur < cfg.MIN_BARS or dur > cfg.MAX_BARS:
        return None
    seg = sw[i:j + 1]
    highs = [(k, p) for k, p, kind in seg if kind == "H"]
    lows = [(k, p) for k, p, kind in seg if kind == "L"]
    if len(highs) < 2 or len(lows) < 2 or len(seg) < cfg.MIN_PIVOTS:
        return None

    sh, ih, rms_h = _fit(np.array([k for k, _ in highs], float), np.array([p for _, p in highs], float))
    sl, il, rms_l = _fit(np.array([k for k, _ in lows], float), np.array([p for _, p in lows], float))

    w_start = (sh * a + ih) - (sl * a + il)
    w_end = (sh * b + ih) - (sl * b + il)
    if w_start <= 0 or w_end <= 0:
        return None                            # lines crossed / inverted -> not a clean channel
    avg_w = (w_start + w_end) / 2.0
    rh, rl = sh * dur / avg_w, sl * dur / avg_w
    converging = w_end < w_start * cfg.CONVERGE
    broadening = w_end > w_start / cfg.CONVERGE

    pattern = _classify(rh, rl, converging, broadening)
    if pattern is None:
        return None

    # containment: bars that sit inside the fitted lines (with an ATR tolerance)
    ks = np.arange(a, b + 1)
    up_line, lo_line = sh * ks + ih, sl * ks + il
    tol = cfg.CONTAIN_TOL * atr[a:b + 1]
    inside = (values[a:b + 1, H] <= up_line + tol) & (values[a:b + 1, L] >= lo_line - tol)
    contain = float(inside.mean())
    if contain < cfg.CONTAIN_MIN:
        return None

    # continuation context: incoming move over PRIOR_BARS before the consolidation
    close = values[:, C]
    p0 = max(0, a - cfg.PRIOR_BARS)
    prior = close[a] - close[p0]
    pole_atr = abs(prior) / atr[a] if atr[a] > 0 else 0.0
    if pattern in ("sym_triangle", "triangle") and dur <= cfg.PENNANT_MAX_BARS and pole_atr >= cfg.POLE_ATR:
        pattern = "pennant"

    # trade/measurement direction: prior move, else shape bias
    bias = {"asc_triangle": 1, "channel_up": 1, "desc_triangle": -1, "channel_down": -1}.get(pattern, 0)
    direction = 1 if prior > 0 else -1 if prior < 0 else (bias or 1)
    side = "long" if direction > 0 else "short"

    atr_end = atr[b] if atr[b] > 0 else 1.0
    tight = (rms_h + rms_l) / atr_end
    score = round(tight / max(1, len(seg) - 1), 5)          # lower = cleaner fit / more touches

    fwd, mfe, mae = _forward(values, close, b, direction)
    lo_reg = float(values[a:b + 1, L].min())
    hi_reg = float(values[a:b + 1, H].max())
    return {
        "pattern": pattern, "side": side,
        "start": a, "pole_end": a, "end": b, "entry": b,     # pole_end=start -> whole span = consolidation
        "score": score, "pivots": len(seg), "bars": int(dur),
        "contain": round(contain, 3), "pole_atr": round(pole_atr, 2),
        "pole_lo": lo_reg, "pole_hi": hi_reg,
        # fitted trendline endpoints (for a future line-drawing chart upgrade)
        "upper": [[a, round(sh * a + ih, 2)], [b, round(sh * b + ih, 2)]],
        "lower": [[a, round(sl * a + il, 2)], [b, round(sl * b + il, 2)]],
        "fwd": fwd, "mfe": mfe, "mae": mae,
    }


def detect(values, atr):
    """Non-overlapping consolidations: for each start swing keep the largest qualifying window."""
    sw = swings(values, atr, cfg.SWING_GRAIN)
    matches, i, N = [], 0, len(sw)
    while i < N - 3:
        best, best_j = None, -1
        j = i + 3
        while j < N and (sw[j][0] - sw[i][0]) <= cfg.MAX_BARS:
            m = _evaluate(values, atr, sw, i, j)
            if m is not None:
                best, best_j = m, j          # prefer the largest valid span from this start
            j += 1
        if best is not None:
            matches.append(best)
            i = best_j + 1                   # non-overlapping
        else:
            i += 1
    return sw, matches


def main(tf, save):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    atr = _atr(values, cfg.ATR_N)
    print(f"{tf}: {len(df):,} bars  {df.index[0].date()} -> {df.index[-1].date()}")

    sw, matches = detect(values, atr)
    # map bar indices -> epoch seconds; add rank
    for m in matches:
        for key in ("start", "pole_end", "end", "entry"):
            m[key] = int(ts[m[key]])
        m["upper"] = [[int(ts[k]), p] for k, p in m["upper"]]
        m["lower"] = [[int(ts[k]), p] for k, p in m["lower"]]
    matches.sort(key=lambda m: m["score"])
    for r, m in enumerate(matches, 1):
        m["rank"] = r

    counts = {}
    for m in matches:
        counts[m["pattern"]] = counts.get(m["pattern"], 0) + 1
    print(f"  {len(sw)} swings -> {len(matches)} consolidations")
    for name, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {name:>13}: {c}")

    if save:
        out = {"tf": tf, "source": cfg.NAME, "variable": True, "pole_bars": None,
               "fwd_window": cfg.FWD_WINDOW, "horizons": cfg.HORIZONS,
               "swing_grain": cfg.SWING_GRAIN,
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "matches": matches}
        os.makedirs(FINDINGS_DIR, exist_ok=True)
        path = os.path.join(FINDINGS_DIR, f"flag_triangle_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> {os.path.relpath(path, os.path.join(HERE, '..', '..', '..'))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.save)
