# Market Order Lifecycle

Spec: `market_order`

## Invariants

- order requires listing_id, buyer_id, quantity
- confirmation records payment and fulfillment acceptance
- delivery records completed transaction

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| mo_cancel | seller | cancelled | Terminal cancelled market order | - | terminal | - | - | terminal |
| mo_confirm | seller | confirmed | Confirm market order | fulfillment failed | cancel | cancelled | mo_cancel | human-approval |
| mo_confirm | seller | confirmed | Confirm market order | order handed to carrier | ship | shipped | mo_ship | human-approval |
| mo_deliver | carrier | delivered | Terminal delivered market order | - | terminal | - | - | terminal |
| mo_pending_entry | buyer | pending | Create market order | withdrawn before confirmation | cancel | cancelled | mo_cancel | entry |
| mo_pending_entry | buyer | pending | Create market order | payment and fulfillment accepted | confirm | confirmed | mo_confirm | entry |
| mo_ship | carrier | shipped | Ship market order | delivery failed | cancel | cancelled | mo_cancel | - |
| mo_ship | carrier | shipped | Ship market order | order received | deliver | delivered | mo_deliver | - |

## Sources

- `schemas/postgres/186_process_state_models.sql`
- `schemas/postgres/187_state_model_triggers.sql`

## Mermaid

```mermaid
flowchart TD
    mo_cancel((mo_cancel: Terminal cancelled market order [seller]))
    mo_confirm[mo_confirm: Confirm market order [seller]]
    mo_deliver((mo_deliver: Terminal delivered market order [carrier]))
    mo_pending_entry[mo_pending_entry: Create market order [buyer]]
    mo_ship[mo_ship: Ship market order [carrier]]
    mo_confirm -->|fulfillment failed / cancel -> cancelled| mo_cancel
    mo_confirm -->|order handed to carrier / ship -> shipped| mo_ship
    mo_pending_entry -->|withdrawn before confirmation / cancel -> cancelled| mo_cancel
    mo_pending_entry -->|payment and fulfillment accepted / confirm -> confirmed| mo_confirm
    mo_ship -->|delivery failed / cancel -> cancelled| mo_cancel
    mo_ship -->|order received / deliver -> delivered| mo_deliver
```
