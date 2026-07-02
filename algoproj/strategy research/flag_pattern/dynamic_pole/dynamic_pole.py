"""
Dynamic pole trace (experiment) — unfreeze the pole in BOTH directions.

Idea (rants, 2026-07-01): the static template scan is only a SEED dropped somewhere inside a
move. Instead of trusting the frozen POLE_BARS window, we walk the pole candle-by-candle out to
its TRUE extremes:

  • FORWARD  — in a bearish pole, follow price down while each next candle does NOT close above
    the current candle's HIGH (by a buffer); the deepest low = the pole's bottom / end (where the
    flag begins). Mirror for bullish (down-side lows).
  • BACKWARD — the pole often started earlier/higher than the seed. Walk back while each earlier
    candle does NOT close below the current candle's LOW (by a buffer); the highest high = the
    pole's true origin / start. Mirror for bullish.

Two cheap knobs (config): a BUFFER (counter-close must clear by POLE_TRACE_BUFFER_ATR x ATR, so
wicks / marginal closes don't end the pole) and a NO-PROGRESS guard (stop if the move stops making
new extremes). Plus a MAX_BACK cap so the backward walk can't swallow the previous move.

The fib 0->1 is then measured off the TRUE traced extremes (not the frozen slice), so the pole
hi/lo/0.5 levels drawn on the chart are the real swing levels the consolidation reacts to.

This is a SEED->STATE-MACHINE split (NOTES §17): the scan is the coarse sensor, the walk is the
per-candle machine that only ever runs INSIDE a matched pole context (so it can't dump 32k
context-free swings like the standalone detector did, §14).

Run (from algoproj/ root):
  python "strategy research/flag_pattern/experiments/dynamic_pole.py" --save
  python "strategy research/flag_pattern/experiments/dynamic_pole.py" --save --buffer-atr 0.4 --no-progress
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))       # algoproj/
sys.path.insert(0, os.path.join(HERE, "..", "signal"))                          # signal_config
from algokit.data import load_tf
from algokit import patterns
import signal_config as cfg
import template_bank as tb

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
    hi, lo = values[entry + 1:end, H], values[entry + 1:end, L]
    if len(hi):
        up, dn = hi.max() / base - 1.0, lo.min() / base - 1.0
        mfe, mae = (up, dn) if direction > 0 else (-dn, -up)
        return fwd, round(mfe * 100, 4), round(mae * 100, 4)
    return fwd, None, None


def _trace_pole(values, close, atr, i, direction, buf_mult, stall_frac, max_back, max_fwd):
    """Grow the pole from seed bar i to its true extremes. Returns (pole_start, pole_end).

    BACKWARD = reversal-only (extend to the true origin). FORWARD = reversal OR a fraction-of-pole
    cool-down: end after the move stalls (no new extreme) for more than stall_frac x the pole's own
    current length, so patience scales with how far the pole has already run."""
    n = len(close)

    # ── backward: the pole's origin (top if bearish, bottom if bullish) — reversal rule only ──
    ext_back, j, steps = i, i, 0
    bestb = values[i, H] if direction < 0 else values[i, L]
    while j - 1 >= 0 and steps < max_back:
        prv, buf = j - 1, buf_mult * atr[j]
        if direction < 0:
            if close[prv] < values[j, L] - buf:              # before here price rose into the top -> origin
                break
            if values[prv, H] > bestb:
                bestb, ext_back = values[prv, H], prv
        else:
            if close[prv] > values[j, H] + buf:
                break
            if values[prv, L] < bestb:
                bestb, ext_back = values[prv, L], prv
        j, steps = prv, steps + 1

    # ── forward: the pole's far extreme — reversal rule + fraction-of-pole cool-down ──
    ext_fwd, j, steps, stall = i, i, 0, 0
    best = values[i, L] if direction < 0 else values[i, H]
    while j + 1 < n and steps < max_fwd:
        nxt, buf = j + 1, buf_mult * atr[j]
        if direction < 0 and close[nxt] > values[j, H] + buf:    # counter-thrust up -> pole ends
            break
        if direction > 0 and close[nxt] < values[j, L] - buf:
            break
        new_ext = (values[nxt, L] < best) if direction < 0 else (values[nxt, H] > best)
        if new_ext:                                              # progress: extend, reset the stall
            best = values[nxt, L] if direction < 0 else values[nxt, H]
            ext_fwd, stall = nxt, 0
        else:                                                    # no new extreme: cooling down
            stall += 1
            if stall_frac and stall > stall_frac * (ext_fwd - ext_back + 1):
                break                                            # stalled longer than frac x pole length
        j, steps = nxt, steps + 1

    if ext_fwd <= ext_back:
        ext_fwd = min(n - 1, ext_back + 1)
    return ext_back, ext_fwd


def _watch(values, close, vol, atr, direction, pole_end, pole_lo, pole_hi, vwap_k):
    """Watch the consolidation forward from the TRUE pole extreme (NOTES §15, on the dynamic pole).

    The flag persists while it HOLDS the pole's 0.5 fib (closing basis). The breakout is redefined
    around the consolidation's EQUILIBRIUM: an anchored VWAP from the pole end (volume-weighted center),
    with a band = VWAP +/- vwap_k x ATR. Resolves as:
      failed   — a close crosses back past the 0.5 against the pole (rolls into a bigger consol),
      broke_out— a close beyond the VWAP band in the pole direction, or a >= ATR-mult spike,
      timeout  — never resolved within CONSOL_MAX_WATCH bars.
    Returns (outcome, resolve_idx, vwap_series) where vwap_series = [(idx, center, up, dn), ...]."""
    n = len(close)
    rng = pole_hi - pole_lo
    if rng <= 0:
        return "skip", pole_end, []
    mid = pole_lo + cfg.FIB_HOLD * rng            # 0.5 hold line off the true pole
    buf = cfg.BREAK_BUFFER * rng
    tp = (values[pole_end, H] + values[pole_end, L] + values[pole_end, C]) / 3   # anchor VWAP at pole end
    cum_pv, cum_v = tp * vol[pole_end], float(vol[pole_end])
    series = []
    for j in range(pole_end + 1, min(n, pole_end + 1 + cfg.CONSOL_MAX_WATCH)):
        tp = (values[j, H] + values[j, L] + values[j, C]) / 3
        cum_pv += tp * vol[j]
        cum_v += float(vol[j])
        vwap = cum_pv / cum_v if cum_v > 0 else close[j]
        band = vwap_k * atr[j]
        up, dn = vwap + band, vwap - band
        series.append((j, vwap, up, dn))
        c = close[j]
        spike = (c - values[j, O]) if direction > 0 else (values[j, O] - c)
        if direction > 0:
            if c < mid - buf:
                return "failed", j, series
            if c > up or spike >= cfg.BREAKOUT_ATR_MULT * atr[j]:
                return "broke_out", j, series
        else:
            if c > mid + buf:
                return "failed", j, series
            if c < dn or spike >= cfg.BREAKOUT_ATR_MULT * atr[j]:
                return "broke_out", j, series
    return "timeout", min(n - 1, pole_end + cfg.CONSOL_MAX_WATCH), series


def _retrace(close, pole_end, brk, direction, pole_lo, pole_hi):
    """Deepest flag retrace into the pole (closing basis) over the variable flag pole_end..brk."""
    rng = pole_hi - pole_lo
    seg = close[pole_end:brk]
    if rng <= 0 or len(seg) == 0:
        return None
    r = (pole_hi - seg.min()) / rng if direction > 0 else (seg.max() - pole_lo) / rng
    return round(float(r), 4)


def _active_mask(vol, vbase, ts):
    """When to hunt: the clock session, a volume surge (>= mult x rolling baseline), or both."""
    clock = cfg.session_mask(ts)
    if cfg.ACTIVITY_MODE == "clock":
        return clock
    surge = vol >= cfg.VOL_ACTIVE_MULT * vbase
    if cfg.ACTIVITY_MODE == "volume":
        return surge
    return clock & surge


def _template_seeds(values, active, pct):
    """Seeds from the frozen shape scan: (score, pattern, side, direction, seed_idx). Lower score=closer."""
    seeds = []
    for name, (direction, side, tmpl) in cfg.SETUP.items():
        scores = patterns.scan_free(values, tmpl, cfg.WINDOW)
        thr = float(np.percentile(scores, pct))
        s = scores.copy()
        s[~active[:len(scores)]] = np.inf
        for i in patterns.matches_under(s, thr, cfg.MIN_GAP):
            seeds.append((float(scores[i]), name, side, direction, int(i)))
    return seeds


def _spike_seeds(values, atr, active, mult):
    """Seeds from ATR spikes: a candle whose directional body >= mult x ATR starts a pole.
    Score = -(body/ATR) so BIGGER spikes win the de-overlap. Filtered to the active window."""
    body = values[:, C] - values[:, O]
    mag = body / np.maximum(atr, 1e-9)          # guard the warm-up bar where ATR can be 0
    seeds = []
    for j in np.where((mag >= mult) & active)[0]:
        seeds.append((-float(mag[j]), "bull_flag", "long", +1, int(j)))
    for j in np.where((mag <= -mult) & active)[0]:
        seeds.append((float(mag[j]), "bear_flag", "short", -1, int(j)))
    return seeds


def _bank_seeds(values, active, pct, bank):
    """Seeds from a BANK of template variations: each window keeps its BEST (min) distance across
    the whole bank, so a flag matching ANY variation seeds. Threshold on that best-distance."""
    seeds = []
    for key, name, side, direction in [("bull", "bull_flag", "long", +1),
                                       ("bear", "bear_flag", "short", -1)]:
        best = None
        for item in bank:
            sc = patterns.scan_free(values, item[key], cfg.WINDOW)
            best = sc if best is None else np.minimum(best, sc)
        thr = float(np.percentile(best, pct))
        s = best.copy()
        s[~active[:len(best)]] = np.inf
        for i in patterns.matches_under(s, thr, cfg.MIN_GAP):
            seeds.append((float(best[i]), name, side, direction, int(i)))
    return seeds


def _vol_sig_ok(vol, vbase, ps, pe, brk):
    """Classic flag volume signature: pole expands (above baseline), flag contracts (< pole),
    breakout surges (>= mult x baseline). Only the enabled legs are required."""
    pole_v = float(vol[ps:pe + 1].mean())
    flag_v = float(vol[pe:brk + 1].mean()) if brk > pe else float(vol[pe])
    if cfg.VOL_POLE_RISING and pole_v < vbase[pe]:
        return False
    if cfg.VOL_FLAG_QUIET and flag_v >= pole_v:
        return False
    if cfg.VOL_BREAKOUT_SURGE and vol[brk] < cfg.VOL_BREAKOUT_MULT * vbase[brk]:
        return False
    return True


def main(tf, pct, save, buf_mult, stall_frac, max_back, max_fwd, min_bars, seed_mode, spike_mult, vwap_k):
    full = load_tf(tf)
    df = full[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    close = values[:, C]
    vol = full["volume"].reindex(df.index).fillna(0.0).to_numpy()   # anchored VWAP + volume signature
    vbase = pd.Series(vol).rolling(cfg.VOL_BASELINE_N, min_periods=1).mean().to_numpy()
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    atr = _atr(values, cfg.ATR_N)

    active = _active_mask(vol, vbase, ts)                           # when to hunt (clock / volume / both)
    bank_n = 0
    if seed_mode == "spike":
        seeds = _spike_seeds(values, atr, active, spike_mult)
    elif seed_mode == "bank":
        bank = tb.make_bank(cfg.WINDOW, cfg.BANK_POLE_BARS, cfg.BANK_POLE_CURVE, cfg.BANK_FLAG_SLOPE)
        bank_n = len(bank)
        seeds = _bank_seeds(values, active, pct, bank)
    else:
        seeds = _template_seeds(values, active, pct)

    raw = []
    for score, name, side, direction, i in seeds:
        ps, pe = _trace_pole(values, close, atr, i, direction, buf_mult, stall_frac, max_back, max_fwd)
        if pe - ps + 1 < min_bars:
            continue
        raw.append((score, name, side, direction, ps, pe, i))

    # de-overlap the TRACED poles (anchors were 40 apart, but extension can overlap): keep best score
    raw.sort(key=lambda r: r[0])
    poles, spans = [], []
    for score, name, side, direction, ps, pe, i in raw:
        if any(ps <= b and a <= pe for a, b in spans):       # overlaps a kept pole
            continue
        spans.append((ps, pe))
        poles.append((score, name, side, direction, ps, pe, i))

    # ── flag-watch each pole forward from its TRUE extreme; keep the breakouts (valid patterns) ──
    kept, counts = [], {"broke_out": 0, "failed": 0, "timeout": 0, "skip": 0}
    for score, name, side, direction, ps, pe, i in poles:
        seg = values[ps:pe + 1]
        pole_hi, pole_lo = float(seg[:, H].max()), float(seg[:, L].min())
        outcome, brk, vser = _watch(values, close, vol, atr, direction, pe, pole_lo, pole_hi, vwap_k)
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome != "broke_out":
            continue
        if brk - pe < cfg.CONSOL_MIN_BARS:                        # consolidation too short -> drop
            counts["short_flag"] = counts.get("short_flag", 0) + 1
            continue
        if cfg.VOL_SIG_ENABLED and not _vol_sig_ok(vol, vbase, ps, pe, brk):   # volume signature
            counts["vol_sig"] = counts.get("vol_sig", 0) + 1
            continue
        fwd, mfe, mae = _forward(values, close, brk, direction)   # outcome measured FROM the breakout
        vwap = [[int(ts[j]), round(cen, 2), round(up, 2), round(dn, 2)] for j, cen, up, dn in vser]
        kept.append({
            "pattern": name, "side": side, "score": round(score, 5),
            "start": int(ts[ps]), "pole_end": int(ts[pe]), "end": int(ts[brk]), "entry": int(ts[brk]),
            "pole_lo": round(pole_lo, 2), "pole_hi": round(pole_hi, 2),
            "pole_bars": int(pe - ps + 1), "back_bars": int(i - ps), "fwd_bars": int(pe - i),
            "flag_bars": int(brk - pe), "retrace": _retrace(close, pe, brk, direction, pole_lo, pole_hi),
            "seed_bars": cfg.POLE_BARS, "vwap": vwap, "fwd": fwd, "mfe": mfe, "mae": mae})

    kept.sort(key=lambda m: (m["pattern"], m["score"]))
    for r, m in enumerate(kept, 1):
        m["rank"] = r

    # ── report ──
    seed_desc = (f"spike {spike_mult}xATR" if seed_mode == "spike"
                 else f"bank {bank_n}var p{pct}" if seed_mode == "bank"
                 else f"template p{pct} free")
    volsig = "on" if cfg.VOL_SIG_ENABLED else "off"
    print(f"{tf}: {len(df):,} bars | seed {seed_desc} ({len(seeds)}) | activity {cfg.ACTIVITY_MODE} | vol-sig {volsig}")
    if cfg.VOL_SIG_ENABLED:
        print(f"  vol-sig dropped {counts.get('vol_sig', 0)} (pole-rising {cfg.VOL_POLE_RISING}, "
              f"flag-quiet {cfg.VOL_FLAG_QUIET}, breakout-surge {cfg.VOL_BREAKOUT_SURGE})")
    print(f"knobs: buffer {buf_mult}xATR | stall_frac {round(stall_frac, 3) if stall_frac else 'off'} "
          f"| fib_hold {cfg.FIB_HOLD} | breakout VWAP +/-{vwap_k}xATR | max_watch {cfg.CONSOL_MAX_WATCH}")
    tried = counts["broke_out"] + counts["failed"] + counts["timeout"] + counts["skip"]
    print(f"poles {len(poles)} (from {len(raw)} anchors)  ->  broke_out {counts['broke_out']} "
          f"({counts['broke_out']/max(tried,1)*100:.0f}%)  failed {counts['failed']}  timeout {counts['timeout']}")
    if kept:
        pb = np.array([m["pole_bars"] for m in kept])
        fl = np.array([m["flag_bars"] for m in kept])
        f6 = [m["fwd"].get("6") for m in kept if m["fwd"].get("6") is not None]
        print(f"kept {len(kept)} breakouts (flag >= {cfg.CONSOL_MIN_BARS} bars; dropped "
              f"{counts.get('short_flag', 0)} short) | pole bars median {np.median(pb):.0f} | "
              f"flag bars median {np.median(fl):.0f} (p90 {np.percentile(fl, 90):.0f})")
        if f6:
            print(f"  fwd6 from breakout: mean {np.mean(f6):+.3f}%  win {np.mean(np.array(f6) > 0) * 100:.0f}%")

    if save:
        out = {"tf": tf, "source": "dynamic_pole", "variable": True, "pole_bars": None,
               "fwd_window": cfg.FWD_WINDOW, "horizons": cfg.HORIZONS,
               "selector": (f"seed=spike {spike_mult}xATR" if seed_mode == "spike"
                            else f"seed=template p{pct} free"),
               "trace": {"buffer_atr": buf_mult, "stall_frac": stall_frac,
                         "max_back": max_back, "max_fwd": max_fwd, "min_bars": min_bars},
               "consolidation": {"fib_hold": cfg.FIB_HOLD, "break_buffer": cfg.BREAK_BUFFER,
                                 "breakout": f"close beyond anchored VWAP +/- {vwap_k}xATR (or {cfg.BREAKOUT_ATR_MULT}xATR spike)",
                                 "vwap_k": vwap_k, "max_watch": cfg.CONSOL_MAX_WATCH},
               "volume": {"activity_mode": cfg.ACTIVITY_MODE, "vol_active_mult": cfg.VOL_ACTIVE_MULT,
                          "baseline_n": cfg.VOL_BASELINE_N, "signature": cfg.VOL_SIG_ENABLED,
                          "pole_rising": cfg.VOL_POLE_RISING, "flag_quiet": cfg.VOL_FLAG_QUIET,
                          "breakout_surge": cfg.VOL_BREAKOUT_SURGE, "breakout_mult": cfg.VOL_BREAKOUT_MULT},
               "session": {"enabled": cfg.SESSION_ENABLED, "tz": cfg.SESSION_TZ,
                           "start_hour": cfg.SESSION_START_HOUR, "end_hour": cfg.SESSION_END_HOUR},
               "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
               "matches": kept}
        os.makedirs(cfg.FINDINGS_DIR, exist_ok=True)
        path = os.path.join(cfg.FINDINGS_DIR, f"dynamic_pole_{tf}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"saved -> {os.path.basename(path)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--pct", type=float, default=cfg.MATCH_PCT)
    ap.add_argument("--buffer-atr", type=float, default=cfg.POLE_TRACE_BUFFER_ATR)
    ap.add_argument("--stall-frac", type=float, default=cfg.POLE_TRACE_STALL_FRAC,
                    help="cool-down: end pole after a stall > this fraction of its length (0 = off)")
    ap.add_argument("--max-back", type=int, default=cfg.POLE_TRACE_MAX_BACK)
    ap.add_argument("--max-fwd", type=int, default=cfg.POLE_TRACE_MAX_FWD)
    ap.add_argument("--min-bars", type=int, default=cfg.POLE_TRACE_MIN_BARS)
    ap.add_argument("--seed", choices=["template", "spike", "bank"], default=cfg.SEED_MODE,
                    help="pole seed source: single template, ATR spike, or template bank")
    ap.add_argument("--spike-atr", type=float, default=cfg.SPIKE_ATR_MULT,
                    help="spike seed: candle body >= this x ATR")
    ap.add_argument("--vwap-k", type=float, default=cfg.BREAKOUT_VWAP_K,
                    help="breakout band half-width in ATRs around the anchored VWAP")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    main(a.tf, a.pct, a.save, a.buffer_atr, a.stall_frac, a.max_back, a.max_fwd, a.min_bars,
         a.seed, a.spike_atr, a.vwap_k)
