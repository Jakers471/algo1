# simplicity — commands

> **CHANGED — permanent shortcuts now set up (via PowerShell profile).**
> Open any PowerShell window and you have two words:
>
> | type | does |
> |---|---|
> | `simp` | jump into the `simplicity` folder |
> | `py <file>` | run a file with the correct 3.11 venv python |
>
> So the normal start is just: **`simp`** then a `py ...` command below.
>
> **Why this exists:** `py` is also a built-in Windows command that points at the WRONG
> Python (3.13). Our profile overrides it to the venv python for every new window, so the
> `py ...` commands below now Just Work. If you ever open a terminal and `py` runs 3.13
> again, the profile didn't load — re-run the setup (see bottom of this file).

Run from `algoproj/simplicity/` (that's what `simp` does). `py` = the 3.11 venv python:
`C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe`

## data
| command | does |
|---|---|
| `py data/build_data.py` | rebuild clean NQ + ES parquets (volume = Up+Down) from the TradeStation source |

## research
| command | does |
|---|---|
| `py research/studies/volume_buckets/build_buckets.py` | build volume + volatility buckets (all → year → … → session) |
| `py research/studies/volume_buckets/make_dashboard.py` | build the dashboard HTML from the buckets |
| `py research/studies/volatility_ranking/rank_volatility.py` | most-vs-least volatile ranking + era comparison |
| `py research/gates/volatility_filter/vol_filter.py` | the vol gate: regime thresholds + tradeable-day counts |
| `py research/gates/volatility_filter/filter_variants.py` | compare filter variants (high/low/…) for the hypothesis test |
| `py research/gates/volatility_filter/make_selection_report.py` | build the "what each filter selected" HTML report |
| `py research/structure/session_anchors/session_anchors.py` | build per-session high/low/open anchors (for the chart overlay) |
| `py research/chart/build_chart_data.py` | cache ≤2000 bars/TF (NQ+ES) for the chart |
| `py research/chart/make_chart.py` | build the self-contained `chart.html` |

## engine
| command | does |
|---|---|
| `engine\run_engine.bat` | fire up the engine; logs each pipeline stage WIRED / NOT WIRED in sequence |
| `engine\run_engine.bat --debug` | same + why each stage isn't wired |

## view
| command | does |
|---|---|
| open `research/studies/volume_buckets/output/volume_dashboard.html` | the volume + volatility dashboard |
| open `research/gates/volatility_filter/output/filter_selections.html` | most/least volatile + what each filter selected |
| open `research/chart/chart.html` | multi-timeframe chart + config sidebar + selection overlay |

## setup — if `simp` / `py` ever stop working

They live in your PowerShell profile: `C:\Users\jakers\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`
(loads automatically in every new window). To re-create it, paste this once:

```powershell
$dir = Split-Path $PROFILE
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
Add-Content $PROFILE @'

function py { & "C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe" @args }
function simp { Set-Location "C:\Users\jakers\Desktop\algo\algoproj\simplicity" }
'@
```

Then open a NEW terminal (the profile only loads on window start). Quick fix for the current
window only: paste those two `function` lines directly.
