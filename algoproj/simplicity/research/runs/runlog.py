"""
runlog — the RUN LEDGER. Every research run saves a SCORECARD bound to its exact config + params.

The point: never tune blindly. Before you change a knob you run the script (it logs a baseline row);
you change the knob and run again (it logs another row). Both are kept forever in an append-only
ledger, so `analyze_runs.py` can show how the outputs moved as the params changed. Nothing is lost.

  record(kind, params, metrics, note) -> appends one JSON line to research/runs/runs.jsonl with:
     run_id (UTC timestamp) · git commit · the component PARAMS used · a strategy_config snapshot ·
     the output METRICS · your note.

A run is one scorecard. The ledger is the history. `analyze_runs.py` is the analytics across it.
(Complements the future per-bar `session_archive`, NOTES F9 — this is per-RUN params+metrics.)
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))          # research/runs
LEDGER = os.path.join(HERE, "runs.jsonl")


def _sim_root():
    h = HERE
    while not os.path.exists(os.path.join(h, "strategy_config.py")):
        nh = os.path.dirname(h)
        if nh == h:
            return HERE
        h = nh
    return h


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=_sim_root(), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def config_snapshot():
    """The strategy_config / research_config values a run depends on (for provenance)."""
    root = _sim_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    import strategy_config as cfg
    snap = {"era_start": cfg.ERA_START_YEAR, "vol_metric": cfg.VOL_METRIC, "trail_window": cfg.TRAIL_WINDOW,
            "filter_session": cfg.FILTER_SESSION.get("allow") if cfg.FILTER_SESSION.get("on") else "off",
            "filter_hour": cfg.FILTER_HOUR.get("allow") if cfg.FILTER_HOUR.get("on") else "off",
            "filter_day_vol": cfg.FILTER_DAY_VOL.get("regimes") if cfg.FILTER_DAY_VOL.get("on") else "off"}
    # the tunable strategy blocks live in strategy_config -> captured here so config == what produced the run
    for k in ("PROFILE", "SHAPE", "ZONE", "BASE", "HTF", "FIB", "LADDER", "SETUP", "ENTRY", "EXIT", "RISK"):
        if hasattr(cfg, k):
            snap[k.lower()] = getattr(cfg, k)
    snap["config_source"] = getattr(cfg, "CONFIG_SOURCE", "strategy")
    snap["costs"] = {"point_value": cfg.POINT_VALUE, "tick": cfg.TICK,
                     "commission_per_side": cfg.COMMISSION_PER_SIDE, "slippage_ticks": cfg.SLIPPAGE_TICKS}
    try:
        import research_config as rcfg
        snap["active_filter"] = rcfg.ACTIVE_FILTER
    except Exception:
        pass
    return snap


def note_from_argv():
    """Free-text note = the non-flag CLI args, e.g. `python shape_filter.py baseline before tuning`."""
    return " ".join(a for a in sys.argv[1:] if not a.startswith("-")).strip()


def record(kind, params, metrics, note=""):
    rec = {"run_id": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
           "git": git_commit(), "kind": kind, "note": note or note_from_argv(),
           "params": params, "config": config_snapshot(), "metrics": metrics}
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[runlog] {kind} run {rec['run_id']} (git {rec['git']})"
          + (f' note="{rec["note"]}"' if rec["note"] else "") + " -> research/runs/runs.jsonl")
    return rec


def load():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
