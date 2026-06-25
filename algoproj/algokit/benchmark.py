"""
Buy-&-hold benchmark — the bar every strategy must clear.

A strategy that returns less than passively holding the same instrument, on the
same capital, over the same period, with the same realistic costs, has no reason
to exist. This module produces that benchmark as a directly comparable dollar
equity curve so the comparison is automatic in the registry and the UI, never
eyeballed.

It is deliberately built on the SAME cost model and the SAME starting capital as
the strategy run, and it enters at the first tradable bar's open (cost-slipped)
and holds to the end — one entry, no exit costs avoided (we mark the final close).
"""
import math

import numpy as np

from . import metrics
from .costs import FuturesCost


def buy_and_hold(open, close, start, cost=None, capital=100_000.0, leverage=1.0):
    """Fully-invested long buy-&-hold on `capital`, entered at open[start].

    Returns dict(rets, equity, contracts, metrics) where metrics mirrors the
    strategy's extended_summary keys that are price-path based (no trade list).
    """
    open = np.asarray(open, float); close = np.asarray(close, float)
    n = len(close)
    cost = cost or FuturesCost()
    pv = float(getattr(cost, "point_value", 20.0))

    entry = cost.fill_price(open[start], is_buy=True)
    contracts = max(1, math.floor(capital * leverage / (entry * pv)))

    equity = np.full(n, float(capital))
    cash = capital - cost.commission(contracts)
    for i in range(start, n):
        equity[i] = cash + contracts * (close[i] - entry) * pv
    rets = np.zeros(n)
    rets[start + 1:] = equity[start + 1:] / equity[start:-1] - 1

    return dict(rets=rets, equity=equity, contracts=contracts,
                metrics=_bench_metrics(rets, start))


def _bench_metrics(rets, start, ppy=None):
    """Price-path metrics for the benchmark (no trade list)."""
    d = dict(
        total_return=metrics.total_return(rets),
        max_drawdown=metrics.max_drawdown(rets),
    )
    if ppy:
        d["cagr"] = metrics.cagr(rets, ppy)
        d["sharpe"] = metrics.sharpe(rets, ppy, start)
    return d


def compare(strat_metrics, bench_metrics):
    """Excess return / alpha-style deltas of the strategy over buy-&-hold."""
    out = {}
    for k in ("total_return", "cagr", "sharpe", "max_drawdown"):
        s = strat_metrics.get(k); b = bench_metrics.get(k)
        if s is not None and b is not None:
            out[f"vs_bench_{k}"] = s - b
    return out
