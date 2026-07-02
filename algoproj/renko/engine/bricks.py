"""
Close-based Renko brick construction — confirmed-only, zero repaint, zero look-ahead.

WHY close-based off 1m closes:
  * A brick is only ever emitted when a CLOSED bar's close crosses a grid threshold, so
    every brick is confirmed at that bar's close time. Nothing repaints; nothing peeks
    inside a bar. This is the single most important correctness property of a Renko
    backtest (an intrabar/high-low engine can print a brick that the bar later "un-prints").
  * The trade-off: a fast intrabar spike that closes back is NOT drawn (fewest bricks,
    most conservative). A high/low variant would catch it but needs an intrabar tie-break
    and flirts with repaint — deferred.

ALGORITHM (traditional, grid-aligned):
  Bricks live on a grid of `anchor + k*brick`. In a trend, each continuation brick is the
  next grid box in the trend direction, emitted when the close reaches its far edge. To
  REVERSE, price must move `reversal_bricks` boxes against the trend: the first box back is
  the current brick's own open (no brick drawn there), and every further box prints one
  opposing brick. `reversal_bricks=2` is standard trend-following Renko.

Each emitted brick records:
  ts    : epoch-seconds of the CLOSED source bar that confirmed it (real time, for costs/exec)
  open  : brick open price (grid line)
  close : brick close price (grid line, = open ± brick)
  dir   : +1 up (white) / -1 down (black)
  src_i : index into the source array of the confirming bar (for joins)
"""
import numpy as np


def build_bricks(ts, close, brick_size, reversal_bricks=2):
    """Build close-based Renko bricks from a source series.

    Parameters
    ----------
    ts    : int64[]  epoch-seconds, ascending, one per source bar.
    close : float[]  source closes (aligned to ts).
    brick_size      : float  points per brick (> 0).
    reversal_bricks : int    boxes against trend required to flip (>= 1).

    Returns
    -------
    dict of equal-length arrays: ts, open, close, dir, src_i  (one row per brick).
    """
    brick = float(brick_size)
    if brick <= 0:
        raise ValueError("brick_size must be > 0")
    rev = int(reversal_bricks)
    if rev < 1:
        raise ValueError("reversal_bricks must be >= 1")

    n = len(close)
    if n == 0:
        return _empty()

    # Grid anchored at the first close. last_g = grid index of the last brick's CLOSE line.
    anchor = float(close[0])
    last_g = 0            # close of the (virtual) seed brick sits on the anchor line
    direction = 0         # 0 until the first brick establishes a trend

    # Pre-size generously; trim at the end. Worst case is bounded by total travel/brick.
    b_ts = []
    b_open = []
    b_close = []
    b_dir = []
    b_i = []

    for i in range(n):
        p = float(close[i])
        # boxes of price relative to the last brick close, as a signed float
        d = (p - anchor) / brick - last_g   # >0 above last close, <0 below

        if direction >= 0:
            # ---- continuation UP ----
            if d >= 1.0:
                nb = int(np.floor(d))
                for _ in range(nb):
                    o = anchor + last_g * brick
                    last_g += 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * brick)
                    b_dir.append(1); b_i.append(i)
                direction = 1
            # ---- reversal DOWN (need `rev` boxes against the up trend) ----
            elif -d >= rev:
                nb = int(np.floor(-d)) - (rev - 1)   # first (rev-1) boxes are the open-side gap
                last_g -= (rev - 1)                  # step back past the open box(es), no brick drawn
                for _ in range(nb):
                    o = anchor + last_g * brick
                    last_g -= 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * brick)
                    b_dir.append(-1); b_i.append(i)
                direction = -1
        else:
            # ---- continuation DOWN ----
            if -d >= 1.0:
                nb = int(np.floor(-d))
                for _ in range(nb):
                    o = anchor + last_g * brick
                    last_g -= 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * brick)
                    b_dir.append(-1); b_i.append(i)
                direction = -1
            # ---- reversal UP ----
            elif d >= rev:
                nb = int(np.floor(d)) - (rev - 1)
                last_g += (rev - 1)
                for _ in range(nb):
                    o = anchor + last_g * brick
                    last_g += 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * brick)
                    b_dir.append(1); b_i.append(i)
                direction = 1

    return {
        "ts":    np.asarray(b_ts, dtype="int64"),
        "open":  np.asarray(b_open, dtype="float64"),
        "close": np.asarray(b_close, dtype="float64"),
        "dir":   np.asarray(b_dir, dtype="int8"),
        "src_i": np.asarray(b_i, dtype="int64"),
    }


def build_bricks_adaptive(ts, close, sizes, reversal_bricks=2):
    """Renko with a TIME-VARYING brick size — the stationarity fix for 20yr of NQ.

    Fixed-point bricks aren't comparable across eras (NQ's daily ATR went ~18pt in 2005 to
    ~300pt in 2025, so one point-size is simultaneously too coarse and too fine). Here the
    brick size is supplied PER BAR (`sizes`, in points — e.g. k*ATR20, updated monthly,
    computed strictly from prior data so no look-ahead). When the size changes, the grid
    re-anchors at the last brick close and the trend direction carries over (the only
    state lost is partial progress toward a reversal — a small, bounded distortion at
    each re-size, 12/yr on a monthly schedule).

    Returns the same arrays as build_bricks plus `bsize`: the brick size (points) in
    effect for each emitted brick — REQUIRED downstream for honest R accounting (1R is
    that brick's own size, not a global constant).
    """
    rev = int(reversal_bricks)
    if rev < 1:
        raise ValueError("reversal_bricks must be >= 1")
    n = len(close)
    if n == 0:
        return _empty(adaptive=True)

    anchor = float(close[0])
    last_g = 0
    direction = 0
    cur = float(sizes[0])
    if cur <= 0:
        raise ValueError("sizes must be > 0")

    b_ts = []; b_open = []; b_close = []; b_dir = []; b_i = []; b_sz = []

    for i in range(n):
        s = float(sizes[i])
        if s != cur:
            # re-anchor at the last brick close price; keep direction
            anchor = anchor + last_g * cur
            last_g = 0
            cur = s
        p = float(close[i])
        d = (p - anchor) / cur - last_g

        if direction >= 0:
            if d >= 1.0:
                nb = int(np.floor(d))
                for _ in range(nb):
                    o = anchor + last_g * cur
                    last_g += 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * cur)
                    b_dir.append(1); b_i.append(i); b_sz.append(cur)
                direction = 1
            elif -d >= rev:
                nb = int(np.floor(-d)) - (rev - 1)
                last_g -= (rev - 1)
                for _ in range(nb):
                    o = anchor + last_g * cur
                    last_g -= 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * cur)
                    b_dir.append(-1); b_i.append(i); b_sz.append(cur)
                direction = -1
        else:
            if -d >= 1.0:
                nb = int(np.floor(-d))
                for _ in range(nb):
                    o = anchor + last_g * cur
                    last_g -= 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * cur)
                    b_dir.append(-1); b_i.append(i); b_sz.append(cur)
                direction = -1
            elif d >= rev:
                nb = int(np.floor(d)) - (rev - 1)
                last_g += (rev - 1)
                for _ in range(nb):
                    o = anchor + last_g * cur
                    last_g += 1
                    b_ts.append(ts[i]); b_open.append(o); b_close.append(anchor + last_g * cur)
                    b_dir.append(1); b_i.append(i); b_sz.append(cur)
                direction = 1

    return {
        "ts":    np.asarray(b_ts, dtype="int64"),
        "open":  np.asarray(b_open, dtype="float64"),
        "close": np.asarray(b_close, dtype="float64"),
        "dir":   np.asarray(b_dir, dtype="int8"),
        "src_i": np.asarray(b_i, dtype="int64"),
        "bsize": np.asarray(b_sz, dtype="float64"),
    }


def _empty(adaptive=False):
    out = {"ts": np.array([], "int64"), "open": np.array([], "float64"),
           "close": np.array([], "float64"), "dir": np.array([], "int8"),
           "src_i": np.array([], "int64")}
    if adaptive:
        out["bsize"] = np.array([], "float64")
    return out


# ── self-test: hand-verifiable synthetic series ──────────────────────────────
if __name__ == "__main__":
    # brick=1, reversal=2. Walk price up to 103, then down to 98.
    #   up:   100->101->102->103  => 3 up bricks (100-101, 101-102, 102-103)
    #   down: from close=103, need 2 boxes to reverse. 103->101 = 2 boxes: first box (102-103)
    #         is the open gap, second prints ONE down brick (102-101). Continue 101->98:
    #         98 is 3 more boxes down => bricks 101-100, 100-99, 99-98. Total down = 4.
    ts = np.arange(20, dtype="int64")
    path = [100, 100.5, 101, 101.9, 102, 103, 102.5, 101, 100, 99, 98, 98]
    close = np.array(path + [98] * (20 - len(path)), dtype="float64")
    bk = build_bricks(ts, close, brick_size=1.0, reversal_bricks=2)
    ups = int((bk["dir"] == 1).sum()); downs = int((bk["dir"] == -1).sum())
    print(f"up bricks={ups} (expect 3), down bricks={downs} (expect 4)")
    for o, c, d in zip(bk["open"], bk["close"], bk["dir"]):
        print(f"  {'WHITE' if d==1 else 'black'}  {o:.1f} -> {c:.1f}")
    assert ups == 3 and downs == 4, "self-test FAILED"
    print("self-test PASSED")
