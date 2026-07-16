# Governance Role Lifecycle

Spec: `governance_role`

## Invariants

- A role is independent of the party filling it.
- An active role requires an active circle.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| active_step | human reviewer | active | Process active | role is superseded | retire | retired | retired_step | transaction, human-approval |
| active_step | human reviewer | active | Process active | role authority is paused | suspend | suspended | suspended_step | transaction, human-approval |
| approved_step | human reviewer | approved | Process approved | role is activated in an active circle | activate | active | active_step | transaction, human-approval |
| draft_step | circle participant | draft | Process draft | invalid role | reject | rejected | rejected_step | entry |
| draft_step | circle participant | draft | Process draft | purpose and accountabilities documented | submit | submitted | submitted_step | entry |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| retired_step | circle participant | retired | Process retired | - | terminal | - | - | terminal |
| submitted_step | circle participant | submitted | Process submitted | human approves role definition | approve | approved | approved_step | - |
| submitted_step | circle participant | submitted | Process submitted | human rejects role definition | reject | rejected | rejected_step | - |
| suspended_step | circle participant | suspended | Process suspended | role is retired | retire | retired | retired_step | - |

## Sources

- `schemas/postgres/242_governance_circles_roles.sql`

## Mermaid

```mermaid
flowchart TD
    active_step[active_step: Process active [human reviewer]]
    approved_step[approved_step: Process approved [human reviewer]]
    draft_step[draft_step: Process draft [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    retired_step((retired_step: Process retired [circle participant]))
    submitted_step[submitted_step: Process submitted [circle participant]]
    suspended_step[suspended_step: Process suspended [circle participant]]
    active_step -->|role is superseded / retire -> retired| retired_step
    active_step -->|role authority is paused / suspend -> suspended| suspended_step
    approved_step -->|role is activated in an active circle / activate -> active| active_step
    draft_step -->|invalid role / reject -> rejected| rejected_step
    draft_step -->|purpose and accountabilities documented / submit -> submitted| submitted_step
    submitted_step -->|human approves role definition / approve -> approved| approved_step
    submitted_step -->|human rejects role definition / reject -> rejected| rejected_step
    suspended_step -->|role is retired / retire -> retired| retired_step
```
