"""
analytics — the full per-run performance breakdown, MACHINE-READABLE.

Turns a backtest's trades (the sim = source of truth) into one analysis dict: headline stats, an
ALL / LONG / SHORT split of the NinjaTrader-style report (returns, risk-adjusted ratios, trade quality,
excursions MAE/MFE/ETD, Monte-Carlo risk-of-ruin, time & exposure), plus the daily equity + drawdown
series for the chart. Pure computation, no rendering — `make_report.py` renders the HTML view from this.

$ model matches the backtest: fixed-fractional on the STARTING balance (pnl = R x risk_pct% x start), so
the report's dollars equal the sim's. Daily returns (for Sharpe/Sortino/DD) are placed on each trade's
exit day over the business-day calendar of the run window.

  analyze(trades, ctx) -> dict     (ctx: starting_balance, risk_pct, era, start_ts, end_ts, n_bars, costs)
"""
import numpy as np
import pandas as pd

PPY = 252  # trading periods per year (daily)


def _frac(trades, key):
    v = [t[key] for t in trades if key in t and t[key] is not None]
    return float(np.mean(v)) if v else None


def _daily(trades, bdays, starting, risk_d):
    """Daily account-return series over the run's business days (trade pnl placed on its exit day)."""
    by = {}
    for t in trades:
        d = pd.Timestamp(t["t_exit"], unit="s", tz="UTC").tz_convert("America/New_York").normalize()
        by[d] = by.get(d, 0.0) + t["R"] * risk_d
    dp = np.array([by.get(d, 0.0) for d in bdays], float)
    eq = starting + np.cumsum(dp)
    rets = dp / starting
    return rets, eq


def _dd(eq):
    peak = np.maximum.accumulate(eq)
    return (eq / peak - 1.0)


def _group(trades, ctx, cal, years, ppy):
    """Full metric dict for one subset (all / long / short). cal = the run's active-day calendar
    (business days ∪ trade-exit days, so no trade is dropped); years/ppy derived from it."""
    starting = ctx["starting_balance"]; risk_d = starting * ctx["risk_pct"] / 100.0
    n = len(trades)
    if n == 0:
        return None
    R = np.array([t["R"] for t in trades], float)
    pnl = R * risk_d
    ret = pnl / starting                              # per-trade account return
    wins = R > 0; losses = R < 0; evens = R == 0
    rets_d, eq = _daily(trades, cal, starting, risk_d)
    dd = _dd(eq)
    gp = float(pnl[wins].sum()); gl = float(-pnl[losses].sum())
    # curve / risk-adjusted (daily over the active calendar)
    mu, sd = rets_d.mean(), rets_d.std()
    downside = rets_d[rets_d < 0]
    dsd = downside.std() if len(downside) else 0.0
    total_ret = float(eq[-1] / starting - 1.0) if len(eq) else 0.0
    cagr = ((eq[-1] / starting) ** (1 / years) - 1.0) if years > 0 and len(eq) and eq[-1] > 0 else 0.0
    maxdd = float(dd.min()) if len(dd) else 0.0
    maxdd_d = float((eq - np.maximum.accumulate(eq)).min()) if len(eq) else 0.0
    ulcer = float(np.sqrt(np.mean((dd * 100) ** 2))) if len(dd) else 0.0
    # streaks
    def streak(mask):
        b = c = 0
        for x in mask:
            c = c + 1 if x else 0; b = max(b, c)
        return b
    # drawdown durations (business days)
    uw = eq < np.maximum.accumulate(eq)
    rec = streak(uw); flat = streak(np.abs(rets_d) < 1e-12)
    bar_days = ctx["bar_seconds"] / 86400.0
    # exposure
    tot_bars = sum(t.get("bars", 0) for t in trades)
    exposure = tot_bars / ctx["n_bars"] if ctx["n_bars"] else 0.0
    # monte-carlo risk of ruin on the R path (additive), ruin = drawdown in R exceeding X% of start (in R units)
    R_per_pct = (starting / 100.0) / risk_d           # how many R = 1% of starting balance
    mc = _mc_ruin_R(R, R_per_pct)
    return {
        "performance": {
            "total_net_profit": float(pnl.sum()), "gross_profit": gp, "gross_loss": gl,
            "commission": n * 2 * ctx["commission_per_side"],
            "total_slippage": n * 2 * ctx["slippage_ticks"] * ctx["tick"] * ctx["point_value"],
            "profit_factor": (gp / gl) if gl > 0 else float("inf"),
            "total_return": total_ret, "cagr": cagr, "max_dd_pct": maxdd, "max_dd_dollar": maxdd_d,
            "sharpe": float(mu / sd * np.sqrt(ppy)) if sd > 0 else 0.0,
            "sortino": float(mu / dsd * np.sqrt(ppy)) if dsd > 0 else 0.0,
            "calmar": float(cagr / abs(maxdd)) if maxdd < 0 else 0.0,
            "ulcer_index": ulcer,
        },
        "trades": {
            "total": n, "pct_profitable": float(wins.mean()),
            "n_win": int(wins.sum()), "n_loss": int(losses.sum()), "n_even": int(evens.sum()),
            "expectancy": float(ret.mean()), "avg_trade": float(pnl.mean()), "avg_R": float(R.mean()),
            "avg_win": float(ret[wins].mean()) if wins.any() else 0.0,
            "avg_loss": float(ret[losses].mean()) if losses.any() else 0.0,
            "payoff": float(ret[wins].mean() / abs(ret[losses].mean())) if losses.any() and ret[losses].mean() != 0 else float("inf"),
            "max_consec_win": streak(wins), "max_consec_loss": streak(losses),
            "largest_win": float(ret.max()), "largest_loss": float(ret.min()),
        },
        "excursion": {"avg_mae": _frac(trades, "mae"), "avg_mfe": _frac(trades, "mfe"), "avg_etd": _frac(trades, "etd")},
        "risk_of_ruin": mc,
        "time_exposure": {
            "avg_trades_per_day": n / len(cal) if len(cal) else 0.0,
            "time_in_market": exposure, "avg_bars_in_trade": float(np.mean([t.get("bars", 0) for t in trades])),
            "profit_per_month": float(pnl.sum()) / (years * 12) if years > 0 else 0.0,
            "max_time_to_recover_days": rec, "longest_flat_days": flat,
        },
    }


def _mc_ruin_R(R, R_per_pct, n=3000, seed=0, levels=(0.20, 0.50)):
    """Reshuffle the R sequence; measure the worst equity drawdown (in R) of each path.
    Convert to $ drawdown fraction via R_per_pct (R that equals 1% of the starting balance)."""
    R = np.asarray(R, float)
    if len(R) == 0:
        return {}
    rng = np.random.default_rng(seed); dds = np.empty(n)
    for i in range(n):
        eq = np.cumsum(rng.permutation(R)); peak = np.maximum.accumulate(eq)
        dds[i] = float((eq - peak).min())            # worst DD in R (<=0)
    dd_pct = dds / R_per_pct / 100.0                 # DD as fraction of starting balance
    out = {"median_dd": float(np.median(dd_pct)), "worst5_dd": float(np.percentile(dd_pct, 5))}
    for lv in levels:
        out[f"p_dd_lt_{int(lv*100)}"] = float(np.mean(dd_pct <= -lv))
    return out


def analyze(trades, ctx):
    start = pd.Timestamp(ctx["start_ts"], unit="s", tz="UTC").tz_convert("America/New_York")
    end = pd.Timestamp(ctx["end_ts"], unit="s", tz="UTC").tz_convert("America/New_York")
    # active-day calendar = business days ∪ every trade's exit day (NQ trades Sun eves/holidays too),
    # so no trade's pnl is dropped and the equity curve reconciles to starting + total pnl.
    cal = set(pd.bdate_range(start.normalize(), end.normalize(), tz="America/New_York"))
    for t in trades:
        cal.add(pd.Timestamp(t["t_exit"], unit="s", tz="UTC").tz_convert("America/New_York").normalize())
    cal = pd.DatetimeIndex(sorted(cal))
    years = max((end - start).days / 365.25, 1e-9)      # calendar years (correct for CAGR)
    ppy = len(cal) / years                              # observed periods/yr (annualization self-consistent)
    longs = [t for t in trades if t["dir"] == "up"]
    shorts = [t for t in trades if t["dir"] == "down"]
    g_all, g_long, g_short = (_group(x, ctx, cal, years, ppy) for x in (trades, longs, shorts))
    risk_d = ctx["starting_balance"] * ctx["risk_pct"] / 100.0
    rets_d, eq = _daily(trades, cal, ctx["starting_balance"], risk_d)
    dd = _dd(eq) * 100.0
    equity_series = {"dates": [d.strftime("%Y-%m-%d") for d in cal],
                     "equity": [round(float(x), 2) for x in eq],
                     "drawdown_pct": [round(float(x), 3) for x in dd]}
    h = g_all["performance"]; ht = g_all["trades"]
    return {
        "run": ctx.get("run", {}),
        "period": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
                   "trading_days": int(len(cal))},
        "headline": {"net_return": h["total_return"], "cagr": h["cagr"], "sharpe": h["sharpe"],
                     "max_dd": h["max_dd_pct"], "win_rate": ht["pct_profitable"], "exposure": g_all["time_exposure"]["time_in_market"],
                     "total_pnl": h["total_net_profit"], "profit_factor": h["profit_factor"], "avg_R": ht["avg_R"], "total_trades": ht["total"]},
        "groups": {"all": g_all, "long": g_long, "short": g_short},
        "equity": equity_series,
        "config": {k: ctx[k] for k in ("starting_balance", "risk_pct", "era_start", "target_r") if k in ctx},
        "config_snapshot": ctx.get("config_snapshot", {}),   # FULL strategy_config that produced this run (provenance)
        "trades": trades,   # the run's full trade list -> analysis.json is a self-contained, mineable archive
    }
