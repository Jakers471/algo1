"""
Strategy #5 — MTF Fanning Regime.

The CONFIG dict below *is* the strategy — it's the single source of truth that the
backtest, the chart, the report and the run registry all read. `run(cfg)` executes
it via algokit and returns everything a run needs (config, build arrays, result, stats).
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from algokit.data import load_tf, align
from algokit.indicators import atr as atr_ind
from algokit.regime import regime_score
from algokit.backtest import run_long_only
from algokit.costs import FuturesCost
from algokit import metrics

NAME = "fanning_mtf"

DEFAULT = dict(
    symbol="NQ",
    htf_tf="1d", ltf_tf="15m",
    # --- SIGNAL params (the strategy itself; untouched) ---
    htf_fan=[5, 500, 0.15],   # [min MA, max MA, slope flat-band eps]
    ltf_fan=[5, 100, 0.03],
    n_ma=32, slope_L=5,
    X=70,           # enter when LTF bull score crosses up through this
    htf_gate=50,    # required HTF bull score (bias filter)
    coil_k=20,      # look-back bars for "was coiled"
    coil_level=40,  # consol score that counts as coiled
    exit_th=30,     # exit when LTF bull score drops below this
    atr_mult=5.0, atr_n=14,
    # --- EXECUTION / COST / SIZING params (pipeline, NOT signal) ---
    # Realistic NQ E-mini fills: see algokit/costs.py. These shape WHAT you'd
    # actually fill & pay, not WHEN the strategy trades.
    capital=100_000.0,      # starting account equity (USD)
    sizing="risk_pct",      # "fixed" or "risk_pct" (algokit/sizing.py)
    size_contracts=1,       # used when sizing == "fixed"
    risk_pct=0.01,          # used when sizing == "risk_pct" (1% of equity to stop)
    max_contracts=20,       # hard cap on position size
    commission_per_side=2.25,   # USD per contract per fill
    slippage_ticks=1,           # ticks of adverse slippage per fill
    point_value=20.0,           # USD per index point (NQ = 20)
    tick=0.25,                  # NQ tick size in points
    tick_value=5.0,             # USD per tick (NQ = 5)
)


def build(cfg):
    """Compute the regime, signals and arrays for a config (no trading yet)."""
    d1 = load_tf(cfg["htf_tf"]); ltf = load_tf(cfg["ltf_tf"])
    hlo, hhi, heps = cfg["htf_fan"]; llo, lhi, leps = cfg["ltf_fan"]
    b1d, _, _   = regime_score(d1,  hlo, hhi, n_ma=cfg["n_ma"], slope_L=cfg["slope_L"], eps=heps)
    b15, c15, _ = regime_score(ltf, llo, lhi, n_ma=cfg["n_ma"], slope_L=cfg["slope_L"], eps=leps)

    idx = ltf.index
    bull1d  = align(b1d, idx).to_numpy()
    bull15  = b15.to_numpy(); consol15 = c15.to_numpy()
    o = ltf["open"].to_numpy(); h = ltf["high"].to_numpy()
    l = ltf["low"].to_numpy();  c = ltf["close"].to_numpy()
    atr = atr_ind(ltf["high"], ltf["low"], ltf["close"], cfg["atr_n"]).to_numpy()
    coil = pd.Series(consol15).rolling(cfg["coil_k"]).max().to_numpy() >= cfg["coil_level"]
    start = max(600, int(np.argmax(~np.isnan(bull1d) & ~np.isnan(bull15) & ~np.isnan(atr)) + 1))

    X = cfg["X"]
    cross     = (bull15 >= X) & (np.r_[np.nan, bull15[:-1]] < X)
    entry_sig = cross & coil & (bull1d >= cfg["htf_gate"])
    exit_sig  = bull15 < cfg["exit_th"]
    return dict(idx=idx, o=o, h=h, l=l, c=c, atr=atr,
                bull15=bull15, consol15=consol15, bull1d=bull1d,
                entry_sig=entry_sig, exit_sig=exit_sig, start=start)


def _cost(cfg):
    """Build the realistic NQ execution/cost model from the config."""
    return FuturesCost(commission_per_side=cfg["commission_per_side"],
                       slippage_ticks=cfg["slippage_ticks"],
                       point_value=cfg["point_value"], tick=cfg["tick"],
                       tick_value=cfg["tick_value"])


def run(cfg=None, **overrides):
    """Run the strategy through the realistic dollar engine.

    Returns cfg, build arrays, result, stats, ppy, plus a buy-&-hold benchmark and
    a config-vs-benchmark comparison — the pipeline the registry/UI consume.
    """
    cfg = dict(DEFAULT if cfg is None else cfg)
    cfg.update(overrides)
    b = build(cfg)
    cost = _cost(cfg)
    res = run_long_only(b["o"], b["h"], b["l"], b["c"], b["entry_sig"], b["exit_sig"],
                        b["atr"], atr_mult=cfg["atr_mult"], cost=cost,
                        sizing=cfg["sizing"], capital=cfg["capital"],
                        start=b["start"], cfg=cfg)
    idx = b["idx"]; ppy = len(b["c"]) / ((idx[-1] - idx[0]).days / 365.25)
    stats = metrics.extended_summary(res["rets"], res["trades"], res["in_market"], ppy, b["start"])

    from algokit import benchmark as bm
    bench = bm.buy_and_hold(b["o"], b["c"], b["start"], cost=cost, capital=cfg["capital"])
    bench["metrics"]["cagr"] = metrics.cagr(bench["rets"], ppy)
    bench["metrics"]["sharpe"] = metrics.sharpe(bench["rets"], ppy, b["start"])
    stats.update(bm.compare(stats, bench["metrics"]))

    return dict(cfg=cfg, build=b, res=res, stats=stats, ppy=ppy, bench=bench)
