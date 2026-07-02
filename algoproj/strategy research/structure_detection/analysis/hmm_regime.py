"""
HMM regime detection (Hamilton-style) — the proper version of the convergence work, done HONESTLY.

Fit a Gaussian HMM on daily NQ [return, realized-vol]; states = hidden regimes with their own
mean/vol + a transition matrix (persistence). Discipline against the #1 finance-HMM trap (look-ahead):
  • fit the model on the FIRST HALF only (train),
  • decode regimes with a FILTERED forward pass (P(state_t | obs up to t) — causal, no future),
  • report the OOS edge on the SECOND HALF only.
Checks: (1) does it find persistent vol regimes (transition diagonal)? (2) does the regime predict
FORWARD VOL (the clustering payoff) and/or FORWARD RETURN (direction — expected weak)?

Run (from algoproj/ root):
  python "strategy research/structure_detection/analysis/hmm_regime.py"
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import multivariate_normal
from scipy.special import logsumexp
from hmmlearn.hmm import GaussianHMM

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from algokit.data import load_tf

BG, TXT = "#080b11", "#9aa7b4"
K = 3
COLORS = ["#26c281", "#9aa7b4", "#ef5350"]   # calm / normal / turbulent (assigned by vol rank)


def filtered_posterior(X, model):
    """Causal filtered P(state_t | obs_1..t) — forward pass only, no look-ahead."""
    T = len(X)
    ll = np.column_stack([multivariate_normal(model.means_[k], model.covars_[k], allow_singular=True).logpdf(X)
                          for k in range(model.n_components)])
    logtrans = np.log(model.transmat_ + 1e-12)
    la = np.full((T, model.n_components), -np.inf)
    la[0] = np.log(model.startprob_ + 1e-12) + ll[0]
    for t in range(1, T):
        la[t] = ll[t] + logsumexp(la[t - 1][:, None] + logtrans, axis=0)
    return np.exp(la - logsumexp(la, axis=1, keepdims=True))


def main():
    df = load_tf("1d").dropna()
    close = df["close"]
    ret = np.log(close).diff()
    vol = ret.rolling(10).std()
    feat = pd.DataFrame({"ret": ret, "vol": vol}).dropna()
    idx = feat.index
    px = close.reindex(idx).to_numpy()

    split = len(feat) // 2
    mu, sd = feat.iloc[:split].mean(), feat.iloc[:split].std()   # standardize on TRAIN only
    X = ((feat - mu) / sd).to_numpy()

    model = GaussianHMM(n_components=K, covariance_type="full", n_iter=300, random_state=1)
    model.fit(X[:split])                                          # fit on TRAIN only

    order = np.argsort(model.means_[:, 1])                        # sort states by vol: calm..turbulent
    lab = {int(s): r for r, s in enumerate(order)}               # raw state -> rank(0 calm..2 turb)

    post = filtered_posterior(X, model)                          # causal, full series
    reg = np.array([lab[s] for s in post.argmax(1)])             # ranked regime per day (filtered)

    # ── report ──
    print("=== HMM regimes (fit on train half, filtered/causal decode) ===")
    diag = np.diag(model.transmat_)
    for rank, s in enumerate(order):
        name = ["CALM", "NORMAL", "TURBULENT"][rank]
        m = mu.to_numpy() + sd.to_numpy() * model.means_[s]      # de-standardize
        dur = 1 / (1 - diag[s] + 1e-9)
        print(f"  {name:<10} daily ret {m[0]*100:+.3f}%  vol {m[1]*100:.2f}%  "
              f"persistence {diag[s]:.2f} (~{dur:.0f}-day stays)")

    test = np.arange(split, len(idx))                            # OOS second half
    print(f"\n=== OOS edge (second half, filtered regime) — does the regime predict? ===")
    print(f"{'regime':<10}{'days':>7}{'fwd20 vol':>12}{'fwd20 ret':>12}{'fwd20 win':>11}")
    fwd = pd.Series(px, index=idx).pct_change(20).shift(-20).to_numpy() * 100
    fvol = pd.Series(ret.reindex(idx).to_numpy()).rolling(20).std().shift(-20).to_numpy() * 100
    for rank in range(K):
        m = (reg == rank) & np.isin(np.arange(len(idx)), test)
        r, v = fwd[m], fvol[m]
        r, v = r[~np.isnan(r)], v[~np.isnan(v)]
        if len(r):
            print(f"{['CALM','NORMAL','TURBULENT'][rank]:<10}{int(m.sum()):>7}{np.nanmean(v):>11.2f}%"
                  f"{np.nanmean(r):>+11.2f}%{(r>0).mean()*100:>10.0f}%")

    # ── plot: price colored by filtered regime + regime-probability band ──
    fig, (axp, axr) = plt.subplots(2, 1, figsize=(22, 10), facecolor=BG, sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05})
    for ax in (axp, axr):
        ax.set_facecolor(BG); ax.tick_params(colors=TXT, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1c2733")
    axp.plot(idx, px, color="#3a4652", lw=0.6, zorder=1)
    for rank in range(K):
        m = reg == rank
        axp.scatter(idx[m], px[m], s=3, c=COLORS[rank], zorder=2,
                    label=["calm", "normal", "turbulent"][rank])
    axp.axvline(idx[split], color="#e0b83a", lw=1, ls="--")
    axp.text(idx[split], axp.get_ylim()[1], " train | test (OOS) →", color="#e0b83a", fontsize=9, va="top")
    axp.set_yscale("log"); axp.set_ylabel("NQ (log)", color=TXT, fontsize=8)
    axp.legend(loc="upper left", facecolor=BG, edgecolor="#1c2733", labelcolor=TXT, fontsize=9)
    axp.set_title("NQ | HMM regime detection (Gaussian, daily) | fit on train, filtered/causal decode | "
                  "colour = regime", color="#e6edf3", fontsize=12)
    axr.stackplot(idx, *[post[:, s] for s in order], colors=COLORS)
    axr.set_ylim(0, 1); axr.set_ylabel("regime prob", color=TXT, fontsize=8)

    out = os.path.join(os.path.dirname(__file__), "output", "hmm_regime.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=140, facecolor=BG)
    print("\nsaved", os.path.relpath(out, os.path.dirname(os.path.dirname(__file__))))


if __name__ == "__main__":
    main()
