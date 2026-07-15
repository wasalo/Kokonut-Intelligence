# Harvest Event Lifecycle

Spec: `harvest_event`

## Invariants

- A harvest event begins in draft, recorded by a farmer or field worker.
- Harvest events require plot_id, crop_id, and harvest_date.
- Verification confirms the harvest occurred and yield data is accurate.
- Publication makes the harvest available for yield analytics and carbon accounting.
- Rejection is terminal and requires a reason.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| he_draft_entry | farmer | draft | Record harvest event | withdrawn before submission | reject | rejected | he_reject_draft | entry |
| he_draft_entry | farmer | draft | Record harvest event | submit for verification | submit | submitted | he_submit | entry |
| he_publish | system | published | Terminal published harvest | - | terminal | - | - | terminal |
| he_reject_draft | reviewer | rejected | Terminal rejected harvest | - | terminal | - | - | terminal |
| he_reject_submitted | reviewer | rejected | Terminal rejected harvest | - | terminal | - | - | terminal |
| he_reject_verified | reviewer | rejected | Terminal rejected harvest | - | terminal | - | - | terminal |
| he_submit | farmer | submitted | Submit harvest for verification | harvest not confirmed | reject | rejected | he_reject_submitted | - |
| he_submit | farmer | submitted | Submit harvest for verification | harvest confirmed | verify | verified | he_verify | - |
| he_verify | reviewer | verified | Verify harvest data | approved for analytics | publish | published | he_publish | human-approval |
| he_verify | reviewer | verified | Verify harvest data | yield data inaccurate | reject | rejected | he_reject_verified | human-approval |

## Sources

- `schemas/postgres/003_operations.sql`
- `schemas/postgres/137_yield_monitoring.sql`

## Mermaid

```mermaid
flowchart TD
    he_draft_entry[he_draft_entry: Record harvest event [farmer]]
    he_publish((he_publish: Terminal published harvest [system]))
    he_reject_draft((he_reject_draft: Terminal rejected harvest [reviewer]))
    he_reject_submitted((he_reject_submitted: Terminal rejected harvest [reviewer]))
    he_reject_verified((he_reject_verified: Terminal rejected harvest [reviewer]))
    he_submit[he_submit: Submit harvest for verification [farmer]]
    he_verify[he_verify: Verify harvest data [reviewer]]
    he_draft_entry -->|withdrawn before submission / reject -> rejected| he_reject_draft
    he_draft_entry -->|submit for verification / submit -> submitted| he_submit
    he_submit -->|harvest not confirmed / reject -> rejected| he_reject_submitted
    he_submit -->|harvest confirmed / verify -> verified| he_verify
    he_verify -->|approved for analytics / publish -> published| he_publish
    he_verify -->|yield data inaccurate / reject -> rejected| he_reject_verified
```
