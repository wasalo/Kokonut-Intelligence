# Cooperative Order Lifecycle

Spec: `cooperative_order`

## Invariants

- order requires cooperative_id, order_name, target quantity and price
- verification confirms participant commitments
- publication enables collective procurement

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| co_draft_entry | member | draft | Create cooperative order | withdrawn before submission | reject | rejected | co_reject_draft | entry |
| co_draft_entry | member | draft | Create cooperative order | submit for verification | submit | submitted | co_submit | entry |
| co_publish | system | published | Terminal published cooperative order | - | terminal | - | - | terminal |
| co_reject_draft | coordinator | rejected | Terminal rejected cooperative order | - | terminal | - | - | terminal |
| co_reject_submitted | coordinator | rejected | Terminal rejected cooperative order | - | terminal | - | - | terminal |
| co_reject_verified | coordinator | rejected | Terminal rejected cooperative order | - | terminal | - | - | terminal |
| co_submit | member | submitted | Submit cooperative order for review | insufficient commitments | reject | rejected | co_reject_submitted | - |
| co_submit | member | submitted | Submit cooperative order for review | participant commitments confirmed | verify | verified | co_verify | - |
| co_verify | coordinator | verified | Verify cooperative order commitments | approved for collective procurement | publish | published | co_publish | human-approval |
| co_verify | coordinator | verified | Verify cooperative order commitments | order requirements not met | reject | rejected | co_reject_verified | human-approval |

## Sources

- `schemas/postgres/194_process_taxonomy_expansion.sql`

## Mermaid

```mermaid
flowchart TD
    co_draft_entry[co_draft_entry: Create cooperative order [member]]
    co_publish((co_publish: Terminal published cooperative order [system]))
    co_reject_draft((co_reject_draft: Terminal rejected cooperative order [coordinator]))
    co_reject_submitted((co_reject_submitted: Terminal rejected cooperative order [coordinator]))
    co_reject_verified((co_reject_verified: Terminal rejected cooperative order [coordinator]))
    co_submit[co_submit: Submit cooperative order for review [member]]
    co_verify[co_verify: Verify cooperative order commitments [coordinator]]
    co_draft_entry -->|withdrawn before submission / reject -> rejected| co_reject_draft
    co_draft_entry -->|submit for verification / submit -> submitted| co_submit
    co_submit -->|insufficient commitments / reject -> rejected| co_reject_submitted
    co_submit -->|participant commitments confirmed / verify -> verified| co_verify
    co_verify -->|approved for collective procurement / publish -> published| co_publish
    co_verify -->|order requirements not met / reject -> rejected| co_reject_verified
```
