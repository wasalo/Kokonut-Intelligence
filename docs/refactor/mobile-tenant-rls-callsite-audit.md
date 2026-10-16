# Field Collector tenant and RLS call-site audit

Updated: 16 October 2026 (static SQL inventory refreshed)

## Finding

Migration 391 pins newly issued enrollment codes and registered devices to the
verified current location owner and rejects later binding changes. Migration
392 moves bearer-token resolution and one-time code redemption behind narrow
functions owned by dedicated non-login, non-bypass roles. Migration 393 signs
mobile-device tenant context with a database-private HMAC key. Migration 394
adds signed OIDC operator context after validating the active session,
tenant-qualified grant, membership, and current owner/share. Both proofs bind
to the current PostgreSQL backend and transaction; the RLS accessor verifies
the signature instead of trusting caller-set labels. Network-isolated
PostgreSQL 16 acceptance applied and replayed migrations 391–396, forced RLS
in disposable databases, and passed mobile credential/context, operator
owner/share, Gateway credential, denial, lock, cleanup, and role-boundary
checks. Migrations 392–403 have now been applied to the local candidate after
encrypted checkpoint and isolated restore rehearsals. The 401/402 rollout left
the retention and legal-hold tables empty. Migration 403 adds an empty
informational KGP policy projection and did not recreate the candidate app. The
candidate reports 394 applied schema migrations through 403, zero pending,
health 200, and a protected-route 401. No migration enables application-table
RLS, which remains disabled. The current generated service SQL inventory
records 3,799 call sites
across 806 Python modules, with 257 sites linked to 20 worker operation roots;
it is a static review aid, not a grant allowlist
([inventory](runtime-sql-inventory.json); [refresh evidence](builds/2026-10-16-recovery/runtime-sql-inventory-refresh.json)). Migration 395 removes runtime-role access to
`operator_session` and gives OIDC a separate auth login for bounded session
functions. Runtime provisioning
now limits `mobile_device` and `mobile_device_enrollment` to explicit column
grants and denies reads of `device_token_hash`, `push_token`, and `code_hash`.
Enrollment issue/revoke remains column-scoped, and device token clearing now
runs through a bounded database function; DML on other public tables remains broad. The new
whole-services SQL inventory is a review aid, not a grant allowlist. Those writes
and other application roles/callers remain to be bounded. Migration 396 now
revalidates API-key and capability-token tenant scope for Gateway mobile-device
writes, signs context in the same transaction, and gives the ordinary runtime
role read-only access to reviewed API-key authentication columns. Gateway
routes beyond those mobile writes, the preflight CLI, and worker jobs still
need explicit database access designs. The optional Kernel Directus profile
now has a dedicated DML-only `kokonut_directus_runtime` identity. Fresh-volume
Compose acceptance verified owner bootstrap, health, synthetic admin login,
runtime database identity, and cleanup; it does not establish Directus
collection/field/row parity or view access. The legacy mobile-offline CLI is
now closed before database access. Do not enable RLS until remaining paths
and their roles are closed.

## Access-path inventory

| Path | Current scope enforcement | RLS readiness / required work |
| --- | --- | --- |
| Device-token resolution: [`_device_for_token`](../../services/mobile/api.py#L353) | Hashes the presented token and calls `kokonut_security.resolve_mobile_device_token`; the function returns only device/user/location identity and whether the stored owner binding is current. It does not return the hash or collection data. | Isolated PostgreSQL acceptance passes for current, legacy-unbound, transferred-owner, and unknown tokens. Through the provisioned runtime login, the bounded resolver succeeds while direct SELECT of `device_token_hash` and `push_token`, hash predicates, and `SELECT *` are denied. |
| Device revocation: [`_revoke_device`](../../services/mobile/api.py#L1052) | Calls migration 398's bounded function on the same transaction after Gateway or OIDC context validation. The function revalidates exact tenant/location/action, changes one active matching device, and clears its token hash; the runtime role cannot directly UPDATE `status`, `device_token_hash`, or `revoked_at`. | Exact-checkpoint PostgreSQL 16 restore/replay forced RLS on synthetic devices and passed API-key, capability, operator, wrong-action/location, cross-tenant, direct-column-denial, and transaction-reset checks. Candidate anonymous route returns 401. Authenticated HTTP under the dedicated runtime login remains open because the candidate currently uses the database superuser and runtime credentials are not provisioned. |
| One-time enrollment redemption: [`register_device`](../../services/mobile/api.py#L834) | Calls `kokonut_security.redeem_mobile_enrollment`, which locks the one-time enrollment, share-locks current owner rows, inserts one owner-bound device, and consumes the code atomically. The function rejects invalid arguments, expiry, stale ownership, and device-ID conflicts without consuming the code. | Isolated PostgreSQL acceptance passes replay, conflict, success/reuse, expiry, owner-transfer, and concurrent redemption checks; two competing requests created exactly one device and consumed the code once. Through the provisioned runtime login, redemption succeeds while direct SELECT of `code_hash` and `SELECT *` are denied. Enrollment issue/revoke SQL remains column-scoped. Migrations 392–400 are now on the local candidate; repeat this race under the final runtime database role/RLS contract. |
| Device-scoped forms, sync, status, and media-policy reads | After token resolution, these handlers call [`set_mobile_device_tenant_context`](../../services/common/tenant_context.py#L90) on the same connection before protected location/data queries. PostgreSQL validates the token hash and current owner, then signs backend/transaction-bound context; policies must use `kokonut_security.current_tenant_context()`, not the diagnostic GUC labels. | Forced-RLS disposable acceptance passes valid mobile scope, cross-tenant filtering, forged/tampered context denial, invalid-token clearing, and transaction reset. Migrations 392–400 are on the candidate, but every SQL statement must still be reviewed under the final runtime role/RLS contract. Media object storage remains a separate provider boundary. |
| OIDC operator enrollment/revocation: [`_create_enrollment`](../../services/mobile/api.py#L762), `_revoke_enrollment`, `_revoke_device` | Middleware binds the authenticated opaque session hash in request-local context. The service passes it to migration 394's definer function, which validates current session/identity, tenant-qualified grants, membership, owner/share, and all additional scopes, locks the rows, and signs tenant context. Migration 395 moves session creation, lookup, and revocation to the dedicated operator-auth connection; the application role cannot read session hashes. | Migrations 394–395 passed forced-RLS disposable acceptance for owner/shared grants, stale/legacy/cross-tenant denial, cleanup, share revocation, scope-revocation locking, direct runtime-role denial, and bounded session lifecycle. Other runtime data access and non-OIDC paths still need the final role and context contract before RLS. |
| Capability/API-key enrollment and revocation: [`router.py`](../../services/gateway/router.py#L58) and [`_create_enrollment`](../../services/mobile/api.py#L762) | Gateway middleware authorizes the exact `mobile_device` action/location, hashes the accepted credential, and records only its type and digest in request state. The same write transaction calls migration 396's bounded function, which verifies active credential status, expiry/revocation, exact location/resource/action grant, and current verified owner before signing backend/transaction-bound context. | Migration 396 passes focused source and forced-RLS disposable checks for API keys and capabilities, including denial cleanup and transaction reset. This closes only tenant-bound mobile-device writes. Shared-organization API-key affiliations, matching database records for environment API keys, all other Gateway routes, and application RLS remain open. |
| OIDC operator report-review queue/detail: [`operator_review.py`](../../services/gateway/operator_review.py) | Each read opens a non-autocommit connection, starts a read-only transaction with statement/lock timeouts, establishes signed operator tenant context on that connection, and then runs the bounded report query. SQL also repeats the location-qualified grant check. Detail output is capped at 512 KiB. | Five focused source tests cover context-before-query ordering on the same connection, queue/detail location-grant predicates, no query after legacy/unqualified-context denial, rollback/close, and oversized detail rejection. The tests use synthetic connections only; live OIDC, database role, owner/share rows, signed function behavior, populated report parity, and application RLS remain open ([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)). |
| Legacy analytics transport CLI: [`mobile_offline.py`](../../services/analytics/mobile_offline.py) | All exported service helpers and historic CLI commands now fail closed before opening a database connection. The module has no in-repository runtime caller. | This unscoped path is closed. Equivalent intake and sync remain available through the authenticated consent-aware Field Collector. A location-scoped OIDC console endpoint now provides device inventory and content-free queue counts under both `mobile_device:read` and `mobile_collection_review:read`; focused source/ASGI checks pass. Live OIDC/database acceptance and other worker/Gateway/RLS paths remain open. |
| Tenant preflight: [`collect_inventory`](../../services/mobile/tenant_preflight.py#L557) | Runs a read-only repeatable-read aggregate and emits opaque references/counts; it deliberately examines ownership and grants across locations. It no longer reads mobile credential columns and uses active/revoked state for device counts. | Give it an explicit owner/preflight database role and document who may invoke it. Do not run the aggregate with the ordinary app role once RLS is enabled. |
| Directus and database views | The optional Kernel profile now uses a dedicated DML-only `kokonut_directus_runtime` identity. Fresh-volume Compose acceptance verifies owner bootstrap, runtime health/login, and that Directus connects as that role; disposable PostgreSQL role checks cover DML, DDL/ownership denial, future-object grants, stale ACL removal, and database isolation ([role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json); [profile evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)). This does not verify the archived service identity, view behavior, collection/field/row parity, or schedules. Migration 139 also defines legacy mobile sync/device views. | Not ready. Inspect view ownership/invoker behavior, hooks, saved queries, and every consumer in a matching isolated Directus runtime before choosing RLS policies or retirement scope. Keep the optional Kernel profile bound to a dedicated PostgreSQL instance because its bootstrap revokes `PUBLIC CONNECT` instance-wide. |
| Recovery fixtures and ordered migrations | Recovery fixture SQL inserts devices into isolated scratch databases. Migration 391 adds owner-binding triggers and indexes; 392 adds credential functions; 393 signs mobile context; 394 signs OIDC operator context and adds dormant definer-role RLS policies; 395 isolates operator sessions behind bounded functions and a dedicated auth login; 396 verifies Gateway credential scope for tenant-bound mobile writes; 397 adds the location-level WorldClim key/view path; 398 bounds device revocation; 399 restores runtime security-schema lookup on DB-only restore; 400 restores restricted function-owner roles, exact SECURITY DEFINER ownership, and narrow grants after role/ACL loss; 401 adds dynamic retention and audited legal holds; 402 adds optional owner-defined retention scope codes; 403 adds the informational KGP governance target-policy projection. None enables application-table RLS. | Migrations 391–403 are applied on the local candidate. The exact pre-400 encrypted checkpoint was restored into an internal-only template0 clone, migration 400 replayed, and runtime/operator-auth role bootstrap accepted. That candidate archive restored 1,010 public tables but had zero public location rows, so this is database/role recovery evidence, not farm-data parity. The separate synthetic owner/ACL-loss forced-RLS acceptance passed. The fresh 401/402 rollout then reported 393 applied schema migrations, zero pending, health 200, anonymous protected route 401, zero policy/hold rows, and RLS off; the app was not recreated. Migration 403 was then applied after a fresh checkpoint and isolated restore; the governance policy table is empty, the app was not recreated, and RLS remains disabled ([migration-403 rollout](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json)). Keep fixtures and migration execution on explicit maintenance credentials. Candidate 391 evidence: [rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json); 392–397 rollout: [checkpoint and candidate evidence](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json); 398–399 evidence: [checkpoint, forced-RLS acceptance and candidate rollout](builds/2026-10-14-recovery/candidate-migration-398-399-device-revocation.json); migration 400 evidence: [owner/ACL repair and candidate rollout](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json); exact pre-400 restore: [database/role recovery](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json); 401–402 evidence: [candidate retention rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json). Disposable migration 392–393 evidence: [mobile acceptance](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json); migration 394 evidence: [operator acceptance](builds/2026-10-14-recovery/operator-tenant-context-disposable.json); migrations 395–396 evidence: [runtime-role acceptance](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json); migration 396 evidence: [Gateway acceptance](builds/2026-10-14-recovery/gateway-tenant-context-disposable.json). |

## Context trust boundary

The mobile-device setter verifies the presented token hash and current owner;
the OIDC operator setter verifies the session hash, tenant-qualified grants,
membership, and owner/share state. Both sign with the private database key,
and the accessor accepts only a signature bound to the current backend and
transaction. The key is unreadable by the ordinary role; caller-set
tenant/location/actor labels do not create a valid proof. Migration 395 removes
direct runtime access to session hashes and limits session operations to a
separate auth login with three bounded functions. Runtime provisioning removes
table-wide grants from mobile device/enrollment rows and prevents reading
device-token, push, and enrollment-code hashes. Migration 398 removes direct
device status/token/revocation updates and exposes one bounded exact-scope
function. Migration 399 grants schema lookup only to the runtime role when it
exists. Migration 400 restores six bounded NOLOGIN function-owner roles, exact
SECURITY DEFINER ownership, and reviewed table/column/function grants; the
restore prerequisite script creates those role names before `pg_restore` reads
RLS policies. Runtime bootstrap verifies the expected isolated owners and
repairs private-function ACLs omitted by DB-only restore. Runtime DML on other public tables remains broad. Migration 396 verifies the Gateway API-key or capability-token grant
for tenant-bound mobile-device writes and signs the resulting scope. The OIDC
console adds a source-covered location-scoped device/queue overview requiring
both device-read and collection-review grants. Live OIDC/database acceptance,
remaining worker paths, Directus/views, and application RLS remain unresolved.
Resolve these database role and credential boundaries before enabling RLS.
See PostgreSQL’s
[custom options](https://www.postgresql.org/docs/current/runtime-config-custom.html)
and [configuration-setting functions](https://www.postgresql.org/docs/current/config-setting.html).

## Worker execution and database identity trace — 14 October 2026

The supported execution allowlist is a code-execution boundary only. It does
not bind a scheduled module or event handler to a database role or tenant.

- In the standard Kernel profile, `services.core.runtime` starts the scheduler
  and event worker as child processes. Compose gives the shared worker
  `PG_USER=${KOKONUT_RUNTIME_USER:-kokonut}` and one runtime password.
- `services.scheduler.engine.SchedulerEngine._execute_task` validates the
  configured module against `ALLOWED_SCHEDULED_MODULES`, then runs it as a
  subprocess without an explicit environment. The module inherits the
  scheduler's full environment and database identity.
- `services.events.bus.EventBus._invoke_handler` starts each allowlisted
  handler in a spawned process. The allowlist narrows module/function names,
  but the child inherits the event worker's environment. Handlers such as
  `services.ingestion.anomaly_detector.handle_sensor_reading` can initiate
  tenant data reads and draft/alert/claim writes; notification handlers write
  the global durable notification outbox; cache handlers route through the
  configured cache provider.
- The legacy worker overlay also defaults `PG_USER` to `kokonut`. The
  portability worker uses its app connection configuration. No worker-specific
  database principal or worker tenant-context setter is currently present in
  these dispatch paths.
- The four cache invalidation handlers now require and canonicalize a valid
  location UUID before selecting the cache adapter. Missing/malformed scope
  fails before provider construction, preventing an event from becoming an
  all-location invalidation. The durable bus records the handler failure and
  applies its existing bounded retry/dead-letter policy. This narrows one
  worker side effect but still does not establish signed DB tenant context or
  a worker-specific database role.

The [worker operation map](worker-operation-map.md) now covers all 15
allowlisted scheduled modules and five event-handler pairs, including their
source-visible data objects, source scope, external effects, and replay notes.
`tests/test_worker_operation_map.py` ensures the inventory matches both
executable allowlists and every entry has source references. This is an
entrypoint inventory only: transitive calculator/helper/provider calls and
database-stored command arguments remain outside the source-effect map. The
new module-specific command schemas bound supported scheduler argv before
activation and dispatch, but do not establish tenant scope or worker grants;
the map must not be used as a worker grant list.

Therefore, the current allowlists protect against arbitrary module/function
dispatch but do not make worker SQL safe under application RLS. Do not assign a
single inferred tenant to a cross-location batch job, and do not enable RLS or
remove runtime grants on this evidence. The first source-level effect pass now
records 43 unique high-confidence process, filesystem, HTTP, email, dynamic
import, and EVM call sites across 49 operation/site memberships and 20 roots
([inventory](worker-effect-inventory.json)).
It intentionally overcounts
mutually exclusive CLI branches and can miss effects behind callbacks or
provider adapters; for example, the credit adjustment worker contract rejects
on-chain transaction calls still visible in the module-wide graph. The graph
now follows the EventBus process target into the local child and resolver, and
the callback inventory traces its validator, dynamic import, and five
source-allowlisted handlers. Runtime string selection and persisted handler
configuration remain unverified.
The actuation helper reachable from a worker only records an approval-gated
command; it does not publish MQTT. Next
code-only work is to reconcile each candidate against its exact scheduler
command contract, inspect remaining dynamic/provider callbacks and transitive
effect wrappers, then reconcile persisted task rows with those contracts. The
source-only JobSpec inventory now identifies 13 accepted default templates
and two rejected defaults (source-less sensors and unlocated climate). Remote
sensing is bounded to sequential `--run-jobs --limit` batches of 1–10 and
ClickHouse projection to one bounded run-once operation; neither enables a
provider or inspects persisted tasks or external Prefect state
([inventory](worker-job-contract-inventory.json)). A
later role/context change needs a non-forgeable system-worker identity and
narrow operation grants. Active provider schedules, operational owners, and
any production identity mapping remain separate owner inputs under OFU-16/02.

## Required sequence before RLS

1. Inventory every table, view, trigger, worker, CLI, API-key route, OIDC route,
   Directus role/hook, and maintenance command that reads or writes the tenant
   tables. Record the database role and whether it bypasses RLS. The source
   trace above confirms that execution allowlists do not create worker
   isolation.
2. Close token, enrollment, and device-revocation credential paths without
   weakening token hashing, one-time use, owner-transfer serialization, or
   revocation.
   Migrations 392–393 implement bounded credential paths and signed mobile
   context, passing isolated PostgreSQL forced-RLS acceptance. Runtime-role
   provisioning now denies direct reads of token, push, and enrollment hashes
   and applies declared mobile-table column grants. Migration 398 now bounds
   device revocation and passed synthetic forced-RLS acceptance; 399 and the
   role bootstrap repair the private security-schema access after DB-only
   restore. Candidate migration rollout is complete. Authenticated
   HTTP-under-runtime checks and final role/RLS acceptance remain open because
   the candidate still uses the database superuser.
3. Keep Gateway capability/API-key mutation context in the same transaction
   and validate it under forced RLS with the final role model. Migration 394
   adds database-verified OIDC context. Migration 395 moves session creation,
   lookup, and revocation to a separate auth role while removing runtime access
   to session hashes. Migration 396 adds database verification of Gateway
   credentials for tenant-bound mobile writes. Mobile, operator, and Gateway
   context cleanup is verified at transaction end.
4. Separate app, migration, backup, Directus, preflight, and recovery-fixture
   database roles. Verify least privilege and view semantics on PostgreSQL 16.
5. In disposable PostgreSQL, test owner and explicitly shared access; wrong or
   stale owner; legacy NULL binding; absent and forged context; expired, used,
   revoked, and concurrently redeemed enrollment codes; owner transfer during
   requests; API-key/OIDC denial; view access; rollback; and transaction reset.
   Migrations 392–396 cover concurrent single-use redemption, expiry, owner
   transfer, mobile, OIDC, and Gateway signed contexts, device revocation, and
   isolated credential-role boundaries under disposable forced RLS. Repeat all
   checks under the final runtime role and add remaining Gateway, view, and
   worker cases.
6. Before preparing any RLS-enabling candidate migration, close the remaining
   access paths with an encrypted checkpoint and verified restore path. The
   schema migrations 392–402 have already been rolled out but do not enable RLS.
   Keep RLS disabled if any access path or consumer remains unknown.

This audit combines source review, isolated migration-392–400
acceptance, candidate schema rollout through 402, and PostgreSQL 16 runtime-role
credential-grant checks. It does not claim Directus parity, worker isolation,
a shared-organization API-key affiliation, a final app-table role allowlist,
database-role hardening across consumers, an RLS migration, or live candidate
RLS acceptance. See [runtime mobile role evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json).
