"""
One-At-A-Time (OAT) sensitivity engine for the `fanning_mtf` strategy.

Purpose
-------
Answer "which parameters actually benefit us, and which are just constants
wearing a parameter costume?" — WITHOUT any UI. For each tunable SIGNAL knob it
holds every other param at the strategy DEFAULT, sweeps that one knob across a
sensible range, and records the objective metric (Sharpe by default). The shape
of each curve tells you what the knob is:

    FLAT     -> metric barely moves            -> freeze it, it's not a decision
    SPIKE    -> great at one value, bad nearby -> overfit trap, don't trust it
    PLATEAU  -> a broad band of good values    -> a real knob worth keeping

It only ever sweeps SIGNAL params (algokit/params.UNIVERSAL_PARAMS — capital,
commission, tick specs, sizing — are machinery, not edges, so they're skipped).

Time estimate / countdown
-------------------------
The first thing it does is run the baseline ONCE and time it, then print an
up-front estimate (per-run seconds x queued runs). While sweeping it shows a
live, in-place line with count, elapsed, rolling seconds/run, and a shrinking
ETA — so you always know how long is left.

Usage
-----
    python research/sensitivity/fanning_mtf_oat.py
    python research/sensitivity/fanning_mtf_oat.py --metric profit_factor
    python research/sensitivity/fanning_mtf_oat.py --only X,exit_th,atr_mult
    python research/sensitivity/fanning_mtf_oat.py --quick      # coarser ranges

Outputs a per-param table to the console and saves the full grid to
research/sensitivity/out/fanning_mtf_oat.{csv,json}.
"""
import os
import sys
import csv
import json
import time
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/
from strategies import fanning_mtf
from algokit.params import UNIVERSAL_PARAMS
from algokit import validation

D = fanning_mtf.DEFAULT


# --- Sweep definitions -------------------------------------------------------
# Each entry: label -> dict(values=[...], make=lambda v -> override-dict).
# Scalar knobs override directly; the MA-fan triples ([min, max, eps]) are swept
# one component at a time so the sweep is genuinely "one thing changes" per run.

def _fan(base_key, index, v):
    """Return an override that replaces one element of a [min, max, eps] fan."""
    fan = list(D[base_key])
    fan[index] = v
    return {base_key: fan}


def _build_sweeps(quick=False):
    def rng(full, q):
        return q if quick else full
    sweeps = {
        # scalar signal knobs (centered on the DEFAULT value)
        "X":            dict(values=rng([50, 55, 60, 65, 70, 75, 80, 85], [55, 65, 70, 80]),
                             make=lambda v: {"X": v}),
        "htf_gate":     dict(values=rng([30, 40, 50, 60, 70], [40, 50, 60]),
                             make=lambda v: {"htf_gate": v}),
        "exit_th":      dict(values=rng([15, 20, 25, 30, 35, 40, 45], [20, 30, 40]),
                             make=lambda v: {"exit_th": v}),
        "coil_k":       dict(values=rng([10, 15, 20, 25, 30, 40], [15, 20, 30]),
                             make=lambda v: {"coil_k": v}),
        "coil_level":   dict(values=rng([20, 30, 40, 50, 60], [30, 40, 50]),
                             make=lambda v: {"coil_level": v}),
        "atr_mult":     dict(values=rng([2, 3, 4, 5, 6, 7, 8], [3, 5, 7]),
                             make=lambda v: {"atr_mult": float(v)}),
        "atr_n":        dict(values=rng([7, 10, 14, 20, 28], [10, 14, 20]),
                             make=lambda v: {"atr_n": v}),
        "slope_L":      dict(values=rng([3, 4, 5, 6, 7, 9], [3, 5, 7]),
                             make=lambda v: {"slope_L": v}),
        "n_ma":         dict(values=rng([16, 24, 32, 40, 48], [24, 32, 40]),
                             make=lambda v: {"n_ma": v}),
        # MA-fan components
        "htf_fan_eps":  dict(values=rng([0.05, 0.10, 0.15, 0.20, 0.25, 0.30], [0.10, 0.15, 0.25]),
                             make=lambda v: _fan("htf_fan", 2, v)),
        "ltf_fan_eps":  dict(values=rng([0.01, 0.02, 0.03, 0.04, 0.05, 0.07], [0.02, 0.03, 0.05]),
                             make=lambda v: _fan("ltf_fan", 2, v)),
        "htf_fan_max":  dict(values=rng([300, 400, 500, 600, 700], [400, 500, 600]),
                             make=lambda v: _fan("htf_fan", 1, v)),
        "ltf_fan_max":  dict(values=rng([60, 80, 100, 120, 160], [80, 100, 120]),
                             make=lambda v: _fan("ltf_fan", 1, v)),
    }
    return sweeps


# --- Time / formatting helpers ----------------------------------------------

def _hms(seconds):
    """Seconds -> 'm:ss' or 'h:mm:ss'."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _progress(done, total, elapsed, label, val):
    """Render the live, in-place countdown line."""
    per = elapsed / done if done else 0.0
    eta = per * (total - done)
    bar_w = 24
    fill = int(bar_w * done / total)
    bar = "#" * fill + "-" * (bar_w - fill)
    line = (f"\r[{bar}] {done:>3}/{total}  {label}={val:<6}  "
            f"{per:4.2f}s/run  elapsed {_hms(elapsed)}  ETA {_hms(eta)}   ")
    sys.stdout.write(line)
    sys.stdout.flush()


# --- Metric extraction & curve classification --------------------------------

def _metric(stats, key):
    v = stats.get(key)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return v


# A metric's "no-edge" level: profit_factor breaks even at 1.0, the rest at 0.0.
NEUTRAL = {"profit_factor": 1.0}


def _seg_metric(block, key):
    """Pull one metric out of a validation segment block (or NaN)."""
    if not block:
        return float("nan")
    try:
        return float(block.get(key))
    except (TypeError, ValueError):
        return float("nan")


def _is_oos(out, metric, split):
    """For a finished run, return (in_sample, out_of_sample, oos_round_trips).

    Reuses algokit.validation.in_out_sample, which just SLICES the run's per-bar
    arrays by time (first `split` = train, rest = test) — no extra backtest.
    """
    res = out["res"]
    idx = out["build"]["idx"]
    ppy = out["ppy"]
    vo = validation.in_out_sample(res["rets"], res["trades"], res["in_market"],
                                  idx, ppy, split=split)
    is_v = _seg_metric(vo["in_sample"], metric)
    oos_v = _seg_metric(vo["out_of_sample"], metric)
    oos_rt = int(vo["out_of_sample"].get("round_trips", 0)) if vo["out_of_sample"] else 0
    return is_v, oos_v, oos_rt


def _survives(is_best, oos_at_best, metric):
    """Does the value we'd PICK in-sample still beat break-even out-of-sample?

    SURVIVES if its OOS edge has the right sign and keeps >=50% of its IS size.
    """
    if is_best != is_best or oos_at_best != oos_at_best:  # NaN
        return "n/a"
    neutral = NEUTRAL.get(metric, 0.0)
    edge_is = is_best - neutral
    edge_oos = oos_at_best - neutral
    if edge_oos > 0 and edge_oos >= 0.5 * edge_is:
        return "SURVIVES"
    return "COLLAPSES"


def _classify(values, baseline, frac=0.15):
    """Heuristic label for a swept metric curve (a hint, not gospel).

    FLAT:    spread is tiny vs the baseline level -> knob doesn't matter.
    SPIKE:   only one value is near the best -> overfit trap.
    PLATEAU: a band of >=3 values sits near the best -> a real, robust knob.
    """
    xs = [v for v in values if v == v]  # drop NaN
    if len(xs) < 2:
        return "n/a"
    lo, hi = min(xs), max(xs)
    spread = hi - lo
    scale = max(abs(baseline), 1e-9)
    if spread / scale < frac:
        return "FLAT (freeze it)"
    near_best = sum(1 for v in xs if v >= hi - 0.10 * spread)
    if near_best <= 1:
        return "SPIKE (overfit risk)"
    return "PLATEAU (real knob)"


# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="OAT sensitivity sweep for fanning_mtf")
    ap.add_argument("--metric", default="sharpe",
                    help="objective stat to track (sharpe, profit_factor, expectancy, total_return, cagr)")
    ap.add_argument("--only", default="",
                    help="comma-separated subset of params to sweep")
    ap.add_argument("--quick", action="store_true", help="coarser ranges (fewer runs)")
    ap.add_argument("--split", type=float, default=0.70,
                    help="in-sample fraction (first X of history to TUNE on; rest is "
                         "held-out test). 0 = no split, score on full history.")
    args = ap.parse_args()
    split = args.split if 0 < args.split < 1 else 0.0  # 0 => full-sample mode

    sweeps = _build_sweeps(quick=args.quick)
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        sweeps = {k: v for k, v in sweeps.items() if k in want}
        missing = want - set(sweeps)
        if missing:
            print(f"WARNING: unknown params ignored: {', '.join(sorted(missing))}")

    metric = args.metric
    total = sum(len(s["values"]) for s in sweeps.values())
    skipped = [k for k in D if k in UNIVERSAL_PARAMS]

    split_txt = (f"in-sample {split*100:.0f}% / out-of-sample {100-split*100:.0f}%"
                 if split else "full history (no split)")
    print("=" * 72)
    print(f"  fanning_mtf  one-at-a-time sensitivity  |  objective = {metric}")
    print(f"  tune/test split: {split_txt}")
    print(f"  {len(sweeps)} params x their ranges = {total} backtests "
          f"(+1 baseline){'  [quick]' if args.quick else ''}")
    print(f"  frozen (universal, not swept): {', '.join(skipped)}")
    print("=" * 72)

    # --- calibrate: time the baseline once, give an up-front estimate ---
    print("\nCalibrating (running baseline once)...", flush=True)
    t0 = time.perf_counter()
    base = fanning_mtf.run()  # DEFAULT config; also warms the data cache
    cal = time.perf_counter() - t0
    if split:
        base_is, base_oos, _ = _is_oos(base, metric, split)
        print(f"  baseline {metric}:  IS {base_is:.4f}   OOS {base_oos:.4f}   "
              f"|   ~{cal:.2f}s per backtest")
    else:
        base_is, base_oos = _metric(base["stats"], metric), float("nan")
        print(f"  baseline {metric} = {base_is:.4f}   |   ~{cal:.2f}s per backtest")
    print(f"  estimated total time for {total} runs: ~{_hms(cal * total)}\n")

    # --- sweep ---  rows: (value, is_metric, oos_metric, oos_round_trips)
    results = {}
    done = 0
    start = time.perf_counter()
    for label, spec in sweeps.items():
        rows = []
        for v in spec["values"]:
            _progress(done, total, time.perf_counter() - start, label, v)
            try:
                out = fanning_mtf.run(**spec["make"](v))
                if split:
                    iv, ov, rt = _is_oos(out, metric, split)
                else:
                    iv, ov, rt = _metric(out["stats"], metric), float("nan"), \
                        int(out["stats"].get("round_trips", 0))
            except Exception:  # degenerate config (e.g. no trades) -> record NaN
                iv, ov, rt = float("nan"), float("nan"), 0
            rows.append((v, iv, ov, rt))
            done += 1
        results[label] = rows
    _progress(done, total, time.perf_counter() - start, "done", "")
    elapsed = time.perf_counter() - start
    print(f"\n\nFinished {total} backtests in {_hms(elapsed)} "
          f"({elapsed/total:.2f}s/run avg)\n")

    # --- console report ---
    if split:
        print(f"Baseline {metric}:  IS {base_is:.4f}   OOS {base_oos:.4f}   "
              f"(IS = data we tune on; OOS = held-out data we only LOOK at)\n")
    else:
        print(f"Baseline {metric} = {base_is:.4f}  (full history)\n")

    verdicts = []  # (label, shape, survival, best_val, is_best, oos_at_best)
    for label, rows in results.items():
        is_vals = [iv for _, iv, _, _ in rows]
        shape = _classify(is_vals, base_is)
        # value we'd PICK by tuning on in-sample, then its out-of-sample score
        best_row = max(rows, key=lambda r: (r[1] if r[1] == r[1] else float("-inf")))
        best_v, is_best, oos_at_best = best_row[0], best_row[1], best_row[2]
        survival = _survives(is_best, oos_at_best, metric) if split else "n/a"
        verdicts.append((label, shape, survival, best_v, is_best, oos_at_best))

        default_v = D.get(label, None)
        print(f"--- {label}  (default={default_v if default_v is not None else '~'})   "
              f"shape(IS)={shape}" + (f"   >> {survival}" if split else ""))
        for v, iv, ov, rt in rows:
            star = "  <- default" if default_v is not None and v == default_v else ""
            pick = "  <- best IS" if v == best_v else ""
            ivs = f"{iv:8.4f}" if iv == iv else "     nan"
            if split:
                ovs = f"{ov:8.4f}" if ov == ov else "     nan"
                print(f"      {str(v):>7}   IS={ivs}   OOS={ovs}   OOS_trips={rt:<5}{star}{pick}")
            else:
                print(f"      {str(v):>7}   {metric}={ivs}   trips={rt:<5}{star}")
        if split:
            print(f"      pick best-IS {best_v}:  IS {is_best:.4f}  ->  OOS {oos_at_best:.4f}   "
                  f"{survival}")
        print()

    # --- verdict summary: survivors first, then by IS shape ---
    shape_order = {"PLATEAU (real knob)": 0, "SPIKE (overfit risk)": 1,
                   "FLAT (freeze it)": 2, "n/a": 3}
    surv_order = {"SURVIVES": 0, "COLLAPSES": 1, "n/a": 2}
    print("=" * 72)
    print("  VERDICT  (tune each knob on in-sample, judge it out-of-sample)")
    print("=" * 72)
    for label, shape, survival, best_v, is_best, oos_at_best in sorted(
            verdicts, key=lambda x: (surv_order.get(x[2], 9), shape_order.get(x[1], 9))):
        if split:
            print(f"  {label:<14} {survival:<10} (IS shape {shape:<22}) "
                  f"best@{str(best_v):<5} IS {is_best:6.3f} -> OOS {oos_at_best:6.3f}")
        else:
            print(f"  {label:<14} {shape:<22} best {metric} {is_best:.4f}")
    if split:
        print("\n  SURVIVES = the value you'd pick in-sample still beats break-even out-of-sample.")
        print("  COLLAPSES = it only worked on the data it was tuned on -> overfit, don't trust it.")
        print("  Trust ONLY survivors. Re-run with a different --split to make sure it isn't luck.")
    else:
        print("\n  Keep PLATEAU knobs, freeze FLAT ones. Re-run with --split 0.7 to test OUT-OF-SAMPLE.")

    # --- save full grid ---
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "fanning_mtf_oat.csv")
    json_path = os.path.join(out_dir, "fanning_mtf_oat.json")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["param", "value", f"{metric}_is", f"{metric}_oos", "oos_round_trips"])
        for label, rows in results.items():
            for v, iv, ov, rt in rows:
                w.writerow([label, v, iv, ov, rt])
    with open(json_path, "w") as f:
        json.dump({"metric": metric, "split": split,
                   "baseline": {"is": base_is, "oos": base_oos},
                   "results": {k: [{"value": v, "is": iv, "oos": ov, "oos_round_trips": rt}
                                   for v, iv, ov, rt in rows] for k, rows in results.items()},
                   "verdicts": {l: {"is_shape": sh, "survival": sv, "best_value": bv,
                                    "is_best": ib, "oos_at_best": ob}
                                for l, sh, sv, bv, ib, ob in verdicts}}, f, indent=2)
    print(f"\n  saved -> {csv_path}")
    print(f"  saved -> {json_path}")


if __name__ == "__main__":
    main()
