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


def _daily_curve(rets_slice, idx_slice, capital=100_000.0):
    """Per-bar return slice -> a daily %-return-from-start curve {dates, pct} for the UI."""
    rets_slice = np.asarray(rets_slice, float)
    if len(rets_slice) == 0:
        return {"dates": [], "pct": []}
    eq = capital * np.cumprod(1.0 + rets_slice)
    s = pd.Series(eq, index=pd.DatetimeIndex(idx_slice)).resample("1D").last().dropna()
    if s.empty:
        return {"dates": [], "pct": []}
    base = float(s.iloc[0])
    return {"dates": [str(d.date()) for d in s.index],
            "pct": [round(float(v / base * 100 - 100), 2) for v in s.values]}


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
        _, is_seg = _score(bestA, train_lo, train_hi, objective)   # chosen config on its TRAIN window

        chosen_rets[test_lo:test_hi] = bestA["rets"][test_lo:test_hi]
        chosen_inmkt[test_lo:test_hi] = bestA["in_market"][test_lo:test_hi]
        oos_trades.extend(validation._trades_in(bestA["trades"], test_lo, test_hi))
        step = dict(
            fold=fold,
            train_from=str(idx[train_lo])[:10], train_to=str(idx[train_hi - 1])[:10],
            test_from=str(idx[test_lo])[:10], test_to=str(idx[test_hi - 1])[:10],
            train_bars=[int(train_lo), int(train_hi)], test_bars=[int(test_lo), int(test_hi)],
            params=best_ov, train_score=float(train_score), test=test_seg)
        step["is"] = is_seg                                        # 'is' is reserved -> set by key
        steps.append(step)
        cursor_t += test_td

    # stitched out-of-sample: test windows tile contiguously from the first test bar
    oos_hi = min(hi, int(idx.searchsorted(min(cursor_t, end_t)))) if steps else hi
    oos_lo = oos_lo if oos_lo is not None else lo
    oos = validation._segment(chosen_rets[oos_lo:oos_hi], oos_trades,
                              chosen_inmkt[oos_lo:oos_hi], ppy)

    # overfit ceiling: the single config chosen WITH HINDSIGHT (best over the whole range), but
    # MEASURED over the OOS span so it's a fair head-to-head with the walk-forward (same span).
    full_scored = [_score(A, lo, hi, objective)[0] for A in arrs]
    fi = int(np.argmax(full_scored))
    fullA, full_ov = arrs[fi], configs[fi]
    full_seg = validation._segment(fullA["rets"][oos_lo:oos_hi],
                                   validation._trades_in(fullA["trades"], oos_lo, oos_hi),
                                   fullA["in_market"][oos_lo:oos_hi], ppy)

    # how often each swept param's value was re-chosen (parameter stability)
    stability = {}
    for p in specs:
        vals = [s["params"].get(p) for s in steps]
        counts = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        stability[p] = counts

    # ---- In-sample vs Out-of-sample + Walk-Forward Efficiency (the standard interpretation) ----
    MK = ["total_return", "cagr", "sharpe", "max_drawdown", "exposure", "round_trips",
          "win_rate", "expectancy", "profit_factor"]
    is_blocks = [s["is"] for s in steps if s.get("is")]
    is_avg = {k: (float(np.mean([b[k] for b in is_blocks if b.get(k) is not None]))
                  if any(b.get(k) is not None for b in is_blocks) else None) for k in MK}
    is_cagrs = [b.get("cagr") for b in is_blocks if b.get("cagr") is not None]
    is_cagr_mean = float(np.mean(is_cagrs)) if is_cagrs else 0.0
    oos_cagr = oos.get("cagr") or 0.0
    per_window_wfe = [((s["test"].get("cagr") / s["is"].get("cagr"))
                       if (s.get("is") and s.get("test") and (s["is"].get("cagr") or 0) > 0
                           and s["test"].get("cagr") is not None) else None) for s in steps]
    wfe = (oos_cagr / is_cagr_mean) if is_cagr_mean > 0 else None
    if wfe is None:
        rating, note = "na", "In-sample return not positive - WFE undefined; judge the OOS result directly."
    else:
        rating = ("excellent" if wfe > 0.70 else "good" if wfe >= 0.50
                  else "weak" if wfe >= 0.30 else "overfit")
        note = ""
    wfe_block = dict(wfe=wfe, is_cagr_mean=is_cagr_mean, oos_cagr=oos_cagr,
                     per_window=per_window_wfe, rating=rating, note=note)

    # ---- consistency / validity across windows ----
    trets = [s["test"].get("total_return") for s in steps if s.get("test") and s["test"].get("total_return") is not None]
    tshs = [s["test"].get("sharpe") for s in steps if s.get("test") and s["test"].get("sharpe") is not None]
    tdds = [s["test"].get("max_drawdown") for s in steps if s.get("test") and s["test"].get("max_drawdown") is not None]
    pos_sum = sum(r for r in trets if r > 0)
    conc = (max([r for r in trets if r > 0], default=0.0) / pos_sum) if pos_sum > 0 else 0.0
    consistency = dict(n_windows=len(steps), n_pos_oos=sum(1 for r in trets if r > 0),
                       oos_sharpe_std=float(np.std(tshs)) if tshs else 0.0,
                       worst_window_dd=float(min(tdds)) if tdds else 0.0,
                       concentration_pct=float(conc), concentrated=bool(conc > 0.5))

    # equity curves on a SHARED span: honest walk-forward OOS vs the overfit ceiling
    equity = {"oos": _daily_curve(chosen_rets[oos_lo:oos_hi], idx[oos_lo:oos_hi]),
              "full": _daily_curve(fullA["rets"][oos_lo:oos_hi], idx[oos_lo:oos_hi])}

    oos_end = str(idx[min(oos_hi, n) - 1])[:10]
    return dict(steps=steps, oos=oos, oos_span=(str(idx[oos_lo])[:10], oos_end),
                full_best=dict(params=full_ov, metrics=full_seg), is_avg=is_avg,
                wfe=wfe_block, consistency=consistency,
                objective=objective, anchored=anchored, equity=equity,
                date_range=(str(idx[lo])[:10], str(idx[min(hi, n) - 1])[:10]),
                train_days=train_days, test_days=test_days, n_windows=len(steps),
                n_configs=len(configs), stability=stability)
