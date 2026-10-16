# Worker tenant-context contract

**Status:** first database/source adapter and dormant anomaly receipt/event/
notification functions implemented and accepted on 16 October 2026. Migration
410 adds a bounded actuation-intent function, accepted in fifteen focused
disposable PostgreSQL checks. Migration 405 and a transaction-bound Python
adapter establish an opt-in worker context; migrations 407–410 add bounded
receipt, canonical event-publication, notification-intent, and actuation-intent
functions for `sensor_reading/process`.
No candidate database, worker credential, worker deployment, handler dispatch,
or application-table RLS policy was changed.

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

The scheduler currently launches allowlisted modules in subprocesses, and the
EventBus starts allowlisted handlers in spawned child processes. Neither path
establishes a signed tenant context today. The child must receive only the
credential for its own execution identity. Credentials must not be inherited
from a process that can dispatch unrelated operations; deployment-level
principal separation is required before claiming isolation between handlers.

## First implementation slice

Use `services.ingestion.anomaly_detector.handle_sensor_reading` as the first
tenant-execution adapter because the durable `sensor_reading` event already
contains a location ID and the handler is explicitly allowlisted. The first
source slice now requires a canonical location UUID and constrains the source
event/reading join by that location. This is not signed worker context or tenant
authorization; those remain the next implementation step. The complete adapter
must:

1. Require and canonicalize `payload.location_id` before opening a database
   connection; reject missing or malformed values.
2. Establish database-signed worker context for that location and the exact
   anomaly-processing operation before querying the source event or reading.
3. Require the joined `platform_event` and `sensor_reading` to match the event
   ID, event type, source table, source row, sensor ID, and authorized location.
4. Preserve the current event receipt, alert idempotency, notification outbox,
   and human-approved actuation boundaries. Shared alert-rule configuration is
   a read-only reference input; event execution now skips the default-rule
   bootstrap, which remains available to the interactive CLI.
5. Keep queue claim, lease renewal, acknowledgement, retry, and dead-letter
   operations in the control-plane boundary. Do not broaden the anomaly
   execution identity to claim or complete arbitrary events.

The first location-lineage source change is in
`services/ingestion/anomaly_detector.py`. Migration 405 adds private worker
principals, SHA-256 credential digests, exact tenant/location/resource/action
grants, a dedicated `kokonut_worker_execution` group role, the bounded signed
context setter, and an exact-scope accessor. `services/common/tenant_context.py`
hashes the supplied worker secret in memory, clears prior context, assumes the
dedicated role locally, and requires a non-autocommit transaction. The adapter
is not yet connected to an event or scheduled handler: no worker-only credential
is provisioned, and the current EventBus dispatcher must not pass one shared
secret to unrelated handler processes.

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

The signed worker operation must authorize the location-bound table access and
route shared queue/audit mutations through bounded database operations. A
single `sensor_reading:process` grant does not by itself authorize global
notification, event-bus, or audit writes. Before handler integration, map each
effect to a tenant-qualified row policy or a database function that derives
scope from the signed context; keep event claim/receipt and queue acknowledgement
in the separate control-plane identity. Any database-backed effect added to
this handler must use the same transaction or a bounded function that preserves
that transaction boundary.

The detailed [sensor anomaly effect contract](worker-sensor-anomaly-effects.json)
now records the source-visible read/write set and the required boundary for each
relation. It is a proposed authorization contract, not a grant list or evidence
that those checks run in PostgreSQL. In particular, it separates global
read-only alert-rule/sensor-type references from location-bound data and treats
event queue state, notification delivery, and actuation delivery as distinct
control-plane work.

Remaining worker-permission work before broader integration:

1. Enforce the direct location keys added by migration 406 for tenant-owned
   alerts, ingestion-audit rows, and notification intents. Existing rows with
   unresolved source lineage remain NULL and must stay inaccessible to the
   worker. Migration 407 protects anomaly-receipt reservation and outcome
   writes through bounded functions; its signed-scope, source-lineage,
   idempotency, and privilege acceptance passed on disposable PostgreSQL 16.
2. **Complete:** migration 408 adds a bounded canonical sensor-alert event
   publisher. It derives payload and priority from the matching alert/receipt,
   inserts a pending event, handles identical retries, rejects ID conflicts,
   and leaves all queue state untouched. Disposable PostgreSQL 16 acceptance
   covers source/alert/scope validation, ACLs, and replay.
3. **Complete:** migration 409 adds a bounded notification-intent function for
   the existing webhook, Directus, and email payload shapes. It validates the
   signed source/alert linkage, fixes the destination key, limits fields and
   payload size, inserts pending intent only, and preserves delivery state on
   retry. Twelve disposable PostgreSQL 16 checks pass. The handler remains
   unwired and must publish the alert event before enqueueing notification.
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
   The future handler must call it after recording the alert receipt and before building
   downstream notification intent data. The alert-event payload itself omits
   `claim_id`; notification and actuation intents follow event publication.
   Fourteen focused disposable PostgreSQL 16 checks pass, including replay,
   role boundaries, and direct-table denial.
6. Integrate the anomaly handler only after its credential is isolated from
   unrelated dispatch. Keep alert creation, receipt update, claim creation,
   alert publication, notification enqueue, and actuation intent creation in
   one caller-owned transaction; the worker must not submit, verify, publish,
   reject, or transmit actuator commands.
7. Provision an isolated worker login/credential in a restored disposable
   database. Verify that it cannot read worker grants, sign operator context,
   issue another worker identity, or access unrelated tenant rows.
8. Expand one operation at a time. Reconcile the 20 worker roots, direct SQL
   inventory, worker effects, external task state, and the control-plane
   identity before reducing runtime grants or enabling any RLS policy.

Migration-410 acceptance covers wrong/missing scope, source and alert lineage,
canonical rule-derived payload, critical/configured approval, one-intent
uniqueness, retry preservation after approval/delivery state changes, role
separation, direct table denial, and migration replay. No base application RLS
or candidate rollout follows automatically.

Migrations 405 and 406 implement the identity primitive and additive source
lineage columns. Migration 407 adds bounded anomaly-receipt reserve/outcome
functions; nine disposable acceptance checks pass. Migration 408 adds the
canonical alert-event publisher; eleven checks pass. Migration 409 adds the
bounded notification-intent function; twelve checks pass. Migration 410 adds
the bounded actuation-intent function, accepted in fifteen disposable checks.
Migration 411 adds the bounded draft-claim function; fourteen disposable
PostgreSQL acceptance checks pass. The Python context adapter can set signed
scope, but no worker login or dispatcher integration exists. No access is granted to the shared
runtime or existing event/notification dispatchers.

The event producers in `services/ingestion/sensor_ingester.py` and
`services/ingestion/http_sensor_receiver.py` already include the location ID.
The sensor source row remains authoritative: the handler must compare the
payload selector with its database row after context is established. Before
implementation, reconcile any alternate or external `sensor_reading` event
producer against this contract.

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
   privilege separation, and replay. These functions remain dormant until
   worker credentials and handler transaction integration are ready.
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
6. Integrate only the sensor-reading handler after its credential is isolated
   from unrelated dispatch, add a regression inventory for producers and
   dispatch, and add disposable PostgreSQL checks for valid grant,
   cross-location denial, inactive/transfer/revocation denial, stale-context
   clearing, same-transaction signature, and transaction cleanup.
7. Provision an isolated worker login/credential in a restored disposable
   database. Verify it cannot read worker grants, sign operator context, issue
   another worker identity, or access unrelated tenant rows.
8. Expand one operation at a time. Reconcile the 20 worker roots, direct SQL
   inventory, worker effects, external task state, and the control-plane
   identity before reducing runtime grants or enabling any RLS policy.

Each step is source/disposable acceptance only. Applying the migration to the
local candidate, provisioning production secrets, activating schedules,
enabling RLS, and retiring the broad runtime principal remain separate rollout
gates.

## Acceptance for the first slice

- Missing/malformed location and invalid scope fail before the worker setter
  call or provider construction. The Python adapter requires a separate secret
  argument; handler-level missing-credential denial remains unintegrated.
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
  the worker execution role has no direct receipt-table privileges. The
  functions are not called by the handler yet.
- Migration 408's event publisher accepts only an alert linked to a matching
  `alert_created` receipt under the signed source location. It derives the
  event payload and critical priority from canonical records, inserts a
  pending event, verifies stable-ID replays, and cannot read or mutate global
  queue rows directly. Eleven disposable PostgreSQL 16 checks pass; handler
  dispatch remains unchanged.
- Migration 409's notification-intent function accepts only the matching
  signed source/alert receipt and published sensor-alert event. It fixes the
  destination key, allowlists channel payload fields, enforces a 16 KiB limit,
  inserts pending intent only, and preserves delivery and attempt state on
  replay. Twelve disposable PostgreSQL 16 checks pass; the anomaly handler is
  not yet wired to this function.
- Event receipt semantics, idempotency, retries, and outbox effects remain
  unchanged under disposable PostgreSQL and source-level checks.
- Migration 405 is tested only in a disposable database. No migration is
  applied to the candidate, no worker is activated, and no application-table
  RLS policy is enabled as part of this source slice.

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
