"""
CAPSTONE TEST (pre-registered) — does the HMM vol-regime change the flag breakout's expectancy, OOS?

Guardrails (locked before looking):
  • metric   = expectancy in R per trade, NET of 0.75-pt round-turn cost (win% reported, not decided on)
  • buckets  = flag breakouts (long+short pooled) x causal HMM regime {calm,normal,turbulent} + flag-alone baseline
  • split    = HMM fit on daily FIRST HALF; flag tested on SECOND HALF only (OOS); sub-period = OOS split in two
  • labels   = each breakout gets YESTERDAY's filtered HMM regime (last completed daily bar, no look-ahead)
  • min n    = 80/bucket to read; RR = 2 fixed (no re-optimising); kill unless a bucket clears +0.05R,
               monotonic/sensible, holds in BOTH sub-periods, not marginal under multiple looks.

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/flag_by_regime.py"
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import multivariate_normal
from scipy.special import logsumexp
from hmmlearn.hmm import GaussianHMM

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

COST_PTS = 0.75          # NQ points round-turn
RR = 2.0
MAXHOLD = 500            # 5m bars
MIN_N = 80


def filtered_posterior(X, model):
    T = len(X)
    ll = np.column_stack([multivariate_normal(model.means_[k], model.covars_[k], allow_singular=True).logpdf(X)
                          for k in range(model.n_components)])
    logtrans = np.log(model.transmat_ + 1e-12)
    la = np.full((T, model.n_components), -np.inf)
    la[0] = np.log(model.startprob_ + 1e-12) + ll[0]
    for t in range(1, T):
        la[t] = ll[t] + logsumexp(la[t - 1][:, None] + logtrans, axis=0)
    return np.exp(la - logsumexp(la, axis=1, keepdims=True))


# ── daily HMM regime (fit train half, causal filtered, label by vol, shift 1 day = yesterday) ──
d1 = load_tf("1d").dropna()
ret = np.log(d1["close"]).diff()
feat = pd.DataFrame({"ret": ret, "vol": ret.rolling(10).std()}).dropna()
split = len(feat) // 2
split_date = feat.index[split]
mu, sd = feat.iloc[:split].mean(), feat.iloc[:split].std()
X = ((feat - mu) / sd).to_numpy()
hmm = GaussianHMM(n_components=3, covariance_type="full", n_iter=300, random_state=1).fit(X[:split])
rank = {int(s): r for r, s in enumerate(np.argsort(hmm.means_[:, 1]))}      # 0 calm..2 turbulent
reg_day = pd.Series([rank[s] for s in filtered_posterior(X, hmm).argmax(1)], index=feat.index).shift(1)  # yesterday

# ── flag breakouts + 5m R:R sim ──
fj = json.load(open("strategy research/flag_pattern/findings/dynamic_pole_5m.json"))
df5 = load_tf("5m")[["open", "high", "low", "close"]].dropna()
V = df5.values
ts = df5.index.values.astype("datetime64[s]").astype("int64")
H, L = 1, 2
NAMES = {0: "CALM", 1: "NORMAL", 2: "TURBULENT"}


def simulate(brk, is_long, entry, stop):
    risk = abs(entry - stop)
    target = entry + RR * risk if is_long else entry - RR * risk
    n = len(V)
    for j in range(brk + 1, min(n, brk + 1 + MAXHOLD)):
        hi, lo = V[j, H], V[j, L]
        if is_long:
            if lo <= stop: return -1.0
            if hi >= target: return RR
        else:
            if hi >= stop: return -1.0
            if lo <= target: return RR
    j = min(n - 1, brk + MAXHOLD)
    return ((V[j, 3] - entry) if is_long else (entry - V[j, 3])) / risk


trades = []   # (date, regime, R_net)
for m in fj["matches"]:
    if not m.get("vwap"):
        continue
    _, _c, up, dn = m["vwap"][-1]
    if up <= dn:
        continue
    is_long = m["side"] == "long"
    entry, stop = (up, dn) if is_long else (dn, up)
    brk = int(np.searchsorted(ts, m["entry"]))
    if brk >= len(V) - 1 or ts[brk] != m["entry"]:
        continue
    when = pd.Timestamp(m["entry"], unit="s")
    if when < split_date:                                 # OOS only
        continue
    rg = reg_day.asof(when)                                # causal: yesterday's regime
    if pd.isna(rg):
        continue
    r_gross = simulate(brk, is_long, entry, stop)
    r_net = r_gross - COST_PTS / abs(entry - stop)
    trades.append((when, int(rg), r_net))

T = pd.DataFrame(trades, columns=["date", "regime", "R"])
oos_mid = T["date"].min() + (T["date"].max() - T["date"].min()) / 2


def line(name, s):
    if len(s) < MIN_N:
        return f"  {name:<24}{len(s):>6}   (< {MIN_N}: underpowered, inconclusive)"
    return f"  {name:<24}{len(s):>6}{s.mean():>+10.3f}R{(s > 0).mean() * 100:>8.0f}%"


print(f"pre-registered | cost {COST_PTS}pt round-turn | RR {RR} | OOS after {split_date.date()} | "
      f"causal (yesterday's) regime\n")
print(f"OOS flag breakouts: {len(T)}   (baseline pooled + 3 regime buckets)")
print(f"{'bucket':<24}{'n':>6}{'net exp':>11}{'win':>9}")
print(line("FLAG baseline (all OOS)", T["R"]))
for rg in (0, 1, 2):
    print(line(NAMES[rg], T[T["regime"] == rg]["R"]))
print("\nsub-period check (does any regime effect hold in BOTH halves of OOS?)")
for tag, sub in [("OOS 1st half", T[T["date"] < oos_mid]), ("OOS 2nd half", T[T["date"] >= oos_mid])]:
    print(f" [{tag}]  baseline n={len(sub)} exp={sub['R'].mean():+.3f}R")
    for rg in (0, 1, 2):
        s = sub[sub["regime"] == rg]["R"]
        flag = "" if len(s) >= MIN_N else "  (underpowered)"
        print(f"    {NAMES[rg]:<12} n={len(s):>4} exp={s.mean():+.3f}R{flag}")
