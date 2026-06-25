"""
Notebook helpers: make `algokit` importable from notebooks/, and small display
utilities (inline lightweight-charts, PNGs, stat tables). Import this first in
any notebook:  `import nbtools as nb`.
"""
import os
import sys

# make algoproj/ importable so `import algokit` / `import config` work from notebooks/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from IPython.display import IFrame, Image, display, HTML  # noqa: E402

from algokit import metrics as _metrics  # noqa: E402


def metrics_table(d):
    """Stats dict -> tidy DataFrame [metric | value | what it means] (shared map)."""
    return pd.DataFrame([(k, _metrics.fmt(k, v), _metrics.EXPLAIN.get(k, "")) for k, v in d.items()],
                        columns=["metric", "value", "what it means"])


def attribution_plot(tr):
    """4-panel winners-vs-losers breakdown from a saved trade log."""
    import matplotlib.pyplot as plt
    tr = tr.copy(); tr["win"] = tr["ret"] > 0; tr["result"] = np.where(tr["win"], "win", "loss")
    base = tr["win"].mean() * 100; days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    wh = tr.groupby("hour_et")["win"].mean() * 100
    ax[0,0].bar(wh.index, wh.values, color="#2dd4bf"); ax[0,0].axhline(base, color="k", ls="--", lw=1)
    ax[0,0].set_title("Win rate by hour (ET)"); ax[0,0].set_ylabel("win %")
    wd = tr.groupby("dow")["win"].mean() * 100
    ax[0,1].bar([days[i] for i in wd.index], wd.values, color="#2dd4bf"); ax[0,1].axhline(base, color="k", ls="--", lw=1)
    ax[0,1].set_title("Win rate by day of week"); ax[0,1].set_ylabel("win %")
    br = tr.groupby("reason").agg(win=("win","mean"), n=("win","size"))
    ax[1,0].bar(br.index, br["win"]*100, color="#26a69a"); ax[1,0].axhline(base, color="k", ls="--", lw=1)
    ax[1,0].set_title("Win rate by exit reason"); ax[1,0].set_ylabel("win %")
    for i,(_,row) in enumerate(br.iterrows()): ax[1,0].text(i, row["win"]*100+1, f"n={int(row['n'])}", ha="center")
    rm = tr.groupby("result")[["bull15","consol15","bull1d"]].mean()
    rm.T.plot(kind="bar", ax=ax[1,1], color={"loss":"#ef5350","win":"#26a69a"})
    ax[1,1].set_title("Avg regime score at ENTRY: win vs loss"); ax[1,1].set_ylabel("score 0-100")
    plt.tight_layout(); plt.show()


def show_chart(path, height=620):
    """Embed a lightweight-charts HTML file inline (served by the Jupyter server).
    Pass the absolute path; rendered relative to the notebook's cwd."""
    rel = os.path.relpath(path, os.getcwd()).replace(os.sep, "/")
    return IFrame(rel, width="100%", height=height)


def show_png(path, width=1000):
    return Image(filename=path, width=width)


def stats_table(d, value_name="value"):
    """Render a dict (or dict-of-dicts) of stats as a tidy DataFrame."""
    if d and isinstance(next(iter(d.values())), dict):
        return pd.DataFrame(d).T
    return pd.DataFrame({value_name: pd.Series(d)})
