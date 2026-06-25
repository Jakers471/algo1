"""
Execution / fill model — the *only* place that decides what price a fill gets.

Kept separate from the engine loop so the trading rules (when) and the fill
mechanics (at what price, how realistic) can be reasoned about and tested
independently. Every function here is deliberately PESSIMISTIC — see costs.py.

Look-ahead policy enforced by the engine that calls these:
  * A decision made on the CLOSE of bar i is filled at the OPEN of bar i+1
    (next-bar-open). You can never trade on information you only have at the
    close using that same close's price.
  * A protective stop is the one exception: it lives *inside* the bar, so it can
    trigger on the bar where price trades through it. If the bar GAPS through the
    stop, you do not get the stop price — you get the (worse) open.
"""


def entry_fill(open_price, cost):
    """Buy at next bar's open, slipped adversely (higher)."""
    return cost.fill_price(open_price, is_buy=True)


def exit_fill(open_price, cost):
    """Sell (signal/exit) at next bar's open, slipped adversely (lower)."""
    return cost.fill_price(open_price, is_buy=False)


def stop_fill(bar_open, stop_price, cost):
    """Long protective-stop fill price (gap-aware).

    If the bar opened at/above the stop, you get filled at the stop (then slipped).
    If the bar GAPPED below the stop, the stop becomes a market order at the open,
    so you get the worse of the two. Slippage is applied on top either way.
    """
    ref = min(bar_open, stop_price)        # gap-through -> the worse (lower) open
    return cost.fill_price(ref, is_buy=False)
