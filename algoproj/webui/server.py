"""
Flask API + static host for the algoproj quant Analyzer, launched in a PyWebView window.

This is a presentation-layer rewrite of the Streamlit app (app/) — it reuses the SAME
engine (algokit, strategies, runs, wfo, validation, significance) and exposes it as JSON
so a vanilla-JS + ECharts dark dashboard can drive it. No analytics logic lives here.

Run:
  python -m webui.server          desktop window (PyWebView)
  python -m webui.server --web    serve only, open http://127.0.0.1:8780 in a browser
"""
from __future__ import annotations

import importlib
import os
import sys
import threading

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # reach algoproj/

import pandas as pd

from algokit import runs, wfo, validation, params
import strategies  # noqa: F401
import pkgutil

HOST = "127.0.0.1"
PORT = 8780
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

# ---- small caches so repeat chart/validation loads + WFO grids stay snappy ----
_ARR_CACHE: dict = {}     # (strategy, items) -> wfo arrays
_BUILD_CACHE: dict = {}   # path -> re-run result (for chart candles)


def _strategy_names():
    return [m.name for m in pkgutil.iter_modules(strategies.__path__) if not m.name.startswith("_")]


def _run_arrays(strategy, overrides):
    key = (strategy, tuple(sorted(overrides.items())))
    if key not in _ARR_CACHE:
        strat = importlib.import_module(f"strategies.{strategy}")
        _ARR_CACHE[key] = wfo.arrays_from_result(strat.run(**overrides))
    return _ARR_CACHE[key]


def _result_for(path):
    """Re-run a saved backtest's config to get build arrays (for candle charts)."""
    if path not in _BUILD_CACHE:
        cfg = runs.load_run(path)["config"]
        strat = importlib.import_module(f"strategies.{runs.load_run(path)['meta']['strategy']}")
        _BUILD_CACHE[path] = strat.run(cfg=cfg)
    return _BUILD_CACHE[path]


# ============================ static ============================
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ============================ catalog ============================
@app.route("/api/strategies")
def api_strategies():
    out = []
    for name in _strategy_names():
        default = dict(importlib.import_module(f"strategies.{name}").DEFAULT)
        signal, execp = params.split_params(default)
        sweepable = [k for k, v in signal.items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool)]
        out.append(dict(name=name, default=default, signal=list(signal),
                        execution=list(execp), sweepable=sweepable))
    return jsonify(out)


@app.route("/api/date-range")
def api_date_range():
    from algokit.data import load_tf
    idx = load_tf(request.args.get("ltf", "15m")).index
    return jsonify([str(idx[0].date()), str(idx[-1].date())])


# ============================ registry ============================
@app.route("/api/runs")
def api_runs():
    return jsonify(runs.list_runs(request.args.get("kind") or None))


@app.route("/api/run")
def api_run():
    path = request.args["path"]
    d = os.path.join(runs.RUNS_DIR, path)
    import json
    out = {"meta": json.load(open(os.path.join(d, "meta.json"))),
           "config": json.load(open(os.path.join(d, "config.json")))}
    for f in ("metrics", "analysis", "settings", "result"):
        p = os.path.join(d, f + ".json")
        if os.path.exists(p):
            out[f] = json.load(open(p))
    if os.path.exists(os.path.join(d, "steps.json")):
        out["steps"] = json.load(open(os.path.join(d, "steps.json")))
    return jsonify(out)


@app.route("/api/run/equity")
def api_run_equity():
    path = request.args["path"]
    eq = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "equity.parquet")).set_index("time")
    daily = eq.resample("1D").last().dropna(subset=["equity"])
    out = {"dates": [str(d.date()) for d in daily.index],
           "equity": daily["equity"].round(2).tolist(),
           "pct": (daily["equity"] / daily["equity"].iloc[0] * 100 - 100).round(2).tolist()}
    if "bench_equity" in daily:
        out["bench_pct"] = (daily["bench_equity"] / daily["bench_equity"].iloc[0] * 100 - 100).round(2).tolist()
    return jsonify(out)


@app.route("/api/run/trades")
def api_run_trades():
    path = request.args["path"]
    tr = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "trades.parquet"))
    tr = tr.copy()
    tr["entry"] = tr["entry"].astype(str)
    tr["exit"] = tr["exit"].astype(str)
    return jsonify(tr.to_dict("records"))


@app.route("/api/run/chart")
def api_run_chart():
    """Candles + order markers for a backtest run (windowed on the trades)."""
    path = request.args["path"]
    r = _result_for(path)
    b, res = r["build"], r["res"]
    idx, trades = b["idx"], res["trades"]
    n = len(b["c"])
    if trades:
        entries = sorted(t["entry_i"] for t in trades)
        last = max(t["exit_i"] for t in trades)
        s = max(b["start"], entries[-min(60, len(entries))] - 200)
        e = min(n, last + 200)
        if e - s > 40000:
            s = max(b["start"], e - 40000)
    else:
        s, e = max(b["start"], n - 40000), n
    candles = [[str(idx[i]), float(b["o"][i]), float(b["c"][i]), float(b["l"][i]), float(b["h"][i])]
               for i in range(s, e)]
    marks = []
    for t in trades:
        if s <= t["entry_i"] < e:
            marks.append({"t": str(idx[t["entry_i"]]), "side": "buy"})
        if s <= t["exit_i"] < e:
            marks.append({"t": str(idx[t["exit_i"]]), "side": "sell", "reason": t["reason"]})
    return jsonify({"candles": candles, "marks": marks})


@app.route("/api/run/validation")
def api_run_validation():
    """Recompute in-sample/out-of-sample at an arbitrary split (fraction or date)."""
    path = request.args["path"]
    split = request.args.get("split", "0.70")
    try:
        split = float(split)
    except ValueError:
        pass
    eq = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "equity.parquet"))
    tr = pd.read_parquet(os.path.join(runs.RUNS_DIR, path, "trades.parquet"))
    idx = pd.DatetimeIndex(eq["time"])
    rets = eq["ret"].to_numpy(float)
    inmkt = eq["in_market"].to_numpy()
    ent = idx.searchsorted(pd.DatetimeIndex(tr["entry"]))
    ext = idx.searchsorted(pd.DatetimeIndex(tr["exit"]))
    trades = [dict(entry_i=int(a), exit_i=int(b), ret=float(r), pnl=float(p))
              for a, b, r, p in zip(ent, ext, tr["ret"], tr["pnl"])]
    days = (idx[-1] - idx[0]).days or 1
    ppy = len(rets) / (days / 365.25)
    ios = validation.in_out_sample(rets, trades, inmkt, idx, ppy, split=split)
    ios["in_pct"] = round(ios["split_bar"] / len(idx) * 100, 1)
    return jsonify(runs._jsonify(ios))


# ============================ run / optimize ============================
@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    d = request.get_json(force=True)
    strat = importlib.import_module(f"strategies.{d['strategy']}")
    result = strat.run(**d.get("overrides", {}))
    run_dir, meta = runs.save_run(result, d["strategy"])
    return jsonify(meta)


@app.route("/api/wfo", methods=["POST"])
def api_wfo():
    d = request.get_json(force=True)
    strat_name = d["strategy"]
    base = {**importlib.import_module(f"strategies.{strat_name}").DEFAULT, **d.get("overrides", {})}
    specs = {k: tuple(v) for k, v in d.get("specs", {}).items()}
    run_fn = lambda ov: _run_arrays(strat_name, {**d.get("overrides", {}), **ov})
    res = wfo.optimize(run_fn, specs, objective=d.get("objective", "sharpe"),
                       train_days=int(d.get("train_days", 1095)),
                       test_days=int(d.get("test_days", 365)),
                       anchored=bool(d.get("anchored", False)),
                       start_date=d.get("start_date"), end_date=d.get("end_date"))
    settings = {"specs": specs, "objective": d.get("objective", "sharpe"),
                "train_days": int(d.get("train_days", 1095)),
                "test_days": int(d.get("test_days", 365)), "anchored": bool(d.get("anchored", False)),
                "backtest_type": d.get("mode", "Walk-Forward Optimization"),
                "start_date": d.get("start_date"), "end_date": d.get("end_date")}
    run_dir, meta = runs.save_wfo(res, strat_name, base, settings)
    return jsonify({"meta": meta, "result": runs._jsonify(res)})


def _run_server():
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


def main():
    url = f"http://{HOST}:{PORT}"
    if "--web" in sys.argv:
        print(f"Serving at {url}")
        _run_server()
        return
    try:
        import webview
    except ImportError:
        print(f"pywebview not installed; serving in browser mode. Open {url}")
        _run_server()
        return
    threading.Thread(target=_run_server, daemon=True).start()
    webview.create_window("algoproj - Quant Analyzer", url, width=1480, height=940,
                          min_size=(1100, 720), background_color="#0a0e13")
    webview.start()


if __name__ == "__main__":
    main()
