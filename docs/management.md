# Management Backbone (Organizing & Work Management)

The Management features add an additive backbone for organizing people and tracking
assigned work, grounded in management-theory functions: **organize** (structure + responsibility)
and **command/control** (work execution with a governed lifecycle).

These pillars reuse existing infrastructure rather than replacing it:

- `organization` / `organization_member` / `staff` / `farmer_identity` (RACI sits on top).
- `scheduled_task` / `task_run` remain the **automation** cron substrate; human/agent *work*
  lives in the distinct `work_item` table so the two concerns never conflate.
- The `work_item` lifecycle is a declarative workflow specification
  (`services/workflow_specs/work_item.py`) validated by the same engine as
  `event_bus_delivery` and `carbon_retirement` (see `docs/workflow-work-item.md`).

## Organizing: teams and RACI responsibility

- `org_team` — teams within an `organization` for delegation and span of control.
- `responsibility_assignment` — generic RACI link between any governed entity
  (`entity_type`, `entity_id`, following the `kokonut:{entity_type}:{entity_id}` IRI convention)
  and a party (`staff`, `farmer`, `agent`, `team`). A partial unique index enforces exactly one
  **accountable** party per entity.
- `organization_member.team_id` is an additive, nullable column (no breaking change).

## Work management: work items

- `work_item` — a unit of assigned work with a governed lifecycle
  (`draft → assigned → in_progress → blocked → done`, plus `cancelled` from any state).
  A `CHECK` constraint prevents leaving `draft` without an assignee.
- `work_item_event` — append-only audit trail of every transition (from/to status, actor, note).
- `services/management/workbench.py` validates every transition against the workflow spec and
  stamps `started_at` / `completed_at` / `cancelled_at`. `check_sla()` is **passive** — it surfaces
  overdue/SLA-breached open items without mutating state, respecting agent safety boundaries.

## Forward compatibility (deferred pillars)

Pillars 3–5 (Performance/MbO loop, Evidence-based management, Risk register) are designed to attach
later via the same generic `(entity_type, entity_id)` link and the `objective_id` / `risk_id`
columns already预留 on `work_item`.

## Commands

See the AGENTS.md "Local Commands" section for the full `services.management` CLI surface
(work-item create/list/show/assign/transition/sla, responsibility assign/list/list-party).

## Tests

- `tests/test_management_workflow.py` — spec validation + DB-backed lifecycle, blocked-note rule, SLA sweep.
- `tests/test_responsibility_assignment.py` — RACI validation + single-accountable enforcement.
- `tests/test_workflow_spec_conformance.py` — work_item spec registered and documented.
