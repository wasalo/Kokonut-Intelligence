# Objective Review Lifecycle

Spec: `objective`

## Invariants

- An objective starts with an initial review setting its health status.
- off_track reviews should spawn a corrective work item.
- closed is terminal; reopening requires a new review.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| at_risk | reviewer | at_risk | At-risk review | resolved or withdrawn | close | closed | closed | - |
| at_risk | reviewer | at_risk | At-risk review | worsened | escalate | off_track | off_track | - |
| at_risk | reviewer | at_risk | At-risk review | recovered | recover | on_track | on_track | - |
| closed | system | closed | Terminal closed objective | - | terminal | - | - | terminal |
| off_track | reviewer | off_track | Off-track review | partial recovery | improve | at_risk | at_risk | - |
| off_track | reviewer | off_track | Off-track review | withdrawn or superseded | close | closed | closed | - |
| off_track | reviewer | off_track | Off-track review | recovered | recover | on_track | on_track | - |
| on_track | reviewer | on_track | Initial or steady-state review | concerns emerging | flag at_risk | at_risk | at_risk | entry |
| on_track | reviewer | on_track | Initial or steady-state review | objective achieved | close | closed | closed | entry |
| on_track | reviewer | on_track | Initial or steady-state review | materially behind | flag off_track | off_track | off_track | entry |

## Sources

- `schemas/postgres/177_objective_enhancements.sql`
- `services/planning/performance.py`
- `services/management/workbench.py`

## Governance Controls

- Human review determines objective health.
- Off-track objectives require a corrective work item; reopening requires a new review.

## Data and Persistence

- objective | KPI targets, reviews, corrective work items

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_objective_performance.py`

## Mermaid

```mermaid
flowchart TD
    at_risk[at_risk: At-risk review [reviewer]]
    closed((closed: Terminal closed objective [system]))
    off_track[off_track: Off-track review [reviewer]]
    on_track[on_track: Initial or steady-state review [reviewer]]
    at_risk -->|resolved or withdrawn / close -> closed| closed
    at_risk -->|worsened / escalate -> off_track| off_track
    at_risk -->|recovered / recover -> on_track| on_track
    off_track -->|partial recovery / improve -> at_risk| at_risk
    off_track -->|withdrawn or superseded / close -> closed| closed
    off_track -->|recovered / recover -> on_track| on_track
    on_track -->|concerns emerging / flag at_risk -> at_risk| at_risk
    on_track -->|objective achieved / close -> closed| closed
    on_track -->|materially behind / flag off_track -> off_track| off_track
```
