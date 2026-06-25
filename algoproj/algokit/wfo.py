"""True walk-forward optimization.

Unlike validation.py (which evaluates a FIXED config across time), this RE-SELECTS the
best parameters on each training window and then trades them on the NEXT, unseen window.
The stitched out-of-sample curve is the honest answer to "what would I actually have made
re-tuning periodically?" — and the gap between it and the single best-on-full-history
config is a direct measure of overfitting.

Efficiency: every grid config's full backtest is causal, so we run each ONCE and then
score any sub-window by slicing the per-bar arrays (selection on train, evaluation on
test). Cost is n_configs full runs, NOT n_configs x n_folds.

  optimize(run_fn, specs, objective, n_folds, anchored) -> dict(steps, oos, full_best, ...)
    run_fn(override_dict) -> arrays dict (see arrays_from_result). Injected so the UI can
    wrap it in a cache; a plain caller passes lambda ov: arrays_from_result(strat.run(**ov)).
"""
import numpy as np
import pandas as pd

from . import optimize as grid, validation

OBJECTIVES = ["sharpe", "total_return", "cagr", "profit_factor", "expectancy"]


def arrays_from_result(result):
    """Pull the causal per-bar arrays + trades out of a strategy.run() result."""
    res, b = result["res"], result["build"]
    return dict(rets=np.asarray(res["rets"], float),
                in_market=np.asarray(res["in_market"], float),
                trades=res["trades"], idx=b["idx"], start=int(b["start"]),
                ppy=float(result["ppy"]))


def _score(A, lo, hi, objective):
    """(objective value, full metric block) for config-arrays A on bar window [lo, hi)."""
    seg = validation._segment(A["rets"][lo:hi],
                              validation._trades_in(A["trades"], lo, hi),
                              A["in_market"][lo:hi], A["ppy"])
    v = seg.get(objective)
    return (v if v is not None and np.isfinite(v) else -np.inf), seg


def optimize(run_fn, specs, objective="sharpe", train_days=1095, test_days=365,
             anchored=False, start_date=None, end_date=None, progress=None):
    """Walk-forward optimize a strategy over a parameter grid (NinjaTrader-style).

    specs       : {param: (min,max,step) | [values]} sweep grid (see optimize.build_grid).
    objective   : metric to maximize on each train window ("Optimize on"; see OBJECTIVES).
    train_days  : optimization-period length in calendar days (the train window).
    test_days   : test-period length in calendar days; the window rolls forward by this.
    anchored    : False = rolling train window (NT "Walk Forward Optimization"); True =
                  expanding train always from the start (NT "Anchored Walk Forward").
    progress    : optional callback(done, total, override_dict) for a UI progress bar.

    Each step trains on `train_days`, tests on the next `test_days` (unseen), then advances
    by `test_days` — so the test windows tile the history out-of-sample and stitch into one
    honest curve.
    """
    configs = grid.build_grid(specs)
    arrs = []
    for i, ov in enumerate(configs):
        arrs.append(run_fn(ov))
        if progress:
            progress(i + 1, len(configs), ov)

    A0 = arrs[0]
    n, warm, ppy = len(A0["rets"]), A0["start"], A0["ppy"]
    idx = pd.DatetimeIndex(A0["idx"])
    # clip the analysis window to the selected date range (default = full history)
    lo, hi = warm, n
    if start_date is not None:
        lo = max(lo, int(idx.searchsorted(pd.Timestamp(start_date))))
    if end_date is not None:
        hi = min(hi, int(idx.searchsorted(pd.Timestamp(end_date) + pd.Timedelta(days=1))))
    start_t, end_t = idx[lo], idx[min(hi, n) - 1]
    train_td, test_td = pd.Timedelta(days=train_days), pd.Timedelta(days=test_days)

    chosen_rets = np.zeros(n)
    chosen_inmkt = np.zeros(n)
    oos_trades = []
    steps = []
    oos_lo = None
    cursor_t = start_t + train_td                 # first test window starts after one train period
    fold = 0
    while end_t - cursor_t >= test_td * 0.5:       # drop a runt final window (< half a test period)
        test_lo = int(idx.searchsorted(cursor_t))
        test_hi = min(hi, int(idx.searchsorted(min(cursor_t + test_td, end_t))))
        train_hi = test_lo
        train_lo = lo if anchored else max(lo, int(idx.searchsorted(cursor_t - train_td)))
        if test_hi <= test_lo or train_hi <= train_lo:
            break
        fold += 1
        if oos_lo is None:
            oos_lo = test_lo

        scored = [_score(A, train_lo, train_hi, objective)[0] for A in arrs]
        bi = int(np.argmax(scored))
        bestA, best_ov, train_score = arrs[bi], configs[bi], scored[bi]
        _, test_seg = _score(bestA, test_lo, test_hi, objective)

        chosen_rets[test_lo:test_hi] = bestA["rets"][test_lo:test_hi]
        chosen_inmkt[test_lo:test_hi] = bestA["in_market"][test_lo:test_hi]
        oos_trades.extend(validation._trades_in(bestA["trades"], test_lo, test_hi))
        steps.append(dict(
            fold=fold,
            train_from=str(idx[train_lo])[:10], train_to=str(idx[train_hi - 1])[:10],
            test_from=str(idx[test_lo])[:10], test_to=str(idx[test_hi - 1])[:10],
            train_bars=[int(train_lo), int(train_hi)], test_bars=[int(test_lo), int(test_hi)],
            params=best_ov, train_score=float(train_score), test=test_seg))
        cursor_t += test_td

    # stitched out-of-sample: test windows tile contiguously from the first test bar
    oos_hi = min(hi, int(idx.searchsorted(min(cursor_t, end_t)))) if steps else hi
    oos_lo = oos_lo if oos_lo is not None else lo
    oos = validation._segment(chosen_rets[oos_lo:oos_hi], oos_trades,
                              chosen_inmkt[oos_lo:oos_hi], ppy)

    # overfit yardstick: single best config chosen on the FULL selected range (in-sample optimal)
    full_scored = [_score(A, lo, hi, objective)[0] for A in arrs]
    fi = int(np.argmax(full_scored))
    fullA, full_ov = arrs[fi], configs[fi]
    full_seg = validation._segment(fullA["rets"][lo:hi],
                                   validation._trades_in(fullA["trades"], lo, hi),
                                   fullA["in_market"][lo:hi], ppy)

    # how often each swept param's value was re-chosen (parameter stability)
    stability = {}
    for p in specs:
        vals = [s["params"].get(p) for s in steps]
        counts = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        stability[p] = counts

    oos_end = str(idx[min(oos_hi, n) - 1])[:10]
    return dict(steps=steps, oos=oos, oos_span=(str(idx[oos_lo])[:10], oos_end),
                full_best=dict(params=full_ov, metrics=full_seg),
                objective=objective, anchored=anchored,
                date_range=(str(idx[lo])[:10], str(idx[min(hi, n) - 1])[:10]),
                train_days=train_days, test_days=test_days, n_windows=len(steps),
                n_configs=len(configs), stability=stability)
