# Business Process Management

Kokonut Intelligence applies Business Process Management (BPM) concepts to
harden the platform's operational approach. The generic `lifecycle_transition`
ledger (179) serves as the process event log; `workflow_specs` define the
intended process models; `value_stream.py` provides the VSM current-state view.
On top of that foundation: process mining, predictive monitoring, statistical
process control, a process-health board, auto-escalation, cross-entity handoff
tracking, maturity assessment, and what-if simulation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BPM Engine                                    │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ workflow_     │  │ lifecycle_   │  │ process_model              │ │
│  │ specs         │  │ transition   │  │ (per-entity-type state     │ │
│  │ (26 specs)    │  │ (event log)  │  │  machines)                 │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────────┘ │
│         │                 │                        │                 │
│  ┌──────┴───────────────┬┴────────────────────────┬┴───────────────┐ │
│  │ process_mining       │ predictive_bpm          │ process_control │ │
│  │ (variants,           │ (breach prediction,     │ (SPC charts,   │ │
│  │  conformance,        │  SLA forecasting)       │  Cp/Cpk, CTQ)  │ │
│  │  cross-entity)       │                         │                │ │
│  └──────────────────────┴─────────────────────────┴────────────────┘ │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ process_health    │  │ escalation       │  │ process_gap       │  │
│  │ (BAM board,       │  │ (SLA breach →    │  │ (CMMI maturity,  │  │
│  │  maturity view)   │  │  draft work_item)│  │  gap analysis)    │  │
│  └──────────────────┘  └──────────────────┘  └───────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │ process_handoff   │  │ process_          │                         │
│  │ (cross-entity     │  │ simulation        │                         │
│  │  interfaces)      │  │ (what-if)         │                         │
│  └──────────────────┘  └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Capability map

| BPM phase | Module | Key function |
|---|---|---|
| Design / Modeling | `services/workflow_specs/` | 26 registered WorkflowSpecs with structural + governance validation |
| Execution / Rules | event bus, scheduler, `services/decision/` | Event delivery, scheduling, policy-gated decisions |
| Monitoring / BAM | `value_stream.py` + `lifecycle_transition` | VSM current-state (WIP, lead time, FTY, bottlenecks) |
| Process Mining | `services/analytics/process_mining.py` | Discovered variants, conformance, timelines, cross-entity traces |
| Predictive BPM | `services/analytics/predictive_bpm.py` | Per-case breach probability, SLA forecasting |
| SPC / Control | `services/systems/process_control.py` | Control charts, Cp/Cpk/Pp/Ppk, CTQ definitions |
| Cross-entity interfaces | `schemas/postgres/190_process_interfaces.sql` | Handoff declarations, observation log, end-to-end traces |
| Process-health board | `services/analytics/process_health.py` | BAM-style board combining VSM + mining + prediction + maturity |
| Auto-escalation | `services/management/escalation.py` | SLA breach → `process_escalation` + draft `work_item` |
| Per-entity-type models | `process_model` (186) + `process_model_sync.py` | Generalized state machines for every governed table |
| Process targets & maturity | `schemas/postgres/191_process_targets.sql` | CMMI-inspired gap analysis, maturity assessments |
| Process simulation | `schemas/postgres/193_process_simulation.sql` | What-if scenarios, capability index persistence |

## 1. Lifecycle transition foundation

The `lifecycle_transition` table (`179_lifecycle_transition.sql`) is an
append-only event log that captures every 5-state lifecycle transition for
governed pipeline entities. Triggers fire `AFTER UPDATE OF status` (or
`review_status`) and record the transition only when the value actually
changes. Actor is enriched from session variables `kokonut.actor_id` /
`kokonut.actor_type` when the application (or Directus hook) sets them.

### Table: `lifecycle_transition`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `entity_type` | VARCHAR(100) | table name (e.g. `data_stream_post`) |
| `entity_id` | UUID | row ID in the source table |
| `from_status` | VARCHAR(50) | previous status (NULL on INSERT) |
| `to_status` | VARCHAR(50) | new status |
| `transitioned_at` | TIMESTAMPTZ | default `now()` |
| `actor_id` | UUID | from `kokonut.actor_id` session var |
| `actor_type` | VARCHAR(50) | from `kokonut.actor_type` session var |
| `source_event_id` | UUID | optional event bus correlation |
| `metadata` | JSONB | default `'{}'` |
| `created_at` | TIMESTAMPTZ | default `now()` |

**Indexes:** `idx_lt_entity (entity_type, entity_id)`, `idx_lt_to_status (to_status)`, `idx_lt_transitioned_at (transitioned_at)`

### Instrumented tables (Phase 1)

| Table | Trigger column | Trigger function |
|---|---|---|
| `data_stream_post` | `status` | `fn_record_lifecycle_transition()` |
| `ai_summary` | `status` | `fn_record_lifecycle_transition()` |
| `impact_claim` | `status` | `fn_record_lifecycle_transition()` |
| `report_snapshot` | `status` | `fn_record_lifecycle_transition()` |
| `stakeholder_feedback` | `status` | `fn_record_lifecycle_transition()` |
| `farm_activity` | `status` | `fn_record_lifecycle_transition()` |
| `harvest_event` | `status` | `fn_record_lifecycle_transition()` |
| `agent_task` | `review_status` | `fn_record_review_transition()` |

## 2. Workflow specifications

`services/workflow_specs/` defines 26 registered `WorkflowSpec` instances —
declarative state-and-control-flow models for governed entity types. Each spec
declares states, steps (actor-owned actions), transitions (guarded outcomes),
invariants, and source references.

### WorkflowSpec model

```python
@dataclass(frozen=True)
class WorkflowSpec:
    id: str                                    # e.g. "work_item"
    title: str                                 # human-readable name
    states: FrozenSet[str]                     # e.g. {"draft","assigned","in_progress",...}
    steps: Tuple[Step, ...]                    # ordered workflow steps
    invariants: Tuple[str, ...] = ()           # structural invariants
    source_refs: Tuple[str, ...] = ()          # source documentation links

@dataclass(frozen=True)
class Step:
    id: str                    # unique step ID
    actor: str                 # who executes (human, agent, system)
    current_state: str         # state when this step is active
    action: str                # human-readable action description
    transitions: Tuple[Transition, ...] = ()
    entry: bool = False        # is this the initial step?
    terminal: bool = False     # does this step end the workflow?
    transaction_boundary: bool = False
    external_side_effect: bool = False
    human_approval: bool = False
    retry_safe: bool = False
    high_risk: bool = False    # requires human approval per safety.py

@dataclass(frozen=True)
class Transition:
    target: str                # target step ID
    next_state: str            # resulting state
    guard: str = "always"      # guard condition
    outcome: str = "continue"
    bounded_retry: bool = False
    loop_rationale: str = ""
```

### Validator governance rules

The `validate()` function enforces structural integrity and governance:

- **Duplicate IDs** — no two steps may share an ID
- **Entry count** — exactly one entry step per spec
- **Dangling targets** — all transition targets must reference existing steps
- **State declaration** — every step's `current_state` must be in `states`
- **Unreachable steps** — every non-entry step must be reachable from entry
- **Cycle bounding** — no unbounded loops (cycles require `bounded_retry`)
- **High-risk enforcement** — steps with `high_risk=True` must have `human_approval=True`
- **Agent path restriction** — agent-owned paths cannot reach governed states (`verified`, `published`) or actions (`verify`, `publish`)

**High-risk actions** (from `services/agents/safety.py`): `attest`, `bulk_update`, `delete`, `financial_write`, `onchain_submit`, `publish`, `status_change_to_published`.

### Registered specs (26)

`carbon_retirement`, `event_bus_delivery`, `work_item`, `budget`, `objective`,
`project`, `data_stream_post`, `ai_summary`, `impact_claim`,
`report_snapshot`, `stakeholder_feedback`, `farm_activity`, `harvest_event`,
`metric_value`, `traceability_batch`, `insurance_claim`, `pest_intervention`,
`emergency_incident`, `cooperative_order`, `extension_enrollment`,
`market_order`, `coordination_alliance`, `governance_circle`,
`governance_role`, `governance_role_assignment`, `governance_tension`,
`governance_proposal`, `governance_tactical_session`,
`governance_tactical_item`, `governance_circle_link`.

### CLI

```bash
python3 -m services.workflow_specs list
python3 -m services.workflow_specs validate [SPEC_ID]
python3 -m services.workflow_specs render SPEC_ID [--format markdown|mermaid]
```

- `list` — prints all registered spec IDs and titles.
- `validate` — structural + governance validation; one spec or all.
- `render` — decision table (markdown) or flowchart (mermaid).

## 3. Process mining (Phase A)

Turns the lifecycle ledger into discovered variants, conformance findings,
case timelines, and cycle-time distributions. The canonical 5-state model
(`draft → submitted → verified → published`, `rejected` reachable from any
non-terminal state, `published`/`rejected` terminal) lives in `process_model`
(`182_process_mining.sql`) so conformance is uniform across every governed
entity type.

### Key functions

| Function | Description |
|---|---|
| `load_model(conn, entity_type)` | Loads process model; per-type rows override the `'*'` default |
| `goal_state(model)` | Finds the success terminal (first `is_goal` state) |
| `initial_state(model)` | Finds the entry state (fallback: `draft`) |
| `get_traces(conn, entity_type, limit)` | Groups lifecycle_transition rows into ordered traces per (type, id) |
| `classify_conformance(step_sequence, model)` | Validates a trace: unknown statuses, non-draft start, illegal transitions, terminal-state exit |
| `discover_variants(conn, entity_type)` | Aggregates traces into variants with instance counts + conformance |
| `check_conformance(conn, entity_type, limit)` | Returns only non-conforming traces with reasons |
| `case_timeline(conn, entity_id)` | Per-step timeline with `duration_seconds` for one entity instance |
| `cycle_time_distribution(conn, entity_type)` | Elapsed days from entry to goal state, per published instance |
| `persist_variants(conn, entity_type)` | Upserts discovered variants into `process_variant` |
| `cross_entity_traces(conn, location_id)` | Traces spanning multiple entity types via `process_handoff_log` |
| `cross_entity_variants(conn, location_id)` | Discovers cross-entity variant signatures |
| `cross_entity_conformance(conn, location_id)` | Checks cross-entity traces against declared `process_handoff` entries |

### CLI

```bash
python3 -m services.analytics.process_mining discover [--entity-type TYPE]
python3 -m services.analytics.process_mining conformance [--entity-type TYPE] [--limit N]
python3 -m services.analytics.process_mining timeline --entity-id UUID
python3 -m services.analytics.process_mining cycle-times [--entity-type TYPE]
python3 -m services.analytics.process_mining persist [--entity-type TYPE]
python3 -m services.analytics.process_mining cross-traces [--location-id UUID]
python3 -m services.analytics.process_mining cross-variants [--location-id UUID]
python3 -m services.analytics.process_mining cross-conformance [--location-id UUID]
```

- `discover` — all variants actually taken, with instance counts and `is_conforming` flag.
- `conformance` — only traces that violate the model (illegal skips, transitions out of terminal state, non-`draft` start), with reasons.
- `timeline` — per-instance step durations.
- `cycle-times` — draft → published elapsed days per published instance.
- `persist` — upsert discovered variants into `process_variant` for trend tracking.
- `cross-traces` — traces spanning multiple entity types via `process_handoff_log`.
- `cross-variants` — variant signatures across entity boundaries.
- `cross-conformance` — validates cross-entity traces against declared handoffs.

## 4. Predictive BPM (Phase B)

Given an in-flight governed entity, predict remaining time to goal state and
the probability of breaching an SLA target. Models are empirical (historical
remaining-time distributions per state) and versioned by date. Reuses
`lifecycle_transition` as the training event log.

**Model version:** `MODEL_VERSION = "v2026.07"` (date-based, auto-bumps monthly).

### Table: `predictive_process_forecast`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `entity_type` | VARCHAR(100) | |
| `entity_id` | UUID | |
| `current_state` | VARCHAR(50) | |
| `age_hours` | DOUBLE PRECISION | hours since first transition |
| `predicted_remaining_hours` | DOUBLE PRECISION | median historical remaining |
| `breach_probability` | DOUBLE PRECISION | P(SLA breach) |
| `sla_target_hours` | DOUBLE PRECISION | |
| `model_version` | VARCHAR(20) | date-based version |
| `predicted_at` | TIMESTAMPTZ | default `now()` |

**Indexes:** `idx_ppf_entity (entity_type, entity_id)`, `idx_ppf_breach (entity_type, breach_probability)`

### Key functions

| Function | Description |
|---|---|
| `predict_remaining(conn, entity_type, current_state)` | Median historical remaining hours from `current_state` to goal |
| `predict(conn, entity_type, current_state, age_hours, sla_target_hours)` | Predict remaining time and SLA-breach probability for one case |
| `breaches(conn, entity_type, sla_target_hours, threshold)` | In-flight instances whose breach probability ≥ threshold |
| `persist_forecasts(conn, entity_type, sla_target_hours)` | Idempotent: DELETE then INSERT current in-flight breach predictions |

### CLI

```bash
python3 -m services.analytics.predictive_bpm predict --entity-type TYPE --state STATE [--age-hours H] [--sla-target-hours H]
python3 -m services.analytics.predictive_bpm breaches --entity-type TYPE --sla-target-hours H [--threshold 0.5]
python3 -m services.analytics.predictive_bpm persist --entity-type TYPE [--sla-target-hours H]
```

`persist_forecasts` is idempotent: a periodic sweep refreshes the single
current forecast row per in-flight instance rather than appending duplicates.

## 5. Statistical process control (Phase C)

Computes control limits, flags out-of-control points, and measures process
capability (Cp/Cpk/Pp/Ppk). Reads from `process_kpi_snapshot` time-series
data; writes to `process_kpi_snapshot` and `process_capability`.

### Tables

**`process_kpi_snapshot`** — time-series KPI data for control charts:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `entity_type` | VARCHAR(100) | |
| `metric` | VARCHAR(100) | e.g. `cycle_time_days`, `fty_pct` |
| `value` | DOUBLE PRECISION | |
| `period` | VARCHAR(40) | default `all` |
| `source_ref` | VARCHAR(200) | |
| `captured_at` | TIMESTAMPTZ | default `now()` |

**`process_ctq`** — Critical-To-Quality definitions (org-authored, not seeded):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `process` | VARCHAR(100) | |
| `ctq_name` | VARCHAR(100) | |
| `target` | DOUBLE PRECISION | |
| `unit` | VARCHAR(40) | |
| `upper_spec` | DOUBLE PRECISION | USL |
| `lower_spec` | DOUBLE PRECISION | LSL |
| `source_ref` | VARCHAR(200) | |
| `created_at` | TIMESTAMPTZ | default `now()` |

### Key functions

| Function | Description |
|---|---|
| `control_limits(values, k=3.0)` | Returns mean, stdev, UCL/LCL (mean ± k·σ), 2-σ warning bands |
| `capture_snapshots(conn, entity_type)` | Computes `cycle_time_days`, `fty_pct`, `rework_rate_pct` per entity type; stores in `process_kpi_snapshot` |
| `evaluate_control(conn, entity_type, metric)` | Computes control limits over KPI series; flags out-of-control points |
| `ctq_report(conn, process)` | Lists CTQ definitions with latest snapshot value |
| `compute_cp_cpk(values, usl, lsl)` | Pure-math Cp/Cpk; rating: not_capable / marginal / capable / highly_capable |
| `ctq_capability(conn, entity_type, metric, usl, lsl)` | Computes Cp/Cpk for a CTQ using spec limits from `process_ctq` or arguments |
| `process_capability(conn, entity_type, metric, usl, lsl)` | Full capability: Cp, Cpk, Pp, Ppk with σ_within (moving-range/d2) and σ_overall |
| `persist_capability(conn, entity_type, metric, usl, lsl, period)` | Computes and persists capability indices to `process_capability` |
| `capability_report(conn, entity_type)` | Full capability report across all CTQs |

### Capability indices

| Index | Formula | Meaning |
|---|---|---|
| **Cp** | (USL − LSL) / (6·σ_within) | Process potential (within-subgroup variation) |
| **Cpk** | min((USL − μ) / (3·σ_within), (μ − LSL) / / (3·σ_within)) | Process centering |
| **Pp** | (USL − LSL) / (6·σ_overall) | Process performance (overall variation) |
| **Ppk** | min((USL − μ) / (3·σ_overall), (μ − LSL) / (3·σ_overall)) | Performance centering |
| **σ_level** | derived from Cpk | 3·Cpk (e.g. Cpk=1.0 → σ=3.0) |

**Rating:** not_capable (Cpk < 1.0), marginal (1.0–1.33), capable (1.33–2.0), highly_capable (> 2.0).

### CLI

```bash
python3 -m services.systems.process_control capture [--entity-type TYPE]
python3 -m services.systems.process_control chart --entity-type TYPE --metric METRIC
python3 -m services.systems.process_control ctq [--process NAME]
```

- `capture` — snapshots current KPIs for all entity types (or one).
- `chart` — control chart data: mean, UCL, LCL, 2-σ bands, out-of-control flags.
- `ctq` — CTQ definitions with latest values.

## 6. Cross-entity handoffs

Declares handoffs between governed entity types, logs actual handoff events
with SLA tracking, and supports end-to-end cross-entity process traces for
value-chain analysis (`190_process_interfaces.sql`).

### Tables

**`process_handoff`** — handoff declarations:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `source_entity_type` | VARCHAR(100) | |
| `target_entity_type` | VARCHAR(100) | |
| `handoff_type` | VARCHAR(50) | `sequential`, `parallel`, `conditional`, `event_driven` |
| `correlation_key` | VARCHAR(100) | join key (e.g. `location_id`) |
| `sla_hours` | DOUBLE PRECISION | target handoff time |
| `description` | TEXT | |

**`process_handoff_log`** — observed handoff events:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `source_entity_type` | VARCHAR(100) | |
| `source_entity_id` | UUID | |
| `target_entity_type` | VARCHAR(100) | |
| `target_entity_id` | UUID | nullable (target not yet created) |
| `handoff_id` | UUID FK → `process_handoff` | |
| `handoff_at` | TIMESTAMPTZ | default `NOW()` |
| `elapsed_hours` | DOUBLE PRECISION | |
| `met_sla` | BOOLEAN | |
| `metadata` | JSONB | default `'{}'` |

**`process_trace`** — end-to-end cross-entity traces:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `trace_key` | VARCHAR(255) | groups trace steps |
| `entity_type` | VARCHAR(100) | |
| `entity_id` | UUID | |
| `step_order` | INTEGER | |
| `entered_at` | TIMESTAMPTZ | |
| `exited_at` | TIMESTAMPTZ | |
| `duration_hours` | DOUBLE PRECISION | |

### Seeded handoff declarations (9)

| Source → Target | Type | Correlation | SLA (h) |
|---|---|---|---|
| `harvest_event` → `data_stream_post` | sequential | `location_id` | 24 |
| `data_stream_post` → `impact_claim` | sequential | `location_id` | 72 |
| `farm_activity` → `harvest_event` | sequential | `location_id` | — |
| `stakeholder_feedback` → `data_stream_post` | event_driven | `location_id` | 48 |
| `agent_task` → `data_stream_post` | event_driven | `subject_id` | 24 |
| `metric_value` → `report_snapshot` | sequential | `location_id` | — |
| `harvest_event` → `traceability_batch` | sequential | `location_id` | 48 |
| `traceability_batch` → `market_order` | event_driven | `location_id` | 72 |
| `pest_intervention` → `extension_enrollment` | event_driven | `location_id` | 168 |

## 7. Process-health board (Phase D)

Single BAM-style view combining VSM metrics (WIP, lead time, FTY,
bottlenecks), process-mining conformance, optional predictive-breach risk,
and CMMI maturity assessment across 10 process keys. Registered as the
`process_health` report type.

### Key functions

| Function | Description |
|---|---|
| `build_health(conn, location_id, sla_target_hours)` | Assembles full BAM board: VSM + conformance + breach risk + maturity |
| `generate_process_health(conn, location_id, period_start, period_end)` | Report-generator compatible entry point (no SLA breach risk) |

### Internal assembly

1. For each entity type in `value_stream._PIPELINE` (8 types): loads model, gets initial/goal/fail states, computes lead times, FTY.
2. Computes `wip_by_stage`, `bottleneck_ranking` from `value_stream`.
3. Computes conformance per entity type (total instances, non-conforming count, ratio).
4. If `sla_target_hours` given: computes breach risk per entity type via `predictive_bpm.breaches()`.
5. Computes maturity for 10 process keys using CMMI-inspired `assess_maturity()` from `process_gap`.

### CLI

```bash
python3 -m services.analytics.process_health board [--location-id UUID] [--sla-target-hours 72]
python3 -m services.export.report_generator --type process_health [--location-id UUID]
```

## 8. Auto-escalation (Phase E)

When a governed process instance is predicted to breach its SLA, raise an
escalation: record it in `process_escalation` and (optionally, when an org is
supplied) create a draft `work_item` for human follow-up. Idempotent per open
instance; never verifies or publishes anything (agents/handlers stay
read/draft-only).

### Table: `process_escalation`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `entity_type` | VARCHAR(100) | |
| `entity_id` | UUID | |
| `work_item_id` | UUID | optional draft work_item for follow-up |
| `reason` | TEXT | |
| `breach_probability` | DOUBLE PRECISION | |
| `escalated_to` | UUID | |
| `resolved_at` | TIMESTAMPTZ | NULL = unresolved |
| `created_at` | TIMESTAMPTZ | default `now()` |

**Indexes:** `idx_pe_entity (entity_type, entity_id)`, `idx_pe_open (resolved_at)`

### Key functions

| Function | Description |
|---|---|
| `find_at_risk(conn, sla_target_hours, threshold)` | All in-flight instances predicted to breach across governed types; work_items use `due_at`/`sla_at` |
| `sweep_and_escalate(conn, sla_target_hours, threshold, org_id)` | Raises escalations; creates draft work_items when `org_id` supplied; idempotent |
| `resolve_escalation(conn, escalation_id, resolved_by)` | Marks an escalation resolved |

### work_item SLA handling

For `work_item` entities, the escalation engine uses the per-instance SLA
target (`due_at` / `sla_at` columns) when present, falling back to the
default 72-hour target. This allows individual work items to have custom
deadlines.

### CLI

```bash
python3 -m services.management.escalation sweep [--org-id UUID] [--sla-target-hours 72] [--threshold 0.5]
python3 -m services.management.escalation resolve --escalation-id UUID [--resolved-by UUID]
```

## 9. Per-entity-type state models (Phase F)

The canonical 5-state `process_model` is generalized to a per-`entity_type`
model (`186_process_state_models.sql`): the `entity_type` column defaults to
`'*'` for the publication pipeline, and explicit rows define other state
machines. Mining, prediction, and escalation load the model for each entity
type, so any governed table with its own lifecycle is handled by the same
engine.

### Seeded per-type models

**`work_item`** — 6 states:

| Status | Terminal | Goal | Allowed next |
|---|---|---|---|
| `draft` | no | no | `assigned`, `cancelled` |
| `assigned` | no | no | `in_progress`, `draft`, `cancelled` |
| `in_progress` | no | no | `blocked`, `done`, `cancelled` |
| `blocked` | no | no | `in_progress`, `cancelled` |
| `done` | yes | yes | — |
| `cancelled` | yes | no | — |

**`market_order`** — 5 states (vocabulary enforced by CHECK constraint):

| Status | Terminal | Goal | Allowed next |
|---|---|---|---|
| `pending` | no | no | `confirmed`, `cancelled` |
| `confirmed` | no | no | `shipped`, `cancelled` |
| `shipped` | no | no | `delivered`, `cancelled` |
| `delivered` | yes | yes | — |
| `cancelled` | yes | no | — |

**`metric_value`** — 2 states (mapped from `verified` boolean):

| Status | Terminal | Goal | Allowed next |
|---|---|---|---|
| `draft` | no | no | `verified` |
| `verified` | yes | yes | — |

**`credit_retirement`** — uses the canonical 5-state vocabulary; only needed a trigger.

### State model triggers (`187_state_model_triggers.sql`)

| Table | Trigger | Notes |
|---|---|---|
| `work_item` | `trg_lt_work_item` | `AFTER UPDATE OF status` |
| `market_order` | `trg_lt_market_order` | `AFTER UPDATE OF status`; CHECK constraint enforces vocabulary |
| `credit_retirement` | `trg_lt_credit_retirement` | `AFTER UPDATE OF status` |
| `metric_value` | `trg_lt_metric_value` | `AFTER INSERT OR UPDATE OF verified`; maps boolean to draft/verified via `fn_record_metric_lifecycle` |

### process_model_sync

Keeps `process_model` rows in sync from registered `WorkflowSpec` instances:

```bash
python3 -m services.analytics.process_model_sync
```

Per-type rows are kept in sync from their `WorkflowSpec`; stale rows for
spec-driven entity types are deleted. Adding a new governed table = add a
`WorkflowSpec` (or seed a `process_model` row) + a lifecycle trigger. No
engine code changes are needed for conformance, prediction, the process-health
board, or auto-escalation.

## 10. Process targets & maturity

Defines target-state process metrics, compares against as-is, computes gaps,
and assigns CMMI-inspired maturity levels (`191_process_targets.sql`).

### Tables

**`process_maturity_level`** — reference data:

| Level | Name | Description |
|---|---|---|
| 1 | Initial | Processes are ad-hoc and chaotic. Success depends on individual effort. |
| 2 | Managed | Processes are planned and tracked. Basic project management exists. |
| 3 | Defined | Processes are well-documented and standardized across the organization. |
| 4 | Quantitatively Managed | Processes are measured and controlled with statistical techniques. |
| 5 | Optimizing | Continuous process improvement through incremental and innovative changes. |

**`process_target`** — target-state process metrics:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `process_key` | VARCHAR(100) FK → `process_map` | |
| `entity_type` | VARCHAR(100) | nullable for process-wide targets |
| `metric_name` | VARCHAR(100) | e.g. `lead_time_days`, `fty_pct` |
| `target_value` | DOUBLE PRECISION | |
| `target_direction` | VARCHAR(10) | `lte`, `gte`, or `eq` |
| `unit` | VARCHAR(40) | |
| `period` | VARCHAR(40) | default `all` |
| `source_ref` | VARCHAR(200) | |

**`process_gap`** — gap analysis results:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `process_key` | VARCHAR(100) FK → `process_map` | |
| `entity_type` | VARCHAR(100) | |
| `metric_name` | VARCHAR(100) | |
| `target_value` | DOUBLE PRECISION | |
| `actual_value` | DOUBLE PRECISION | |
| `gap_value` | DOUBLE PRECISION | |
| `gap_pct` | DOUBLE PRECISION | |
| `maturity_level` | INTEGER | 1–5 |
| `assessment_notes` | TEXT | |
| `assessed_at` | TIMESTAMPTZ | default `NOW()` |
| `assessed_by` | UUID | |

**`process_maturity`** — CMMI maturity assessments:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `process_key` | VARCHAR(100) FK → `process_map` | |
| `maturity_level` | INTEGER | 1–5 |
| `level_name` | VARCHAR(100) | |
| `description` | TEXT | |
| `assessed_at` | TIMESTAMPTZ | default `NOW()` |
| `assessed_by` | UUID | |

### Seeded targets (10 processes, 25+ metrics)

| Process | Entity type | Metrics |
|---|---|---|
| `farm_operations` | `farm_activity` | lead_time_days ≤ 3, fty_pct ≥ 85, rework_rate_pct ≤ 10 |
| `harvest_management` | `harvest_event` | lead_time_days ≤ 2, fty_pct ≥ 90 |
| `data_publication` | `data_stream_post` | lead_time_days ≤ 5, fty_pct ≥ 80, cycle_time_days ≤ 7 |
| `impact_verification` | `impact_claim` | lead_time_days ≤ 10, fty_pct ≥ 75 |
| `metric_governance` | `metric_value` | lead_time_days ≤ 1, fty_pct ≥ 95 |
| `work_management` | `work_item` | lead_time_days ≤ 5, fty_pct ≥ 80, cycle_time_days ≤ 10 |
| `event_delivery` | — | delivery_success_pct ≥ 99, avg_latency_ms ≤ 500 |
| `stakeholder_feedback` | `stakeholder_feedback` | lead_time_days ≤ 14, fty_pct ≥ 70 |
| `agent_execution` | `agent_task` | lead_time_days ≤ 1, fty_pct ≥ 90 |
| `reporting` | `report_snapshot` | lead_time_days ≤ 3, fty_pct ≥ 85 |

### Taxonomy expansion (`194_process_taxonomy_expansion.sql`)

Six additional processes with entity mappings and SLA targets:

| Process | Entity type | lead_time_days | fty_pct | cycle_time_days |
|---|---|---|---|---|
| `traceability` | `traceability_batch` | ≤ 5 | ≥ 85 | ≤ 7 |
| `digital_finance` | `insurance_claim` | ≤ 3 | ≥ 90 | ≤ 5 |
| `pest_management` | `pest_intervention` | ≤ 2 | ≥ 80 | ≤ 4 |
| `emergency_response` | `emergency_incident` | ≤ 1 | ≥ 75 | ≤ 3 |
| `cooperative_management` | `cooperative_order` | ≤ 7 | ≥ 80 | ≤ 14 |
| `extension_training` | `extension_enrollment` | ≤ 5 | ≥ 85 | ≤ 10 |

### Key functions (`process_gap.py`)

| Function | Description |
|---|---|
| `assess_process(conn, process_key, location_id)` | Full gap analysis: loads targets, computes actuals, calculates gaps |
| `assess_maturity(conn, process_key)` | Auto-assess maturity level (1–5) based on capabilities and gap analysis |
| `assess_all_processes(conn, location_id)` | Gap analysis across all processes from `process_map` |
| `process_improvement_initiatives(conn, process_key)` | Recommended improvement actions based on gap analysis |
| `process_maturity_trend(conn, process_key)` | Historical maturity assessments |

## 11. Process simulation

Enables what-if process simulation, stores simulation results, and persists
process capability indices (`193_process_simulation.sql`).

### Tables

**`process_simulation`** — simulation scenarios:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | VARCHAR(255) | |
| `description` | TEXT | |
| `process_key` | VARCHAR(100) FK → `process_map` | |
| `scenario_params` | JSONB | parameter overrides |
| `status` | VARCHAR(50) | `draft`, `running`, `completed`, `cancelled` |
| `results` | JSONB | |
| `created_by` | UUID | |
| `location_id` | UUID FK → `location` | |
| `created_at` | TIMESTAMPTZ | default `now()` |
| `completed_at` | TIMESTAMPTZ | |

**`process_simulation_result`** — per-metric simulation results:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `simulation_id` | UUID FK → `process_simulation` | |
| `metric_name` | VARCHAR(100) | |
| `baseline_value` | DOUBLE PRECISION | |
| `simulated_value` | DOUBLE PRECISION | |
| `improvement_pct` | DOUBLE PRECISION | |
| `confidence` | DOUBLE PRECISION | |
| `computed_at` | TIMESTAMPTZ | default `now()` |

**`process_capability`** — persisted capability indices:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `entity_type` | VARCHAR(100) | |
| `metric` | VARCHAR(100) | |
| `cp` | DOUBLE PRECISION | process potential |
| `cpk` | DOUBLE PRECISION | process centering |
| `pp` | DOUBLE PRECISION | process performance |
| `ppk` | DOUBLE PRECISION | performance centering |
| `sigma_level` | DOUBLE PRECISION | derived from Cpk |
| `period` | VARCHAR(40) | |
| `computed_at` | TIMESTAMPTZ | default `now()` |

## 12. Database schemas summary

17 tables across 8 schema files:

| Schema | Tables |
|---|---|
| `179_lifecycle_transition.sql` | `lifecycle_transition` |
| `182_process_mining.sql` | `process_variant`, `process_model` |
| `183_predictive_process.sql` | `predictive_process_forecast` |
| `184_process_control.sql` | `process_kpi_snapshot`, `process_ctq` |
| `185_process_escalation.sql` | `process_escalation` |
| `186_process_state_models.sql` | extends `process_model` with per-type rows |
| `190_process_interfaces.sql` | `process_handoff`, `process_handoff_log`, `process_trace` |
| `191_process_targets.sql` | `process_maturity_level`, `process_target`, `process_gap`, `process_maturity` |
| `193_process_simulation.sql` | `process_simulation`, `process_simulation_result`, `process_capability` |
| `194_process_taxonomy_expansion.sql` | extends `process_target`, `process_handoff`, `process_entity_mapping` |

## 13. Testing

```bash
python3 -m pytest tests/test_process_mining.py -v
python3 -m pytest tests/test_predictive_bpm.py -v
python3 -m pytest tests/test_process_control.py -v
python3 -m pytest tests/test_process_health.py -v
python3 -m pytest tests/test_process_escalation.py -v
python3 -m pytest tests/test_process_model_sync.py -v
python3 -m pytest tests/test_workflow_specs.py tests/test_workflow_spec_conformance.py -v
```

| Test file | Tests | Coverage |
|---|---|---|
| `test_process_mining.py` | `test_discover_variants`, `test_classify_conformance`, `test_check_conformance`, `test_case_timeline`, `test_cycle_time_distribution` | Variants, conformance rules, timelines, cycle times |
| `test_predictive_bpm.py` | `test_predict_remaining`, `test_predict_with_sla`, `test_breaches`, `test_persist_forecasts` | Prediction, SLA breach, persistence |
| `test_process_control.py` | `test_control_limits`, `test_capture_snapshots`, `test_evaluate_control` | Control limits math, snapshot capture, OOC detection |
| `test_process_health.py` | `test_build_health_structure`, `test_generate_process_health_signature`, `test_report_registration` | BAM board structure, report registration |
| `test_process_escalation.py` | `test_sweep_creates_escalation_and_work_item`, `test_sweep_idempotent`, `test_resolve_escalation`, `test_work_item_due_at_escalation` | Escalation creation, idempotency, resolution, work_item SLA |
| `test_process_model_sync.py` | `test_sync_work_item_model` | WorkflowSpec → process_model sync |
| `test_workflow_specs.py` | structural validation tests | Spec validation |
| `test_workflow_spec_conformance.py` | 26 spec validation, lifecycle conformance for 9 entity types | All registered specs validate |
