# threatcasting

`services.threatcasting` — Threatcasting service: cross-impact analysis, warning flags, threat intelligence,

## CLI Usage

```bash
python3 -m services.threatcasting
```
```bash
python3 -m services.threatcasting.cli --help
```

## Modules

- `backcasting` — Header-backed backcasting plans with normalized milestone dependencies.
- `cascades` — Cascade Modeler — models cascading failure scenarios, detects active cascades,
- `cli` — CLI for Threatcasting service — threat management, cross-impact analysis,
- `config` — Configuration for Threatcasting service: GNH dimensions, desirability weights,
- `cross_impact` — Cross-Impact Analyzer — maps how threats influence each other,
- `desirability` — Desirability Assessor — evaluates threat narratives against wellbeing frameworks
- `flags` — Flag Monitor — tracks observable warning indicators for threats,
- `horizons` — Horizon Planner — multi-timeframe planning, threat linking, review cycles.
- `intelligence` — Threat Intelligence — aggregates all threatcasting data into intelligence
- `models` — Pydantic models for Threatcasting service: threat, flag, cross-impact, signal,
- `narratives` — Narrative Engine — constructs threat scenario stories, evaluates
- `path_comparison` — Path Comparison — compare multiple backcasting routes to the same desirable future.
- `preempt` — Preemptive Intervention Planner — the "best defense is a good offense" layer.
- `principles` — Principles — sustainability principles that define success, with milestone alignment.
- `probability` — Resolvable threat probability forecasts and Brier calibration.
- `signals` — Signal Ingestor — aggregates external signals from various sources,

## Files

17 Python modules
