# Governance Role Assignment Lifecycle

Spec: `governance_role_assignment`

## Invariants

- An active assignment requires human approval and a non-recused party.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| active_step | human reviewer | active | Process active | term ends | end | ended | ended_step | transaction, human-approval |
| active_step | human reviewer | active | Process active | recusal or authority pause | suspend | suspended | suspended_step | transaction, human-approval |
| ended_step | circle participant | ended | Process ended | - | terminal | - | - | terminal |
| proposed_step | circle participant | proposed | Process proposed | human approves assignment | activate | active | active_step | entry |
| proposed_step | circle participant | proposed | Process proposed | assignment is rejected | reject | rejected | rejected_step | entry |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| suspended_step | circle participant | suspended | Process suspended | assignment ends | end | ended | ended_step | - |

## Sources

- `schemas/postgres/243_governance_role_authority.sql`

## Governance Controls

- Assignment requires human approval and a non-recused party.
- Suspension and end states require explicit authority disposition.

## Data and Persistence

- governance_role_assignment | party, role, term, recusal

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_governance_links.py`
- `tests/test_governance_role_authority.py`

## Mermaid

```mermaid
flowchart TD
    active_step[active_step: Process active [human reviewer]]
    ended_step((ended_step: Process ended [circle participant]))
    proposed_step[proposed_step: Process proposed [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    suspended_step[suspended_step: Process suspended [circle participant]]
    active_step -->|term ends / end -> ended| ended_step
    active_step -->|recusal or authority pause / suspend -> suspended| suspended_step
    proposed_step -->|human approves assignment / activate -> active| active_step
    proposed_step -->|assignment is rejected / reject -> rejected| rejected_step
    suspended_step -->|assignment ends / end -> ended| ended_step
```
