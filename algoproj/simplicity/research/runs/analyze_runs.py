"""
analyze_runs — read the run ledger and show how outputs moved as configs/params changed.

This is the "analytics across the board": every logged run is a scorecard (params + config +
metrics + note); grouped by kind and shown in order, so a before/after tune is two rows you can
diff by eye. Extend later (plots, auto-deltas) — the ledger (`runs.jsonl`) is the durable record.

Run:  python research/runs/analyze_runs.py            # all kinds
      python research/runs/analyze_runs.py shape_filter   # one kind
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runlog


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def main():
    runs = runlog.load()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if not runs:
        print("no runs logged yet — run a research script (shape_filter / zone_calibration / fib_bias) first.")
        return
    kinds = {}
    for r in runs:
        if only and r["kind"] != only:
            continue
        kinds.setdefault(r["kind"], []).append(r)
    for kind, rs in kinds.items():
        print(f"\n=== {kind}   ({len(rs)} run{'s' if len(rs) != 1 else ''}) ===")
        for r in rs:
            note = f'   "{r["note"]}"' if r.get("note") else ""
            cfg = _flat(r.get("config", {}))
            print(f"  {r['run_id']}  git {r['git']}{note}")
            print(f"    config : era>={cfg.get('era_start')}  session={cfg.get('filter_session')}  "
                  f"day_vol={cfg.get('filter_day_vol')}  active_filter={cfg.get('active_filter')}")
            print(f"    params : " + ", ".join(f"{k}={v}" for k, v in _flat(r.get('params', {})).items()))
            print(f"    metrics: " + ", ".join(f"{k}={v}" for k, v in _flat(r.get('metrics', {})).items()))
    print(f"\n{len(runs)} runs total in research/runs/runs.jsonl")


if __name__ == "__main__":
    main()
