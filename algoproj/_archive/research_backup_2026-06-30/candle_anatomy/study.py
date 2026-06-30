"""Candle-anatomy conditional forward-return study (NY cash session).

Question: does the *shape* of one candle leak the next few candles' returns?

Method (measurement, not trading):
  1. Turn the chosen timeframe into scale-free geometry (algokit.candles.anatomy).
  2. Restrict to the NY cash session (09:30-16:00 ET) - where the movement is.
  3. For several forward horizons, compute the forward return, keeping the whole
     window INSIDE the same session day (no overnight-gap contamination).
  4. Bucket each geometric feature into deciles and compare each bucket's forward
     return / hit-rate to the in-session baseline. The "edge" is the lift over
     baseline, reported next to the sample size so we don't fool ourselves.

Outputs (research/candle_anatomy/output/):
  map.csv               every feature x decile x horizon: mean/median/hit/N/lift
  summary.json          baseline + the strongest cells
  01_movement_by_hour.png    avg range by NY hour (validates the session)
  02_anatomy_map.png         fwd-return lift by decile, one panel per feature
  03_edge_heatmap.png        feature x horizon: how much the shape separates outcomes

Run:
  cd algoproj
  & <venv>/python.exe research/candle_anatomy/study.py
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
from algokit import candles

# ------------------------------- config -------------------------------
TF = "15m"                       # day-trading timeframe
SESSION = ("09:30", "16:00")     # NY cash session
HORIZONS = [1, 2, 4, 8]          # forward bars (15m -> 15m / 30m / 1h / 2h)
N_DECILES = 10
OUT = os.path.join(os.path.dirname(__file__), "output")
BP = 1e4                         # report returns in basis points (1% = 100 bps)


def forward_returns(close, ny_date, in_session, horizon):
    """N-bar forward return, valid only when entry+exit are the SAME session day.

    Returns (fwd_bps, valid_mask). fwd[i] = close[i+N]/close[i]-1, in bps.
    """
    c = np.asarray(close, float)
    n = len(c)
    fwd = np.full(n, np.nan)
    fwd[: n - horizon] = (c[horizon:] / c[: n - horizon] - 1) * BP
    same_day = np.zeros(n, bool)
    same_day[: n - horizon] = ny_date[horizon:] == ny_date[: n - horizon]
    exit_in = np.zeros(n, bool)
    exit_in[: n - horizon] = in_session[horizon:]
    valid = in_session & same_day & exit_in & ~np.isnan(fwd)
    return fwd, valid


def decile_table(feat, fwd, valid, base_mean, base_hit):
    """Per-decile mean/median/hit/N and lift-over-baseline for one feature+horizon."""
    f = feat[valid]; r = fwd[valid]
    if len(f) < N_DECILES * 20:
        return None
    # rank-based deciles guarantee equal-sized buckets even with tied feature values
    buckets = pd.qcut(pd.Series(f).rank(method="first"), N_DECILES, labels=False)
    rows = []
    for d in range(N_DECILES):
        rr = r[buckets.to_numpy() == d]
        if len(rr) == 0:
            continue
        rows.append(dict(decile=d + 1, n=int(len(rr)),
                         feat_lo=float(np.min(f[buckets.to_numpy() == d])),
                         feat_hi=float(np.max(f[buckets.to_numpy() == d])),
                         mean_bps=float(np.mean(rr)), median_bps=float(np.median(rr)),
                         hit=float(np.mean(rr > 0)),
                         lift_bps=float(np.mean(rr) - base_mean),
                         hit_lift=float(np.mean(rr > 0) - base_hit)))
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load_tf(TF)
    print(f"loaded {TF}: {len(df):,} bars  {df.index[0].date()} -> {df.index[-1].date()}")

    anat = candles.anatomy(df)
    in_sess = candles.session_mask(df.index, *SESSION)
    ny_date = candles.ny_day(df.index)
    close = df["close"].to_numpy(float)
    print(f"in-session bars: {in_sess.sum():,} ({in_sess.mean()*100:.0f}% of all bars)")

    # ---- build the map: feature x decile x horizon ----
    all_rows = []
    baselines = {}
    for H in HORIZONS:
        fwd, valid = forward_returns(close, ny_date, in_sess, H)
        base_mean = float(np.mean(fwd[valid])); base_hit = float(np.mean(fwd[valid] > 0))
        baselines[H] = dict(mean_bps=base_mean, hit=base_hit, n=int(valid.sum()))
        for feat in candles.FEATURES:
            tbl = decile_table(anat[feat].to_numpy(float), fwd, valid, base_mean, base_hit)
            if tbl is None:
                continue
            tbl.insert(0, "feature", feat); tbl.insert(1, "horizon", H)
            all_rows.append(tbl)
    mp = pd.concat(all_rows, ignore_index=True)
    mp.to_csv(os.path.join(OUT, "map.csv"), index=False)

    # ---- console: baselines + strongest cells ----
    print("\n=== baseline (in-session, same-day forward) ===")
    for H, b in baselines.items():
        print(f"  {H:>2}-bar: mean {b['mean_bps']:+.2f} bps  hit {b['hit']*100:.1f}%  N={b['n']:,}")
    print("\n=== strongest decile edges (|lift| over baseline, bps) ===")
    top = mp.reindex(mp["lift_bps"].abs().sort_values(ascending=False).index).head(12)
    for _, r in top.iterrows():
        print(f"  {r.feature:<11} H={int(r.horizon)}  decile {int(r.decile):>2}/10 "
              f"[{r.feat_lo:+.4f}..{r.feat_hi:+.4f}]  "
              f"fwd {r.mean_bps:+.2f} bps (lift {r.lift_bps:+.2f})  "
              f"hit {r.hit*100:.1f}% ({r.hit_lift*100:+.1f})  N={int(r.n):,}")

    # ---- summary.json ----
    summary = dict(tf=TF, session=SESSION, horizons=HORIZONS, baselines=baselines,
                   top_edges=json.loads(top.to_json(orient="records")))
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    make_plots(df, mp, baselines)
    print(f"\nwrote map.csv, summary.json + 3 PNGs to {OUT}")


# ------------------------------- plots -------------------------------
def make_plots(df, mp, baselines):
    plt.style.use("dark_background")
    accent = "#3fb6ff"

    # 01 movement by NY hour (validates session)
    et = candles.to_ny(df.index)
    rng_bps = (df["high"] - df["low"]) / df["open"] * BP
    by_hour = pd.Series(rng_bps.to_numpy(), index=et.hour).groupby(level=0).mean()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    colors = [accent if 9 <= h < 16 else "#39424d" for h in by_hour.index]
    ax.bar(by_hour.index, by_hour.values, color=colors)
    ax.set_title("NQ 15m avg bar range by New York hour  (cash session highlighted)")
    ax.set_xlabel("NY hour"); ax.set_ylabel("avg range (bps)")
    ax.set_xticks(range(24))
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "01_movement_by_hour.png"), dpi=120); plt.close(fig)

    # 02 anatomy map: fwd-return lift by decile, one panel per feature
    feats = candles.FEATURES
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True)
    cmap = plt.get_cmap("viridis")
    for ax, feat in zip(axes.ravel(), feats):
        sub = mp[mp.feature == feat]
        for i, H in enumerate(sorted(sub.horizon.unique())):
            s = sub[sub.horizon == H].sort_values("decile")
            ax.plot(s.decile, s.lift_bps, marker="o", ms=3,
                    color=cmap(i / max(1, len(HORIZONS) - 1)), label=f"{H}-bar")
        ax.axhline(0, color="#888", lw=0.8)
        ax.set_title(feat); ax.set_xlabel("decile (1=low .. 10=high)")
        ax.set_ylabel("fwd-return lift (bps)")
    axes.ravel()[0].legend(fontsize=8, loc="best")
    fig.suptitle(f"Candle anatomy -> forward return, lift over baseline  ({TF}, NY session)", y=1.0)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "02_anatomy_map.png"), dpi=120); plt.close(fig)

    # 03 edge heatmap: feature x horizon, max |decile lift| (how much shape separates outcomes)
    heat = (mp.assign(absl=mp.lift_bps.abs())
              .groupby(["feature", "horizon"])["absl"].max()
              .unstack("horizon").reindex(feats))
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(heat.values, cmap="magma", aspect="auto")
    ax.set_xticks(range(len(heat.columns))); ax.set_xticklabels([f"{h}-bar" for h in heat.columns])
    ax.set_yticks(range(len(heat.index))); ax.set_yticklabels(heat.index)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.values[i, j]:.1f}", ha="center", va="center",
                    color="#fff", fontsize=9)
    ax.set_title("Max |forward-return lift| (bps) by feature x horizon")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "03_edge_heatmap.png"), dpi=120); plt.close(fig)


if __name__ == "__main__":
    main()
