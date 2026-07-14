# Business Process Management

Kokonut Intelligence uses Business Process Management (BPM) concepts to harden
the platform's business approach. The generic `lifecycle_transition` ledger
(`179_lifecycle_transition.sql`) is the process event log; `workflow_specs` are
the intended process models; `value_stream.py` is the VSM current-state view.
This module adds process mining, predictive monitoring, SPC, a process-health
board, and auto-escalation on top of that foundation.

## Capability map

| BPM phase | Module | Status |
|---|---|---|
| Design / Modeling | `services/workflow_specs` | exists (6 specs) |
| Execution / Rules | event bus, scheduler, `decision` engine | exists |
| Monitoring / BAM | `value_stream.py` + `lifecycle_transition` | exists (batch) |
| Process Mining | `services/analytics/process_mining.py` | **Phase A** |
| Predictive BPM | `services/analytics/predictive_bpm.py` | **Phase B** |
| SPC / Control | `services/systems/process_control.py` | **Phase C** |
| Process-health board | `services/analytics/process_health.py` | **Phase D** |
| Auto-escalation | `services/management/escalation.py` | planned |

## Phase A — Process mining

Turns the lifecycle ledger into discovered variants, conformance findings,
case timelines, and cycle-time distributions. The canonical 5-state model
(`draft -> submitted -> verified -> published`, `rejected` reachable from any
non-terminal state, `published`/`rejected` terminal) lives in the `process_model`
table (`182_process_mining.sql`) so conformance is uniform across every
governed entity type.

### Usage

```bash
python3 -m services.analytics.process_mining discover [--entity-type TYPE]
python3 -m services.analytics.process_mining conformance [--entity-type TYPE] [--limit N]
python3 -m services.analytics.process_mining timeline --entity-id UUID
python3 -m services.analytics.process_mining cycle-times [--entity-type TYPE]
python3 -m services.analytics.process_mining persist [--entity-type TYPE]
```

- `discover` — all variants actually taken, with instance counts and a
  `is_conforming` flag.
- `conformance` — only the traces that violate the model (illegal skips,
  transitions out of a terminal state, non-`draft` start), with reasons.
- `timeline` — per-instance step durations.
- `cycle-times` — draft → published elapsed days per published instance.
- `persist` — upsert discovered variants into `process_variant` for trend
  tracking.

### Schema

- `182_process_mining.sql` — `process_variant` (discovered set cache) and
  `process_model` (canonical conformance model).

### Tests

```bash
python3 -m pytest tests/test_process_mining.py -v
```

## Phase D — Process-health board

Single BAM-style view combining VSM metrics (WIP, lead time, FTY,
bottlenecks), process-mining conformance, and optional predictive-breach
risk. Registered as the `process_health` report type and exposed via a CLI.

```bash
python3 -m services.analytics.process_health board [--location-id UUID] [--sla-target-hours 72]
python3 -m services.export.report_generator --type process_health [--location-id UUID]
```

> Process mining surfaced two latent VSM bugs that were fixed as part of
> this phase: `wip_by_stage` was missing a `GROUP BY`, and `_entity_loc_sql`
> assumed every pipeline table had `location_id` (it does not for
> `agent_task` and `ai_summary`).

