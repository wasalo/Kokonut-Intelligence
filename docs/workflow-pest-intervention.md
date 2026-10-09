# Pest Intervention Lifecycle

Spec: `pest_intervention`

## Invariants

- intervention requires scouting_id, type, method
- verification confirms IPM compliance
- publication records intervention for resistance tracking

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| pi_draft_entry | farmer | draft | Create pest intervention | withdrawn before submission | reject | rejected | pi_reject_draft | entry |
| pi_draft_entry | farmer | draft | Create pest intervention | submit for verification | submit | submitted | pi_submit | entry |
| pi_publish | system | published | Terminal published pest intervention | - | terminal | - | - | terminal |
| pi_reject_draft | reviewer | rejected | Terminal rejected pest intervention | - | terminal | - | - | terminal |
| pi_reject_submitted | reviewer | rejected | Terminal rejected pest intervention | - | terminal | - | - | terminal |
| pi_reject_verified | reviewer | rejected | Terminal rejected pest intervention | - | terminal | - | - | terminal |
| pi_submit | farmer | submitted | Submit pest intervention for review | IPM non-compliance | reject | rejected | pi_reject_submitted | - |
| pi_submit | farmer | submitted | Submit pest intervention for review | IPM compliance confirmed | verify | verified | pi_verify | - |
| pi_verify | reviewer | verified | Verify pest intervention compliance | approved for resistance tracking | publish | published | pi_publish | human-approval |
| pi_verify | reviewer | verified | Verify pest intervention compliance | intervention rejected | reject | rejected | pi_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Governance Controls

- Human IPM-compliance verification is required before publication.
- Published intervention data feeds resistance and compliance tracking.

## Data and Persistence

- pest_intervention | scouting, IPM method, pesticide and resistance records

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_pest_management.py`

## Mermaid

```mermaid
flowchart TD
    pi_draft_entry[pi_draft_entry: Create pest intervention [farmer]]
    pi_publish((pi_publish: Terminal published pest intervention [system]))
    pi_reject_draft((pi_reject_draft: Terminal rejected pest intervention [reviewer]))
    pi_reject_submitted((pi_reject_submitted: Terminal rejected pest intervention [reviewer]))
    pi_reject_verified((pi_reject_verified: Terminal rejected pest intervention [reviewer]))
    pi_submit[pi_submit: Submit pest intervention for review [farmer]]
    pi_verify[pi_verify: Verify pest intervention compliance [reviewer]]
    pi_draft_entry -->|withdrawn before submission / reject -> rejected| pi_reject_draft
    pi_draft_entry -->|submit for verification / submit -> submitted| pi_submit
    pi_submit -->|IPM non-compliance / reject -> rejected| pi_reject_submitted
    pi_submit -->|IPM compliance confirmed / verify -> verified| pi_verify
    pi_verify -->|approved for resistance tracking / publish -> published| pi_publish
    pi_verify -->|intervention rejected / reject -> rejected| pi_reject_verified
```
