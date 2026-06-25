"""
Run a backtest and save it as a numbered run in runs/.

Usage:
    python run_backtest.py                 # run with the strategy's default config
    python run_backtest.py --open          # also pop the chart open in a browser
    python run_backtest.py X=60 exit_th=25 # override config params on the fly

Each run is saved machine-readable (config/metrics/trades/equity/meta) with an
auto config-diff vs the previous run; see runs/RUNS.md for the registry.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategies import fanning_mtf
from algokit import runs


def _parse_overrides(args):
    ov = {}
    for a in args:
        if a == "--open" or "=" not in a:
            continue
        k, v = a.split("=", 1)
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        ov[k] = v
    return ov


if __name__ == "__main__":
    overrides = _parse_overrides(sys.argv[1:])
    result = fanning_mtf.run(**overrides)
    d, meta = runs.save_run(result, fanning_mtf.NAME)

    h = meta["headline"]
    if meta.get("unchanged"):
        print(f"\nUNCHANGED — config matches {meta['name']}, no new run created")
    else:
        print(f"\nSAVED {meta['name']}  (parent: {meta['parent']})")
        if meta["config_diff"] and meta["config_diff"]["changed"]:
            print("  changed:", meta["config_diff"]["changed"])
    print(f"  net {h['total_return']*100:+.0f}%  CAGR {h['cagr']*100:+.1f}%  "
          f"Sharpe {h['sharpe']:.2f}  maxDD {h['max_drawdown']*100:.0f}%  "
          f"trips {int(h['round_trips'])}  win {h['win_rate']*100:.0f}%")
    print(f"  artifacts -> {d}")

    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open("file:///" + os.path.join(d, "chart.html").replace("\\", "/"))
