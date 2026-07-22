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

## Governance Controls

- Seller confirmation and shipment evidence are required for later states.
- Cancellation remains an explicit governed path.

## Data and Persistence

- market_order | buyer, seller, payment, carrier, delivery

## Audit Controls

- Lifecycle transitions are recorded with actor and timestamp.
- Rejection, cancellation, or terminal disposition requires an explicit reason where applicable.

## Tests

- `tests/test_marketplace.py`
- `tests/test_bpm_state_models.py`

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
