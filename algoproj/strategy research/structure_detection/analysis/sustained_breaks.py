"""
Sustained-break analysis on the structure swings (per grain).

For each leg, draw the fib (low->high for bull, high->low for bear) and measure how deep the next
pullback retraces it. A leg "sustains" the trend if it BREAKS in the trend direction (higher high /
lower low) AND its pullback held the fib (retrace <= threshold, default 0.5). We then count RUNS of
consecutive sustained breaks — "how many sustained moves in a row, and in which direction."

A run ends when a pullback retraces past the threshold, or the trend fails to make a new extreme
(a break the other way = direction change). Reads findings/structure_<tf>.json. Prints only.

Run: python "strategy research/structure_detection/analysis/sustained_breaks.py" [--tf 5m] [--fib 0.5]
"""
import argparse
import json
import os


def legs(swings, up):
    """Ordered (base, extreme) pairs: up -> (low, high) from L then H; down -> (high, low)."""
    a, b = ("L", "H") if up else ("H", "L")
    out = []
    for i in range(len(swings) - 1):
        if swings[i]["k"] == a and swings[i + 1]["k"] == b:
            out.append((swings[i]["p"], swings[i + 1]["p"]))
    return out


def sustained_flags(pairs, up, fib):
    """For each leg j>=1: did it break in-trend AND hold the fib on the pullback before it?"""
    flags = []
    for j in range(1, len(pairs)):
        base0, ext0 = pairs[j - 1]      # previous leg: base(low/high), extreme(high/low)
        base1, ext1 = pairs[j]          # this leg; base1 = the pullback extreme after ext0
        span = abs(ext0 - base0)
        if span == 0:
            flags.append(False)
            continue
        retrace = abs(ext0 - base1) / span                 # how far the pullback retraced the prior leg
        broke = ext1 > ext0 if up else ext1 < ext0         # new higher-high / lower-low = a break in-trend
        flags.append(broke and retrace <= fib)
    return flags


def run_lengths(flags):
    """Lengths of consecutive-True runs."""
    runs, c = [], 0
    for f in flags:
        if f:
            c += 1
        elif c:
            runs.append(c); c = 0
    if c:
        runs.append(c)
    return runs


def report(name, swings, fib):
    print(f"\n=== {name}  ({len(swings)} swings) ===")
    for up, lab in [(True, "BULL"), (False, "BEAR")]:
        pairs = legs(swings, up)
        flags = sustained_flags(pairs, up, fib)
        runs = run_lengths(flags)
        n_legs = len(flags)
        held = sum(flags)
        dist = {}
        for r in runs:
            b = "5+" if r >= 5 else str(r)
            dist[b] = dist.get(b, 0) + 1
        order = ["1", "2", "3", "4", "5+"]
        cells = "  ".join(f"{k}:{dist.get(k, 0)}" for k in order)
        mx = max(runs) if runs else 0
        print(f"  {lab}: {n_legs} legs, {held} sustained ({held/max(n_legs,1)*100:.0f}%)  |  "
              f"runs {cells}  |  longest {mx} in a row")


def main(tf, fib):
    HERE = os.path.dirname(os.path.abspath(__file__))
    data = json.load(open(os.path.join(HERE, "..", "findings", f"structure_{tf}.json")))
    print(f"{tf}: sustained breaks (pullback <= {fib*100:.0f}% of the leg = held, in-trend break)")
    print("run = consecutive sustained legs; a >50% pullback or a reverse break ends the run")
    for g in data["grains"]:
        report(g["name"], g["swings"], fib)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m")
    ap.add_argument("--fib", type=float, default=0.5)
    a = ap.parse_args()
    main(a.tf, a.fib)
