# flag_triangle — consolidation finder

Finds sideways **consolidations** and classifies their shape by fitting trendlines
through swing highs and swing lows.

## What it detects
| pattern | upper bound | lower bound |
|---|---|---|
| `rectangle` | flat | flat |
| `channel_up` / `channel_down` | sloped, parallel | sloped, parallel |
| `sym_triangle` | falling | rising (converging) |
| `asc_triangle` | flat | rising (converging) |
| `desc_triangle` | falling | flat (converging) |
| `triangle` | converging (other) | converging (other) |
| `pennant` | short converging **after a sharp move** (>= `POLE_ATR`×ATR) | |

## How it works (`signal/flag_triangle.py`)
1. **Swings** — ATR-threshold swing tracker (same as `structure_detection`), grain = `SWING_GRAIN`.
2. **Windows** — slide over the swing sequence; for each start swing keep the *largest*
   span that stays a consolidation: `MIN_PIVOTS`+ swings, duration in `[MIN_BARS, MAX_BARS]`,
   and `>= CONTAIN_MIN` of bars sitting inside the fitted lines (±`CONTAIN_TOL`×ATR). Non-overlapping.
3. **Classify** — from the two fitted slopes (normalized by channel width, `FLAT` threshold) and
   whether the channel is converging (`CONVERGE`).
4. **Outcome** — the end of the consolidation is treated as the breakout bar; forward returns
   (`HORIZONS`) and MFE/MAE (`FWD_WINDOW`) are measured in the continuation direction
   (prior move over `PRIOR_BARS`, else the shape's bias).

All tunables live in `signal/signal_config.py`.

## Run
```
python "strategy research/flag_triangle/signal/flag_triangle.py" --save
python "strategy research/flag_triangle/signal/flag_triangle.py" --save --tf 15m
```
Writes `findings/flag_triangle_<tf>.json` in the tv_chart "matches" schema, so it shows up in
the chart's findings dropdown automatically (consolidation span as a band, arrow at the breakout
bar, forward stats). Each match also stores the fitted `upper`/`lower` trendline endpoints.
