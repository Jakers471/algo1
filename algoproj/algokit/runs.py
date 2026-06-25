"""
Versioned backtest run registry.

Every backtest is saved as a numbered, machine-readable run under runs/run_NNNN/:
  config.json   exact config used (reproducible)
  metrics.json  every stat the backtest produced
  trades.parquet  full trade list
  equity.parquet  per-bar returns / equity curve
  chart.html    popout candlestick chart with order markers
  meta.json     id, timestamp, strategy, parent run, and a DIFF vs the parent config
A registry index (runs/index.json + runs/RUNS.md) is auto-rebuilt each save.
"""
import os
import json
import datetime

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import _ROOT

RUNS_DIR = os.path.join(_ROOT, "runs")


# the three test kinds are kept strictly separate on disk and in the UI
KINDS = ("backtest", "wfo", "anchored")
_SUB = {"backtest": "backtest", "wfo": "walk_forward", "anchored": "anchored"}
_PREFIX = {"backtest": "run_", "wfo": "wfo_", "anchored": "awf_"}
# human label per kind/backtest_type (anchored is NOT called "WFO")
TYPE_LABEL = {"backtest": "Backtest", "wfo": "Walk-Forward", "anchored": "Anchored"}


def _sub(kind):
    return _SUB.get(kind, "backtest")


def _type_dir(strategy, kind="backtest"):
    """runs/<strategy>/<backtest|walk_forward|anchored> — where runs of this kind live."""
    return os.path.join(RUNS_DIR, strategy, _sub(kind))


def _prefix(kind):
    return _PREFIX.get(kind, "run_")


def _ids(strategy, kind="backtest"):
    """Sorted numeric ids already used for this strategy + kind (numbering is per-folder)."""
    d = _type_dir(strategy, kind)
    if not os.path.isdir(d):
        return []
    p = len(_prefix(kind))
    pre = _prefix(kind)
    return sorted(int(x[p:]) for x in os.listdir(d)
                  if x.startswith(pre) and x[p:].isdigit())


def _relpath(d):
    """Run directory relative to RUNS_DIR, forward-slashed (stable across OSes)."""
    return os.path.relpath(d, RUNS_DIR).replace("\\", "/")


def _clean(v):
    """JSON-safe: numpy -> python, non-finite -> None."""
    try:
        f = float(v)
        return None if not np.isfinite(f) else f
    except (TypeError, ValueError):
        return v


def _jsonify(v):
    """Recursively JSON-safe a nested dict/list of numbers (numpy -> python)."""
    if isinstance(v, dict):
        return {k: _jsonify(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonify(x) for x in v]
    if isinstance(v, (str, bool, type(None))):
        return v
    return _clean(v)


def trial_count(strategy_name):
    """How many backtests of this strategy exist (for the deflated-Sharpe multiple-testing
    haircut). Each saved backtest is one config tried."""
    return len(_ids(strategy_name, "backtest"))


def _config_diff(old, new):
    diff = {"changed": {}, "added": {}, "removed": {}}
    for k in new:
        if k not in old:
            diff["added"][k] = new[k]
        elif old[k] != new[k]:
            diff["changed"][k] = [old[k], new[k]]
    for k in old:
        if k not in new:
            diff["removed"][k] = old[k]
    return diff


def save_run(result, strategy_name, notes=""):
    """Persist a result dict from strategy.run() as the next numbered run."""
    os.makedirs(RUNS_DIR, exist_ok=True)
    cfg = result["cfg"]; stats = result["stats"]; res = result["res"]; b = result["build"]
    idx = b["idx"]

    parent_dir = _type_dir(strategy_name, "backtest")
    # de-dup: if the config is identical to the most recent run, do NOT create a
    # duplicate (nothing changed -> nothing to save).
    ids = _ids(strategy_name, "backtest")
    if ids:
        last_dir = os.path.join(parent_dir, f"run_{ids[-1]:04d}")
        last_cfg = json.load(open(os.path.join(last_dir, "config.json")))
        if json.loads(json.dumps(cfg)) == last_cfg:
            meta = json.load(open(os.path.join(last_dir, "meta.json")))
            meta["unchanged"] = True
            return last_dir, meta

    rid = (ids[-1] + 1) if ids else 1
    name = f"run_{rid:04d}"
    d = os.path.join(parent_dir, name)
    os.makedirs(d, exist_ok=True)

    json.dump(cfg, open(os.path.join(d, "config.json"), "w"), indent=2)
    json.dump({k: _clean(v) for k, v in stats.items()},
              open(os.path.join(d, "metrics.json"), "w"), indent=2)

    # rich trade log so research loads-and-analyzes with no recompute
    rows = []
    for tr in res["trades"]:
        ei, xi, ep, xp, reason = (tr["entry_i"], tr["exit_i"], tr["entry_px"],
                                  tr["exit_px"], tr["reason"])
        t = idx[ei]; et = pd.Timestamp(t, tz="UTC").tz_convert("America/New_York")
        rows.append(dict(entry=t, exit=idx[xi], entry_px=ep, exit_px=xp, ret=xp / ep - 1,
                         pnl=tr.get("pnl"), contracts=tr.get("contracts"),
                         mae=tr.get("mae"), mfe=tr.get("mfe"), etd=tr.get("etd"),
                         reason=reason, hold_bars=xi - ei, hour_et=et.hour, dow=t.dayofweek,
                         bull15=b["bull15"][ei], consol15=b["consol15"][ei], bull1d=b["bull1d"][ei]))
    pd.DataFrame(rows).to_parquet(os.path.join(d, "trades.parquet"))

    # dollar equity (engine is dollar-account); carry the benchmark alongside it
    eq = res["equity"]
    cols = {"time": idx, "ret": res["rets"], "equity": eq, "in_market": res["in_market"]}
    if result.get("bench"):
        cols["bench_equity"] = result["bench"]["equity"]
    pd.DataFrame(cols).to_parquet(os.path.join(d, "equity.parquet"))

    # --- validation (IS/OOS + walk-forward) & significance (multiple-testing) ---
    from algokit import validation, significance
    ppy = result.get("ppy", 252.0); start = b["start"]
    analysis = {
        "in_out_sample": validation.in_out_sample(res["rets"], res["trades"],
                                                  res["in_market"], idx, ppy),
        "walk_forward": validation.walk_forward(res["rets"], res["trades"],
                                                res["in_market"], idx, ppy),
        "significance": significance.edge_report(
            res, ppy, n_trials=trial_count(strategy_name) + 1, close=b["c"], start=start),
        "benchmark": result.get("bench", {}).get("metrics", {}),
    }
    json.dump({k: _jsonify(v) for k, v in analysis.items()},
              open(os.path.join(d, "analysis.json"), "w"), indent=2)

    prev = ids[-1] if ids else None
    diff = None
    if prev is not None:
        old = json.load(open(os.path.join(parent_dir, f"run_{prev:04d}", "config.json")))
        diff = _config_diff(old, cfg)

    from algokit import params as _params
    signal_p, exec_p = _params.split_params(cfg)
    now = datetime.datetime.now()
    meta = dict(run_id=rid, name=name, kind="backtest", backtest_type="Backtest",
                strategy=strategy_name, path=_relpath(d),
                timestamp=now.isoformat(timespec="seconds"), date=now.date().isoformat(),
                parent=(f"run_{prev:04d}" if prev else None), notes=notes, config_diff=diff,
                config_labeled={"signal_params": signal_p, "account_execution": exec_p},
                headline={k: _clean(stats[k]) for k in
                          ("total_return", "cagr", "sharpe", "max_drawdown",
                           "round_trips", "win_rate", "exposure")})
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=2)

    make_chart(result, os.path.join(d, "chart.html"))
    _rebuild_index()
    return d, meta


def save_wfo(result, strategy_name, base_cfg, settings, notes=""):
    """Persist a walk-forward optimization result as the next numbered wfo_NNNN run.

    Saves everything the UI shows, fully labeled:
      meta.json     backtest type, strategy, timestamp+date, optimize settings, headline,
                    and the base config split into signal vs account/execution.
      config.json   the reproducible base config the whole sweep shared.
      settings.json the sweep grid + walk-forward options (objective, periods, anchored).
      steps.json    per-window: train range, picked params, train score, test range+metrics.
      result.json   stitched out-of-sample metrics, best-on-full yardstick, param stability.
    """
    os.makedirs(RUNS_DIR, exist_ok=True)
    from algokit import params as _params

    kind = "anchored" if result["anchored"] else "wfo"
    parent_dir = _type_dir(strategy_name, kind)
    ids = _ids(strategy_name, kind)
    rid = (ids[-1] + 1) if ids else 1
    name = f"{_prefix(kind)}{rid:04d}"
    d = os.path.join(parent_dir, name)
    os.makedirs(d, exist_ok=True)

    signal_p, exec_p = _params.split_params(base_cfg)
    bt = TYPE_LABEL[kind]                              # "Anchored" / "Walk-Forward" (not "WFO")
    now = datetime.datetime.now()

    json.dump(base_cfg, open(os.path.join(d, "config.json"), "w"), indent=2)
    json.dump(_jsonify(settings), open(os.path.join(d, "settings.json"), "w"), indent=2)
    json.dump(_jsonify(result["steps"]), open(os.path.join(d, "steps.json"), "w"), indent=2)
    json.dump(_jsonify({"oos": result["oos"], "oos_span": result["oos_span"],
                        "full_best": result["full_best"], "stability": result["stability"],
                        "equity": result.get("equity")}),
              open(os.path.join(d, "result.json"), "w"), indent=2)

    o = result["oos"]; fb = result["full_best"]["metrics"]
    meta = dict(run_id=rid, name=name, kind=kind, backtest_type=bt,
                strategy=strategy_name, path=_relpath(d),
                timestamp=now.isoformat(timespec="seconds"), date=now.date().isoformat(),
                notes=notes,
                objective=result["objective"], anchored=result["anchored"],
                train_days=result["train_days"], test_days=result["test_days"],
                n_windows=result["n_windows"], n_configs=result["n_configs"],
                oos_span=result["oos_span"], date_range=result.get("date_range"),
                swept_params=_jsonify(settings.get("specs", {})),
                config_labeled={"signal_params": signal_p, "account_execution": exec_p},
                headline={"oos_total_return": _clean(o.get("total_return")),
                          "oos_cagr": _clean(o.get("cagr")),
                          "oos_sharpe": _clean(o.get("sharpe")),
                          "oos_max_drawdown": _clean(o.get("max_drawdown")),
                          "oos_exposure": _clean(o.get("exposure")),
                          "oos_win_rate": _clean(o.get("win_rate")),
                          "full_total_return": _clean(fb.get("total_return"))})
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=2)
    _rebuild_index()
    return d, meta


def make_chart(result, out_path, recent_trades=60, max_candles=40000, pad=200):
    """Popout candlestick chart with order markers + config/stats panel for a run.

    The full history is far too large to dump as one HTML, so the window is anchored
    on the TRADES (not just the last N bars) — it spans the most recent `recent_trades`
    round-trips, padded, and capped at `max_candles` candles. This guarantees the chart
    actually shows orders even when trades are sparse / clustered early in the history.
    """
    from algokit import charts
    b = result["build"]; res = result["res"]; cfg = result["cfg"]; stats = result["stats"]
    idx = b["idx"]; n = len(b["c"]); trades = res["trades"]

    if trades:
        entries = sorted(t["entry_i"] for t in trades)
        last_exit = max(t["exit_i"] for t in trades)
        anchor = entries[-min(recent_trades, len(entries))]
        e = min(n, last_exit + pad)
        s = max(b["start"], anchor - pad)
        if e - s > max_candles:           # keep the HTML light: cap candle count
            s = max(b["start"], e - max_candles)
    else:
        s, e = max(b["start"], n - max_candles), n

    candles = [{"time": int(idx[i].value // 10**9), "open": float(b["o"][i]),
                "high": float(b["h"][i]), "low": float(b["l"][i]), "close": float(b["c"][i])}
               for i in range(s, e)]
    markers = []
    for tr in trades:
        ei, xi, reason = tr["entry_i"], tr["exit_i"], tr["reason"]
        if s <= ei < e:
            markers.append(dict(time=int(idx[ei].value // 10**9), position="belowBar",
                                color="#26a69a", shape="arrowUp", text="BUY"))
        if s <= xi < e:
            markers.append(dict(time=int(idx[xi].value // 10**9), position="aboveBar",
                                color="#ef5350", shape="arrowDown", text="SELL(" + reason + ")"))

    pct = lambda v: f"{v*100:+.1f}%"
    sc = {"STRATEGY CONFIG": {
            "Symbol": cfg["symbol"], "Timeframes": f'{cfg["htf_tf"]} + {cfg["ltf_tf"]}',
            "Entry": f'15m bull>={cfg["X"]} from coil', "HTF gate": f'1d bull>={cfg["htf_gate"]}',
            "Exit": f'15m bull<{cfg["exit_th"]}', "Stop": f'{cfg["atr_mult"]}xATR({cfg["atr_n"]})',
            "Cost": f'${cfg["commission_per_side"]}/side + {cfg["slippage_ticks"]}tick slip'}}
    st = {"PERFORMANCE": {"Net": pct(stats["total_return"]), "CAGR": pct(stats["cagr"]),
                          "Sharpe": f'{stats["sharpe"]:.2f}', "Max DD": pct(stats["max_drawdown"]),
                          "Exposure": f'{stats["exposure"]*100:.1f}%'},
          "TRADES": {"Round trips": stats["round_trips"], "Win rate": f'{stats["win_rate"]*100:.0f}%',
                     "Avg win": pct(stats["avg_win"]), "Avg loss": pct(stats["avg_loss"])}}
    charts.lightweight_chart(candles, markers, sc, st, out_path, title="FANNING REGIME")
    return out_path


def _all_metas():
    """Every run's meta across runs/<strategy>/<backtest|walk_forward>/<name>/, path-tagged."""
    metas = []
    if not os.path.isdir(RUNS_DIR):
        return metas
    for strat in sorted(os.listdir(RUNS_DIR)):
        sdir = os.path.join(RUNS_DIR, strat)
        if not os.path.isdir(sdir):
            continue
        for sub in _SUB.values():
            subdir = os.path.join(sdir, sub)
            if not os.path.isdir(subdir):
                continue
            for name in sorted(os.listdir(subdir)):
                mp = os.path.join(subdir, name, "meta.json")
                if os.path.exists(mp):
                    m = json.load(open(mp))
                    m["path"] = _relpath(os.path.join(subdir, name))
                    metas.append(m)
    metas.sort(key=lambda m: m.get("timestamp", ""))
    return metas


def list_runs(kind=None):
    """All saved runs as meta dicts (kind='backtest'|'wfo'|'anchored' to filter), oldest first."""
    metas = _all_metas()
    if kind:
        metas = [m for m in metas if m.get("kind", "backtest") == kind]
    return metas


def _rebuild_index():
    """Rebuild runs/index.json + runs/RUNS.md across BOTH backtests and WFO runs."""
    metas = _all_metas()
    json.dump(metas, open(os.path.join(RUNS_DIR, "index.json"), "w"), indent=2)

    def _pct(v):
        return "n/a" if v is None else f"{v * 100:+.0f}%"

    def _num(v):
        return "n/a" if v is None else f"{v:.2f}"

    def _changed(ch):
        if ch is None:
            return "first run"
        parts = [f"{k} {v[0]}->{v[1]}" for k, v in ch["changed"].items()]
        parts += [f"+{k}" for k in ch["added"]] + [f"-{k}" for k in ch["removed"]]
        return ", ".join(parts) or "no change"

    lines = ["# Runs registry", "",
             "| run | type | when | strategy | result | detail |",
             "|---|---|---|---|---|---|"]
    for r in metas:
        bt = r.get("backtest_type", "Backtest")
        h = r.get("headline", {})
        if r.get("kind") in ("wfo", "anchored"):
            result = (f"OOS {_pct(h.get('oos_total_return'))} · "
                      f"sharpe {_num(h.get('oos_sharpe'))} · "
                      f"win {_pct(h.get('oos_win_rate')).lstrip('+')}")
            detail = (f"optimize {r.get('objective')} · train {r.get('train_days')}d/"
                      f"test {r.get('test_days')}d · {r.get('n_windows')}win · "
                      f"{r.get('n_configs')}cfg")
        else:
            result = (f"{_pct(h.get('total_return'))} · sharpe {_num(h.get('sharpe'))} · "
                      f"win {_pct(h.get('win_rate')).lstrip('+')}")
            detail = _changed(r.get("config_diff"))
        lines.append(f"| {r['name']} | {bt} | {r.get('timestamp','')} | "
                     f"{r.get('strategy','')} | {result} | {detail} |")
    open(os.path.join(RUNS_DIR, "RUNS.md"), "w", encoding="utf-8").write("\n".join(lines))


def _resolve_dir(ref):
    """Locate a run directory from a meta dict, relative path, absolute path, or bare name."""
    if isinstance(ref, dict):
        ref = ref.get("path") or ref.get("name")
    ref = str(ref)
    for cand in (ref, os.path.join(RUNS_DIR, ref)):
        if os.path.isdir(cand):
            return cand
    base = os.path.basename(ref)               # legacy/bare name: search the tree
    for m in _all_metas():
        if m["name"] == base:
            return os.path.join(RUNS_DIR, m["path"])
    raise FileNotFoundError(f"no run found for {ref!r}")


def load_run(run_id):
    """Load a saved BACKTEST run's artifacts back into memory for research."""
    d = _resolve_dir(run_id)
    return dict(meta=json.load(open(os.path.join(d, "meta.json"))),
                config=json.load(open(os.path.join(d, "config.json"))),
                metrics=json.load(open(os.path.join(d, "metrics.json"))),
                trades=pd.read_parquet(os.path.join(d, "trades.parquet")),
                equity=pd.read_parquet(os.path.join(d, "equity.parquet")),
                dir=d)
