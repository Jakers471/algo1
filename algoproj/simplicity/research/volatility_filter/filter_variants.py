"""
filter_variants — a bank of volatility filters to A/B test ONE hypothesis:

    H: the strategy performs BETTER in high-volatility / high-activity periods.

`vol_filter.py` is the single chosen gate (high-vol days). To *confirm* that choice
isn't luck we need its opposites AND an unconditional baseline to compare against:

  * select(mode)   -> per-day frame with a `selected` flag for that variant
  * compare()      -> descriptive stats per variant (day count, vol, volume) -> output/
  * evaluate(outcomes) -> THE test. Given a future strategy's per-day result (R):
        - expectancy under each variant, AND
        - a RANDOM baseline: many random same-size day samples from the whole era
          -> a null distribution; report where each variant lands (percentile).
     H is real ONLY if `high` beats RANDOM (high percentile), not merely `low`.
     If `high` beats `low` but NOT random, the "edge" is just that low-vol days are
     unusually bad, not that high-vol is good.

Research only. The winner, once confirmed, is what strategy_config.TRADEABLE_REGIMES
locks and what gets promoted to engine/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vol_filter as vf

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# variants over the {low, medium, high} trailing-vol regimes
PRESETS = {
    "all":         {"low", "medium", "high"},   # baseline: no filter (trade everything)
    "high":        {"high"},                     # THE hypothesis (what vol_filter locks)
    "medium":      {"medium"},
    "low":         {"low"},                      # opposite of the hypothesis
    "high_medium": {"high", "medium"},           # avoid only the calmest third
    "not_high":    {"low", "medium"},            # the complement of high
    "extremes":    {"low", "high"},              # tails vs the middle
}


def select(mode):
    """Per-day frame with `selected` True where the day's regime is in PRESETS[mode]."""
    if mode not in PRESETS:
        raise KeyError(f"unknown filter '{mode}'. options: {list(PRESETS)}")
    d = vf.daily_frame().copy()
    d["selected"] = d["regime"].isin(PRESETS[mode])
    return d


def compare():
    """Descriptive: what each variant selects (no strategy needed yet). Saves output/."""
    import pandas as pd
    base = vf.daily_frame()
    total = len(base)
    rows = []
    for name, regs in PRESETS.items():
        s = base[base["regime"].isin(regs)]
        rows.append({"variant": name, "days": len(s), "pct_era": round(len(s) / total * 100, 1),
                     "mean_trail_vol": round(s["trail_vol"].mean(), 3),
                     "mean_avg_range": round(s["avg_range"].mean(), 3),
                     "mean_volume": int(s["volume"].mean())})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "filter_variants.csv"), index=False)
    print(f"volatility filter variants  (era >= {vf.cfg.ERA_START_YEAR}, "
          f"metric={vf.cfg.VOL_METRIC}, {total} days)\n")
    print(f"  {'variant':<12}{'days':>6}{'%era':>7}{'mean trail':>12}{'mean range':>12}{'mean volume':>14}")
    for r in rows:
        print(f"  {r['variant']:<12}{r['days']:>6}{r['pct_era']:>6.1f}%"
              f"{r['mean_trail_vol']:>11.3f}%{r['mean_avg_range']:>11.3f}%{r['mean_volume']:>14,}")
    print("\n  -> to CONFIRM the hypothesis, run evaluate(per-day R) [vs low AND vs random baseline]")
    return df


def random_baseline(outcomes, n, iters=2000, seed=0):
    """Null: mean R of `iters` random n-day samples drawn from ALL days with outcomes."""
    import numpy as np
    vals = outcomes.to_numpy()
    n = min(n, len(vals))
    rng = np.random.default_rng(seed)
    return np.array([rng.choice(vals, n, replace=False).mean() for _ in range(iters)])


def evaluate(outcomes, iters=2000):
    """THE hypothesis test. `outcomes`: Series/dict of date(YYYY-MM-DD) -> R.
    For each variant: expectancy + total, and its percentile vs a RANDOM same-size null.
    H holds iff `high` sits in the top tail (beats random), not just beats `low`.
    """
    import numpy as np, pandas as pd
    o = pd.Series(outcomes).dropna()
    base = vf.daily_frame().set_index("date")
    print(f"  {'variant':<12}{'trades':>7}{'exp(R)':>9}{'total(R)':>10}"
          f"{'rand exp':>10}{'vs-rand pct':>12}")
    out = []
    for name, regs in PRESETS.items():
        days = base.index[base["regime"].isin(regs)]
        r = o.reindex(o.index.intersection(days)).dropna()
        if len(r) < 10:
            continue
        null = random_baseline(o, len(r), iters)
        pct = float((null < r.mean()).mean() * 100)  # percentile of variant vs random
        out.append((name, len(r), round(r.mean(), 4), round(r.sum(), 1),
                    round(float(null.mean()), 4), round(pct, 1)))
        print(f"  {name:<12}{len(r):>7}{r.mean():>9.4f}{r.sum():>10.1f}"
              f"{null.mean():>10.4f}{pct:>11.1f}%")
    print("\n  read: 'vs-rand pct' = where the variant's expectancy sits in the random null.")
    print("        H is real if HIGH is ~>=95% (beats random) AND > LOW. If HIGH only beats")
    print("        LOW but not random, the signal is 'low-vol is bad', not 'high-vol is good'.")
    return out


if __name__ == "__main__":
    compare()
