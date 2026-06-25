# Runs registry

| run | type | when | strategy | result | detail |
|---|---|---|---|---|---|
| run_0001 | Backtest | 2026-06-24T16:55:15 | fanning_mtf | +24% · sharpe 0.32 · win 46% | first run |
| run_0002 | Backtest | 2026-06-24T16:55:21 | fanning_mtf | +17% · sharpe 0.23 · win 44% | X 70->60 |
| run_0003 | Backtest | 2026-06-24T16:57:55 | fanning_mtf | +24% · sharpe 0.32 · win 46% | X 60->70 |
| run_0004 | Backtest | 2026-06-24T19:21:50 | fanning_mtf | +28% · sharpe 0.44 · win 44% | +capital, +sizing, +size_contracts, +risk_pct, +max_contracts, +commission_per_side, +slippage_ticks, +point_value, +tick, +tick_value, -cost_per_turn |
| run_0005 | Backtest | 2026-06-24T19:22:42 | fanning_mtf | +36% · sharpe 0.50 · win 45% | X 70->65 |
| run_0006 | Backtest | 2026-06-24T19:23:19 | fanning_mtf | +28% · sharpe 0.44 · win 44% | X 65->70 |
| wfo_0001 | Walk-Forward Optimization | 2026-06-24T20:06:27 | fanning_mtf | OOS +15% · sharpe 0.28 · win 43% | optimize sharpe · train 1095d/test 365d · 17win · 3cfg |
| wfo_0002 | Walk-Forward Optimization | 2026-06-24T20:18:11 | fanning_mtf | OOS +30% · sharpe 0.47 · win 43% | optimize sharpe · train 1095d/test 365d · 17win · 7cfg |