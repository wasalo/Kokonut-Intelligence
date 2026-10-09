# Extension Enrollment Lifecycle

Spec: `extension_enrollment`

## Invariants

- enrollment requires farmer_id, module_id
- verification confirms completion and assessment score
- publication records learning progress

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| ee_draft_entry | farmer | draft | Create extension enrollment | withdrawn before submission | reject | rejected | ee_reject_draft | entry |
| ee_draft_entry | farmer | draft | Create extension enrollment | submit for verification | submit | submitted | ee_submit | entry |
| ee_publish | system | published | Terminal published extension enrollment | - | terminal | - | - | terminal |
| ee_reject_draft | trainer | rejected | Terminal rejected extension enrollment | - | terminal | - | - | terminal |
| ee_reject_submitted | trainer | rejected | Terminal rejected extension enrollment | - | terminal | - | - | terminal |
| ee_reject_verified | trainer | rejected | Terminal rejected extension enrollment | - | terminal | - | - | terminal |
| ee_submit | farmer | submitted | Submit extension enrollment for review | incomplete enrollment | reject | rejected | ee_reject_submitted | - |
| ee_submit | farmer | submitted | Submit extension enrollment for review | completion and score confirmed | verify | verified | ee_verify | - |
| ee_verify | trainer | verified | Verify extension enrollment completion | approved for learning progress recording | publish | published | ee_publish | human-approval |
| ee_verify | trainer | verified | Verify extension enrollment completion | assessment score below threshold | reject | rejected | ee_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Governance Controls

- A trainer verifies completion and score before publication.

## Data and Persistence

- extension_enrollment | module, farmer, progress, assessment

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_extension.py`

## Mermaid

```mermaid
flowchart TD
    ee_draft_entry[ee_draft_entry: Create extension enrollment [farmer]]
    ee_publish((ee_publish: Terminal published extension enrollment [system]))
    ee_reject_draft((ee_reject_draft: Terminal rejected extension enrollment [trainer]))
    ee_reject_submitted((ee_reject_submitted: Terminal rejected extension enrollment [trainer]))
    ee_reject_verified((ee_reject_verified: Terminal rejected extension enrollment [trainer]))
    ee_submit[ee_submit: Submit extension enrollment for review [farmer]]
    ee_verify[ee_verify: Verify extension enrollment completion [trainer]]
    ee_draft_entry -->|withdrawn before submission / reject -> rejected| ee_reject_draft
    ee_draft_entry -->|submit for verification / submit -> submitted| ee_submit
    ee_submit -->|incomplete enrollment / reject -> rejected| ee_reject_submitted
    ee_submit -->|completion and score confirmed / verify -> verified| ee_verify
    ee_verify -->|approved for learning progress recording / publish -> published| ee_publish
    ee_verify -->|assessment score below threshold / reject -> rejected| ee_reject_verified
```
