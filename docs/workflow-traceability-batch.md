# Traceability Batch Lifecycle

Spec: `traceability_batch`

## Invariants

- batch requires location_id, crop, quantity, harvest_date
- verification confirms custody chain integrity
- publication enables provenance tracking

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| tb_draft_entry | farmer | draft | Create traceability batch | withdrawn before submission | reject | rejected | tb_reject_draft | entry |
| tb_draft_entry | farmer | draft | Create traceability batch | submit for verification | submit | submitted | tb_submit | entry |
| tb_publish | system | published | Terminal published traceability batch | - | terminal | - | - | terminal |
| tb_reject_draft | reviewer | rejected | Terminal rejected traceability batch | - | terminal | - | - | terminal |
| tb_reject_submitted | reviewer | rejected | Terminal rejected traceability batch | - | terminal | - | - | terminal |
| tb_reject_verified | reviewer | rejected | Terminal rejected traceability batch | - | terminal | - | - | terminal |
| tb_submit | farmer | submitted | Submit traceability batch for review | custody chain invalid | reject | rejected | tb_reject_submitted | - |
| tb_submit | farmer | submitted | Submit traceability batch for review | custody chain verified | verify | verified | tb_verify | - |
| tb_verify | reviewer | verified | Verify traceability batch integrity | approved for provenance tracking | publish | published | tb_publish | human-approval |
| tb_verify | reviewer | verified | Verify traceability batch integrity | integrity check failed | reject | rejected | tb_reject_verified | human-approval |

## Sources

- `schemas/postgres/003_operations.sql`
- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Governance Controls

- Human custody-chain verification is required before provenance publication.

## Data and Persistence

- produce_batch | custody, quality, certification, provenance, food safety

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_traceability.py`

## Mermaid

```mermaid
flowchart TD
    tb_draft_entry[tb_draft_entry: Create traceability batch [farmer]]
    tb_publish((tb_publish: Terminal published traceability batch [system]))
    tb_reject_draft((tb_reject_draft: Terminal rejected traceability batch [reviewer]))
    tb_reject_submitted((tb_reject_submitted: Terminal rejected traceability batch [reviewer]))
    tb_reject_verified((tb_reject_verified: Terminal rejected traceability batch [reviewer]))
    tb_submit[tb_submit: Submit traceability batch for review [farmer]]
    tb_verify[tb_verify: Verify traceability batch integrity [reviewer]]
    tb_draft_entry -->|withdrawn before submission / reject -> rejected| tb_reject_draft
    tb_draft_entry -->|submit for verification / submit -> submitted| tb_submit
    tb_submit -->|custody chain invalid / reject -> rejected| tb_reject_submitted
    tb_submit -->|custody chain verified / verify -> verified| tb_verify
    tb_verify -->|approved for provenance tracking / publish -> published| tb_publish
    tb_verify -->|integrity check failed / reject -> rejected| tb_reject_verified
```
