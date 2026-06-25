"""
Trading-cost / execution models.

The backtest is a DOLLAR-ACCOUNT engine (see backtest.py). A cost model therefore
has to answer two questions on every fill:

  1. what price do I actually get?   -> fill_price(ref, is_buy)  (slippage)
  2. what does the broker charge?     -> commission(contracts)   (commission)

REALISM NOTE (read this before trusting any number):
Every fill in this project is intentionally PESSIMISTIC. We would rather a
backtest under-state edge than over-state it. Slippage is added against us on
every entry and every exit; commission is charged per contract per side; stops
fill at the stop OR at the gap-through open, whichever is worse.

FuturesCost is the realistic default (NQ /NQ E-mini specs). FlatCost is kept only
so the OLD fractional engine numbers can still be reproduced; new runs use
FuturesCost.

NQ E-mini contract specs (CME):
    point_value = $20 per index point
    tick        = 0.25 points  ->  tick_value = $5.00
Typical retail all-in commission is ~$2.00-2.50 per side; 1 tick of slippage per
fill is a sane, slightly conservative default for a liquid future.
"""


class FuturesCost:
    """Realistic NQ-futures execution model: per-side commission + tick slippage.

    Parameters
    ----------
    commission_per_side : USD charged per contract on EACH fill (entry and exit).
    slippage_ticks      : ticks of adverse slippage applied to EACH fill.
    point_value         : USD per 1.0 index point (NQ = $20).
    tick                : minimum price increment in points (NQ = 0.25).
    tick_value          : USD per tick  (= point_value * tick = $5 for NQ).
    """

    def __init__(self, commission_per_side=2.25, slippage_ticks=1.0,
                 point_value=20.0, tick=0.25, tick_value=5.0):
        self.commission_per_side = float(commission_per_side)
        self.slippage_ticks = float(slippage_ticks)
        self.point_value = float(point_value)
        self.tick = float(tick)
        self.tick_value = float(tick_value)

    def fill_price(self, ref_price, is_buy):
        """Price actually obtained: buys fill HIGHER, sells fill LOWER (adverse)."""
        slip = self.slippage_ticks * self.tick
        return ref_price + slip if is_buy else ref_price - slip

    def commission(self, contracts):
        """Total commission in USD for `contracts` on one side of a trade."""
        return self.commission_per_side * abs(contracts)

    def describe(self):
        return (f"{self.commission_per_side:.2f}/side + {self.slippage_ticks:g} tick slip "
                f"(${self.point_value:g}/pt, tick {self.tick:g})")


class FlatCost:
    """LEGACY flat fractional cost per turn (the original COST=0.0002).

    Only used to reproduce pre-realism fractional backtests. The dollar engine
    does NOT use this; prefer FuturesCost.
    """

    def __init__(self, per_turn=0.0002):
        self.per_turn = per_turn

    def per_turn_fraction(self, price=None):
        return self.per_turn
