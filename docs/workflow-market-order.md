# Market Order Lifecycle

Spec: `market_order`

## Invariants

- order requires listing_id, buyer_id, quantity
- verification confirms payment and shipping
- publication records completed transaction

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| mo_draft_entry | buyer | draft | Create market order | withdrawn before submission | reject | rejected | mo_reject_draft | entry |
| mo_draft_entry | buyer | draft | Create market order | submit for verification | submit | submitted | mo_submit | entry |
| mo_publish | system | published | Terminal published market order | - | terminal | - | - | terminal |
| mo_reject_draft | seller | rejected | Terminal rejected market order | - | terminal | - | - | terminal |
| mo_reject_submitted | seller | rejected | Terminal rejected market order | - | terminal | - | - | terminal |
| mo_reject_verified | seller | rejected | Terminal rejected market order | - | terminal | - | - | terminal |
| mo_submit | buyer | submitted | Submit market order for review | payment failed | reject | rejected | mo_reject_submitted | - |
| mo_submit | buyer | submitted | Submit market order for review | payment and shipping confirmed | verify | verified | mo_verify | - |
| mo_verify | seller | verified | Verify market order payment and shipping | approved for transaction recording | publish | published | mo_publish | human-approval |
| mo_verify | seller | verified | Verify market order payment and shipping | order fulfillment failed | reject | rejected | mo_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Mermaid

```mermaid
flowchart TD
    mo_draft_entry[mo_draft_entry: Create market order [buyer]]
    mo_publish((mo_publish: Terminal published market order [system]))
    mo_reject_draft((mo_reject_draft: Terminal rejected market order [seller]))
    mo_reject_submitted((mo_reject_submitted: Terminal rejected market order [seller]))
    mo_reject_verified((mo_reject_verified: Terminal rejected market order [seller]))
    mo_submit[mo_submit: Submit market order for review [buyer]]
    mo_verify[mo_verify: Verify market order payment and shipping [seller]]
    mo_draft_entry -->|withdrawn before submission / reject -> rejected| mo_reject_draft
    mo_draft_entry -->|submit for verification / submit -> submitted| mo_submit
    mo_submit -->|payment failed / reject -> rejected| mo_reject_submitted
    mo_submit -->|payment and shipping confirmed / verify -> verified| mo_verify
    mo_verify -->|approved for transaction recording / publish -> published| mo_publish
    mo_verify -->|order fulfillment failed / reject -> rejected| mo_reject_verified
```
