# Emergency Incident Lifecycle

Spec: `emergency_incident`

## Invariants

- incident requires type, severity, description, affected_area
- verification confirms response actions
- publication enables compliance reporting

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| ei_draft_entry | farmer | draft | Create emergency incident report | withdrawn before submission | reject | rejected | ei_reject_draft | entry |
| ei_draft_entry | farmer | draft | Create emergency incident report | submit for verification | submit | submitted | ei_submit | entry |
| ei_publish | system | published | Terminal published emergency incident | - | terminal | - | - | terminal |
| ei_reject_draft | reviewer | rejected | Terminal rejected emergency incident | - | terminal | - | - | terminal |
| ei_reject_submitted | reviewer | rejected | Terminal rejected emergency incident | - | terminal | - | - | terminal |
| ei_reject_verified | reviewer | rejected | Terminal rejected emergency incident | - | terminal | - | - | terminal |
| ei_submit | farmer | submitted | Submit emergency incident for review | incident details invalid | reject | rejected | ei_reject_submitted | - |
| ei_submit | farmer | submitted | Submit emergency incident for review | response actions confirmed | verify | verified | ei_verify | - |
| ei_verify | reviewer | verified | Verify emergency incident response | approved for compliance reporting | publish | published | ei_publish | human-approval |
| ei_verify | reviewer | verified | Verify emergency incident response | incident response inadequate | reject | rejected | ei_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Governance Controls

- Human verification is required before compliance publication.

## Data and Persistence

- emergency_incident | response actions and remediation evidence

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_emergency_response.py`

## Mermaid

```mermaid
flowchart TD
    ei_draft_entry[ei_draft_entry: Create emergency incident report [farmer]]
    ei_publish((ei_publish: Terminal published emergency incident [system]))
    ei_reject_draft((ei_reject_draft: Terminal rejected emergency incident [reviewer]))
    ei_reject_submitted((ei_reject_submitted: Terminal rejected emergency incident [reviewer]))
    ei_reject_verified((ei_reject_verified: Terminal rejected emergency incident [reviewer]))
    ei_submit[ei_submit: Submit emergency incident for review [farmer]]
    ei_verify[ei_verify: Verify emergency incident response [reviewer]]
    ei_draft_entry -->|withdrawn before submission / reject -> rejected| ei_reject_draft
    ei_draft_entry -->|submit for verification / submit -> submitted| ei_submit
    ei_submit -->|incident details invalid / reject -> rejected| ei_reject_submitted
    ei_submit -->|response actions confirmed / verify -> verified| ei_verify
    ei_verify -->|approved for compliance reporting / publish -> published| ei_publish
    ei_verify -->|incident response inadequate / reject -> rejected| ei_reject_verified
```
