# 01 - Quant Researcher findings: walk-forward testing

Role: Quant Researcher. Input: the literature + our codebase. Output for: the Data Scientist.

---

## 0. TL;DR (the root cause)

**We are comparing the wrong two things.** Our walk-forward result compares the honest stitched
**out-of-sample (OOS)** result against a **"best-on-full-history"** config. That is NOT the
industry-standard frame, and it is exactly why we keep getting confused (and why the two equity
curves cover different spans).

**The standard frame is In-Sample (IS) vs Out-of-Sample (OOS)**, summarized by **Walk-Forward
Efficiency (WFE) = OOS return / IS return**, computed **per window** and aggregated. Every
serious source and platform (Pardo, TradeStation, Build Alpha, Unger) frames it this way.

Concretely, we must:
1. For each window, record the chosen config's performance on **its own training (IS) window**,
   not just the objective score we used to pick it.
2. Compare **IS vs OOS** per window and overall (WFE), with the negative-IS caveat handled.
3. Keep "best-on-full" only as an optional, clearly-labeled overfit *ceiling* computed over the
   **same span** as OOS - or drop it. It is not the primary comparison.

This single reframe fixes the apples-to-oranges span bug and aligns us with how this is actually
done.

---

## 1. Theory - how walk-forward actually works

Walk-forward analysis is the "gold standard" for strategy validation. The loop:

1. **Optimize** parameters on the first **in-sample (training)** window.
2. **Test** those exact parameters on the **next, unseen out-of-sample (test)** window.
3. **Advance** the window forward and repeat to the end of history.
4. **Concatenate** the test-window results into one **master OOS equity curve** - the realistic
   performance estimate. ("By combining these out-of-sample period results, we create a more
   realistic assessment.")

Key correctness properties: parameters are always chosen on *past* data and graded on *future*
unseen data, so there is no look-ahead bias, and you get *many* IS/OOS pairs instead of one
(more statistical confidence). [Quantreo; QuantInsti; Wikipedia]

A passing walk-forward is a **candidate for further testing, not a deploy signal**. "Positive
OOS Sharpe doesn't mean the strategy works. It means it worked in that particular walk-forward
configuration." [Susan Potter; Quanthop]

---

## 2. Anchored vs Rolling (these are genuinely different - never mix them)

| | Rolling | Anchored |
| --- | --- | --- |
| Train window | **fixed length**, slides forward | **start pinned**, grows each step |
| Sees | only recent lookback | all history to date |
| Best when | market **drifts** (non-stationary); intraday | edge is **persistent**; few/weekly bars; want max data |
| Character | more **conservative**, the common default | more stable estimates, slower to adapt |

"Rolling is the more conservative choice and the more common default... If you are unsure, start
with rolling." For **intraday** models (ours is 15m) rolling is generally preferred; anchored
suits longer bars / wanting the full history. [Unger Academy; Sahm Capital; Susan Potter]

Our engine implements both correctly (verified earlier: rolling slides `train_lo`, anchored pins
it). Good - just keep them in separate buckets (we now do).

---

## 3. The standard interpretation framework (what we're missing)

### 3a. Walk-Forward Efficiency (WFE) - the headline number
**Definition:** the ratio of the **annualized OOS return to the annualized IS return**.
> TradeStation: "a comparison of annualized rates of return for the in-sample and out-of-sample
> results"; "50% or more is considered a successful walk-forward analysis."

Thresholds (consensus): **> 70% excellent**, **50-70% good** (typical for solid strategies),
**< 30% red flag / overfit**. [Kiploks; TradeStation; Quanthop]

WFE is a **process metric**, not a capital-allocation signal, and **must not be read in
isolation** - pair it with drawdown consistency, profit-factor stability, and win-rate
variability across windows.

**Pitfall we will hit:** WFE is a ratio, so it **breaks down when IS return is negative or near
zero** (ratio meaningless / explosive). Our strategy *does* produce weak/negative windows, so we
must guard this: report WFE only when IS return is meaningfully positive, otherwise fall back to
**OOS Retention** (how much of the IS result carried into the paired OOS, in absolute/relative
terms) and flag the window. [Kiploks: OOS Retention vs WFE]

### 3b. Per-window IS vs OOS (the unit of analysis)
The atomic comparison is, for each window: **IS metrics (chosen config on its train slice)** vs
**OOS metrics (same config on its test slice)**. From these you get WFE per window and can see
*where* the edge decays. We currently store the train **objective score** and the OOS metrics,
but **not the full IS metrics** of the chosen config - so we cannot compute WFE or show IS-vs-OOS
per window. This is the core missing data.

### 3c. Consistency / robustness across windows (not just the average)
Report and eyeball across windows: **max-drawdown consistency, profit-factor stability,
win-rate variability, # trades per window**. "A strategy with high WFE but wildly fluctuating
drawdowns across periods may indicate fragility despite good average performance." [Kiploks]

### 3d. A concrete validity guard
TradeStation invalidates a walk-forward if "any unusually large win, winning run, or winning
time period contributes more than 50% of total net profit." Cheap to compute, catches
lottery-ticket curves. We don't do this.

### 3e. Parameter stability (we already have this - keep it)
"A parameter that jumps from 12 to 47 to 23 to 35 to 55 to 13 is most likely curve fitting."
Stable picks across windows = robustness. We compute this; good.

---

## 4. What professional platforms report (the display standard)

- **Combined OOS master equity curve** (top) **+ per-window breakdown** of each test period.
  [Build Alpha] - we have the stitched curve; we lack the per-window breakdown.
- **WFE** (IS vs OOS annualized return). - missing.
- Per-window **distribution of profit / loss / trades**, **R/R = annualized profit / max DD**,
  win rate. [TradeStation] - partly missing.
- **Parameter stability** across windows. - have it.
- A **matrix of pass/fail** across (run count x OOS %) configurations. [Build Alpha, "5x5"] -
  advanced; later.
- Methodology line: # steps, train/test lengths, purge/embargo, anchored/rolling. - have most.

Build Alpha's blunt framing is useful: **"The walk-forward process is only concerned with the
out-of-sample periods; we can completely discard the in-sample results"** for the *deployable
equity curve*. IS is used **only** to compute WFE / judge decay - not as a headline equity curve
to brag about. (This is precisely the trap our "best-on-full" curve fell into.)

---

## 5. Audit of OUR implementation

Files: `algokit/wfo.py`, `algokit/validation.py`, `algokit/runs.py (save_wfo)`,
`webui/static/js/pages/wfo.js`.

**Correct / keep:**
- Window geometry: rolling vs anchored, contiguous train/test (`train_hi == test_lo`), no overlap,
  no look-ahead - verified.
- Stitched OOS curve over the contiguous test windows. Good and standard.
- Parameter stability table. Standard.
- Train:test default 1095d:365d = **3:1**, which matches best practice (Unger ~3:1). Good.

**Wrong / root cause:**
- `wfo.optimize` builds **`full_best`** = the single config with the best score over the WHOLE
  range, and the UI compares **OOS vs best-on-full**. This is **non-standard** and conflates two
  different ideas. Worse, `full_seg` and the full equity curve were computed over **`[lo, hi]`**
  while OOS is over **`[oos_lo, hi]`** - **different spans**, so the headline numbers (e.g.
  +24.98% vs +14.64%) are not comparable (the +24.98% includes ~3 warm-up years of extra
  compounding). This is the exact bug the user caught.

**Missing data (blocks the standard view):**
- **Per-window IS metrics**: we store `train_score` (the objective only) but not the chosen
  config's full IS performance on its train slice. Needed for WFE and IS-vs-OOS per window.
- **WFE** (aggregate + per-window), with the negative-IS guard.
- **Per-window OOS equity segments** (for the per-window breakdown chart/table).
- **Consistency metrics** across windows (DD consistency, PF stability, win-rate variability).
- **Validity guard** (>50% of profit from one window/run).
- No **purge/embargo** buffer between train and test. For our 1d-gated 15m strategy the leakage
  is small (signals are causal, train/test are contiguous not overlapping), but it is technically
  absent; note it, low priority.

---

## 6. Recommendations (prioritized, tagged for the Data Scientist)

1. **[correctness bug] Reframe to IS vs OOS.** Make the primary walk-forward comparison the
   chosen config's **IS (train) vs OOS (test)** performance, summarized by **WFE**. Demote/remove
   "best-on-full." If kept, label it explicitly as an **overfit ceiling** and compute it over the
   **same span as OOS**, never the full range.

2. **[missing data] Save per-window IS metrics.** For each window, evaluate the chosen config on
   its **train slice** and store the same metric block we store for the test slice
   (return, cagr, sharpe, max_dd, win, trades, profit_factor). The engine already has the arrays;
   this is one extra `_segment` call per window in `wfo.optimize`.

3. **[missing metric] Compute WFE.** Aggregate WFE = annualized OOS return / annualized IS return
   over the stitched windows, **plus** per-window WFE. Guard against IS<=~0 (report "n/a, IS not
   positive" and/or OOS Retention instead). Surface the threshold reading (>70 / 50-70 / <30).

4. **[interpretation aid] Per-window breakdown.** A table: window | train period | IS net/sharpe |
   OOS net/sharpe | WFE | picked params. And the **per-window OOS equity segments** so the master
   curve can be decomposed.

5. **[interpretation aid] Consistency + validity flags.** Compute across windows: # positive OOS
   windows, OOS Sharpe dispersion, max-DD consistency, and the **>50%-of-profit-from-one-window**
   validity flag. Show as read-out flags.

6. **[best practice] Lock the WFO methodology per strategy.** The user's instinct is correct and
   matches the literature: re-picking window sizes/objective until OOS looks good is
   **meta-overfitting** ("you've overfit the validation procedure itself"). Fix train/test/step/
   objective once per strategy so all its WF runs are comparable and you can't fish the windows.

7. **[nice-to-have] Robustness matrix.** Later: run a small matrix of window configs (Build
   Alpha's 5x5) and show pass/fail counts. Powerful but secondary.

8. **[hygiene] Keep params few.** Enforce/flag "free params <= sqrt(train window length)" and
   "test window >= ~20-30 trades"; more params systematically lowers WFE.

---

## 7. Open questions for the human

- **Drop best-on-full entirely, or keep it as a labeled ceiling?** My recommendation: keep it,
  but renamed ("overfit ceiling"), computed over the OOS span, and visually secondary to IS-vs-OOS.
- **WFE on returns or on a risk-adjusted measure (Sharpe/CAGR)?** TradeStation uses annualized
  return; some use Sharpe. Recommend **annualized return for WFE** (the standard) and *also* show
  IS-vs-OOS Sharpe separately.
- **Lock methodology: store where?** A per-strategy `wfo_methodology.json` in the strategy's run
  folder, or in the strategy module. (Data Scientist to spec.)

---

## 8. Sources

- Quantreo - Walk Forward Optimization in trading: https://www.blog.quantreo.com/the-walk-forward-optimization-in-trading/
- Wikipedia - Walk forward optimization: https://en.wikipedia.org/wiki/Walk_forward_optimization
- Unger Academy - You may be doing it wrong: https://ungeracademy.com/posts/how-to-use-walk-forward-analysis-you-may-be-doing-it-wrong
- Susan Potter - Anchored vs Rolling mechanics: https://www.susanpotter.net/quant/walk-forward-optimization/
- QuantInsti - Walk-Forward Optimization intro: https://blog.quantinsti.com/walk-forward-optimization-introduction/
- TradeStation - Walk-Forward Summary (OOS): https://help.tradestation.com/09_01/tswfo/topics/walk-forward_summary_out-of-sample.htm
- Build Alpha - Walk Forward Optimization: https://www.buildalpha.com/walk-forward-optimization/
- Kiploks - WFE explained / OOS Retention vs WFE: https://kiploks.com/research/walk-forward-efficiency-wfe-explained-what-it-means-and-how-to-read-it , https://kiploks.com/research/oos-retention-vs-walk-forward-efficiency-whats-the-difference
- Quanthop - Walk-Forward Analysis: https://quanthop.com/learn/validation-robustness/walk-forward-analysis
