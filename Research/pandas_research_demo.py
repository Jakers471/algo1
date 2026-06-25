"""
RESEARCH PIPELINE (local, pure-Python) on the REAL Lean data.
Same workflow QuantBook gives you: history -> dataframe -> indicators -> plot -> signals.
"""
import os, zipfile, io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = r"C:\Users\jakers\AppData\Local\Temp\claude\C--Users-jakers-Desktop-algo\d075bf1d-9d3d-405b-8bb6-28ad6fe66dc9\scratchpad"
ZIP = r"C:\Users\jakers\Desktop\algo\Data\equity\usa\daily\spy.zip"

# --- 1) HISTORY REQUEST: read Lean's daily file into a DataFrame ---
with zipfile.ZipFile(ZIP) as z:
    raw = z.read(z.namelist()[0]).decode()
cols = ["time", "open", "high", "low", "close", "volume"]
df = pd.read_csv(io.StringIO(raw), header=None, names=cols)
df["time"] = pd.to_datetime(df["time"], format="%Y%m%d %H:%M")
# Lean stores equity prices scaled x10000 -> convert to dollars
for c in ["open", "high", "low", "close"]:
    df[c] = df[c] / 10000.0
df = df.set_index("time")

print("=== SPY HISTORY (the 'data request') ===")
print("rows:", len(df), "| range:", df.index.min().date(), "->", df.index.max().date())
print(df[["close"]].describe().round(2).to_string())

# --- 2) INDICATORS (same ones QuantBook exposes) ---
df["SMA20"] = df["close"].rolling(20).mean()
df["SMA50"] = df["close"].rolling(50).mean()
mid = df["close"].rolling(30).mean()
sd = df["close"].rolling(30).std()
df["BB_upper"] = mid + 2 * sd
df["BB_mid"] = mid
df["BB_lower"] = mid - 2 * sd

# --- 3) SIGNAL RESEARCH: find moving-average crossovers ---
above = df["SMA20"] > df["SMA50"]
cross_up = above & ~above.shift(1).fillna(False)
cross_dn = ~above & above.shift(1).fillna(False)
print("\n=== RESEARCH FINDING: SMA20/SMA50 crossovers ===")
print("bullish crossovers (buy signals):", int(cross_up.sum()))
print("bearish crossovers (sell signals):", int(cross_dn.sum()))
print("most recent 3 bullish signals:")
print(df.index[cross_up][-3:].strftime("%Y-%m-%d").tolist())

# --- 4) PLOT 1: last 2 years, price + bollinger bands ---
recent = df.loc["2019":"2021"]
ax = recent[["close", "BB_upper", "BB_mid", "BB_lower"]].plot(
    figsize=(12, 5), title="SPY + Bollinger Bands (2019-2021) — research view")
ax.set_ylabel("price ($)")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "research_1_bollinger.png"), dpi=110); plt.close()

# --- 5) PLOT 2: price with the two moving averages + crossover markers ---
fig, ax = plt.subplots(figsize=(12, 5))
recent["close"].plot(ax=ax, label="SPY close", color="black", lw=1)
recent["SMA20"].plot(ax=ax, label="SMA20 (fast)", color="tab:blue")
recent["SMA50"].plot(ax=ax, label="SMA50 (slow)", color="tab:orange")
ax.scatter(recent.index[cross_up.loc["2019":"2021"]],
           recent["close"][cross_up.loc["2019":"2021"]], marker="^", color="green", s=90, label="BUY")
ax.scatter(recent.index[cross_dn.loc["2019":"2021"]],
           recent["close"][cross_dn.loc["2019":"2021"]], marker="v", color="red", s=90, label="SELL")
ax.set_title("SPY moving-average crossover strategy — research signals (2019-2021)")
ax.set_ylabel("price ($)"); ax.legend()
plt.tight_layout(); plt.savefig(os.path.join(OUT, "research_2_crossover.png"), dpi=110); plt.close()

print("\nSAVED: research_1_bollinger.png, research_2_crossover.png")
print("RESEARCH DEMO DONE")
