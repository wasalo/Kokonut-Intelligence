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
| Auto-escalation | `services/management/escalation.py` | **Phase E** |
| Per-entity-type models | `process_model` (186) + `process_model_sync.py` | **Phase F** |

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

## Phase E — Auto-escalation / handover

When a governed process instance is predicted to breach its SLA, raise an
escalation: record it in `process_escalation` and (optionally, when an org is
supplied) create a draft `work_item` for human follow-up. Idempotent per open
instance; never verifies or publishes anything (agents/handlers stay
read/draft-only).

```bash
python3 -m services.management.escalation sweep [--org-id UUID] [--sla-target-hours 72] [--threshold 0.5]
python3 -m services.management.escalation resolve --escalation-id UUID [--resolved-by UUID]
```

## Phase F — Per-entity-type state models

The canonical 5-state `process_model` is generalized to a per-`entity_type`
model (`186_process_state_models.sql`): the `entity_type` column defaults to
`'*'` for the existing publication pipeline, and explicit rows define other
state machines. Mining, prediction, and escalation now load the model for each
entity type, so any governed table with its own lifecycle is handled by the
same engine.

Four more tables are instrumented (`187_state_model_triggers.sql`):

- `work_item` — 6-state spec (`draft→assigned→in_progress→done`, with `blocked`
  and back-edges, `cancelled` terminal). Rows are kept in sync from
  `services/workflow_specs/work_item.py` via `process_model_sync`.
- `market_order` — `pending→confirmed→shipped→delivered`, `cancelled` terminal;
  vocabulary enforced by a `CHECK` constraint.
- `credit_retirement` — already the 5-state vocabulary; only needed a trigger.
- `metric_value` — no `status` column; the `verified` boolean is mapped to
  `draft`/`verified` by a dedicated trigger (`fn_record_metric_lifecycle`).

```bash
python3 -m services.analytics.process_model_sync   # workflow_specs -> process_model
```

## Notes & follow-ups

- `persist_forecasts` is idempotent: a periodic sweep refreshes the single
  current forecast row per in-flight instance (DELETE-then-INSERT) rather than
  appending duplicates.
- Per-entity-type models make the BPM engine data-driven: adding a new governed
  table = add a `workflow_spec` (or seed a `process_model` row) + a lifecycle
  trigger. No engine code changes are needed for conformance, prediction, the
  process-health board, or auto-escalation.
- `work_item` escalation uses `due_at`/`sla_at` as the per-instance SLA target
  when present, falling back to the default 72h.



