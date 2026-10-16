# Worker tenant-context contract

**Status:** the signed sensor-anomaly and registered cache-handler integrations
are implemented and accepted in disposable checks on 16 October 2026. Migration
410 adds a bounded actuation-intent function, accepted in fifteen focused
disposable PostgreSQL checks. Migration 411 adds a bounded draft-claim function,
accepted in fourteen focused disposable PostgreSQL checks. Migration 412 adds
four bounded read functions, accepted in ten disposable PostgreSQL checks.
Migration 413 creates a source-validated alert, appends its ingestion audit
row, and advances the reserved receipt atomically. Nine focused disposable
PostgreSQL 16 checks pass, including forced-RLS writes and rollback on audit
failure. Migration 414 completes the handler's bounded effect sequence and
event/notification payload parity; eight end-to-end disposable PostgreSQL
checks pass, including EventBus child-process crash recovery. Migration 405 and the transaction-bound Python adapter establish
an opt-in worker context; migrations 407–414 add bounded receipt, source-read,
rule/evaluation/cooldown, event-publication, notification-intent,
actuation-intent, draft-claim, and worker-delivery operations for
`sensor_reading/process`. The anomaly handler now uses these operations through
one dedicated worker transaction, and EventBus secret forwarding is limited
to this exact handler. No candidate database, worker credential, or active
location grant was provisioned. Migration 412 adds a narrow owner
SELECT policy only on source tables where RLS is already enabled; it does not
enable RLS globally.

Migrations 415–416 and the opt-in adapters for all four registered cache
invalidation handlers are now verified. Eighty focused cache/EventBus/allowlist
and operation-map tests pass. Eight checks on network-isolated disposable
PostgreSQL 16 cover migration replay, signed event/type/location agreement,
location and computation-type isolation, idempotent retry, forced RLS, direct
table denial, and handler registration. The worker-specific DSN and credential
reach only the exact four registered handlers. The flag remains off by default;
no credential or active grant is provisioned, and migration 416 is not deployed
to the candidate.

The `services.common.worker_database.get_worker_db()` factory supports isolated
execution and is used by the anomaly adapter. It requires a worker-specific
`KOKONUT_<WORKER>_DATABASE_URL`, verifies the login is exactly
`kokonut_worker_login`, enforces transactional mode, and never falls back to
shared `PG_*` settings. The anomaly worker calls it through the exact-handler
EventBus allowlist; twelve focused mocked unit checks pass. Code-level
per-handler credential delivery is implemented; the actual credential and
database identity remain unprovisioned. Bounded anomaly reads are implemented
in migrations 412–414
([evidence](builds/2026-10-16-recovery/worker-database-factory-unit.json)).
`get_worker_credential()` now similarly reads only the named worker secret,
requires 32–4096 UTF-8 bytes, and never normalizes or logs the opaque value.
Do not place that secret in a shared dispatcher environment. Focused tests
cover exact byte bounds, missing and fallback behavior, invalid UTF-8 text,
opaque-value preservation, worker-key validation, and named-key-only lookup
([evidence](builds/2026-10-16-recovery/worker-credential-resolver-unit.json)).
The secret reader is integrated for this handler, but no real worker
credential has been provisioned.

## Decision

Workers use a database-verified `system_worker` identity. They never impersonate
an operator, reuse an OIDC session, trust a caller-supplied tenant label, or
install tenant scope by setting a custom PostgreSQL GUC directly.

Each execution receives an exact operation grant and a location scope. A
database-owned function resolves the tenant from the current active location
owner, checks the worker grant and ownership rows, locks the authorization rows
for the transaction, and signs context with the existing private HMAC key. The
existing `current_tenant_context()` accessor verifies the signature against the
current backend and transaction. A failed setter clears any earlier context.
Location transfers, grant revocations, and worker execution therefore
serialize through the same authorization rows.

Wildcards and implicit tenant-wide worker grants are not allowed. Cross-location
work is expanded into separately authorized location executions. Global
catalog/reference reads and durable queue coordination are control-plane
operations; they need separate, narrowly granted database functions or roles
and must not be made tenant-scoped by inventing a location.

## Authorization and secret boundary

- Store only a one-way digest of each high-entropy worker credential in the
  private security schema. Keep the raw credential in the deployment secret
  provider; never print it in logs or store it in job arguments, event payloads,
  the database, or a process command line.
- Bind each credential to a stable worker principal and explicit
  `(tenant, location, resource, action)` grants. A missing or ambiguous grant,
  inactive tenant/location, absent current owner proof, or owner mismatch fails
  closed.
- The database function owner is a dedicated `NOLOGIN`, non-superuser,
  `NOBYPASSRLS` role with only the reads and row locks needed to verify the
  worker principal, grant, owner, location, organization, and signing key. It
  cannot mutate those records.
- The setter is available only to a dedicated worker execution login. Browser,
  Directus, operator-auth, and general application logins cannot use it. The
  current broad runtime role is not evidence of this separation and remains a
  gate before application RLS.
- Every tenant-data query and write runs in the same non-autocommit transaction
  and connection as the verified context. Connection-pool reuse, commits
  between setter and query, and continuation after denial must not preserve
  scope.
- The signed payload includes worker actor type and identity, tenant, location,
  backend PID, transaction ID, and nonce. The context accessor accepts the new
  actor type only after the worker setter exists and its authorization checks
  are covered by disposable PostgreSQL tests.

## Dispatch boundaries

The existing worker operation inventory shows two distinct kinds of work:

1. **Control plane:** scheduler leases, event claims, handler dispatch,
   retries, and dead-letter state. Some operations are intentionally global and
   do not access farm records. They need their own worker-control principal and
   bounded database operations; a signed tenant context is not a substitute.
2. **Tenant execution:** provider work and event handlers that read or write
   farm records. They need a location-bound worker authorization before the
   first protected query and must revalidate source/event location against that
   authorization in SQL.

The scheduler launches allowlisted modules in subprocesses without signed
tenant context. The EventBus also starts allowlisted handlers in subprocesses;
the sensor-anomaly handler establishes signed context, while other handlers do
not yet have an operation-specific adapter. Each child must receive only the
credential for its own execution identity. Deployment-level principal and
credential provisioning remains required before activation.

The shared application subprocess boundary removes worker-specific database
URLs and credentials before exec, except for explicit handler-to-worker
allowlist entries. The EventBus now forwards the sensor-anomaly DSN and
credential only to `services.ingestion.anomaly_detector.handle_sensor_reading`.
The request travels on stdin, not command-line arguments, and a small JSON
result channel prevents handler stdout from corrupting status reporting. The
runner validates the allowlisted module/function, preserves legacy handler
signatures, and kills/reaps timed-out children. Twenty-six subprocess-boundary
unit checks plus focused exact-handler environment checks pass
([evidence](builds/2026-10-16-recovery/event-handler-child-environment.json)).

## First implementation slice

`services.ingestion.anomaly_detector.handle_sensor_reading` is the first
tenant-execution adapter. It requires and canonicalizes `payload.location_id`
before connecting, establishes database-signed context, and delegates to the
worker module's bounded reads and writes. Migrations 405–414 and the adapter
preserve exact source/event/location matching, idempotent effects, read-only
alert-rule references, caller-owned transaction semantics, and human-approved
actuation. Event execution skips default-rule bootstrap; the interactive CLI
retains it. Queue claim, lease, acknowledgement, retry, and dead-letter work
remain in the control-plane boundary. The current end-to-end runner passes
eight checks on disposable PostgreSQL, including an EventBus child crash after
commit followed by attempt-two recovery without duplicate effects. Real
deployment credential, login, location grant, and candidate rollout remain
open.

The first location-lineage source change is in
`services/ingestion/anomaly_detector.py`. Migration 405 adds private worker
principals, SHA-256 credential digests, exact tenant/location/resource/action
grants, a dedicated `kokonut_worker_execution` group role, the bounded signed
context setter, and an exact-scope accessor. `services/common/tenant_context.py`
hashes the supplied worker secret in memory, clears prior context, assumes the
dedicated role locally, and requires a non-autocommit transaction. The anomaly
adapter now uses these primitives. No real worker-only credential, login, or
active location grant is provisioned; the disposable acceptance uses synthetic
values only.

Migration 412 supplies the read contract through four SECURITY DEFINER
functions owned by `kokonut_anomaly_read_owner`, a no-login,
`NOBYPASSRLS`, non-member role with only the selected source columns:

- `read_sensor_anomaly_source(event_id, location_id, sensor_id)` returns the
  matching reading and device/type/location context only when event type,
  source table/ID, payload location, and every supplied sensor selector agree.
- `list_sensor_anomaly_rules(device_id, location_id)` returns enabled rules
  for that device's sensor type and signed location.
- `evaluate_sensor_anomaly_rule(event_id, reading_id, rule_id, location_id)`
  validates the same source event and computes the configured value,
  rate-of-change, gap, minimum, or maximum predicate using location-bounded
  history.
- `sensor_anomaly_in_cooldown(device_id, rule_id, location_id)` checks only
  the enabled rule/device pair's location-bound alert history.

The execution role has EXECUTE on these functions but no direct SELECT on the
source tables. If a source relation has RLS enabled or forced, a narrow SELECT
policy for this no-login owner lets the SECURITY DEFINER functions run; each
function still checks the signed-location predicate. This does not enable RLS
on any table and is not a global isolation acceptance. Disposable PostgreSQL 16
checks verify a mismatched event is rejected and one location's sensor history
does not affect another location's metric result
([migration](../../schemas/postgres/412_sensor_anomaly_worker_reads.sql);
[runner](../../scripts/check-sensor-anomaly-worker-reads-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-reads-disposable.json)).

Migration 413 closes the alert/audit write boundary. Its
`create_sensor_anomaly_alert` function validates the signed source event,
reading, device, enabled rule, and reserved `no_match` receipt, then inserts the
location-bound alert and append-only ingestion audit row and advances the
receipt to `alert_created` in the same transaction. The execution role retains
function `EXECUTE` only. Nine disposable PostgreSQL 16 checks pass for replay,
missing/mismatched scope, rule validation, required receipt, source-derived
alert fields, single audit linkage, duplicate suppression, atomic rollback,
forced RLS, and role/table boundaries. Candidate and legacy databases were not
accessed; handler integration is accepted separately by migration 414's
end-to-end disposable runner
([migration](../../schemas/postgres/413_sensor_anomaly_alert_write.sql);
[fixture](../../tests/fixtures/sensor_anomaly_alert_write_disposable.sql);
[runner](../../scripts/check-sensor-anomaly-alert-write-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-alert-write-disposable.json)).

Migration 414 and `services.ingestion.sensor_anomaly_worker` now connect the
bounded operations in one non-autocommit transaction. EventBus sends the
worker-specific DSN and opaque credential only to the exact anomaly handler.
The runner applies/replays migrations 405–414, invokes the Python worker with
synthetic credentials under forced RLS, verifies canonical notification
payload parity, draft claims, approval-only actuation intent, idempotent
retries, and direct-table denial, and passes eight checks, including a real
EventBus child-process crash and idempotent attempt-two recovery. No candidate or
legacy database was accessed. A real login, secret, active location grant,
candidate rollout, global application RLS, and live provider acceptance are
still required; isolated worker crash/retry acceptance passes
([migration](../../schemas/postgres/414_sensor_anomaly_worker_delivery.sql);
[runner](../../scripts/check-sensor-anomaly-worker-delivery-disposable.py);
[evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json)).

The focused anomaly and pilot seed-guard suites passed 19 tests, the EventBus
durability suite passed 17 tests, and two transaction tests passed. They cover
missing/malformed location selectors, validation before DB access, source/event
location mismatch, seed lineage guards, read-only alert-rule behavior, and
caller-owned transaction success/error paths. The worker-context unit suite
passed 30 tests. The migration was applied and replayed in isolated PostgreSQL
16 with forced RLS on synthetic ownership and private grant tables; 17 checks
passed for exact scope, payload tampering, transaction cleanup, private key and
credential access denial, runtime-role separation, owner transfer, grant expiry
and revocation, credential revocation, and authorization-row lock behavior.
Ruff, Python compilation, migration source validation, and diff checks passed.
No candidate or legacy database was accessed
([anomaly evidence](builds/2026-10-16-recovery/worker-anomaly-transaction-source.json);
[worker database evidence](builds/2026-10-16-recovery/worker-tenant-context-disposable.json)).

### Observed effect boundary for the first handler

Source review of `run_check`, `create_alert`, notification enqueue, and the
shared EventBus shows that location-bound source validation is only one part of
the authorization contract:

- Reads include the source `platform_event`, its `sensor_reading`, sensor
  metadata, shared `alert_rule` reference data, recent `sensor_alert` rows for
  cooldown, and optional sensor history used by rate-of-change rules.
- Writes include the idempotency row in `sensor_anomaly_effect`, new
  `sensor_alert` rows, optional draft `mrv_claim` rows, ingestion audit rows,
  notification outbox intents, and a new `platform_event` for the alert. These
  paths share the handler's connection. `EventBus.publish` now accepts an
  explicit caller-owned transaction mode, and anomaly handling uses it so the
  final handler commit controls all effects.
- The event path does not call the direct email or Directus notifier. It
  enqueues configured notifications and records any configured actuator
  action through the existing human-approval gate. External delivery remains
  the responsibility of separate workers.
- `alert_rule` defaults are now bootstrapped only by the interactive CLI;
  event execution reads existing rules without creating global configuration.
  Focused regressions verify both paths.

Migration 414 now maps each sensor-anomaly effect to a bounded operation that
derives scope from signed context. A single `sensor_reading:process` grant does
not authorize global notification, EventBus, or audit writes; those effects use
dedicated functions and preserve the caller's transaction. Event claim, lease,
acknowledgement, retry, and dead-letter state stay in the separate control-plane
identity. This contract does not authorize other worker handlers or global
application-table RLS.

The detailed [sensor anomaly effect contract](worker-sensor-anomaly-effects.json)
records the source-visible read/write set and required boundary for each
relation. Migrations 405–414 and the integrated worker enforce and exercise
the anomaly slice in disposable PostgreSQL; the document is still not a grant
list for other workers. It separates global read-only alert-rule and sensor-type
references from location-bound data and treats event queue state, notification
delivery, and actuation delivery as distinct operations.

Remaining worker-permission work before broader integration:

1. **Complete for the sensor-anomaly handler:** migration 406 adds direct
   location lineage, migration 407 bounds receipt reservation/outcomes, and
   migrations 413–414 bind alert creation and ingestion audit to signed source
   context. Unresolved historical rows remain inaccessible to the worker.
   Other workers' location lineage still needs its own review.
2. **Complete:** migration 408 adds a bounded canonical sensor-alert event
   publisher. It derives payload and priority from the matching alert/receipt,
   inserts a pending event, handles identical retries, rejects ID conflicts,
   and leaves all queue state untouched. Disposable PostgreSQL 16 acceptance
   covers source/alert/scope validation, ACLs, and replay.
3. **Complete:** migration 409 adds a bounded notification-intent function for
   the existing webhook, Directus, and email payload shapes. It validates the
   signed source/alert linkage, fixes the destination key, limits fields and
   payload size, inserts pending intent only, and preserves delivery state on
   retry. Twelve disposable PostgreSQL 16 checks pass. Migration 414 wires the
   handler to publish the alert event before enqueueing notification.
4. **Complete:** migration 410 adds a separate non-login
   actuation-function owner and `create_sensor_alert_actuation_intent`. It
   validates the source event, reading, receipt, alert, recorded alert event,
   enabled rule, and signed location, then derives the command from the rule.
   Critical alerts always require approval; retries return the existing intent
   without resetting approval or transport state. A partial unique key limits
   the operation to one intent per alert event. Fifteen disposable PostgreSQL
   16 checks pass for scope/linkage, canonical command, critical and configured
   approval, retry state preservation, role boundaries, direct table denial,
   and migration replay.
5. **Complete:** migration 411 adds a bounded draft-MRV
   claim operation. Its idempotency key is the source sensor-reading event plus
   the alert. It validates signed scope and the `alert_created` source receipt,
   inserts only a `draft` claim, links the claim to the alert, and can adopt the
   exact legacy-linked claim without changing its lifecycle or review state.
   Migration 414 calls it after recording the alert receipt and before
   constructing downstream notification intent data. The alert-event payload
   itself omits `claim_id`; notification and actuation intents follow event
   publication.
   Fourteen focused disposable PostgreSQL 16 checks pass, including replay,
   role boundaries, and direct-table denial.
6. **Complete:** migration 412 adds read-only source, rule, metric/history, and
   cooldown operations behind a no-login owner. They validate signed location
   and event/reading/device/rule relationships; the worker receives no direct
   source-table SELECT. Ten focused disposable PostgreSQL 16 checks pass for
   replay, forced RLS, metric results, cooldown, and role boundaries.
7. **Complete in source and disposable acceptance:** integrate the anomaly
   handler with isolated worker resolvers and bounded operations. Keep alert
   creation, receipt update, claim creation, alert publication, notification
   enqueue, and actuation intent creation in one caller-owned transaction; the
   worker must not submit, verify, publish, reject, or transmit actuator
   commands. Eight end-to-end checks pass, including process crash after
   handler commit and attempt-two recovery without duplicate effects.
8. **Complete in disposable PostgreSQL:** provision a synthetic isolated worker
   login/credential and verify that it cannot read worker grants, sign operator
   context, issue another worker identity, or access unrelated tenant rows.
   Real deployment login, credential, and grant provisioning remain open.
9. Expand one operation at a time. Reconcile the 20 worker roots, direct SQL
   inventory, worker effects, external task state, and the control-plane
   identity before reducing runtime grants or enabling any RLS policy.

Migration-410 acceptance covers wrong/missing scope, source and alert lineage,
canonical rule-derived payload, critical/configured approval, one-intent
uniqueness, retry preservation after approval/delivery state changes, role
separation, direct table denial, and migration replay. No base application RLS
or candidate rollout follows automatically.

Migrations 405–414 implement and disposable-check the signed sensor-anomaly
worker path, including source reads, receipt transitions, alert/audit creation,
draft claims, canonical event publication, notification intents, and
approval-required actuation intents. The handler uses a worker-specific DSN and
credential supplied only by the exact EventBus allowlist entry. Disposable
acceptance also verifies that the worker login cannot directly access protected
tables or use unrelated tenant rows. A real deployment login, secret, and
active location grant have not been provisioned. No access is granted to the
shared runtime or existing event/notification dispatchers.

Migrations 415–416 and source integration cover all four registered cache
invalidation handlers: `metric_computed`, `crisp_scored`, `sensor_reading`, and
`harvest_recorded`. The default-off path retains existing behavior; when
enabled, each handler uses its own worker DSN, an exact EventBus credential
allowlist entry, and a signed `computation_cache/invalidate` scope. The bounded
function rechecks the durable event ID, event type, and location before
invalidating only the corresponding analytics, CRISP, or metric cache rows.
Focused handler and disposable PostgreSQL 16 acceptance pass; migration 416
has not been rolled out, and no credential or grant is provisioned.

The event producers in `services/ingestion/sensor_ingester.py` and
`services/ingestion/http_sensor_receiver.py` already include the location ID.
The sensor source row remains authoritative, and the integrated handler
compares payload selectors against it after context is established. Reconcile
any alternate or external `sensor_reading` producer before extending this
authorization contract to it.

## Planned code and migration sequence

1. **Complete:** migration 405 adds worker principal/grant storage, the bounded
   signed-context setter, and `system_worker` accessor support. It does not
   enable application-table RLS or grant access to `kokonut_runtime`.
2. **Complete:** the adapter in `services/common/tenant_context.py` validates
   transaction state and canonical selectors, hashes the credential in memory,
   clears prior context, calls the database setter through the dedicated role,
   and returns typed scope. It never reads a credential from event/job payloads.
3. **Complete:** migration 407 adds a separate non-login function owner and
   signed-scope checked receipt reserve/outcome functions. Disposable
   PostgreSQL 16 acceptance verifies event/reading/device/rule/location
   agreement, duplicate suppression, valid transitions, alert-link checks,
   privilege separation, and replay. Migration 414 calls these functions
   through the integrated worker in disposable acceptance.
4. **Complete:** migration 408 adds a separate non-login event-function owner
   and `publish_sensor_alert_event`. It derives canonical event content from a
   signed-scope alert and `alert_created` receipt, inserts a pending event with
   current priority/retry semantics, suppresses identical replays, and never
   mutates queue state. Eleven disposable PostgreSQL 16 checks pass.
5. **Complete:** migration 409 adds a separate non-login notification-function
   owner and bounded sensor-alert outbox enqueue operation. It validates the
   signed source receipt and published alert, accepts only the existing three
   channel payload shapes, and inserts pending intent without touching
   delivery attempts. Twelve disposable PostgreSQL 16 checks pass.
6. **Complete:** migration 410 adds the bounded rule-derived actuation intent;
   fifteen disposable PostgreSQL 16 checks pass for signed scope, approval,
   idempotency, privilege boundaries, and replay.
7. **Complete:** migration 411 adds the bounded draft-claim operation; fourteen
   disposable PostgreSQL 16 checks pass for draft-only creation, exact legacy
   adoption without lifecycle mutation, role boundaries, and replay.
8. **Complete:** migration 412 adds event-linked source reads, scoped device
   rules, metric/history evaluation, and cooldown reads; ten disposable
   PostgreSQL 16 checks pass for signed scope, forced RLS, metric results,
   role boundaries, and replay.
9. **Complete:** integrate the sensor-reading handler after isolating its
   credential from unrelated dispatch; retain event/source/location checks,
   same-transaction effects, retry coverage, and producer/dispatch regression
   inventories. Eight end-to-end disposable checks pass.
10. **Complete in disposable PostgreSQL:** provision a synthetic isolated
    worker login/credential and verify it cannot read worker grants, sign
    operator context, issue another worker identity, or access unrelated tenant
    rows. Provisioning real deployment identities and secrets remains an
    activation gate.
11. **Complete in source and disposable acceptance:** add a signed, opt-in cache
    invalidation path for all four registered EventBus handlers. Eighty focused
    tests and eight isolated PostgreSQL checks pass for event ID/type/location
    matching, cache-type scoping, retry safety, forced RLS, role boundaries,
    handler registration, and migrations 415–416 replay. Credential and active
    grant provisioning remain an activation gate.
12. Expand one operation at a time. Reconcile the 20 worker roots, direct SQL
   inventory, worker effects, external task state, and the control-plane
   identity before reducing runtime grants or enabling any RLS policy.

Each step is source/disposable acceptance only. Applying the migration to the
local candidate, provisioning production secrets, activating schedules,
enabling RLS, and retiring the broad runtime principal remain separate rollout
gates.

## Acceptance for the first slice

- Missing/malformed location and missing/invalid worker credential fail before
  scoped database operations. The handler obtains a separate secret from the
  worker-only environment and validates it before opening the worker DB; the
  source/unit and disposable suites cover this boundary.
- Database-selected tenant scope matches the current owner and exact worker
  resource/action grant; caller tenant input is never accepted. Migration 405
  acceptance verifies the exact scope in disposable PostgreSQL.
- Cross-tenant, cross-location, revoked-grant, transferred-owner, inactive
  location, and replayed-transaction contexts fail closed and clear prior local
  context.
- Source event ID and sensor row are joined and checked against the verified
  location before alert processing.
- Migration 407's receipt functions require signed `sensor_reading/process`
  location scope, bind the event and reading to the same source/device, require
  an enabled rule, suppress duplicates, permit only one `no_match` transition,
  and validate any linked alert. Nine disposable PostgreSQL 16 checks pass;
  the worker execution role has no direct receipt-table privileges. Migration
  414 calls them through the integrated handler.
- Migration 408's event publisher accepts only an alert linked to a matching
  `alert_created` receipt under the signed source location. It derives the
  event payload and critical priority from canonical records, inserts a
  pending event, verifies stable-ID replays, and cannot read or mutate global
  queue rows directly. Eleven disposable PostgreSQL 16 checks pass; migration
  414 calls the publisher through the integrated handler.
- Migration 409's notification-intent function accepts only the matching
  signed source/alert receipt and published sensor-alert event. It fixes the
  destination key, allowlists channel payload fields, enforces a 16 KiB limit,
  inserts pending intent only, and preserves delivery and attempt state on
  replay. Twelve disposable PostgreSQL 16 checks pass; migration 414 now wires
  the handler through this function.
- Migration 412's bounded source read and metric evaluation validate signed
  location plus event/source/sensor selectors; the rule list checks the
  device's sensor type and enabled state; history and cooldown queries stay in
  the same location. Ten disposable PostgreSQL 16 checks pass, including a
  forced-RLS source read and worker direct-table denial. Migration 414 now
  wires the handler through these functions.
- Event receipt semantics, idempotency, retries, and outbox effects remain
  unchanged under disposable PostgreSQL and source-level checks.
- Migrations 405–414 are tested only in disposable databases. No migration is
  applied to the candidate, no worker is activated, and no application-table
  RLS rollout is enabled. Migration 412's narrow owner SELECT policy is added
  only where a source table already has RLS enabled or forced.

## Rollback

Before candidate rollout, remove the new Python adapter/integration and add a
forward-only migration that revokes its function privileges and disables worker
credentials; never edit an applied migration. Keep event handler and scheduler
allowlists unchanged until rollback is verified. A worker credential is
revoked, not reused. Do not restore the broad runtime identity as an implicit
fallback after the worker path has been activated.

## Source anchors

- [Worker operation map](worker-operation-map.md) and
  [job contract inventory](worker-job-contract-inventory.json)
- [Worker source closure](worker-source-closure.json),
  [function reachability](worker-function-reachability.json),
  [SQL inventory](worker-sql-inventory.json), and
  [boundary preflight](worker-boundary-preflight.json)
- [Tenant/RLS call-site audit](mobile-tenant-rls-callsite-audit.md)
- [`services/common/tenant_context.py`](../../services/common/tenant_context.py)
- [`services/security/execution_allowlist.py`](../../services/security/execution_allowlist.py)
- [`services/events/bus.py`](../../services/events/bus.py)
- [`services/ingestion/anomaly_detector.py`](../../services/ingestion/anomaly_detector.py)
