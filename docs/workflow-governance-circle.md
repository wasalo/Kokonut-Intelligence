# Governance Circle Lifecycle

Spec: `governance_circle`

## Invariants

- An active circle requires a purpose, scope, and human governance.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| active_step | human reviewer | active | Process active | circle is no longer needed | retire | retired | retired_step | transaction, human-approval |
| active_step | human reviewer | active | Process active | governance risk requires pause | suspend | suspended | suspended_step | transaction, human-approval |
| draft_step | circle participant | draft | Process draft | invalid proposal | reject | rejected | rejected_step | entry |
| draft_step | circle participant | draft | Process draft | purpose and scope documented | submit | submitted | submitted_step | entry |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| retired_step | circle participant | retired | Process retired | - | terminal | - | - | terminal |
| submitted_step | circle participant | submitted | Process submitted | human approves circle | activate | active | active_step | - |
| submitted_step | circle participant | submitted | Process submitted | human rejects circle | reject | rejected | rejected_step | - |
| suspended_step | circle participant | suspended | Process suspended | circle is retired | retire | retired | retired_step | - |

## Sources

- `schemas/postgres/242_governance_circles_roles.sql`

## Mermaid

```mermaid
flowchart TD
    active_step[active_step: Process active [human reviewer]]
    draft_step[draft_step: Process draft [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    retired_step((retired_step: Process retired [circle participant]))
    submitted_step[submitted_step: Process submitted [circle participant]]
    suspended_step[suspended_step: Process suspended [circle participant]]
    active_step -->|circle is no longer needed / retire -> retired| retired_step
    active_step -->|governance risk requires pause / suspend -> suspended| suspended_step
    draft_step -->|invalid proposal / reject -> rejected| rejected_step
    draft_step -->|purpose and scope documented / submit -> submitted| submitted_step
    submitted_step -->|human approves circle / activate -> active| active_step
    submitted_step -->|human rejects circle / reject -> rejected| rejected_step
    suspended_step -->|circle is retired / retire -> retired| retired_step
```
