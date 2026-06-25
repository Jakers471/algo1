"""Parameter grid search — turn NinjaTrader-style min;max;increment specs into configs.

Deliberately tiny: the only job here is expanding a set of per-parameter sweep specs
into the cartesian product of override dicts. Running/scoring them is the caller's job
(see wfo.py), which keeps this reusable for plain optimization too.
"""
import itertools


def expand_spec(spec):
    """One parameter's sweep spec -> the explicit list of values to try.

    spec is either an explicit list/tuple of values, or a (min, max, step) tuple
    interpreted INCLUSIVELY (like NinjaTrader's `min;max;increment`). Integer-valued
    specs stay ints so configs hash/serialize cleanly.
    """
    if isinstance(spec, tuple) and len(spec) == 3:
        lo, hi, step = spec
        if step <= 0:
            return [lo]
        n = int(round((hi - lo) / step)) + 1
        vals = [lo + i * step for i in range(max(1, n))]
        if all(float(v).is_integer() for v in (lo, hi, step)):
            vals = [int(round(v)) for v in vals]
        return vals
    return list(spec)


def parse_minmax(text):
    """Parse a NinjaTrader-style `min;max;increment` string -> (min,max,step) or None.

    Accepts ';' or ',' separators; returns ints when all three are integer-valued so the
    expanded grid stays integer. Returns None on anything malformed (caller treats the
    param as not-swept).
    """
    parts = [p.strip() for p in str(text).replace(",", ";").split(";") if p.strip()]
    if len(parts) != 3:
        return None
    try:
        lo, hi, step = (float(p) for p in parts)
    except ValueError:
        return None
    if all(float(x).is_integer() for x in (lo, hi, step)):
        return (int(lo), int(hi), int(step))
    return (lo, hi, step)


def build_grid(specs):
    """`{name: (min,max,step) | [values]}` -> list of override dicts (cartesian product)."""
    if not specs:
        return [{}]
    names = list(specs)
    value_lists = [expand_spec(specs[n]) for n in names]
    return [dict(zip(names, combo)) for combo in itertools.product(*value_lists)]


def grid_size(specs):
    """How many configs a spec set expands to (for a pre-run time estimate)."""
    n = 1
    for s in specs.values():
        n *= len(expand_spec(s))
    return n
