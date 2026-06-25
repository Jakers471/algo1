"""
Characterize the MA-slope regime on NQ daily and find the
trend -> pullback -> compression/coil -> volume-spike breakout -> trend pattern.

Outputs:
  1) prints frequency of each condition + an EDGE TEST on detected breakouts
  2) saves nq_slope_heatmap.png  (price+MAs, slope heatmap, compression+volume)

Data + fan/slope/spread come from algokit; scan + plotting stay local.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # reach algoproj/
from config import OUTPUT_DIR
from algokit.data import load_tf
from algokit.indicators import fan, slope_pct, ma_spread

L = 10            # slope lookback (bars)
MAS = [20, 50, 100, 200]

df = load_tf("1d")
dt = df.index.normalize()
close = df["close"]; high = df["high"]; low = df["low"]; vol = df["volume"]

ma = fan(close, MAS)
slope = {n: slope_pct(ma[n], L) for n in MAS}                    # % over L bars

# --- regime conditions ---
import pandas as pd
all_up = pd.concat([slope[n] > 0 for n in MAS], axis=1).all(axis=1)
spread = ma_spread([ma[n] for n in MAS], close)                  # MA spread %
compressed = spread < spread.rolling(252).quantile(0.20)          # coiled vs past year
vol_spike = vol > 1.5 * vol.rolling(20).mean()
breakout = close > high.rolling(20).max().shift(1)                 # break 20-day high
uptrend = close > ma[200]

# --- full pattern: trend recently up, MAs coiled recently, breakout with a
# volume spike nearby (same bar or just before), all in an uptrend ---
recent_trend = all_up.rolling(60).max().astype(bool)              # strong uptrend in last 60
recent_coil = compressed.rolling(15).max().astype(bool)           # coiled within last 15 bars
vol_recent = vol_spike.rolling(3).max().astype(bool)              # volume spike within last 3 bars
signal = recent_trend & recent_coil & vol_recent & breakout & uptrend
signal = signal.fillna(False)

print("NQ daily %d bars  %s -> %s" % (len(close), dt[0].date(), dt[-1].date()))
print("\n=== condition frequencies (% of bars) ===")
for name, s in [("all MAs upsloping", all_up), ("MAs compressed (coil)", compressed),
                ("volume spike", vol_spike), ("20-day breakout", breakout),
                ("price>200MA (uptrend)", uptrend), ("FULL PATTERN signal", signal)]:
    print("  %-26s %5.1f%%   (%d bars)" % (name, s.mean()*100, int(s.sum())))

# --- edge test: forward return after the FULL PATTERN signal ---
H = 10
fwd = close.shift(-H) / close - 1.0
sig_dates = close.index[signal.to_numpy()]
after = fwd.reindex(sig_dates).dropna()
base = fwd.dropna()
print("\n=== EDGE TEST: %d-day forward return after FULL PATTERN ===" % H)
print("  signals: %d" % len(after))
print("  after signal: %+.2f%%  (win %.0f%%)" % (after.mean()*100, (after>0).mean()*100))
print("  baseline:     %+.2f%%  (win %.0f%%)" % (base.mean()*100, (base>0).mean()*100))
edge = (after.mean()-base.mean())*100
print("  EDGE: %+.2f%% per %d days -> %s" % (edge, H, "HAS EDGE" if edge > 0.05 else "no real edge"))

# ----------------- visualization -----------------
x = mdates.date2num(dt.to_pydatetime())
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1.4, 1.4]})

# panel 1: price + MAs + signal markers
ax1.semilogy(x, close, color="black", lw=0.8, label="NQ close")
for n, col in zip(MAS, ["tab:blue", "tab:green", "tab:orange", "tab:red"]):
    ax1.semilogy(x, ma[n], lw=0.9, label=f"MA{n}", color=col)
sx = x[signal.to_numpy()]
ax1.scatter(sx, close[signal.to_numpy()], marker="^", s=70, color="magenta",
            zorder=5, label="pattern breakout")
ax1.set_title("NQ — trend / pullback / coil / volume-breakout scanner"); ax1.legend(loc="upper left", ncol=3, fontsize=8)

# panel 2: slope heatmap (rows = MAs, green=up / red=down)
M = np.vstack([slope[n].to_numpy() for n in MAS])
im = ax2.imshow(M, aspect="auto", cmap="RdYlGn", vmin=-3, vmax=3,
                extent=[x[0], x[-1], 0, 4], origin="lower", interpolation="nearest")
ax2.set_yticks([0.5, 1.5, 2.5, 3.5]); ax2.set_yticklabels([f"MA{n}" for n in MAS])
ax2.set_ylabel("slope %")
fig.colorbar(im, ax=ax2, orientation="vertical", pad=0.01, fraction=0.025, label=f"slope % per {L} bars")

# panel 3: MA compression (spread) + volume spikes
ax3.fill_between(x, 0, spread, color="steelblue", alpha=0.5, label="MA spread % (low=coiled)")
ax3.scatter(x[vol_spike.fillna(False).to_numpy()],
            np.full(vol_spike.fillna(False).sum(), spread.min()),
            marker="|", color="purple", alpha=0.3, label="volume spike")
ax3.set_ylabel("MA spread %"); ax3.legend(loc="upper right", fontsize=8)
ax3.xaxis.set_major_locator(mdates.YearLocator(2)); ax3.xaxis_date()

plt.tight_layout()
out = os.path.join(OUTPUT_DIR,"nq_slope_heatmap.png")
plt.savefig(out, dpi=110); plt.close()
print("\nSAVED:", out)
