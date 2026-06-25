"""
Strategy-agnostic, long-only, DOLLAR-ACCOUNT backtest engine.

This is the orchestrator. It owns none of the trading logic and none of the fill
mechanics — it wires together:
    signals   (entry_sig / exit_sig boolean arrays, supplied by ANY strategy)
    sizing    (algokit.sizing : how many contracts)
    execution (algokit.execution : at what price a fill happens)
    costs     (algokit.costs : commission + slippage)
into a mark-to-market dollar equity curve. Because any strategy that produces
two boolean arrays + an ATR array can drive it, the same engine backtests every
strategy in strategies/.

================  NO LOOK-AHEAD — THE ONE RULE  ================
A decision is made on the CLOSE of bar i and FILLED AT THE OPEN OF BAR i+1.
The loop literally cannot place a fill on the bar whose close produced the
signal. The only intrabar event is the protective stop, which is allowed to
trigger on its bar and fills gap-aware (worse of stop / open). Stops use the ATR
of the SIGNAL bar (i-1), which is already known. Verify this with the unit tests
in tests/test_no_lookahead.py before trusting any result.

REALISM: fills are pessimistic (adverse slippage every fill, commission per side,
gap-through stops). Sizing is path-dependent on live equity. Returns are the
percentage change of a real dollar account, so every metric in metrics.py
reflects the account you would actually trade.
"""
import numpy as np

from . import execution, sizing as sizing_mod
from .costs import FuturesCost


def run_long_only(open, high, low, close, entry_sig, exit_sig, atr,
                  atr_mult=5.0, cost=None, sizing="fixed", capital=100_000.0,
                  start=0, cfg=None):
    """Run the long-only dollar engine.

    open, high, low, close, atr : 1-D arrays of equal length (points).
    entry_sig, exit_sig : boolean arrays. Decision on bar i -> fill at open[i+1].
    atr_mult : protective stop = entry_fill - atr_mult * atr[signal_bar].
    cost     : a FuturesCost (default NQ specs). Drives slippage + commission.
    sizing   : name in algokit.sizing.SIZERS, or a callable.
    capital  : starting account equity in USD.
    start    : first bar eligible to trade (warmup boundary).
    cfg      : config dict passed through to the sizing model (size_contracts,
               risk_pct, max_contracts, ...).

    Returns dict(rets, equity, trades, in_market, capital, final_equity) where
    trades is a list of dicts: entry_i, exit_i, entry_px, exit_px, contracts,
    reason, ret (gross price %), pnl (net USD incl. both commissions).
    """
    open = np.asarray(open, float); high = np.asarray(high, float)
    low = np.asarray(low, float);   close = np.asarray(close, float)
    atr = np.asarray(atr, float)
    entry_sig = np.asarray(entry_sig, bool); exit_sig = np.asarray(exit_sig, bool)
    n = len(close)
    cost = cost or FuturesCost()
    cfg = cfg or {}
    size = sizing_mod.resolve(sizing, cfg)
    pv = float(getattr(cost, "point_value", cfg.get("point_value", 20.0)))

    rets = np.zeros(n)
    equity = np.full(n, float(capital))
    inmkt = np.zeros(n)
    trades = []
    total_commission = 0.0

    cash = float(capital)        # realized equity
    eq_prev = float(capital)
    pos = 0                      # contracts held (0 = flat)
    entry_px = stop = np.nan
    entry_i = -1
    trade_lo = trade_hi = np.nan  # running low/high WHILE a trade is open (for MAE/MFE/ETD)
    pending = None               # 'enter' | 'exit', decided last bar

    def _close_trade(exit_i, exit_px, reason):
        nonlocal cash, pos, total_commission
        comm = cost.commission(pos)
        cash += pos * (exit_px - entry_px) * pv - comm
        pnl = pos * (exit_px - entry_px) * pv - 2 * comm
        total_commission += comm                      # exit-side (entry-side tracked at entry)
        trades.append(dict(entry_i=entry_i, exit_i=exit_i, entry_px=entry_px,
                           exit_px=exit_px, contracts=pos, reason=reason,
                           ret=exit_px / entry_px - 1, pnl=pnl,
                           # excursions as a fraction of entry price (long): adverse / favorable / give-back
                           mae=(entry_px - trade_lo) / entry_px,
                           mfe=(trade_hi - entry_px) / entry_px,
                           etd=(trade_hi - exit_px) / entry_px))
        pos = 0

    for i in range(start, n):
        # 1) execute the decision made on bar i-1, at THIS bar's open
        if pending == "enter" and pos == 0:
            fill = execution.entry_fill(open[i], cost)
            stop_px = fill - atr_mult * atr[i - 1]
            c = size(eq_prev, fill, stop_px, pv, cfg)
            if c > 0:
                pos = c; entry_px = fill; stop = stop_px; entry_i = i
                trade_lo = low[i]; trade_hi = high[i]
                comm = cost.commission(c)
                cash -= comm; total_commission += comm
        elif pending == "exit" and pos > 0:
            trade_lo = min(trade_lo, low[i]); trade_hi = max(trade_hi, high[i])
            _close_trade(i, execution.exit_fill(open[i], cost), "signal")
        pending = None

        # 2) protective stop lives inside the bar (gap-aware, worst-case fill)
        if pos > 0 and low[i] <= stop:
            trade_lo = min(trade_lo, low[i]); trade_hi = max(trade_hi, high[i])
            _close_trade(i, execution.stop_fill(open[i], stop, cost), "stop")

        # 2b) accrue the excursion for any bar we remain in the position
        if pos > 0:
            trade_lo = min(trade_lo, low[i]); trade_hi = max(trade_hi, high[i])

        # 3) mark to market -> dollar equity & per-bar return
        eq_i = cash + (pos * (close[i] - entry_px) * pv if pos > 0 else 0.0)
        equity[i] = eq_i
        rets[i] = eq_i / eq_prev - 1 if eq_prev else 0.0
        inmkt[i] = 1 if pos > 0 else 0
        eq_prev = eq_i

        # 4) decide on THIS close, to be filled next bar's open (no look-ahead)
        if i + 1 < n:
            if pos == 0 and entry_sig[i]:
                pending = "enter"
            elif pos > 0 and exit_sig[i]:
                pending = "exit"

    return dict(rets=rets, equity=equity, trades=trades, in_market=inmkt,
                capital=float(capital), final_equity=float(equity[-1]),
                total_commission=float(total_commission))
