"""
serve — the tiny local server that makes the chart's "Run Backtest" button real.

A browser file:// page can't launch Python. So this serves the simplicity folder over http://localhost
and exposes ONE endpoint the chart calls:

  POST /run  {start, end, source}  ->  runs backtest/run_backtest.py with those dates (env override) +
                                       research/chart/build_trades.py, then returns the run_id + the URLs
                                       of that run's report + the trade-replay page.

Everything else is static file serving (same origin, so the chart's fetch has no CORS issue). Start it with
run_chart.bat (or `py serve.py`); it opens the chart in your browser. Ctrl-C to stop.
"""
import os
import re
import sys
import json
import subprocess
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("SIMP_PORT", "8765"))
CHART_URL = f"http://localhost:{PORT}/research/chart/chart.html"


def _run(start, end, source):
    """Run the backtest (dates via env) + rebuild the trade-replay data. Returns (run_id, source, log)."""
    env = os.environ.copy()
    env["SIMP_BT_START"] = start or ""
    env["SIMP_BT_END"] = end or ""
    args = [sys.executable, os.path.join("backtest", "run_backtest.py"), "chart-run"]
    if source == "strategy":
        args.append("--real")
    p = subprocess.run(args, cwd=HERE, env=env, capture_output=True, text=True)
    log = p.stdout + p.stderr
    m = re.search(r"RESULT (\S+) (\S+)", p.stdout)
    if not m:
        return None, None, log
    run_id, src = m.group(1), m.group(2)
    # rebuild the trade-replay export so the replay page reflects THIS run
    subprocess.run([sys.executable, os.path.join("research", "chart", "build_trades.py")],
                   cwd=HERE, capture_output=True, text=True)
    return run_id, src, log


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass  # quiet

    def do_POST(self):
        if self.path.rstrip("/") != "/run":
            self.send_error(404); return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception:
            body = {}
        start, end = body.get("start") or "", body.get("end") or ""
        source = "strategy" if body.get("source") == "strategy" else "research"
        print(f"[serve] run backtest  source={source}  window={start or 'era'}..{end or 'latest'}")
        try:
            run_id, src, log = _run(start, end, source)
        except Exception as e:
            run_id, src, log = None, None, str(e)
        if run_id:
            out = {"ok": True, "run_id": run_id, "source": src,
                   "report": f"/research/runs/reports/{src}/{run_id}/report.html",
                   "replay": "/research/chart/trade_replay.html"}
            print(f"[serve]   -> {src}/{run_id}")
        else:
            out = {"ok": False, "error": "backtest produced no result", "log": log[-1500:]}
            print("[serve]   -> FAILED\n" + (log[-1500:] if log else ""))
        b = json.dumps(out).encode()
        self.send_response(200 if run_id else 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def main():
    os.chdir(HERE)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"simplicity chart server -> {CHART_URL}\n(Ctrl-C to stop)")
    try:
        webbrowser.open(CHART_URL)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
