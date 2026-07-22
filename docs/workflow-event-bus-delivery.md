# Durable Event Bus Delivery

Spec: `event_bus_delivery`

## Invariants

- The event claim commits before any handler executes.
- Only the current lease owner may complete, retry, or dead-letter an event.
- A successful handler delivery is not intentionally invoked again during normal retry or replay.
- Handler effects are at-least-once; handlers must make external effects idempotent.
- An event completes only after every enabled handler has a successful delivery or no handlers are enabled.
- Retries are bounded by max_retries and final failure creates one pending dead-letter disposition.
- Replay and disposal are explicit operator actions; disposal is terminal.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| claim | worker | pending | Atomically claim event and create lease | not due or locked | leave pending | deferred | deferred | entry, transaction, retry-safe |
| claim | worker | pending | Atomically claim event and create lease | claim acquired | process | processing | load_handlers | entry, transaction, retry-safe |
| complete | worker | processing | Conditionally mark event completed and clear lease | lease owner update succeeds | completed | completed | completed | transaction, retry-safe |
| complete | worker | processing | Conditionally mark event completed and clear lease | lease owner update changes no row | stop | lease_lost | lease_lost | transaction, retry-safe |
| completed | system | completed | Terminal completed event | - | terminal | - | - | retry-safe, terminal |
| dead_letter | worker | dead_letter | Persist event and pending dead-letter atomically | operator investigates | review | dead_letter | operator_review | transaction, retry-safe |
| deferred | worker | deferred | Stop this polling attempt | - | terminal | - | - | retry-safe, terminal |
| disposed | system | disposed | Terminal operator disposition | - | terminal | - | - | retry-safe, terminal |
| invoke | handler process | delivery_processing | Invoke handler with bounded timeout | error, timeout, or missing result | failure | processing | record_failure | external-side-effect |
| invoke | handler process | delivery_processing | Invoke handler with bounded timeout | handler returns success | success | processing | record_success | external-side-effect |
| lease_check | worker | processing | Extend and verify event lease | lease not owned | stop | lease_lost | lease_lost | transaction, retry-safe |
| lease_check | worker | processing | Extend and verify event lease | lease owned | prepare | processing | mark_delivery | transaction, retry-safe |
| lease_lost | worker | lease_lost | Stop without changing another worker's event | - | terminal | - | - | retry-safe, terminal |
| load_handlers | worker | processing | Load enabled handlers | no enabled handlers or every delivery succeeded | complete | processing | complete | transaction, retry-safe |
| load_handlers | worker | processing | Load enabled handlers | handler remains | deliver | processing | lease_check | transaction, retry-safe |
| mark_delivery | worker | processing | Persist handler delivery as processing | delivery not already successful | invoke | delivery_processing | invoke | transaction, retry-safe |
| mark_delivery | worker | processing | Persist handler delivery as processing | delivery already successful | skip | processing | load_handlers | transaction, retry-safe |
| operator_review | human operator | dead_letter | Choose replay, resolve, or discard | replay with original event present | replay | pending | claim | human-approval |
| operator_review | human operator | dead_letter | Choose replay, resolve, or discard | original event missing | reject replay | disposed | disposed | human-approval |
| operator_review | human operator | dead_letter | Choose replay, resolve, or discard | resolve or discard with reason | dispose | disposed | disposed | human-approval |
| record_failure | worker | processing | Persist failed delivery and attempt log | all handlers visited | evaluate retry | processing | retry_decision | transaction, retry-safe |
| record_success | worker | processing | Persist successful delivery and attempt log | more handlers may remain | continue | processing | load_handlers | transaction, retry-safe |
| retry_decision | worker | processing | Conditionally retry or dead-letter under lease ownership | attempts remain | retry | pending | claim | transaction, retry-safe |
| retry_decision | worker | processing | Conditionally retry or dead-letter under lease ownership | retry limit reached | dead letter | dead_letter | dead_letter | transaction, retry-safe |
| retry_decision | worker | processing | Conditionally retry or dead-letter under lease ownership | lease ownership changed | stop | lease_lost | lease_lost | transaction, retry-safe |

## Sources

- `services/events/bus.py`
- `schemas/postgres/116_event_bus.sql`
- `schemas/postgres/165_event_bus_durability.sql`

## Governance Controls

- Lease ownership prevents concurrent claims.
- Retries are bounded; replay and disposal require an operator.

## Data and Persistence

- event_handler_delivery | leases, attempts, handler results, dead letters

## Audit Controls

- Lease owner, expiry, attempt number, retry reason, and dead-letter disposition are durable.

## Tests

- `tests/test_event_bus_durability.py`

## Mermaid

```mermaid
flowchart TD
    claim[claim: Atomically claim event and create lease [worker]]
    complete[complete: Conditionally mark event completed and clear lease [worker]]
    completed((completed: Terminal completed event [system]))
    dead_letter[dead_letter: Persist event and pending dead-letter atomically [worker]]
    deferred((deferred: Stop this polling attempt [worker]))
    disposed((disposed: Terminal operator disposition [system]))
    invoke[invoke: Invoke handler with bounded timeout [handler process]]
    lease_check[lease_check: Extend and verify event lease [worker]]
    lease_lost((lease_lost: Stop without changing another worker's event [worker]))
    load_handlers[load_handlers: Load enabled handlers [worker]]
    mark_delivery[mark_delivery: Persist handler delivery as processing [worker]]
    operator_review[operator_review: Choose replay, resolve, or discard [human operator]]
    record_failure[record_failure: Persist failed delivery and attempt log [worker]]
    record_success[record_success: Persist successful delivery and attempt log [worker]]
    retry_decision[retry_decision: Conditionally retry or dead-letter under lease ownership [worker]]
    claim -->|not due or locked / leave pending -> deferred| deferred
    claim -->|claim acquired / process -> processing| load_handlers
    complete -->|lease owner update succeeds / completed -> completed| completed
    complete -->|lease owner update changes no row / stop -> lease_lost| lease_lost
    dead_letter -->|operator investigates / review -> dead_letter| operator_review
    invoke -->|error, timeout, or missing result / failure -> processing| record_failure
    invoke -->|handler returns success / success -> processing| record_success
    lease_check -->|lease not owned / stop -> lease_lost| lease_lost
    lease_check -->|lease owned / prepare -> processing| mark_delivery
    load_handlers -->|no enabled handlers or every delivery succeeded / complete -> processing| complete
    load_handlers -->|handler remains / deliver -> processing| lease_check
    mark_delivery -->|delivery not already successful / invoke -> delivery_processing| invoke
    mark_delivery -->|delivery already successful / skip -> processing| load_handlers
    operator_review -->|replay with original event present / replay -> pending| claim
    operator_review -->|original event missing / reject replay -> disposed| disposed
    operator_review -->|resolve or discard with reason / dispose -> disposed| disposed
    record_failure -->|all handlers visited / evaluate retry -> processing| retry_decision
    record_success -->|more handlers may remain / continue -> processing| load_handlers
    retry_decision -->|attempts remain / retry -> pending| claim
    retry_decision -->|retry limit reached / dead letter -> dead_letter| dead_letter
    retry_decision -->|lease ownership changed / stop -> lease_lost| lease_lost
```
