"""Candle-anatomy ROUND TWO — triple-barrier outcome + context + combinations.

Round one (study.py) used fixed N-bar mean return and found single-candle geometry
~= noise. That outcome washes out structure (a stab-down-then-recover nets zero).
This study fixes all four weaknesses we identified:

  #4 outcome    triple barrier: from each close, did price hit +k*ATR (up) BEFORE
                -k*ATR (down), within the same session day? -> a clean directional
                probability P(up first), symmetric, the way a real day trade resolves.
  #2 context    every bar tagged by time-of-day bucket and trend regime (vs SMA).
  #3 structure  multi-candle sequence features (mom2/accel/run_len/coil/gap/inside).
  #1 combos     2-D grids (feature x feature, feature x time-of-day) to see interaction.

Everything is measured as LIFT over the in-session baseline P(up first), with the
sample size next to it. Still measurement, not trading.

Outputs (research/candle_anatomy/output/):
  barrier_map.csv        feature x decile: P(up first), N, lift
  barrier_summary.json   baseline, by-time-of-day, by-regime, top edges
  04_baseline_by_tod.png P(up first) by time-of-day bucket (where the asymmetry is)
  05_feature_edges.png   P(up first) lift by decile, single + multi-candle features
  06_combo_heatmap.png   top-2 features crossed -> P(up first) (the interaction)
  07_trend_split.png     best feature's edge in up-trend vs down-trend regime

Run:  cd algoproj && <venv>/python.exe research/candle_anatomy/study_barrier.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # reach algoproj/

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from algokit.data import load_tf
from algokit.indicators import atr as atr_ind
from algokit import candles

# ------------------------------- config -------------------------------
TF = "15m"
SESSION = ("09:30", "16:00")
ATR_N = 14
K = 1.0                # barrier = +/- K * ATR
MAX_BARS = 24          # give a trade up to 24 bars (6h) to resolve, capped at session close
SMA_N = 50             # trend-regime moving average (15m bars)
OUT = os.path.join(os.path.dirname(__file__), "output")
# single-candle + multi-candle features studied by decile
FEATURES = list(candles.FEATURES) + list(candles.SEQ_FEATURES)


def barrier_labels(high, low, close, atr, in_sess, ny_date, k=K, max_bars=MAX_BARS):
    """Triple-barrier label per bar: +1 up-first, -1 down-first, 0 unresolved.

    Walks forward from each in-session bar's close until a barrier is touched, the
    session day ends, or max_bars elapse. A bar that straddles BOTH barriers is
    ambiguous (OHLC can't tell order) -> left unresolved.
    """
    n = len(close)
    lab = np.zeros(n, np.int8)
    resolved = np.zeros(n, bool)
    cand = np.where(in_sess & ~np.isnan(atr) & (atr > 0))[0]
    for i in cand:
        up = close[i] + k * atr[i]; dn = close[i] - k * atr[i]
        end = min(n, i + max_bars + 1)
        for j in range(i + 1, end):
            if ny_date[j] != ny_date[i]:
                break
            hit_up = high[j] >= up; hit_dn = low[j] <= dn
            if hit_up and hit_dn:
                break          # ambiguous bar -> unresolved
            if hit_up:
                lab[i] = 1; resolved[i] = True; break
            if hit_dn:
                lab[i] = -1; resolved[i] = True; break
    return lab, resolved


def decile_edge(feat, up, resolved, base_p, min_n=200):
    """P(up first) per feature decile, among RESOLVED bars, with lift over baseline."""
    m = resolved & ~np.isnan(feat)
    f = feat[m]; u = up[m]
    if len(f) < N_DECILES * min_n:
        return None
    d = pd.qcut(pd.Series(f).rank(method="first"), N_DECILES, labels=False).to_numpy()
    rows = []
    for k in range(N_DECILES):
        sel = d == k
        if sel.sum() == 0:
            continue
        p = float(u[sel].mean())
        rows.append(dict(decile=k + 1, n=int(sel.sum()),
                         feat_lo=float(f[sel].min()), feat_hi=float(f[sel].max()),
                         p_up=p, lift=p - base_p))
    return pd.DataFrame(rows)


N_DECILES = 10


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load_tf(TF)
    anat = candles.anatomy(df)
    seq = candles.sequence(df)
    feats = pd.concat([anat, seq], axis=1)

    high = df["high"].to_numpy(float); low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    atr = atr_ind(df["high"], df["low"], df["close"], ATR_N).to_numpy()
    in_sess = candles.session_mask(df.index, *SESSION)
    ny_date = candles.ny_day(df.index)
    tod = candles.tod_bucket(df.index)
    sma = df["close"].rolling(SMA_N).mean().to_numpy()
    uptrend = close > sma

    print(f"loaded {TF}: {len(df):,} bars  | labelling triple barrier (k={K} ATR, <= {MAX_BARS} bars)...")
    lab, resolved = barrier_labels(high, low, close, atr, in_sess, ny_date)
    up = lab == 1
    res_in = resolved & in_sess
    base_p = float(up[res_in].mean())
    print(f"in-session resolved: {res_in.sum():,} / {in_sess.sum():,} "
          f"({res_in.sum()/in_sess.sum()*100:.0f}% hit a barrier same day)")
    print(f"\nBASELINE P(up first) = {base_p*100:.2f}%   (50% = no directional edge)\n")

    # ---- context: by time-of-day ----
    tod_rows = {}
    print("=== P(up first) by time-of-day (context #2) ===")
    for b in candles.TOD_ORDER:
        sel = res_in & (tod == b)
        if sel.sum() == 0:
            continue
        p = float(up[sel].mean())
        tod_rows[b] = dict(p_up=p, lift=p - base_p, n=int(sel.sum()))
        print(f"  {b:<10} P(up) {p*100:5.2f}%  lift {(p-base_p)*100:+5.2f}  N={sel.sum():,}")

    # ---- context: by trend regime ----
    print("\n=== P(up first) by trend regime (context #2) ===")
    regime_rows = {}
    for name, sel in (("uptrend", res_in & uptrend), ("downtrend", res_in & ~uptrend)):
        p = float(up[sel].mean())
        regime_rows[name] = dict(p_up=p, lift=p - base_p, n=int(sel.sum()))
        print(f"  {name:<10} P(up) {p*100:5.2f}%  lift {(p-base_p)*100:+5.2f}  N={sel.sum():,}")

    # ---- single + multi-candle feature deciles ----
    all_rows = []
    for f in FEATURES:
        tbl = decile_edge(feats[f].to_numpy(float), up, res_in, base_p)
        if tbl is None:
            continue
        tbl.insert(0, "feature", f)
        all_rows.append(tbl)
    mp = pd.concat(all_rows, ignore_index=True)
    mp.to_csv(os.path.join(OUT, "barrier_map.csv"), index=False)

    print("\n=== strongest single-feature decile edges (lift in P(up first), pts) ===")
    top = mp.reindex(mp["lift"].abs().sort_values(ascending=False).index).head(12)
    for _, r in top.iterrows():
        print(f"  {r.feature:<13} decile {int(r.decile):>2}/10 "
              f"[{r.feat_lo:+.4f}..{r.feat_hi:+.4f}]  "
              f"P(up) {r.p_up*100:5.2f}%  lift {r.lift*100:+5.2f}  N={int(r.n):,}")

    # ---- combination: cross the two strongest features (combos #1) ----
    rank = (mp.groupby("feature")["lift"].apply(lambda s: s.abs().max())
              .sort_values(ascending=False))
    fa, fb = rank.index[0], rank.index[1]
    combo = combo_grid(feats[fa].to_numpy(float), feats[fb].to_numpy(float), up, res_in)
    print(f"\n=== combo (#1): {fa} x {fb} -> P(up first), 5x5 quintile grid ===")
    print((combo * 100).round(1).to_string())

    summary = dict(tf=TF, session=SESSION, k_atr=K, max_bars=MAX_BARS, sma_n=SMA_N,
                   baseline_p_up=base_p, by_tod=tod_rows, by_regime=regime_rows,
                   top_features=list(rank.index[:5]),
                   top_edges=json.loads(top.to_json(orient="records")))
    with open(os.path.join(OUT, "barrier_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    make_plots(mp, tod_rows, base_p, combo, fa, fb,
               feats, up, res_in, uptrend, rank.index[0])
    print(f"\nwrote barrier_map.csv, barrier_summary.json + 4 PNGs to {OUT}")


def combo_grid(fa, fb, up, mask, q=5):
    """5x5 quintile grid of P(up first) for two features (rows=fa, cols=fb)."""
    m = mask & ~np.isnan(fa) & ~np.isnan(fb)
    da = pd.qcut(pd.Series(fa[m]).rank(method="first"), q, labels=False).to_numpy()
    db = pd.qcut(pd.Series(fb[m]).rank(method="first"), q, labels=False).to_numpy()
    u = up[m]
    grid = np.full((q, q), np.nan)
    for i in range(q):
        for j in range(q):
            sel = (da == i) & (db == j)
            if sel.sum() > 50:
                grid[i, j] = u[sel].mean()
    return pd.DataFrame(grid, index=[f"q{i+1}" for i in range(q)],
                        columns=[f"q{j+1}" for j in range(q)])


# ------------------------------- plots -------------------------------
def make_plots(mp, tod_rows, base_p, combo, fa, fb, feats, up, res_in, uptrend, best_feat):
    plt.style.use("dark_background")

    # 04 baseline by time-of-day
    fig, ax = plt.subplots(figsize=(9, 4.5))
    names = list(tod_rows); vals = [tod_rows[n]["p_up"] * 100 for n in names]
    cols = ["#3fb6ff" if v >= base_p * 100 else "#ff5d6c" for v in vals]
    ax.bar(names, vals, color=cols)
    ax.axhline(base_p * 100, color="#ffd166", ls="--", label=f"baseline {base_p*100:.1f}%")
    for i, n in enumerate(names):
        ax.text(i, vals[i] + 0.1, f"{vals[i]:.1f}%\nN={tod_rows[n]['n']:,}", ha="center", fontsize=8)
    ax.set_title("P(up first) by time-of-day  (triple barrier, NY session)")
    ax.set_ylabel("P(up first) %"); ax.legend(); ax.set_ylim(min(vals) - 1, max(vals) + 1.2)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "04_baseline_by_tod.png"), dpi=120); plt.close(fig)

    # 05 feature edges (single + multi-candle), lift by decile
    fl = sorted(mp.feature.unique())
    ncol = 4; nrow = int(np.ceil(len(fl) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3 * nrow), sharey=True)
    for ax, f in zip(axes.ravel(), fl):
        s = mp[mp.feature == f].sort_values("decile")
        ax.plot(s.decile, s.lift * 100, marker="o", ms=3, color="#3fb6ff")
        ax.axhline(0, color="#888", lw=0.8)
        ax.set_title(f, fontsize=10); ax.set_xlabel("decile")
    for ax in axes.ravel()[len(fl):]:
        ax.axis("off")
    axes.ravel()[0].set_ylabel("P(up first) lift (pts)")
    fig.suptitle("Candle structure -> P(up first), lift over baseline  (single + multi-candle)", y=1.0)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "05_feature_edges.png"), dpi=120); plt.close(fig)

    # 06 combo heatmap
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(combo.values * 100, cmap="RdYlGn", aspect="auto",
                   vmin=base_p * 100 - 6, vmax=base_p * 100 + 6)
    ax.set_xticks(range(combo.shape[1])); ax.set_xticklabels(combo.columns)
    ax.set_yticks(range(combo.shape[0])); ax.set_yticklabels(combo.index)
    ax.set_xlabel(f"{fb}  (low q1 -> high q5)"); ax.set_ylabel(f"{fa}  (low q1 -> high q5)")
    for i in range(combo.shape[0]):
        for j in range(combo.shape[1]):
            v = combo.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v*100:.1f}", ha="center", va="center", fontsize=9, color="#111")
    ax.set_title(f"P(up first) %:  {fa} x {fb}  (baseline {base_p*100:.1f}%)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "06_combo_heatmap.png"), dpi=120); plt.close(fig)

    # 07 trend split for the single strongest feature
    f = feats[best_feat].to_numpy(float)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, sel, col in (("uptrend", res_in & uptrend, "#3fb6ff"),
                           ("downtrend", res_in & ~uptrend, "#ff5d6c")):
        m = sel & ~np.isnan(f)
        ff = f[m]; uu = up[m]
        bp = float(uu.mean())
        d = pd.qcut(pd.Series(ff).rank(method="first"), N_DECILES, labels=False).to_numpy()
        ys = [(uu[d == k].mean() - bp) * 100 for k in range(N_DECILES)]
        ax.plot(range(1, N_DECILES + 1), ys, marker="o", ms=4, color=col,
                label=f"{name} (base {bp*100:.1f}%)")
    ax.axhline(0, color="#888", lw=0.8)
    ax.set_title(f"'{best_feat}' edge by decile, split by trend regime")
    ax.set_xlabel("decile (1=low .. 10=high)"); ax.set_ylabel("P(up first) lift vs own baseline (pts)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "07_trend_split.png"), dpi=120); plt.close(fig)


if __name__ == "__main__":
    main()
