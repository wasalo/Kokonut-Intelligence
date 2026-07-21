# Management Backbone

The management domain provides an additive operating backbone for organizing
parties, assigning responsibility, coordinating work, and surfacing execution
capacity. It does not replace scheduled automation, governance workflows,
stakeholder consent, or human approval gates.

The main implementation areas are:

- Organization structure and RACI responsibility.
- Human and agent work items with a governed lifecycle.
- Governed self-selection and bounded work allocation.
- Internal and Adelphi capacity, demand, learning, coaching, and resource signals.
- Capacity-aware work queues and portfolio health projections.
- Predictive process escalation and optional draft follow-up work.

## Organizing

`org_team` stores teams within an `organization`, including an optional staff
team lead. `organization_member.team_id` is nullable and additive, so team
membership does not replace existing organization membership.

`responsibility_assignment` is a polymorphic RACI link:

- Entity: `entity_type` plus `entity_id`, using the platform IRI convention.
- Party: `party_type` plus `party_id`.
- Party types: `staff`, `farmer`, `agent`, and `team`.
- RACI roles: `accountable`, `responsible`, `consulted`, and `informed`.

A partial unique index allows exactly one accountable party per entity. The
table intentionally uses polymorphic IDs instead of foreign keys so it can
attach to locations, work items, objectives, risks, cooperatives, and other
governed entities.

The workflow specification states that an accountable assignment should exist
before work starts. The current database and workbench do not enforce that
cross-table rule during `transition`; callers must establish and validate RACI
separately.

## Work Items

`work_item` represents human or agent work. It is separate from
`scheduled_task` and `task_run`, which remain the automation and cron substrate.

Core fields include organization, title, description, priority, assignee,
creator, location, parent item, objective/risk links, due and SLA timestamps,
and lifecycle timestamps. Later schema extensions add work type, estimated
effort, governance role, capability, skill requirements, selection mode,
autonomy level, allocation status, and an optional party assignee.

### Lifecycle

The authoritative specification is `services/workflow_specs/work_item.py` and
the generated reference is `docs/workflow-work-item.md`.

```text
draft -> assigned -> in_progress -> done
                         |             |
                         v             v
                      blocked       terminal
                         |
                         +-> in_progress
```

Cancellation is terminal and can be reached from every non-terminal state.
Assignment can return an assigned item to draft before work begins. A work item
cannot leave draft without an assignee, cannot start before assignment, and
cannot enter blocked without a reason note. The workbench records
`started_at`, `completed_at`, and `cancelled_at` when those transitions occur.

`work_item_event` is an append-only transition log containing the actor,
from/to states, action, note, and timestamp. Database actor types are
`staff`, `farmer`, `agent`, and `system`.

`check_sla()` is passive. It returns open items whose `due_at` or `sla_at` is
past and does not mutate lifecycle state or publish anything.

### Work selection

Non-assigned work can be exposed as an opportunity through `work_item` and
`v_work_opportunity_queue`. Supported selection modes are `assigned`,
`self_selected`, `delegated`, `volunteer`, and `rotational`. Autonomy levels
are `guided`, `bounded`, and `autonomous`.

An opportunity can declare a work type, effort estimate, governance role,
business capability, and JSON skill requirements. A party submits a
`work_item_claim` with optional role and capability evidence. Claims are
`proposed`, `accepted`, `rejected`, or `withdrawn`; acceptance or rejection
requires a reviewer and review timestamp. Selection events are append-only,
and the allocation state moves through `open`, `claimed`, `allocated`,
`paused`, and `closed`.

Self-selection does not bypass governance. Assigned work cannot be claimed,
closed work cannot be claimed, and claim review requires a person party.

## Operating Signals

The operating model is explicitly split into two scopes:

- `internal`: Kokonut organizational operations.
- `adelphi`: Kokonut Adelphi field operations.

`operating_pilot_scope` records the authority boundary, data boundary, and
escalation policy for each scope. A scope may be `draft`, `submitted`,
`active`, `paused`, or `retired`; active scopes require an approving party and
approval timestamp. The bootstrap helper creates or updates the corresponding
governance circle, operating coordinator role, and pilot registry entry.

Internal records keep personnel, capacity, coaching, and competency details
within the internal scope, exposing aggregates outside it. Adelphi records
keep field, ecological, market, stakeholder, and consent data in their
canonical domains; internal personnel data is not copied into field records.

### Capacity and demand

`operating_capacity_profile` records time-bounded available, committed, and
protected hours for a party. Sources may be self-reported, manager-reviewed,
system-derived, or field-coordinator supplied. The database prevents committed
plus protected hours from exceeding available hours.

`operating_demand_signal` records required hours by work type, period, scope,
priority, and source. Capacity and demand are governed independently and may be
`draft`, `submitted`, or `approved` before they contribute to
`v_operating_capacity_gap`. Gap coverage is classified as `gap`, `thin`, or
`covered`.

`v_capacity_aware_work_queue` annotates non-terminal work items with inferred
scope, capacity status, net capacity, and demand priority. It is a planning
projection, not an automatic allocator. `v_operating_portfolio_health` rolls
up demand count, gaps, thin coverage, required hours, available hours, net
hours, and covered percentage by scope.

### Competencies and learning

`operating_competency_profile` stores role-linked competency evidence with
current and target levels from 0 through 5. Submitted or verified records with
a positive difference appear in `v_operating_competency_gaps`.

`operating_learning_plan` stores competency goals, requested support, target
date, party, and scope. Its statuses are `draft`, `submitted`, `active`,
`completed`, `paused`, and `cancelled`.

### Coaching and resources

`operating_coaching_session` records focus, commitments, wellbeing check,
notes, date, coach, coachee, and status. Privacy is explicit: `private`,
`limited`, or `aggregate_only`.

`operating_resource_request` records a requested resource, description,
urgency, requested-by date, decision, rationale, and decision-maker. Decisions
are `pending`, `approved`, `partially_approved`, `declined`, or `fulfilled`;
non-pending decisions require a deciding party.

## Escalation

`services.management.escalation` reads predictive BPM state and raises an
idempotent `process_escalation` record for an open predicted SLA breach. The
default sweep target is 72 hours with a breach-probability threshold of 0.5.
For `work_item`, per-item `due_at` or `sla_at` is preferred when present.

When an organization ID is supplied, the sweep also creates a high-priority
draft `work_item` for human follow-up. It does not verify, publish, mutate the
underlying governed process, or automatically resolve the escalation.
Resolution is an explicit human action through `resolve_escalation`.

## Commands

The base CLI is:

```bash
python3 -m services.management
```

Available command groups in the current CLI are:

- `work-item create|list|show|assign|transition|sla`
- `responsibility assign|list|list-party`

Examples:

```bash
python3 -m services.management work-item create --org-id UUID --title "Review field evidence"
python3 -m services.management work-item transition --id UUID --to-status blocked --note "Awaiting sensor data"
python3 -m services.management responsibility assign --entity-type work_item --entity-id UUID --party-type staff --party-id UUID --role accountable
python3 -m services.management work-item sla --org-id UUID
```

The newer capacity, learning, work-selection, operating-pilot, operating-
support, and escalation services are currently library APIs or have their own
module CLIs; they are not all mounted under `services.management.cli`.

Known CLI caveat: `work-item assign` defaults `--actor-type` to `manager` and
`work-item transition` defaults it to `worker`, but the database accepts only
`staff`, `farmer`, `agent`, or `system`. Pass a valid actor type explicitly
until the CLI defaults are aligned.

## Safety Boundaries

- Work selection is bounded by claim review and allocation state.
- Capacity, competency, coaching, and resource records do not publish private
  personnel data by default.
- Escalation creates records and optional draft follow-up only.
- Existing agent safety and human approval gates remain authoritative for
  publication, financial actions, attestations, and other high-risk writes.
- Management records are coordination data; they do not grant authority to
  execute on-chain or governed actions.

## Source References

- `schemas/postgres/174_management_organization.sql`
- `schemas/postgres/175_management_work_items.sql`
- `schemas/postgres/185_process_escalation.sql`
- `schemas/postgres/250_work_selection_claims.sql`
- `schemas/postgres/251_operating_capacity_demand.sql`
- `schemas/postgres/252_operating_competencies_learning.sql`
- `schemas/postgres/253_operating_coaching_resources.sql`
- `schemas/postgres/254_capacity_aware_planning.sql`
- `schemas/postgres/255_dual_scope_operating_pilot.sql`
- `services/management/`
- `services/workflow_specs/work_item.py`

## Tests

- `tests/test_management_workflow.py`
- `tests/test_responsibility_assignment.py`
- `tests/test_work_selection.py`
- `tests/test_capacity_signals.py`
- `tests/test_capacity_aware_planning.py`
- `tests/test_learning_plans.py`
- `tests/test_operating_support.py`
- `tests/test_operating_pilot.py`
- `tests/test_process_escalation.py`
- `tests/test_workflow_spec_conformance.py`
