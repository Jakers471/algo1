# renko — Rant Journal

> The unfiltered idea log for this strategy line. User rants are copied **verbatim** (typos and
> all — that's the point, it's the raw thinking). Claude's responses are summarized. Read
> top-to-bottom to follow how it evolved. New rants get appended with a timestamp.
>
> Companion docs: **NOTES.md** (clean concept + spec + roadmap), **README.md** (premise +
> workflow), **derivative.md** (the source DM exchange this whole line came from).

---

## Rant 0 — the pivot (2026-07-01)

Context: the user paused both prior lines (`flag_pattern`, `structure_detection`) — explicitly
marking them "on hold," not abandoned — and said their mental model was changing toward
"something completely different." Then dropped seven screenshots + `derivative.md` (a long DM
exchange with a veteran Renko trend-follower, handle **derivativesnyc**) and said, verbatim
intent: *look at all the screenshots, then read this.*

The source's throughline (his words, from `derivative.md`):
> If it takes a nanosecond or the whole of eternity for brick to form a particular distance
> amount, what do you care ... you end up riding the wave, noy shaken out by multicolored bars
> which time-based charts produce ... U just need to spot zigzag inflections early. No crayon
> spaghetti squigly indicator shit. Only raw px action.

> No need for volume, A/D, institutional order flow ... PRICE ACTION reigns supreme - all is
> contained in the bricks ... Fixed size bricks are inherent baked-in riak mgmt - calc R:Rw
> precisely

> Buy white, sell black. When colors align across MPFs

And the user's own realization, in the log:
> Started comparing how I see orders on a regular candlestick chart to Renkos and the simplicity
> is genius ... I see how much more powerful a Renko chart can be. Especially for the purposes of
> creating an Algo. It eliminates a ton of noise

> renko is powerful. The system i feel like reflects renko style tho in a way.... Stages are
> inherently price bricks. Same fractal structure. Not thinking of price in terms of time but in
> orders. ill definitely be sticking to renko for algo goals

**Claude (summary):** Read all 7 screenshots + the full DM log. Reflected back the philosophy
(time is the enemy; bricks contain everything; fixed brick = mechanical R:R; ride, no preset
targets) and the mechanics extracted from the images: **MPF** (Multiple Price Frames = brick
sizes replacing timeframes, SPF/LPF), the **core+hedge state machine** (enter LPF core → SPF
reverses → hedge → LPF holds = drop hedge/keep core, LPF flips = core dies/hedge becomes new
core), the execution params (`20 size / 5 offset / TSL 5 ticks below brick low`), the 3 states
(trend, momentum accel, vol breakout), and the R:R-vs-winrate profitability map. Key connection
made: this **resolves** three things the paused work kept fighting — *"no fixed anything"* (Renko
fixes price, not time), *"trade WITH the larger trend"* (MPF alignment is exactly that), and the
*R:R-geometry reframe* (fixed bricks make risk exact). Then set up the folder to mirror the
siblings: moved the seven screenshots into `images/` with descriptive names, wrote `README.md`
(premise), `NOTES.md` (concept/spec/roadmap), and this journal. Nothing built yet — next is
locking the brick-engine decisions in NOTES §3 (fixed close-based, confirmed-brick-only, no
look-ahead) before any code.
</content>

---

## Rant 1 — "are these results even real?" → no, and neither is the edge (2026-07-01)

User, verbatim (two messages, same session):
> working here, we kept runnint the expectancy.py and the other ai kept syaing the results
> were not real/somehting was off with execution or osmehting ?

> sooo whats the edge/expectancy ? can we [derivative.md + images/] look atthese and tets
> multiple price frames together based on the strtagey presented in the images/ and md and
> do relaistic tetss

**Claude (summary):** The other AI was right. The +0.49R/trade baseline was grid-price fill
fantasy — a brick only confirms when a 1m bar closes at/past its grid line, so the real fill
is that bar's close, always against the trade at a flip. Quantified it (audit script), patched
`expectancy.py` to honest fills (F2), then built `harness/mpf.py` and tested the source's
actual strategy — MPF color alignment, shown to be economically identical to the core+hedge
flowchart on a single instrument. Result over 20yr, honest fills, all pairs of 10/25/50pt:
**expectancy ≈ 0 (t < 1), in-sample AND out.** The promised R:R geometry shows up exactly
(~3.2R wins vs ~1.7R losses at ~35% win rate) but nets to breakeven — the market prices the
asymmetry fairly. Also found fixed-point bricks are badly non-stationary over 20yr of NQ
(82% of small-brick trades land in 2020–24); %-of-price or ATR bricks are the follow-up (F3).

---

## Rant 2 — both directions at once: ATR frames, exits, volume, risk (2026-07-01)

User, verbatim:
> keep building this thred with what you epxlained the two directions please and lets try
> again. also if we could find the best price frames = alignment scoring also add in volume
> clustering and see if that helps at all in temrs of trading wiht or without volume. also
> risk managment too ofc.

**Claude (summary):** Found the 1m store is a BACK-ADJUSTED continuous contract (2005 shows
~4700, real NQ was ~1550) → %-of-price bricks are invalid, so the stationarity fix became
**ATR-scaled bricks** (k × daily ATR20, monthly causal re-set, per-brick size stored so
1R = the brick that printed = risk-normalized sizing). Built the 0.04–0.64 ladder, then
`harness/sweep.py`: all 10 frame pairs, 5-frame alignment scoring, exit mechanics
(trail-k = the TSL from the images, generalized), and volume-intensity gating. Verdict in
NOTES F4: alignment entries still zero (now on stationary bricks); scoring deeper = worse;
**exit width monotonically buys gross expectancy** (ride-to-LPF = +0.22R gross on
0.08:0.32); **brick volume intensity is the cleanest signal found so far** (HIGH-vol
entries beat LOW in both pairs, IS and OOS — the veteran's "no need for volume" looks
wrong). Focused combo 0.32:0.64 + trail-3 + HIGH-vol: **+0.13R net, PF 1.10, positive in
3/4 eras, OOS +0.23R** — but t≈1 after two selection rounds, so it's a *candidate, not an
edge*. Next move is validation on unseen data (MNQ/ES or fresh NQ), not more sweeping.
