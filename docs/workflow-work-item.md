# Work Item Lifecycle

Spec: `work_item`

## Invariants

- A work item cannot leave draft without an assignee.
- An item must be assigned before it can be started.
- blocked requires a reason recorded in work_item_event.
- done requires an assignee and a recorded completion event.
- cancelled is terminal and may be reached from any non-terminal state.
- Exactly one accountable responsibility should exist before work starts (RACI).

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| assign | manager | assigned | Assign owner | cancelled while assigned | cancel | cancelled | cancel_assigned | - |
| assign | manager | assigned | Assign owner | work begins | start | in_progress | start | - |
| assign | manager | assigned | Assign owner | owner removed | unassign | draft | unassign | - |
| block | worker | blocked | Record impediment | cancelled while blocked | cancel | cancelled | cancel_active | - |
| block | worker | blocked | Record impediment | impediment cleared | unblock | in_progress | unblock | - |
| cancel_active | manager | cancelled | Terminal cancelled item | - | terminal | - | - | terminal |
| cancel_assigned | manager | cancelled | Terminal cancelled item | - | terminal | - | - | terminal |
| cancel_draft | manager | cancelled | Terminal cancelled item | - | terminal | - | - | terminal |
| complete | worker | done | Terminal completed work item | - | terminal | - | - | terminal |
| draft_entry | manager | draft | Create work item | has assignee | assign | assigned | assign | entry |
| draft_entry | manager | draft | Create work item | rejected before assignment | cancel | cancelled | cancel_draft | entry |
| start | worker | in_progress | Begin work | impediment found | block | blocked | block | - |
| start | worker | in_progress | Begin work | cancelled in progress | cancel | cancelled | cancel_active | - |
| start | worker | in_progress | Begin work | work finished | complete | done | complete | - |
| unassign | manager | draft | Return to draft without owner | reassigned | assign | assigned | assign | - |
| unassign | manager | draft | Return to draft without owner | cancelled in draft | cancel | cancelled | cancel_draft | - |
| unblock | worker | in_progress | Resume work | re-impediment | block | blocked | block | - |
| unblock | worker | in_progress | Resume work | cancelled in progress | cancel | cancelled | cancel_active | - |
| unblock | worker | in_progress | Resume work | work finished | complete | done | complete | - |

## Sources

- `schemas/postgres/175_management_work_items.sql`
- `services/management/workbench.py`
- `services/management/responsibility.py`

## Governance Controls

- A work item requires an assignee and exactly one accountable responsibility before start.
- Claims, leases, escalation, and completion are durable.

## Data and Persistence

- work_item | assignment, claims, events, responsibilities, SLA

## Audit Controls

- Assignment, blocker, completion, cancellation, and SLA timestamps are recorded.

## Tests

- `tests/test_management_workflow.py`
- `tests/test_responsibility_assignment.py`

## Mermaid

```mermaid
flowchart TD
    assign[assign: Assign owner [manager]]
    block[block: Record impediment [worker]]
    cancel_active((cancel_active: Terminal cancelled item [manager]))
    cancel_assigned((cancel_assigned: Terminal cancelled item [manager]))
    cancel_draft((cancel_draft: Terminal cancelled item [manager]))
    complete((complete: Terminal completed work item [worker]))
    draft_entry[draft_entry: Create work item [manager]]
    start[start: Begin work [worker]]
    unassign[unassign: Return to draft without owner [manager]]
    unblock[unblock: Resume work [worker]]
    assign -->|cancelled while assigned / cancel -> cancelled| cancel_assigned
    assign -->|work begins / start -> in_progress| start
    assign -->|owner removed / unassign -> draft| unassign
    block -->|cancelled while blocked / cancel -> cancelled| cancel_active
    block -->|impediment cleared / unblock -> in_progress| unblock
    draft_entry -->|has assignee / assign -> assigned| assign
    draft_entry -->|rejected before assignment / cancel -> cancelled| cancel_draft
    start -->|impediment found / block -> blocked| block
    start -->|cancelled in progress / cancel -> cancelled| cancel_active
    start -->|work finished / complete -> done| complete
    unassign -->|reassigned / assign -> assigned| assign
    unassign -->|cancelled in draft / cancel -> cancelled| cancel_draft
    unblock -->|re-impediment / block -> blocked| block
    unblock -->|cancelled in progress / cancel -> cancelled| cancel_active
    unblock -->|work finished / complete -> done| complete
```
