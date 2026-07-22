# Project Lifecycle

Spec: `project`

## Invariants

- A project cannot start without being created in draft.
- on_hold requires a reason note.
- done and cancelled are terminal.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| project_active | manager | active | Active project | cancelled while active | cancel | cancelled | project_cancel_active | - |
| project_active | manager | active | Active project | work finished | complete | done | project_done | - |
| project_active | manager | active | Active project | work paused | hold | on_hold | project_hold | - |
| project_cancel_active | manager | cancelled | Terminal cancelled project | - | terminal | - | - | terminal |
| project_cancel_draft | manager | cancelled | Terminal cancelled project | - | terminal | - | - | terminal |
| project_cancel_hold | manager | cancelled | Terminal cancelled project | - | terminal | - | - | terminal |
| project_done | manager | done | Terminal completed project | - | terminal | - | - | terminal |
| project_draft | manager | draft | Create project | work begins | start | active | project_active | entry |
| project_draft | manager | draft | Create project | cancelled before start | cancel | cancelled | project_cancel_draft | entry |
| project_hold | manager | on_hold | On-hold project | work resumed | resume | active | project_active | - |
| project_hold | manager | on_hold | On-hold project | cancelled while on hold | cancel | cancelled | project_cancel_hold | - |

## Sources

- `schemas/postgres/178_program_portfolio.sql`
- `services/planning/portfolio.py`

## Governance Controls

- Managers control start, hold, resume, completion, and cancellation.
- Hold and cancellation reasons are explicit.

## Data and Persistence

- project | program, manager, milestones, completion evidence

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_program_portfolio.py`

## Mermaid

```mermaid
flowchart TD
    project_active[project_active: Active project [manager]]
    project_cancel_active((project_cancel_active: Terminal cancelled project [manager]))
    project_cancel_draft((project_cancel_draft: Terminal cancelled project [manager]))
    project_cancel_hold((project_cancel_hold: Terminal cancelled project [manager]))
    project_done((project_done: Terminal completed project [manager]))
    project_draft[project_draft: Create project [manager]]
    project_hold[project_hold: On-hold project [manager]]
    project_active -->|cancelled while active / cancel -> cancelled| project_cancel_active
    project_active -->|work finished / complete -> done| project_done
    project_active -->|work paused / hold -> on_hold| project_hold
    project_draft -->|work begins / start -> active| project_active
    project_draft -->|cancelled before start / cancel -> cancelled| project_cancel_draft
    project_hold -->|work resumed / resume -> active| project_active
    project_hold -->|cancelled while on hold / cancel -> cancelled| project_cancel_hold
```
