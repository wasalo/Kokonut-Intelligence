# Tactical Governance Session Lifecycle

Spec: `governance_tactical_session`

## Invariants

- A completed session has an outcome summary.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| active_step | human reviewer | active | Process active | session cancelled | cancel | cancelled | cancelled_step | transaction, human-approval |
| active_step | human reviewer | active | Process active | outcomes recorded | complete | completed | completed_step | transaction, human-approval |
| cancelled_step | circle participant | cancelled | Process cancelled | - | terminal | - | - | terminal |
| completed_step | human reviewer | completed | Process completed | - | terminal | - | - | terminal |
| planned_step | circle participant | planned | Process planned | session begins | start | active | active_step | entry |
| planned_step | circle participant | planned | Process planned | session cancelled | cancel | cancelled | cancelled_step | entry |

## Sources

- `schemas/postgres/247_governance_tactical_coordination.sql`

## Mermaid

```mermaid
flowchart TD
    active_step[active_step: Process active [human reviewer]]
    cancelled_step((cancelled_step: Process cancelled [circle participant]))
    completed_step((completed_step: Process completed [human reviewer]))
    planned_step[planned_step: Process planned [circle participant]]
    active_step -->|session cancelled / cancel -> cancelled| cancelled_step
    active_step -->|outcomes recorded / complete -> completed| completed_step
    planned_step -->|session begins / start -> active| active_step
    planned_step -->|session cancelled / cancel -> cancelled| cancelled_step
```
