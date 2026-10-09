# Farm Activity Lifecycle

Spec: `farm_activity`

## Invariants

- A farm activity begins in draft, created by a farmer or field worker.
- Farm activities require source_system, source_id, and source_raw for data lineage.
- Verification confirms the activity occurred and data is accurate.
- Publication makes the activity available for metric computation.
- Rejection is terminal and requires a reason.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| fa_draft_entry | farmer | draft | Record farm activity | withdrawn before submission | reject | rejected | fa_reject_draft | entry |
| fa_draft_entry | farmer | draft | Record farm activity | submit for verification | submit | submitted | fa_submit | entry |
| fa_publish | system | published | Terminal published activity | - | terminal | - | - | terminal |
| fa_reject_draft | reviewer | rejected | Terminal rejected activity | - | terminal | - | - | terminal |
| fa_reject_submitted | reviewer | rejected | Terminal rejected activity | - | terminal | - | - | terminal |
| fa_reject_verified | reviewer | rejected | Terminal rejected activity | - | terminal | - | - | terminal |
| fa_submit | farmer | submitted | Submit activity for verification | activity not confirmed | reject | rejected | fa_reject_submitted | - |
| fa_submit | farmer | submitted | Submit activity for verification | activity confirmed | verify | verified | fa_verify | - |
| fa_verify | reviewer | verified | Verify activity data | approved for metric computation | publish | published | fa_publish | human-approval |
| fa_verify | reviewer | verified | Verify activity data | data inaccurate after verification | reject | rejected | fa_reject_verified | human-approval |

## Sources

- `schemas/postgres/003_operations.sql`
- `services/ingestion/sensor_ingester.py`

## Governance Controls

- Human verification is required before publication or metric use.
- Operational parent context must agree with location, plot, and crop cycle constraints.

## Data and Persistence

- farm_activity | location, plot, crop cycle, source lineage

## Audit Controls

- source_system, source_id, and source_raw preserve ingestion provenance.

## Tests

- `tests/test_metrics.py`
- `tests/test_relational_integrity.py`

## Mermaid

```mermaid
flowchart TD
    fa_draft_entry[fa_draft_entry: Record farm activity [farmer]]
    fa_publish((fa_publish: Terminal published activity [system]))
    fa_reject_draft((fa_reject_draft: Terminal rejected activity [reviewer]))
    fa_reject_submitted((fa_reject_submitted: Terminal rejected activity [reviewer]))
    fa_reject_verified((fa_reject_verified: Terminal rejected activity [reviewer]))
    fa_submit[fa_submit: Submit activity for verification [farmer]]
    fa_verify[fa_verify: Verify activity data [reviewer]]
    fa_draft_entry -->|withdrawn before submission / reject -> rejected| fa_reject_draft
    fa_draft_entry -->|submit for verification / submit -> submitted| fa_submit
    fa_submit -->|activity not confirmed / reject -> rejected| fa_reject_submitted
    fa_submit -->|activity confirmed / verify -> verified| fa_verify
    fa_verify -->|approved for metric computation / publish -> published| fa_publish
    fa_verify -->|data inaccurate after verification / reject -> rejected| fa_reject_verified
```
