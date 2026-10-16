# Worker tenant-context contract

**Status:** implementation contract, 16 October 2026. No migration, runtime
identity, candidate database, or worker deployment was changed for this design.

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
   a read-only reference input; default rule creation must not be performed by
   the tenant worker.
5. Keep queue claim, lease renewal, acknowledgement, retry, and dead-letter
   operations in the control-plane boundary. Do not broaden the anomaly
   execution identity to claim or complete arbitrary events.

The first location-lineage source change is in
`services/ingestion/anomaly_detector.py`. Focused regression checks have not yet
been added or run; the repository checklist requires explicit owner approval
before that verification step.

The event producers in `services/ingestion/sensor_ingester.py` and
`services/ingestion/http_sensor_receiver.py` already include the location ID.
The sensor source row remains authoritative: the handler must compare the
payload selector with its database row after context is established. Before
implementation, reconcile any alternate or external `sensor_reading` event
producer against this contract.

## Planned code and migration sequence

1. Add an ordered migration for worker principal/grant storage, the bounded
   signed-context setter, and accessor support for `system_worker`. Do not
   enable RLS or change existing runtime grants in this migration.
2. Add a small Python adapter beside
   `services/common/tenant_context.py` that validates transaction state,
   canonical location/resource/action inputs, hashes the credential in memory,
   clears prior context, calls the database setter, and returns a typed worker
   context. It must not read credentials from event/job payloads.
3. Integrate only the sensor-reading handler, add a regression inventory for
   producers and dispatch, and add disposable PostgreSQL checks for valid grant,
   cross-location denial, inactive/transfer/revocation denial, stale-context
   clearing, same-transaction signature, and transaction cleanup.
4. Provision an isolated worker login/credential in a restored disposable
   database. Verify it cannot read worker grants, sign operator context, issue
   another worker identity, or access unrelated tenant rows.
5. Expand one operation at a time. Reconcile the 20 worker roots, direct SQL
   inventory, worker effects, external task state, and the control-plane
   identity before reducing runtime grants or enabling any RLS policy.

Each step is source/disposable acceptance only. Applying the migration to the
local candidate, provisioning production secrets, activating schedules,
enabling RLS, and retiring the broad runtime principal remain separate rollout
gates.

## Acceptance for the first slice

- Missing/malformed location and missing/invalid worker credential fail before
  tenant SQL or provider construction.
- Database-selected tenant scope matches the current owner and exact worker
  resource/action grant; caller tenant input is never accepted.
- Cross-tenant, cross-location, revoked-grant, transferred-owner, inactive
  location, and replayed-transaction contexts fail closed and clear prior local
  context.
- Source event ID and sensor row are joined and checked against the verified
  location before alert processing.
- Event receipt semantics, idempotency, retries, and outbox effects remain
  unchanged under disposable PostgreSQL and source-level checks.
- No migration is applied to the candidate, no worker is activated, and no RLS
  policy is enabled as part of this first source slice.

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
