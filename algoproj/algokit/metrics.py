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


def gross_profit(trades):
    """Sum of all winning trades' net PnL (USD)."""
    return float(sum(p for p in _trade_pnls(trades) if p > 0))


def gross_loss(trades):
    """Sum of all losing trades' net PnL as a POSITIVE number (USD)."""
    return float(-sum(p for p in _trade_pnls(trades) if p < 0))


def win_loss_even_counts(trades):
    r = _trade_returns(trades)
    return (sum(1 for x in r if x > 0), sum(1 for x in r if x < 0), sum(1 for x in r if x == 0))


def largest_win(trades):
    r = [x for x in _trade_returns(trades) if x > 0]
    return float(max(r)) if r else 0.0


def largest_loss(trades):
    r = [x for x in _trade_returns(trades) if x < 0]
    return float(min(r)) if r else 0.0


def max_consecutive_wins(trades):
    best = cur = 0
    for x in _trade_returns(trades):
        cur = cur + 1 if x > 0 else 0
        best = max(best, cur)
    return best


def avg_bars_in_trade(trades):
    h = [t["exit_i"] - t["entry_i"] for t in trades
         if isinstance(t, dict) and "exit_i" in t and "entry_i" in t]
    return float(np.mean(h)) if h else 0.0


def ulcer_index(rets):
    """RMS of the percent-drawdown series — pain/lumpiness of the equity curve."""
    e = _equity(rets)
    dd = (e / np.maximum.accumulate(e) - 1.0) * 100.0
    return float(np.sqrt(np.mean(dd * dd)))


def r_squared(rets):
    """How LINEAR the (log) equity curve is vs time. ~1 = smooth steady climb."""
    e = _equity(rets)
    y = np.log(np.clip(e, 1e-9, None))
    if len(y) < 2 or y.std() == 0:
        return 0.0
    c = np.corrcoef(np.arange(len(y), dtype=float), y)[0, 1]
    return float(c * c) if np.isfinite(c) else 0.0


def _drawdown_durations(rets):
    """(longest underwater run, longest flat run) in BARS."""
    e = _equity(rets)
    underwater = e < np.maximum.accumulate(e)
    rec = cur = 0
    for u in underwater:
        cur = cur + 1 if u else 0
        rec = max(rec, cur)
    flat = curf = 0
    for r in rets:
        curf = curf + 1 if abs(r) < 1e-12 else 0
        flat = max(flat, curf)
    return rec, flat


def _avg_field(trades, key):
    v = [t[key] for t in trades if isinstance(t, dict) and key in t]
    return float(np.mean(v)) if v else None


def extended_summary(rets, trades, in_market, ppy, start=0):
    """The full report: returns, risk-adjusted ratios, trade quality, exposure,
    excursions, curve-quality, and a Monte-Carlo drawdown/risk-of-ruin block."""
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
    # --- extended NinjaTrader-style report fields ---
    years = (len(rets) / ppy) if ppy else 0.0
    bars_per_day = (ppy / 365.25) if ppy else 1.0
    w, l, ev = win_loss_even_counts(trades)
    rec_bars, flat_bars = _drawdown_durations(rets)
    d.update(
        gross_profit=gross_profit(trades), gross_loss=gross_loss(trades),
        n_winners=w, n_losers=l, n_even=ev,
        largest_win=largest_win(trades), largest_loss=largest_loss(trades),
        max_consec_winners=max_consecutive_wins(trades),
        avg_bars_in_trade=avg_bars_in_trade(trades),
        avg_trades_per_day=(len(trades) / (years * 252) if years else 0.0),
        profit_per_month=(total_pnl(trades) / (years * 12) if years else 0.0),
        ulcer_index=ulcer_index(rets),
        r_squared=r_squared(rets),
        max_time_to_recover_days=rec_bars / bars_per_day,
        longest_flat_days=flat_bars / bars_per_day,
        avg_mae=_avg_field(trades, "mae"),
        avg_mfe=_avg_field(trades, "mfe"),
        avg_etd=_avg_field(trades, "etd"),
    )
    d.update(bootstrap_drawdown(trades))
    return d
