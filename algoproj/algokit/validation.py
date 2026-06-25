"""
Out-of-sample & walk-forward validation.

THE point of this module: a backtest measured on the same data its parameters
were chosen on is marketing, not evidence. Everything here splits a run in time
so you can see whether an edge SURVIVES on data it never touched.

Two tools, both operating on a finished run's per-bar arrays (so they work on a
live result OR a saved run reloaded from the registry):

  in_out_sample(...)  : one train/test boundary (default 70/30 by time). Compare
                        the in-sample metrics to the out-of-sample metrics. If OOS
                        falls off a cliff, the config is overfit.
  walk_forward(...)   : K sequential, non-overlapping folds across the whole
                        history. Stable edge => similar metrics fold to fold.

NOTE: this evaluates a FIXED config across time (stability / honesty check). It is
not a parameter re-optimizer — that belongs with an objective + a search, and we
do not auto-tune the signal yet. When tuning IS added, tune on the in-sample
slice only and report the out-of-sample slice ONCE.
"""
import numpy as np
import pandas as pd

from . import metrics


def _segment(rets, trades, in_market, ppy):
    """Compact metric block for one time slice (arrays already sliced)."""
    if len(rets) == 0:
        return {}
    d = dict(
        total_return=metrics.total_return(rets),
        cagr=metrics.cagr(rets, ppy),
        sharpe=metrics.sharpe(rets, ppy),
        max_drawdown=metrics.max_drawdown(rets),
        exposure=metrics.exposure(in_market) if len(in_market) else 0.0,
        round_trips=len(trades),
        win_rate=metrics.win_rate(trades),
        expectancy=metrics.expectancy(trades),
        profit_factor=metrics.profit_factor(trades),
    )
    return d


def _boundary(idx, split):
    """Resolve `split` (a fraction in (0,1) or a date-like) to a bar position."""
    idx = pd.DatetimeIndex(idx)
    if isinstance(split, (int, float)) and 0 < split < 1:
        return int(len(idx) * split)
    return int(idx.searchsorted(pd.Timestamp(split)))


def _trades_in(trades, lo, hi):
    """Trades whose ENTRY bar falls in [lo, hi)."""
    return [t for t in trades if lo <= t["entry_i"] < hi]


def in_out_sample(rets, trades, in_market, idx, ppy, split=0.70):
    """Split once into in-sample / out-of-sample and return both metric blocks.

    split : fraction of bars (0.70 = first 70% train) or a date string/Timestamp.
    """
    b = _boundary(idx, split)
    return {
        "split_bar": b,
        "split_time": str(pd.DatetimeIndex(idx)[min(b, len(idx) - 1)]),
        "in_sample": _segment(rets[:b], _trades_in(trades, 0, b), in_market[:b], ppy),
        "out_of_sample": _segment(rets[b:], _trades_in(trades, b, len(rets)),
                                  in_market[b:], ppy),
    }


def walk_forward(rets, trades, in_market, idx, ppy, n_folds=5):
    """Evaluate the fixed config across K equal, sequential time folds.

    Returns a list of per-fold metric blocks. Compare them: an edge that only
    shows up in one fold is noise.
    """
    n = len(rets)
    edges = np.linspace(0, n, n_folds + 1).astype(int)
    out = []
    for f in range(n_folds):
        lo, hi = edges[f], edges[f + 1]
        seg = _segment(rets[lo:hi], _trades_in(trades, lo, hi), in_market[lo:hi], ppy)
        seg["fold"] = f + 1
        seg["from"] = str(pd.DatetimeIndex(idx)[lo])
        seg["to"] = str(pd.DatetimeIndex(idx)[min(hi, n - 1)])
        out.append(seg)
    return out
