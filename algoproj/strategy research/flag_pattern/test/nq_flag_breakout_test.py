"""
Does a pole+flag actually lead anywhere?  (continuation test)

Matches ONLY the pole+flag (signal_config.WINDOW bars), enters at the flag's last
bar -- BEFORE the breakout -- then measures the forward move. Sweeps the distance
threshold (tighter -> looser) so you see how the edge holds with sample size.
Uses the same templates / geometry / session filter as the live signal (imports
signal_config), so these numbers describe the actual signal.

Run:  python "strategy research/flag_pattern/test/nq_flag_breakout_test.py"  [--tf 5m] [--no-session]
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))  # algoproj/
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "signal")))    # signal_config
from algokit.data import load_tf
from algokit import patterns
import signal_config as cfg

COLS = ["open", "high", "low", "close"]
PCTS = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0]   # distance-threshold percentiles (tight -> loose)


def main(tf, use_session):
    df = load_tf(tf)[COLS].dropna()
    if cfg.HISTORY_START:
        df = df[df.index >= cfg.HISTORY_START]
    values = df.values
    close = df["close"].to_numpy(float)
    ts = df.index.values.astype("datetime64[s]").astype("int64")
    n = len(values)
    mask = cfg.session_mask(ts) if use_session else np.ones(n, bool)
    print(f"{cfg.describe() if use_session else cfg.describe().replace('ET', 'ET [off]')}")
    print(f"{tf}: {n:,} bars  {df.index[0].date()} -> {df.index[-1].date()}\n")

    base = {h: np.nanmean(close[h:] / close[:-h] - 1.0) for h in cfg.HORIZONS}
    print("baseline drift/horizon (%):  " + "  ".join(f"h{h}={base[h]*100:+.3f}" for h in cfg.HORIZONS) + "\n")

    for name, (direction, side, tmpl) in cfg.SETUP.items():
        scores = patterns.scan(values, tmpl, cfg.WINDOW)
        s_mask = mask[:len(scores)]
        print(f"=== {name} (entry at flag end, dir={'+up' if direction > 0 else '-down'}) ===")
        print(f"{'thresh':>8} {'score<':>8} {'n':>6} | " + " ".join(f"{'h'+str(h):>13}" for h in cfg.HORIZONS))
        print(f"{'':>8} {'':>8} {'':>6} | " + " ".join(f"{'edge%(win%)':>13}" for _ in cfg.HORIZONS))
        print("-" * (26 + 14 * len(cfg.HORIZONS)))
        for pct in PCTS:
            thr = np.percentile(scores, pct)
            sm = scores.copy()
            sm[~s_mask] = np.inf
            idxs = patterns.matches_under(sm, thr, cfg.MIN_GAP)
            e = np.array([i + cfg.WINDOW - 1 for i in idxs])
            cells, n_eff = [], 0
            for h in cfg.HORIZONS:
                ent = e[e + h < n]
                r = direction * (close[ent + h] / close[ent] - 1.0)
                n_eff = len(r)
                edge = (r.mean() - direction * base[h]) * 100
                cells.append(f"{edge:+6.3f}({(r > 0).mean() * 100:4.1f})")
            print(f"{pct:>7.2f}% {thr:>8.4f} {n_eff:>6} | " + " ".join(f"{c:>13}" for c in cells))
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default=cfg.TF)
    ap.add_argument("--no-session", action="store_true")
    a = ap.parse_args()
    main(a.tf, not a.no_session and cfg.SESSION_ENABLED)
