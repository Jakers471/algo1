"""
Statistical significance — is the edge REAL, or did we find it by looking?

Three independent questions, three tools (no scipy dependency; normal CDF/inverse
implemented locally):

  trade_tstat(trades)
      Are the per-trade returns distinguishable from zero? t-stat + p-value.
      Rule of thumb: |t| < ~2 means you cannot reject "no edge".

  random_entry_test(close, trades, start, n_sims)
      Does the ENTRY TIMING add anything over random long exposure with the same
      footprint (same number of trades, same holding-length distribution)? Returns
      a p-value = P(random does as well as the strategy). Big p => the signal is
      no better than throwing darts.

  deflated_sharpe(sr, n_trials, n_obs, ...)
      MULTIPLE TESTING. If you tried N configs and kept the best, the best Sharpe
      is inflated. This haircuts it: the probability the Sharpe is truly > 0 after
      accounting for N trials. THE most important number once you start sweeping.

Feed n_trials from the run registry (runs.trial_count) so the haircut reflects
how many configs you have actually tried.
"""
import math

import numpy as np

_SQRT2 = math.sqrt(2.0)
_EULER = 0.5772156649015329


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_ppf(p):
    """Inverse normal CDF (Acklam's rational approximation; good to ~1e-9)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _trade_rets(trades):
    return np.array([t["ret"] for t in trades], float)


def trade_tstat(trades):
    """t-stat & two-sided p-value that mean per-trade return != 0."""
    r = _trade_rets(trades)
    n = len(r)
    if n < 2 or r.std(ddof=1) == 0:
        return {"n": n, "mean": float(r.mean()) if n else 0.0, "t": 0.0, "p": 1.0}
    t = r.mean() / (r.std(ddof=1) / math.sqrt(n))
    p = 2 * (1 - _norm_cdf(abs(t)))            # normal approx (n is large here)
    return {"n": n, "mean": float(r.mean()), "t": float(t), "p": float(p)}


def random_entry_test(close, trades, start, n_sims=2000, seed=0):
    """P-value: can random entries with the same footprint match the strategy?

    Footprint preserved = same number of trades and same holding-length set, just
    placed at random (non-overlapping) start bars. Score = mean per-trade log
    return. p = fraction of random books with score >= the strategy's score.
    """
    close = np.asarray(close, float)
    holds = [t["exit_i"] - t["entry_i"] for t in trades if t["exit_i"] > t["entry_i"]]
    if not holds:
        return {"p": 1.0, "strategy_score": 0.0, "random_median": 0.0, "n_sims": 0}
    actual = np.mean([math.log(t["exit_px"] / t["entry_px"]) for t in trades])
    rng = np.random.default_rng(seed)
    n = len(close)
    scores = np.empty(n_sims)
    for s in range(n_sims):
        rets = []
        for h in holds:
            j = rng.integers(start, max(start + 1, n - h))
            rets.append(math.log(close[min(j + h, n - 1)] / close[j]))
        scores[s] = np.mean(rets)
    p = float(np.mean(scores >= actual))
    return {"p": p, "strategy_score": float(actual),
            "random_median": float(np.median(scores)), "n_sims": n_sims}


def probabilistic_sharpe_ratio(sr, n_obs, sr_benchmark=0.0, skew=0.0, kurt=3.0):
    """P(true Sharpe > sr_benchmark) given the observed Sharpe `sr` (per-obs units)."""
    if n_obs < 2:
        return 0.0
    num = (sr - sr_benchmark) * math.sqrt(n_obs - 1)
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4.0 * sr * sr)
    return _norm_cdf(num / den) if den > 0 else 0.0


def expected_max_sharpe(n_trials, sr_trials_std=1.0):
    """Expected MAX Sharpe from N independent trials of noise (per-obs units)."""
    if n_trials < 2:
        return 0.0
    e = (1 - _EULER) * _norm_ppf(1 - 1.0 / n_trials) + \
        _EULER * _norm_ppf(1 - 1.0 / (n_trials * math.e))
    return sr_trials_std * e


def deflated_sharpe(sr, n_trials, n_obs, sr_trials_std=1.0, skew=0.0, kurt=3.0):
    """Deflated Sharpe Ratio: P(true Sharpe > 0) after N-trial selection bias.

    sr, sr_trials_std are in PER-OBSERVATION units (annualized_sharpe / sqrt(ppy)).
    Returns a probability in [0,1]; > 0.95 is the usual "survives" threshold.
    """
    bench = expected_max_sharpe(n_trials, sr_trials_std)
    return probabilistic_sharpe_ratio(sr, n_obs, bench, skew, kurt)


def edge_report(res, ppy, n_trials=1, close=None, start=0):
    """One call -> the whole significance block for a backtest result dict.

    res      : dict from backtest.run_long_only (needs rets, trades).
    ppy      : bars per year (to express the Sharpe used for the haircut).
    n_trials : how many configs have been tried (feed runs.trial_count).
    close    : close prices; if given, also runs the random-entry permutation test.
    """
    rets = np.asarray(res["rets"], float)
    trades = res["trades"]
    nz = rets[rets != 0]
    n_obs = len(nz) or len(rets)
    sr_per_obs = (rets.mean() / rets.std()) if rets.std() > 0 else 0.0
    # Dispersion of per-observation Sharpe ACROSS trials. The DSR works in per-obs
    # units, so the old default of 1.0 was wildly off-scale (a per-obs Sharpe of 1.0
    # is astronomical) and forced deflated_sharpe -> 0 and the annualized expected-max
    # -> hundreds. Absent measured trial Sharpes, use the analytic standard error of a
    # per-obs Sharpe under the null, sqrt(1/n_obs) — the natural noise floor.
    sr_trials_std = math.sqrt(1.0 / n_obs) if n_obs > 0 else 1.0
    exp_max = expected_max_sharpe(max(1, n_trials), sr_trials_std)
    out = {
        "trade_t": trade_tstat(trades),
        "deflated_sharpe": deflated_sharpe(sr_per_obs, max(1, n_trials), n_obs,
                                           sr_trials_std=sr_trials_std),
        "n_trials": int(n_trials),
        "sharpe_ann": sr_per_obs * math.sqrt(ppy),
        "expected_max_sharpe_ann": exp_max * math.sqrt(ppy),
    }
    if close is not None:
        out["random_entry"] = random_entry_test(close, trades, start)
    return out
