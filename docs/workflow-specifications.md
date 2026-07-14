# Workflow Specifications

Kokonut uses Python-native, DRAKON-inspired specifications for workflows where correctness depends on state, transaction ordering, retries, external effects, or human authority. Production code remains authoritative for execution; the specifications define the allowed control-flow contract and generate review documentation and tests.

## Design

Each specification declares:

- One entry step.
- States, actors, actions, guards, outcomes, and destinations.
- Transaction and external-side-effect boundaries.
- Human approval and high-risk actions.
- Retry safety and explicitly bounded loops.
- Terminal outcomes and invariants.

Validation rejects unreachable steps, dangling targets, undeclared states, nonterminating paths, unbounded cycles, high-risk paths without prior human approval, and agent paths reaching verification or publication.

Markdown decision tables are authoritative for review. Mermaid output is explanatory and introduces no renderer or runtime dependency.

## Current Scope

### Event Bus

`event_bus_delivery` specifies event claiming, handler delivery, lease checks, external invocation, partial success, retries, dead-letter creation, replay, and disposal. It explicitly documents at-least-once handler effects.

### Carbon Retirement

`carbon_retirement` specifies reservation, submission, independent review, confirmation, rejection, cancellation, terminal idempotency, and the reserved/retired supply equation.

## Commands

```bash
python3 -m services.workflow_specs list
python3 -m services.workflow_specs validate
python3 -m services.workflow_specs render event_bus_delivery --format markdown
python3 -m services.workflow_specs render carbon_retirement --format mermaid
python3 scripts/render-workflow-specs.py
```

CI validates the specifications and checks that committed generated documents are current.

## Follow-On Phases

1. Scheduler claims, dependencies, resource acquisition, retries, and lease recovery.
2. Directus governed lifecycle, role routing, collection guards, and durable audit behavior.
3. Decision evaluation, approval, atomic execution claim, and outcomes.
4. Delphi study readiness, contribution loop, stopping advice, dissent review, approval, and public eligibility.
5. Backcast milestone status, dependency readiness, assumption challenges, premortems, and advisory winners.
6. Evidence-lineage generation rebuild and activation fault boundaries.
7. Threat forecast question lifecycle, temporal resolution, scoring, and flag decision tables.
8. Canonical ingestion retry semantics and side-effect idempotency.
9. Operator deployment, incident, retirement, replay, and advisory-adoption runbooks.

Each phase should be added only when it produces useful conformance or fault-injection tests. Straightforward CRUD and pure calculations remain outside this framework.
