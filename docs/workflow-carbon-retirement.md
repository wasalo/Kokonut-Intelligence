# Carbon Credit Retirement

Spec: `carbon_retirement`

## Invariants

- issuable_tonnes, retired_tonnes, and reserved_tonnes remain nonnegative.
- retired_tonnes + reserved_tonnes never exceeds issuable_tonnes.
- Creating a draft changes reserved_tonnes by +Q and retired_tonnes by 0.
- Confirmation changes reserved_tonnes by -Q and retired_tonnes by +Q atomically.
- Rejection or cancellation changes reserved_tonnes by -Q and retired_tonnes by 0 atomically.
- Permanent retirement requires an independent human reviewer distinct from the requester.
- Terminal reviews never mutate balances a second time.
- Certificates are ineligible until retirement is independently confirmed.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| cancelled | system | cancelled | Terminal cancelled retirement; repeated review is a no-op | - | terminal | - | - | retry-safe, terminal |
| confirm_draft | system | reviewed_draft | Move Q from reserved to retired and record confirmation atomically | guard or transaction fails | rollback | error | request_error | transaction, retry-safe, high-risk |
| confirm_draft | system | reviewed_draft | Move Q from reserved to retired and record confirmation atomically | reservation exists and credit remains eligible | confirmed | verified | verified | transaction, retry-safe, high-risk |
| confirm_submitted | system | reviewed_submitted | Move Q from reserved to retired and record confirmation atomically | guard or transaction fails | rollback | error | request_error | transaction, retry-safe, high-risk |
| confirm_submitted | system | reviewed_submitted | Move Q from reserved to retired and record confirmation atomically | reservation exists and credit remains eligible | confirmed | verified | verified | transaction, retry-safe, high-risk |
| draft | requester | draft | Await submission or independent review | review requested | review | draft | review_draft | - |
| draft | requester | draft | Await submission or independent review | submit for review | submitted | submitted | submitted | - |
| draft_existing | system | draft | Return existing draft without another reservation | - | terminal | - | - | retry-safe, terminal |
| rejected | system | rejected | Terminal rejected retirement; repeated review is a no-op | - | terminal | - | - | retry-safe, terminal |
| release_draft | system | reviewed_draft | Release Q from reserved and record reject or cancel atomically | decision is cancel | cancelled | cancelled | cancelled | transaction, retry-safe |
| release_draft | system | reviewed_draft | Release Q from reserved and record reject or cancel atomically | decision is reject | rejected | rejected | rejected | transaction, retry-safe |
| release_draft | system | reviewed_draft | Release Q from reserved and record reject or cancel atomically | guard or transaction fails | rollback | error | request_error | transaction, retry-safe |
| release_submitted | system | reviewed_submitted | Release Q from reserved and record reject or cancel atomically | decision is cancel | cancelled | cancelled | cancelled | transaction, retry-safe |
| release_submitted | system | reviewed_submitted | Release Q from reserved and record reject or cancel atomically | decision is reject | rejected | rejected | rejected | transaction, retry-safe |
| release_submitted | system | reviewed_submitted | Release Q from reserved and record reject or cancel atomically | guard or transaction fails | rollback | error | request_error | transaction, retry-safe |
| request_error | system | error | Rollback and return failure | - | terminal | - | - | retry-safe, terminal |
| reserve | system | requested | Lock credit, reserve Q, and create draft retirement atomically | conditional balance update succeeds | draft created | draft | draft | transaction, retry-safe |
| reserve | system | requested | Lock credit, reserve Q, and create draft retirement atomically | conditional update or insert fails | rollback | error | request_error | transaction, retry-safe |
| review_draft | human reviewer | draft | Verify reviewer independence and choose disposition | confirm | approve | reviewed_draft | confirm_draft | human-approval |
| review_draft | human reviewer | draft | Verify reviewer independence and choose disposition | reject or cancel | release | reviewed_draft | release_draft | human-approval |
| review_submitted | human reviewer | submitted | Verify reviewer independence and choose disposition | confirm | approve | reviewed_submitted | confirm_submitted | human-approval |
| review_submitted | human reviewer | submitted | Verify reviewer independence and choose disposition | reject or cancel | release | reviewed_submitted | release_submitted | human-approval |
| submitted | system | submitted | Await independent review | review requested | review | submitted | review_submitted | - |
| terminal_existing | system | verified | Return existing terminal result without balance mutation | - | terminal | - | - | retry-safe, terminal |
| validate_request | requester | requested | Validate quantity, requester, credit eligibility, availability, and idempotency | matching draft idempotency key | return existing | draft | draft_existing | entry |
| validate_request | requester | requested | Validate quantity, requester, credit eligibility, availability, and idempotency | invalid, unavailable, or conflicting request | reject | error | request_error | entry |
| validate_request | requester | requested | Validate quantity, requester, credit eligibility, availability, and idempotency | new valid request | reserve | requested | reserve | entry |
| validate_request | requester | requested | Validate quantity, requester, credit eligibility, availability, and idempotency | matching terminal idempotency key | return existing | verified | terminal_existing | entry |
| verified | system | verified | Terminal confirmed retirement; repeated review is a no-op | - | terminal | - | - | retry-safe, terminal |

## Sources

- `services/analytics/carbon_credits.py`
- `schemas/postgres/078_carbon_credits.sql`
- `schemas/postgres/163_carbon_retirement_integrity.sql`

## Governance Controls

- Independent human confirmation is required before final retirement or certificate use.
- Reservation and balance mutations must be atomic and idempotent.

## Data and Persistence

- credit_retirement | credit balance, reservation, retirement certificate

## Audit Controls

- Idempotency keys and reviewer identity are retained with the retirement ledger.
- Certificate linkage follows confirmed retirement only.

## Tests

- `tests/test_carbon_credits.py`
- `tests/test_bpm_state_models.py`

## Mermaid

```mermaid
flowchart TD
    cancelled((cancelled: Terminal cancelled retirement; repeated review is a no-op [system]))
    confirm_draft[confirm_draft: Move Q from reserved to retired and record confirmation atomically [system]]
    confirm_submitted[confirm_submitted: Move Q from reserved to retired and record confirmation atomically [system]]
    draft[draft: Await submission or independent review [requester]]
    draft_existing((draft_existing: Return existing draft without another reservation [system]))
    rejected((rejected: Terminal rejected retirement; repeated review is a no-op [system]))
    release_draft[release_draft: Release Q from reserved and record reject or cancel atomically [system]]
    release_submitted[release_submitted: Release Q from reserved and record reject or cancel atomically [system]]
    request_error((request_error: Rollback and return failure [system]))
    reserve[reserve: Lock credit, reserve Q, and create draft retirement atomically [system]]
    review_draft[review_draft: Verify reviewer independence and choose disposition [human reviewer]]
    review_submitted[review_submitted: Verify reviewer independence and choose disposition [human reviewer]]
    submitted[submitted: Await independent review [system]]
    terminal_existing((terminal_existing: Return existing terminal result without balance mutation [system]))
    validate_request[validate_request: Validate quantity, requester, credit eligibility, availability, and idempotency [requester]]
    verified((verified: Terminal confirmed retirement; repeated review is a no-op [system]))
    confirm_draft -->|guard or transaction fails / rollback -> error| request_error
    confirm_draft -->|reservation exists and credit remains eligible / confirmed -> verified| verified
    confirm_submitted -->|guard or transaction fails / rollback -> error| request_error
    confirm_submitted -->|reservation exists and credit remains eligible / confirmed -> verified| verified
    draft -->|review requested / review -> draft| review_draft
    draft -->|submit for review / submitted -> submitted| submitted
    release_draft -->|decision is cancel / cancelled -> cancelled| cancelled
    release_draft -->|decision is reject / rejected -> rejected| rejected
    release_draft -->|guard or transaction fails / rollback -> error| request_error
    release_submitted -->|decision is cancel / cancelled -> cancelled| cancelled
    release_submitted -->|decision is reject / rejected -> rejected| rejected
    release_submitted -->|guard or transaction fails / rollback -> error| request_error
    reserve -->|conditional balance update succeeds / draft created -> draft| draft
    reserve -->|conditional update or insert fails / rollback -> error| request_error
    review_draft -->|confirm / approve -> reviewed_draft| confirm_draft
    review_draft -->|reject or cancel / release -> reviewed_draft| release_draft
    review_submitted -->|confirm / approve -> reviewed_submitted| confirm_submitted
    review_submitted -->|reject or cancel / release -> reviewed_submitted| release_submitted
    submitted -->|review requested / review -> submitted| review_submitted
    validate_request -->|matching draft idempotency key / return existing -> draft| draft_existing
    validate_request -->|invalid, unavailable, or conflicting request / reject -> error| request_error
    validate_request -->|new valid request / reserve -> requested| reserve
    validate_request -->|matching terminal idempotency key / return existing -> verified| terminal_existing
```
