"""
Standalone NQ chart viewer — TradingView lightweight-charts, just the chart.

Independent of webui/ (the full Analyzer). No strategies, no runs, no side panels.
20 years of data stay smooth because the browser only pulls small windows and the
server slices a cached numpy store (see datastore/store.py) — not full parquet.

Run:
  python tv_chart/serve.py            # serves + opens browser at 127.0.0.1:8790
  python tv_chart/serve.py --no-open  # serve only
  python tv_chart/serve.py --warm     # pre-build every timeframe cache first
"""
import os
import sys
import threading
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # algoproj/
sys.path.insert(0, ROOT)
from algokit.data import TF
from tv_chart.datastore import store, indseries

HOST, PORT = "127.0.0.1", 8790
HERE = os.path.dirname(os.path.abspath(__file__))
SR_DIR = os.path.join(ROOT, "strategy research")   # each strategy keeps its own findings/ folder
CHUNK_MAX = 20000  # safety cap on a single request

app = Flask(__name__, static_folder=HERE, static_url_path="")


@app.route("/")
def index():
    return send_from_directory(HERE, "chart.html")


@app.route("/timeframes")
def timeframes():
    order = ["1m", "5m", "15m", "60m", "1d"]
    return jsonify([t for t in order if t in TF])


@app.route("/meta")
def meta():
    return jsonify(store.meta(request.args.get("tf", "5m")))


@app.route("/candles")
def candles():
    """Most recent `count` bars of a timeframe."""
    tf = request.args.get("tf", "5m")
    count = min(int(request.args.get("count", 3000)), CHUNK_MAX)
    return jsonify({"tf": tf, "candles": store.latest(tf, count)})


@app.route("/candles/before")
def candles_before():
    """`count` bars immediately older than epoch-second cursor `ts` (left-paging)."""
    tf = request.args.get("tf", "5m")
    ts = int(request.args["ts"])
    count = min(int(request.args.get("count", 3000)), CHUNK_MAX)
    return jsonify({"tf": tf, "candles": store.before(tf, ts, count)})


@app.route("/candles/after")
def candles_after():
    """`count` bars immediately newer than epoch-second cursor `ts` (right-paging)."""
    tf = request.args.get("tf", "5m")
    ts = int(request.args["ts"])
    count = min(int(request.args.get("count", 3000)), CHUNK_MAX)
    return jsonify({"tf": tf, "candles": store.after(tf, ts, count)})


@app.route("/candles/around")
def candles_around():
    """`count` bars centered on epoch-second `ts` (snapping to a finding)."""
    tf = request.args.get("tf", "5m")
    ts = int(request.args["ts"])
    count = min(int(request.args.get("count", 600)), CHUNK_MAX)
    return jsonify({"tf": tf, "candles": store.around(tf, ts, count)})


@app.route("/indicators")
def indicators_list():
    """Every registered indicator's spec (name, label, default params, lines)."""
    return jsonify(indseries.specs())


@app.route("/indicator")
def indicator_series():
    """Indicator line values for a timeframe over [from, to] epoch seconds.

    Query: tf, name, from, to, plus any param overrides (e.g. n, k)."""
    tf = request.args.get("tf", "5m")
    name = request.args["name"]
    t0, t1 = int(request.args["from"]), int(request.args["to"])
    reserved = {"tf", "name", "from", "to"}
    params = {k: v for k, v in request.args.items() if k not in reserved}
    return jsonify({"name": name, "lines": indseries.window(tf, name, params, t0, t1)})


@app.route("/findings")
def findings_list():
    """Discover findings inside each strategy's own folder: strategy research/<strat>/findings/*.json"""
    out = []
    for p in glob.glob(os.path.join(SR_DIR, "*", "findings", "*.json")):
        rel = os.path.relpath(p, SR_DIR).replace(os.sep, "/")
        strat = rel.split("/")[0]
        name = os.path.splitext(os.path.basename(p))[0]
        out.append({"id": rel, "label": f"{strat} / {name}"})
    return jsonify(sorted(out, key=lambda x: x["label"]))


@app.route("/findings/<path:fid>")
def findings_get(fid):
    return send_from_directory(SR_DIR, fid)


def _free_port(port):
    """Kill any process already listening on `port` so the instance we're about to
    start is the only server — prevents stale servers from serving old code."""
    import subprocess
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return
    me = os.getpid()
    pids = set()
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 5 and p[0] == "TCP" and p[-2] == "LISTENING" \
                and p[1].endswith(f":{port}") and p[-1].isdigit() and int(p[-1]) != me:
            pids.add(p[-1])
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", pid, "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"freed port {port}: terminated stale server (PID {pid})")
        except Exception:
            pass


def main():
    _free_port(PORT)
    if "--warm" in sys.argv:
        print("warming caches…")
        store.warm()
        print("done.")
    url = f"http://{HOST}:{PORT}"
    if "--no-open" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Standalone chart at {url}")
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
