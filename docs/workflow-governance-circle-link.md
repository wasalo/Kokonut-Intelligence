# Cross-Circle Link Lifecycle

Spec: `governance_circle_link`

## Invariants

- A
- n
-  
- a
- c
- t
- i
- v
- e
-  
- l
- i
- n
- k
-  
- r
- e
- q
- u
- i
- r
- e
- s
-  
- a
- c
- t
- i
- v
- e
-  
- c
- i
- r
- c
- l
- e
- s
- ,
-  
- a
- n
-  
- a
- c
- t
- i
- v
- e
-  
- r
- o
- l
- e
-  
- a
- s
- s
- i
- g
- n
- m
- e
- n
- t
- ,
-  
- a
-  
- m
- a
- n
- d
- a
- t
- e
- ,
-  
- a
- n
- d
-  
- h
- u
- m
- a
- n
-  
- a
- p
- p
- r
- o
- v
- a
- l
- .

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| active_step | human reviewer | active | Process active | term ends | end | ended | ended_step | transaction, human-approval |
| active_step | human reviewer | active | Process active | recusal or mandate pause | suspend | suspended | suspended_step | transaction, human-approval |
| ended_step | circle participant | ended | Process ended | - | terminal | - | - | terminal |
| proposed_step | circle participant | proposed | Process proposed | human approves link | activate | active | active_step | entry |
| proposed_step | circle participant | proposed | Process proposed | link rejected | reject | rejected | rejected_step | entry |
| rejected_step | circle participant | rejected | Process rejected | - | terminal | - | - | terminal |
| suspended_step | circle participant | suspended | Process suspended | link ends | end | ended | ended_step | - |

## Sources

- `schemas/postgres/248_governance_circle_links.sql`

## Governance Controls

- Active links require active circles, an active assignment, a mandate, and human approval.

## Data and Persistence

- governance_circle_link | source circle, target circle, mandate

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_governance_links.py`

## Mermaid

```mermaid
flowchart TD
    active_step[active_step: Process active [human reviewer]]
    ended_step((ended_step: Process ended [circle participant]))
    proposed_step[proposed_step: Process proposed [circle participant]]
    rejected_step((rejected_step: Process rejected [circle participant]))
    suspended_step[suspended_step: Process suspended [circle participant]]
    active_step -->|term ends / end -> ended| ended_step
    active_step -->|recusal or mandate pause / suspend -> suspended| suspended_step
    proposed_step -->|human approves link / activate -> active| active_step
    proposed_step -->|link rejected / reject -> rejected| rejected_step
    suspended_step -->|link ends / end -> ended| ended_step
```
