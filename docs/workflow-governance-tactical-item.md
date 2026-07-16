# Tactical Governance Item Lifecycle

Spec: `governance_tactical_item`

## Invariants

- A disposed item has a disposition type, summary, and actor.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| cancelled_step | circle participant | cancelled | Process cancelled | - | terminal | - | - | terminal |
| disposed_step | circle participant | disposed | Process disposed | - | terminal | - | - | terminal |
| in_progress_step | circle participant | in_progress | Process in_progress | item cancelled | cancel | cancelled | cancelled_step | - |
| in_progress_step | circle participant | in_progress | Process in_progress | explicit disposition recorded | dispose | disposed | disposed_step | - |
| open_step | circle participant | open | Process open | item cancelled | cancel | cancelled | cancelled_step | entry |
| open_step | circle participant | open | Process open | an owner starts the action | start | in_progress | in_progress_step | entry |

## Sources

- `schemas/postgres/247_governance_tactical_coordination.sql`

## Mermaid

```mermaid
flowchart TD
    cancelled_step((cancelled_step: Process cancelled [circle participant]))
    disposed_step((disposed_step: Process disposed [circle participant]))
    in_progress_step[in_progress_step: Process in_progress [circle participant]]
    open_step[open_step: Process open [circle participant]]
    in_progress_step -->|item cancelled / cancel -> cancelled| cancelled_step
    in_progress_step -->|explicit disposition recorded / dispose -> disposed| disposed_step
    open_step -->|item cancelled / cancel -> cancelled| cancelled_step
    open_step -->|an owner starts the action / start -> in_progress| in_progress_step
```
