"""
Performance & risk metrics. Operate on a per-bar return array (rets) and/or the
trade list from backtest.run_long_only (entry_i, exit_i, entry_px, exit_px, reason).
ppy = bars per year (for annualizing).
"""
import numpy as np


def _equity(rets):
    return np.cumprod(1 + np.asarray(rets, float))


def total_return(rets):
    """Total compounded return (fraction)."""
    return _equity(rets)[-1] - 1


def cagr(rets, ppy):
    """Compound annual growth rate (fraction)."""
    eq = _equity(rets)
    return eq[-1] ** (ppy / len(rets)) - 1


def sharpe(rets, ppy, start=0):
    """Annualized Sharpe: mean return / volatility, scaled to a year."""
    r = np.asarray(rets, float)[start:]
    return (r.mean() / r.std()) * np.sqrt(ppy) if r.std() > 0 else 0.0


def sortino(rets, ppy, start=0):
    """Like Sharpe but only penalizes DOWNSIDE volatility."""
    r = np.asarray(rets, float)[start:]
    dn = r[r < 0]
    dd = dn.std() if len(dn) else 0.0
    return (r.mean() / dd) * np.sqrt(ppy) if dd > 0 else 0.0


def annual_vol(rets, ppy, start=0):
    """Annualized standard deviation of returns."""
    return np.asarray(rets, float)[start:].std() * np.sqrt(ppy)


def max_drawdown(rets):
    """Max peak-to-trough drop (fraction, negative)."""
    eq = _equity(rets)
    return (eq / np.maximum.accumulate(eq) - 1).min()


def calmar(rets, ppy):
    """CAGR divided by max drawdown — return earned per unit of worst drop."""
    mdd = abs(max_drawdown(rets))
    return cagr(rets, ppy) / mdd if mdd > 0 else 0.0


def _trade_returns(trades):
    """Per-trade gross price return. Accepts the engine's trade dicts (preferred)
    or the legacy 5-tuples (entry_i, exit_i, entry_px, exit_px, reason)."""
    out = []
    for t in trades:
        if isinstance(t, dict):
            out.append(t["ret"])
        else:
            _, _, ep, xp, _ = t
            out.append(xp / ep - 1)
    return out


def _trade_pnls(trades):
    """Net per-trade PnL in USD (dollar engine only); empty for legacy tuples."""
    return [t["pnl"] for t in trades if isinstance(t, dict) and "pnl" in t]


def total_pnl(trades):
    """Total realized net dollar profit across all trades."""
    p = _trade_pnls(trades)
    return float(np.sum(p)) if p else 0.0


def avg_pnl(trades):
    """Average net dollar profit per trade."""
    p = _trade_pnls(trades)
    return float(np.mean(p)) if p else 0.0


def win_rate(trades):
    tr = _trade_returns(trades)
    return np.mean([t > 0 for t in tr]) if tr else 0.0


def expectancy(trades):
    """Mean per-trade return fraction (the average edge per trade)."""
    tr = _trade_returns(trades)
    return np.mean(tr) if tr else 0.0


def avg_win(trades):
    tr = [t for t in _trade_returns(trades) if t > 0]
    return np.mean(tr) if tr else 0.0


def avg_loss(trades):
    tr = [t for t in _trade_returns(trades) if t <= 0]
    return np.mean(tr) if tr else 0.0


def profit_factor(trades):
    """Gross profit / gross loss. >1 = profitable; 2.0 = wins are 2x the losses."""
    tr = _trade_returns(trades)
    g = sum(t for t in tr if t > 0)
    l = -sum(t for t in tr if t < 0)
    return g / l if l > 0 else float("inf")


def payoff_ratio(trades):
    """Average win size / average loss size."""
    al = avg_loss(trades)
    return avg_win(trades) / abs(al) if al < 0 else float("inf")


def max_consecutive_losses(trades):
    """Longest losing streak (in trades) — drives drawdown psychology."""
    m = c = 0
    for t in _trade_returns(trades):
        c = c + 1 if t <= 0 else 0
        m = max(m, c)
    return m


def exposure(in_market):
    """Fraction of bars actually holding a position (time in market)."""
    return float(np.mean(in_market))


def bootstrap_drawdown(trades, n=2000, seed=0, ruin_levels=(0.20, 0.50)):
    """Monte-Carlo robustness: reshuffle the trade order many times (final return
    is identical, but the PATH/drawdown differs) and look at the drawdown distribution.
    Returns median & 95th-percentile worst drawdown, and P(drawdown worse than each ruin level)."""
    tr = np.array(_trade_returns(trades), float)
    if len(tr) == 0:
        return {}
    rng = np.random.default_rng(seed)
    dds = np.empty(n)
    for i in range(n):
        eq = np.cumprod(1 + rng.permutation(tr))
        dds[i] = (eq / np.maximum.accumulate(eq) - 1).min()
    out = {"mc_median_dd": float(np.median(dds)),
           "mc_p95_worst_dd": float(np.percentile(dds, 5))}  # 5th pct = worst 5%
    for lvl in ruin_levels:
        out[f"P(dd<-{int(lvl*100)}%)"] = float(np.mean(dds <= -lvl))
    return out


def summary(rets, trades, ppy, start=0):
    """Headline numbers (the original compact set)."""
    return dict(
        total_return=total_return(rets),
        cagr=cagr(rets, ppy),
        sharpe=sharpe(rets, ppy, start),
        max_drawdown=max_drawdown(rets),
        round_trips=len(trades),
        win_rate=win_rate(trades),
        expectancy=expectancy(trades),
    )


EXPLAIN = {
 "total_return": "Total compounded gain over the whole backtest.",
 "cagr": "Compound Annual Growth Rate — return smoothed to a yearly rate.",
 "annual_vol": "How much returns swing (annualized) = risk.",
 "sharpe": "Return per unit of TOTAL risk. >1 good, <0.5 weak, <0 losing.",
 "sortino": "Like Sharpe but only DOWNSIDE swings count as risk.",
 "calmar": "Annual return / worst drawdown — reward vs pain.",
 "max_drawdown": "Worst peak-to-trough drop the account would have felt.",
 "exposure": "Share of time actually holding a position (rest = in cash).",
 "round_trips": "Number of completed buy->sell trades.",
 "win_rate": "Share of trades that made money.",
 "expectancy": "Average profit PER TRADE (your edge per trade).",
 "avg_win": "Average size of a winning trade.",
 "avg_loss": "Average size of a losing trade.",
 "profit_factor": "Gross profit / gross loss. >1 profitable; 2 = wins double the losses.",
 "payoff_ratio": "Average win size / average loss size.",
 "max_consec_losses": "Longest losing streak — what you must stomach.",
 "total_pnl": "Total realized net profit in USD (after commission + slippage).",
 "avg_pnl": "Average net profit per trade in USD (after costs).",
 "mc_median_dd": "Typical worst-drawdown across reshuffled trade orders (robustness).",
 "mc_p95_worst_dd": "A bad-luck-ordering drawdown (worst 5%).",
 "P(dd<-20%)": "Chance of a >20% drawdown across reshuffled orders (risk-of-ruin proxy).",
 "P(dd<-50%)": "Chance of a >50% drawdown across reshuffled orders (risk-of-ruin proxy).",
}
_PCT_KEYS = {"total_return", "cagr", "annual_vol", "max_drawdown", "exposure", "win_rate",
             "expectancy", "avg_win", "avg_loss", "mc_median_dd", "mc_p95_worst_dd"}


_USD_KEYS = {"total_pnl", "avg_pnl"}


def fmt(key, val):
    """Human-format a metric value for display."""
    if val is None:
        return "n/a"
    if isinstance(val, str):
        return val
    if key.startswith("P(dd"):
        return f"{val*100:.1f}%"
    if key in _USD_KEYS:
        return f"${val:,.0f}"
    if key in _PCT_KEYS:
        return f"{val*100:.2f}%"
    if key in {"round_trips", "max_consec_losses"}:
        return f"{int(val)}"
    try:
        return f"{float(val):.2f}"
    except (TypeError, ValueError):
        return str(val)


def extended_summary(rets, trades, in_market, ppy, start=0):
    """The full report: returns, risk-adjusted ratios, trade quality, exposure,
    and a Monte-Carlo drawdown/risk-of-ruin block."""
    d = dict(
        total_return=total_return(rets),
        cagr=cagr(rets, ppy),
        annual_vol=annual_vol(rets, ppy, start),
        sharpe=sharpe(rets, ppy, start),
        sortino=sortino(rets, ppy, start),
        calmar=calmar(rets, ppy),
        max_drawdown=max_drawdown(rets),
        exposure=exposure(in_market),
        round_trips=len(trades),
        win_rate=win_rate(trades),
        expectancy=expectancy(trades),
        avg_win=avg_win(trades),
        avg_loss=avg_loss(trades),
        profit_factor=profit_factor(trades),
        payoff_ratio=payoff_ratio(trades),
        max_consec_losses=max_consecutive_losses(trades),
        total_pnl=total_pnl(trades),
        avg_pnl=avg_pnl(trades),
    )
    d.update(bootstrap_drawdown(trades))
    return d
