# Governance Tension Lifecycle

Spec: `governance_tension`

## Invariants

- A triaged or active tension has an owner role or party.
- A resolved tension has a resolution summary.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| closed_step | circle participant | closed | Process closed | - | terminal | - | - | terminal |
| deferred_step | circle participant | deferred | Process deferred | deferred item is closed with rationale | close | closed | closed_step | - |
| draft_step | circle participant | draft | Process draft | invalid report | reject | rejected | rejected_step | entry |
| draft_step | circle participant | draft | Process draft | report is ready for triage | submit | submitted | submitted_step | entry |
| in_progress_step | circle participant | in_progress | Process in_progress | tension is invalidated | reject | rejected | rejected_step | - |
| in_progress_step | circle participant | in_progress | Process in_progress | resolution is evidenced | resolve | resolved | resolved_step | - |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| resolved_step | circle participant | resolved | Process resolved | review confirms closure | close | closed | closed_step | - |
| submitted_step | circle participant | submitted | Process submitted | not actionable | reject | rejected | rejected_step | - |
| submitted_step | circle participant | submitted | Process submitted | owner is assigned | triage | triaged | triaged_step | - |
| triaged_step | circle participant | triaged | Process triaged | action is intentionally deferred | defer | deferred | deferred_step | - |
| triaged_step | circle participant | triaged | Process triaged | owned action begins | start | in_progress | in_progress_step | - |

## Sources

- `schemas/postgres/244_governance_tensions.sql`

## Mermaid

```mermaid
flowchart TD
    closed_step((closed_step: Process closed [circle participant]))
    deferred_step[deferred_step: Process deferred [circle participant]]
    draft_step[draft_step: Process draft [circle participant]]
    in_progress_step[in_progress_step: Process in_progress [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    resolved_step[resolved_step: Process resolved [circle participant]]
    submitted_step[submitted_step: Process submitted [circle participant]]
    triaged_step[triaged_step: Process triaged [circle participant]]
    deferred_step -->|deferred item is closed with rationale / close -> closed| closed_step
    draft_step -->|invalid report / reject -> rejected| rejected_step
    draft_step -->|report is ready for triage / submit -> submitted| submitted_step
    in_progress_step -->|tension is invalidated / reject -> rejected| rejected_step
    in_progress_step -->|resolution is evidenced / resolve -> resolved| resolved_step
    resolved_step -->|review confirms closure / close -> closed| closed_step
    submitted_step -->|not actionable / reject -> rejected| rejected_step
    submitted_step -->|owner is assigned / triage -> triaged| triaged_step
    triaged_step -->|action is intentionally deferred / defer -> deferred| deferred_step
    triaged_step -->|owned action begins / start -> in_progress| in_progress_step
```
