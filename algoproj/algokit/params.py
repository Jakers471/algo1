"""Which config keys are universal (account/execution/cost) vs strategy-specific.

A strategy's DEFAULT mixes the SIGNAL knobs that define its edge (X, exit_th, fans, ...)
with EXECUTION/COST/SIZING settings that are the same machinery for ANY strategy (account
size, commission, tick specs, position sizing). The UI groups them separately — signal
params in the main panel, universal ones behind a collapsed "Account & execution" panel —
and the optimizer only ever sweeps signal params (the cost specs aren't edges).
"""

# account / execution / cost knobs shared across all strategies
UNIVERSAL_PARAMS = ("capital", "sizing", "size_contracts", "risk_pct", "max_contracts",
                    "commission_per_side", "slippage_ticks", "point_value", "tick", "tick_value")

UNIVERSAL_LABEL = "Account & execution"


def split_params(default):
    """Split a strategy DEFAULT into (signal_params, universal_params), preserving order."""
    signal = {k: v for k, v in default.items() if k not in UNIVERSAL_PARAMS}
    universal = {k: v for k, v in default.items() if k in UNIVERSAL_PARAMS}
    return signal, universal
