# AI roles

A small team of specialized Claude agent roles for building this quant platform correctly.
We kept conflating three different jobs - **theory**, **data design**, and **implementation** -
which is why things got confused (e.g. the best-on-full vs OOS span mismatch). Splitting them
with explicit written hand-offs fixes that.

## The team

| Role | Owns | Reads internet? | Deliverable (artifact) |
| --- | --- | --- | --- |
| **Quant Researcher** (`quant_researcher.md`) | Theory + correctness. Is our methodology and backend wiring actually right vs the literature? | Yes (deep research) | `outputs/NN_quant_*.md` - findings, audit, prioritized recommendations |
| **Data Scientist / Analyst** (`data_scientist.md`) | Data design + interpretation. Exactly what metrics/curves/fields/graphs we need and the schema to store them. | Light | `outputs/NN_data_*.md` - data + metric + visualization spec |
| **Quant Engineer** (`quant_engineer.md`) | Implementation. Wire the backend/frontend to the data spec, matching our conventions. | No | working code + `outputs/NN_build_*.md` changelog |

## Workflow (sequential for the foundation)

```
Quant Researcher  ->  Data Scientist  ->  Quant Engineer
  (what's true &        (what data &        (build it,
   what's wrong)         schema we need)     communicate)
```

Each role consumes the prior role's artifact and produces its own. We do NOT skip steps for
foundational work - getting the theory and data model right is the whole point. Parallelize
only later, for independent, well-specified features.

## Rules for every role

- No emojis, anywhere (see project convention).
- Distinguish clearly: **theory** (what should be true) vs **our implementation** (what we
  actually do) vs **recommendation** (what to change). Never blur them.
- Cite sources when researching. No hand-waving.
- Flag look-ahead bias, overfitting, and apples-to-oranges comparisons explicitly.
- Number outputs (`01_`, `02_` ...) so the sequence/lineage is readable.

## Current state (snapshot for any role)

- Engine: `algokit/{backtest,metrics,wfo,validation,significance,sizing,costs}.py`.
- One strategy: `strategies/fanning_mtf.py` (long-only NQ 15m, 1d HTF regime gate).
- Registry: `runs/<strategy>/{backtest,walk_forward,anchored}/<id>/` (run_/wfo_/awf_).
- UI: `webui/` (Flask + ECharts). Nav: Analyzer | Performance | Runs | Strategies.
- Known open issue at time of writing: best-on-full was evaluated over the full range while
  OOS covers only the test windows - spans don't match (the quant should rule on this).
