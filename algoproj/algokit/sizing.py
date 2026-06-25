"""
Position-sizing models — pluggable, like the indicator registry.

A sizing model answers ONE question: given the account equity and the trade's
entry/stop, how many contracts do I buy? It returns an integer >= 0 (0 = the
trade is skipped because it can't be sized within risk limits).

Register a new model with @sizer; it lands in SIZERS under its name and is then
selectable by string from the engine / config / Streamlit UI.

Signature: model(equity, entry_price, stop_price, point_value, cfg) -> int
    equity       : current account equity in USD (sizing is path-dependent).
    entry_price  : fill price of the entry (points).
    stop_price   : protective-stop price (points); entry - stop = risk distance.
    point_value  : USD per index point (NQ = 20).
    cfg          : the full strategy/exec config dict (read your own params).
"""
import math

SIZERS = {}


def sizer(fn):
    """Register a position-sizing model in SIZERS under its function name."""
    SIZERS[fn.__name__] = fn
    return fn


@sizer
def fixed(equity, entry_price, stop_price, point_value, cfg):
    """Always trade a fixed number of contracts (cfg['size_contracts'], default 1)."""
    return max(0, int(cfg.get("size_contracts", 1)))


@sizer
def risk_pct(equity, entry_price, stop_price, point_value, cfg):
    """Risk a fixed % of equity to the stop (cfg['risk_pct'], default 0.01 = 1%).

    contracts = floor( (equity * risk_pct) / (stop_distance_pts * point_value) ).
    Falls back to 0 if the stop distance is non-positive or risk buys < 1 contract.
    """
    risk_usd = equity * float(cfg.get("risk_pct", 0.01))
    stop_dist = entry_price - stop_price
    if stop_dist <= 0 or point_value <= 0:
        return 0
    n = math.floor(risk_usd / (stop_dist * point_value))
    cap = int(cfg.get("max_contracts", 1_000_000))
    return max(0, min(n, cap))


def resolve(sizing, cfg):
    """Turn a sizing spec (name string or callable) into a sizing callable."""
    if callable(sizing):
        return sizing
    name = sizing or cfg.get("sizing", "fixed")
    if name not in SIZERS:
        raise KeyError(f"unknown sizing model {name!r}; have {list(SIZERS)}")
    return SIZERS[name]
