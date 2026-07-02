"""
The expectancy harness — turns a brick-flip signal into trades measured in R, net of
costs, with an OOS split baked in from trade one. This is deliberately built BEFORE any
real signal work (see NOTES.md): nothing gets measured cost-free, ever.

THE ONE NUMBER: expectancy = win% * avg_win_R - loss% * avg_loss_R  (net of costs).
Everything below exists to compute that number honestly.

BASELINE SIGNAL (the minimal defensible one, per the build order): trade every color
flip — when a brick's direction differs from the previous brick's, enter in the NEW
direction at that brick's close (this IS "buy white, sell black"). Exit on whichever
comes first:
  * STOP   : price closes `stop_bricks` bricks against the entry (checked on brick
             closes only — no intrabar peeking, consistent with the confirmed-only engine).
  * TARGET : price closes `target_R * stop_bricks` bricks in favor (skipped if target_R
             is None => ride until the next opposite flip, the "no preset targets" thesis).
  * FLIP   : an opposite-direction flip prints before stop/target (forced exit there).

Everything is measured on the SOURCE close-based grid the bricks already live on, so no
new look-ahead is introduced by the harness.

FILL HONESTY (the F2 lesson — this harness originally filled at brick GRID prices and
printed +0.49R/trade of pure fantasy on the every-flip baseline): a brick only CONFIRMS
when a 1m bar CLOSES at/past its grid line, so the only tradable price at that moment is
that bar's close — at a flip it is always at-or-past the grid line AGAINST the trade
(measured mean gap 0.23R per side at 25pt, 0.46R at 10pt). Pass `src_close` (the same 1m
close array the bricks were built from) and every market fill (entry, stop, flip, eod)
happens at the confirming source close. Only the resting-limit TARGET may fill at its
nominal price. Grid fills (src_close=None) are kept only as a what-not-to-do comparison.
"""
import os
import sys

import numpy as np

_r = os.path.dirname(os.path.abspath(__file__))
while _r != os.path.dirname(_r) and not os.path.isdir(os.path.join(_r, "algokit")):
    _r = os.path.dirname(_r)
sys.path.insert(0, _r)
from algokit.costs import FuturesCost
from renko import config as C


def simulate_trades(bricks, stop_bricks=1, target_R=None, brick_size=None, cost=None,
                    src_close=None):
    """Trade every color flip; exit on stop / target / opposite flip.

    Parameters
    ----------
    bricks      : dict from engine.bricks.build_bricks (ts/open/close/dir/src_i).
    stop_bricks : int    stop distance in BRICKS behind the entry (>=1). This is 1R.
    target_R    : float or None.  None => ride to the next opposite flip (no preset target).
    brick_size  : points/brick (defaults to config.BRICK_SIZE — must match what built `bricks`).
    cost        : algokit.costs.FuturesCost instance (defaults to project standard).
    src_close   : float[] the SOURCE close array the bricks were built from. When given,
                  all market fills use the confirming 1m close (honest). None = grid-price
                  fills — known-fantasy, kept only for comparison (see module docstring).

    Returns
    -------
    list of trade dicts: entry_i (brick index), exit_i, ts_entry, ts_exit, dir,
    entry_price, exit_price, stop_price, target_price (or None), reason
    ("stop"|"target"|"flip"|"eod" ), r_gross, cost_R, r_net.
    """
    brick = float(brick_size if brick_size is not None else C.BRICK_SIZE)
    cost = cost or FuturesCost()
    d = bricks["dir"]
    close = bricks["close"]
    ts = bricks["ts"]
    si = bricks["src_i"]
    n = len(d)
    if n < 2:
        return []

    def _mkt_fill(j):
        """Real fill for a market order triggered by brick j confirming: the source close
        that confirmed it (honest), or the grid close (fantasy mode, src_close=None)."""
        return float(src_close[si[j]]) if src_close is not None else float(close[j])

    # 1R in USD (stop distance) and the round-turn cost expressed as a fraction of 1R —
    # the exact "cost/1R" lens from the brick build, applied per trade here.
    one_R_usd = stop_bricks * brick * C.POINT_VALUE
    rt_cost_usd = 2 * cost.commission_per_side + 2 * cost.slippage_ticks * cost.tick * C.POINT_VALUE
    cost_R = rt_cost_usd / one_R_usd

    trades = []
    i = 1
    while i < n:
        if d[i] == d[i - 1]:
            i += 1
            continue
        # a flip at i: enter in the NEW direction at the price that actually printed when
        # this brick confirmed (stop/target measured off the REAL entry, so 1R stays 1R)
        entry_dir = int(d[i])
        entry_price = _mkt_fill(i)
        stop_price = entry_price - entry_dir * stop_bricks * brick
        target_price = (entry_price + entry_dir * target_R * stop_bricks * brick
                         if target_R is not None else None)

        exit_i, exit_price, reason = None, None, "eod"
        j = i + 1
        while j < n:
            p = float(close[j])
            hit_stop = (entry_dir == 1 and p <= stop_price) or (entry_dir == -1 and p >= stop_price)
            hit_target = target_price is not None and (
                (entry_dir == 1 and p >= target_price) or (entry_dir == -1 and p <= target_price))
            opp_flip = d[j] != d[j - 1] and d[j] != entry_dir
            if hit_stop:
                # NO fill-optimism: a reversal always jumps >= reversal_bricks bricks, so a
                # stop can be BLOWN THROUGH, never hit exactly. Fill at the real confirming
                # price, not the nominal stop line -- the pessimistic, honest fill.
                exit_i, exit_price, reason = j, _mkt_fill(j), "stop"
                break
            if hit_target:
                # A target is a resting limit order: it fills AT the limit, never past it
                # (the market can gap through a limit but the fill is capped there), so the
                # nominal target price is the correct (not optimistic) fill here.
                exit_i, exit_price, reason = j, target_price, "target"
                break
            if opp_flip:
                exit_i, exit_price, reason = j, _mkt_fill(j), "flip"
                break
            j += 1

        if exit_i is None:
            exit_i, exit_price, reason = n - 1, _mkt_fill(n - 1), "eod"

        r_gross = entry_dir * (exit_price - entry_price) / (stop_bricks * brick)
        r_net = r_gross - cost_R
        trades.append({
            "entry_i": i, "exit_i": exit_i,
            "ts_entry": int(ts[i]), "ts_exit": int(ts[exit_i]),
            "dir": entry_dir,
            "entry_price": entry_price, "exit_price": exit_price,
            "stop_price": stop_price, "target_price": target_price,
            "reason": reason, "r_gross": r_gross, "cost_R": cost_R, "r_net": r_net,
        })
        # Resume AT exit_i, not past it: a stop/flip exit brick is very often itself the
        # opposite-direction flip (adverse closes only happen via a flip, see bricks.py),
        # so it must be re-examined as a fresh entry next iteration -- skipping past it
        # was silently discarding every reversal and made the sim long-only (found via
        # the long/short split sanity check below).
        i = exit_i

    return trades


def expectancy_report(trades, split=0.70):
    """The headline numbers, plus an in-sample / out-of-sample split (by trade order).

    split : fraction of trades kept in-sample (time-ordered, so this is a real OOS split,
            not a shuffle). Mirrors algokit.validation.in_out_sample's 70/30 default.
    """
    def _block(ts):
        n = len(ts)
        if n == 0:
            return {"n": 0}
        r = np.array([t["r_net"] for t in ts])
        wins = r[r > 0]
        losses = r[r <= 0]
        win_rate = len(wins) / n
        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss = float(-losses.mean()) if len(losses) else 0.0
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
        # risk stats — all in R, i.e. assuming risk-normalized sizing (fixed $ risked/trade)
        cum = np.cumsum(r)
        max_dd = float((cum - np.maximum.accumulate(cum)).min()) if n else 0.0
        gross_loss = float(-losses.sum())
        pf = float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf")
        t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(n))) if n > 1 and r.std(ddof=1) > 0 else 0.0
        return {
            "n": n, "win_rate": win_rate, "avg_win_R": avg_win, "avg_loss_R": avg_loss,
            "expectancy_R": expectancy, "total_R": float(r.sum()),
            "max_dd_R": max_dd, "profit_factor": pf, "t_stat": t_stat,
            "cum_R": cum,  # equity-curve-in-R shape, not just the endpoint
        }

    b = int(len(trades) * split)
    return {
        "all": _block(trades),
        "in_sample": _block(trades[:b]),
        "out_of_sample": _block(trades[b:]),
        "split_trade": b,
    }


def print_report(rep, label=""):
    print(f"\n=== expectancy report {label} ===")
    for key in ("all", "in_sample", "out_of_sample"):
        blk = rep[key]
        if blk["n"] == 0:
            print(f"  {key:14s}: n=0")
            continue
        print(f"  {key:14s}: n={blk['n']:5d}  win%={blk['win_rate']*100:5.1f}  "
              f"avg_win={blk['avg_win_R']:.3f}R  avg_loss={blk['avg_loss_R']:.3f}R  "
              f"expectancy={blk['expectancy_R']:+.4f}R  total={blk['total_R']:+.1f}R  "
              f"PF={blk['profit_factor']:.2f}  maxDD={blk['max_dd_R']:+.0f}R  t={blk['t_stat']:+.2f}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=C.BRICK_SIZE)
    ap.add_argument("--reversal", type=int, default=C.REVERSAL_BRICKS)
    ap.add_argument("--stop-bricks", type=int, default=1)
    ap.add_argument("--target-r", type=float, default=None)
    ap.add_argument("--grid-fills", action="store_true",
                    help="use the known-fantasy grid-price fills (comparison only)")
    a = ap.parse_args()

    path = C.bricks_path(a.size)
    if not os.path.exists(path):
        raise SystemExit(f"no bricks at {path} — run engine/build_bricks.py --size {a.size:g} first")
    z = np.load(path)
    bricks = {k: z[k] for k in ("ts", "open", "close", "dir", "src_i")}

    src_close = None
    if not a.grid_fills:
        from algokit.data import load_tf
        src_close = load_tf(C.SOURCE_TF)[["close"]].dropna()["close"].to_numpy("float64")

    trades = simulate_trades(bricks, stop_bricks=a.stop_bricks, target_R=a.target_r,
                             brick_size=a.size, src_close=src_close)
    rep = expectancy_report(trades)
    fills = "GRID(fantasy)" if a.grid_fills else "honest"
    label = f"brick={a.size:g}pt stop={a.stop_bricks}R target={a.target_r} fills={fills}"
    print_report(rep, label)
