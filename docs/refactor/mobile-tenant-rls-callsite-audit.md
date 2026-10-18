# Field Collector tenant and RLS call-site audit

Updated: 17 October 2026 (static SQL and worker inventories refreshed)

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
checks. Migrations 392–433 have now been applied to the local candidate after
checkpoint and isolated restore rehearsals. The ordered migration plan reports
424 applied schema entries through migration 433 and zero pending; the candidate
app health route returns 200 and the anonymous protected route returns 401.
No migration enables application-table RLS, which remains disabled. The current
generated SQL inventory records 4,004 execution sites across 825 service source
files, with 322 sites linked to 31 worker operation roots across 93 source files.
The worker graph records 632 function memberships, 862 direct-call edges,
and 20 dynamic-dispatch edges; its SQL report records 321 operation/site
memberships on static paths, 249 unique sites with a static operation path, and
73 sites without a static function match. These generated counts are source
navigation aids, not an authorization allowlist or proof of tenant isolation
([inventory](runtime-sql-inventory.json);
[latest worker evidence](builds/2026-10-17-recovery/ci-431-worker-inventory-fix.json);
[runtime inventory evidence](builds/2026-10-17-recovery/worker-inventory-refresh-current.json)). Migration 395 removes runtime-role access to
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
report-review, Field Collector review, Data Stream create, and non-Field-Collector
farm-activity operations now have source-level transaction-context contracts.
Migration 404 is applied on the candidate; broad runtime DML and application
RLS remain separate open gates.
Other Gateway paths, the preflight CLI, and worker jobs still need explicit
database access designs. The optional Kernel Directus profile
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
| Capability/API-key enrollment and revocation: [`router.py`](../../services/gateway/router.py#L58) and [`_create_enrollment`](../../services/mobile/api.py#L762) | Gateway middleware authorizes the exact `mobile_device` action/location, hashes the accepted credential, and records only its type and digest in request state. The same write transaction calls migration 396's bounded function, which verifies active credential status, expiry/revocation, exact location/resource/action grant, and current verified owner before signing backend/transaction-bound context. A one-shot, dry-run-first provisioner now prepares environment key hashes and exact location scopes without granting database writes to the runtime role. | Migration 396 passes focused source and forced-RLS disposable checks for API keys and capabilities, including denial cleanup and transaction reset. The provisioner’s parser/idempotency/conflict contract has focused checks ([source evidence](builds/2026-10-16-recovery/gateway-api-key-provisioner-source.json)); an operator must still supply its encrypted maintenance DSN and reconcile actual production key rows. Shared-organization API-key affiliations, all other Gateway routes, and application RLS remain open. |
| OIDC operator report-review queue/detail: [`operator_review.py`](../../services/gateway/operator_review.py) | Each read opens a non-autocommit connection, starts a read-only transaction with statement/lock timeouts, establishes signed operator tenant context on that connection, and then runs the bounded report query. SQL also repeats the location-qualified grant check. Detail output is capped at 512 KiB. | Five focused source tests cover context-before-query ordering on the same connection, queue/detail location-grant predicates, no query after legacy/unqualified-context denial, rollback/close, and oversized detail rejection. The tests use synthetic connections only; live OIDC, database role, owner/share rows, signed function behavior, populated report parity, and application RLS remain open ([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)). |
| OIDC non-Field-Collector farm-activity operations: [`farm_activity_records.py`](../../services/gateway/farm_activity_records.py) | Each read, create, draft correction, and lifecycle transition establishes signed operator tenant context for the exact location/resource/action before farm-activity SQL. Queries retain explicit location and source-provenance filters; the database trigger appends operator events and rejects Field Collector rows or invalid actor/lifecycle changes. | Thirteen focused service/HTTP/route-policy tests and 11 disposable PostgreSQL 16 migration-404 checks pass. This is source/disposable evidence only: migration 404 is on the candidate, the ordinary runtime role still has broad DML on other public data, and configured OIDC, browser behavior, populated legacy-row reconciliation, and application RLS remain open ([contract](gateway-farm-activity-operations.md); [database evidence](builds/2026-10-16-recovery/gateway-farm-activity-operations-disposable.json); [console evidence](builds/2026-10-16-recovery/operator-console-farm-activity-contract.json)). |
| Legacy analytics transport CLI: [`mobile_offline.py`](../../services/analytics/mobile_offline.py) | All exported service helpers and historic CLI commands now fail closed before opening a database connection. The module has no in-repository runtime caller. | This unscoped path is closed. Equivalent intake and sync remain available through the authenticated consent-aware Field Collector. A location-scoped OIDC console endpoint now provides device inventory and content-free queue counts under both `mobile_device:read` and `mobile_collection_review:read`; focused source/ASGI checks pass. Live OIDC/database acceptance and other worker/Gateway/RLS paths remain open. |
| Tenant preflight: [`collect_inventory`](../../services/mobile/tenant_preflight.py) | Requires a separate `KOKONUT_TENANT_PREFLIGHT_DSN`, pins `search_path`, and starts a read-only repeatable-read transaction before querying. It verifies a direct `kokonut_tenant_preflight` login with no memberships, public-table DML/ownership, or object-creation rights, emits only aggregate/opaque references, and evaluates the configured runtime login separately. | Source and synthetic PostgreSQL enforcement pass. The isolated role/password still needs deployment provisioning and operator authorization; do not pass its DSN to app/worker containers. The role's `BYPASSRLS` setting must match whether any inventory relation has RLS enabled, or the CLI refuses to run to avoid silently filtered counts. |
| Directus and database views | The optional Kernel profile now uses a dedicated DML-only `kokonut_directus_runtime` identity. Fresh-volume Compose acceptance verifies owner bootstrap, runtime health/login, and that Directus connects as that role; disposable PostgreSQL role checks cover DML, DDL/ownership denial, future-object grants, stale ACL removal, and database isolation ([role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json); [profile evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)). This does not verify the archived service identity, view behavior, collection/field/row parity, or schedules. Migration 139 also defines legacy mobile sync/device views. | Not ready. Inspect view ownership/invoker behavior, hooks, saved queries, and every consumer in a matching isolated Directus runtime before choosing RLS policies or retirement scope. Keep the optional Kernel profile bound to a dedicated PostgreSQL instance because its bootstrap revokes `PUBLIC CONNECT` instance-wide. |
| Recovery fixtures and ordered migrations | Recovery fixture SQL inserts devices into isolated scratch databases. Migration 391 adds owner-binding triggers and indexes; 392 adds credential functions; 393 signs mobile context; 394 signs OIDC operator context and adds dormant definer-role RLS policies; 395 isolates operator sessions behind bounded functions and a dedicated auth login; 396 verifies Gateway credential scope for tenant-bound mobile writes; 397 adds the location-level WorldClim key/view path; 398 bounds device revocation; 399 restores runtime security-schema lookup on DB-only restore; 400 restores restricted function-owner roles, exact SECURITY DEFINER ownership, and narrow grants after role/ACL loss; 401 adds dynamic retention and audited legal holds; 402 adds optional owner-defined retention scope codes; 403 adds the informational KGP governance target-policy projection. None enables application-table RLS. | Migrations 391–432 are applied on the local candidate after checkpoint and isolated restore rehearsal; no migration enables application-table RLS. The exact pre-400 encrypted checkpoint was restored into an internal-only template0 clone, migration 400 replayed, and runtime/operator-auth role bootstrap accepted. That candidate archive restored 1,010 public tables but had zero public location rows, so this is database/role recovery evidence, not farm-data parity. The separate synthetic owner/ACL-loss forced-RLS acceptance passed. The fresh 401/402 rollout then reported 393 applied schema migrations, zero pending, health 200, anonymous protected route 401, zero policy/hold rows, and RLS off; the app was not recreated. Migration 403 was then applied after a fresh checkpoint and isolated restore; the governance policy table is empty, the app was not recreated, and RLS remains disabled ([migration-403 rollout](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json)). Keep fixtures and migration execution on explicit maintenance credentials. Candidate 391 evidence: [rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json); 392–397 rollout: [checkpoint and candidate evidence](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json); 398–399 evidence: [checkpoint, forced-RLS acceptance and candidate rollout](builds/2026-10-14-recovery/candidate-migration-398-399-device-revocation.json); migration 400 evidence: [owner/ACL repair and candidate rollout](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json); exact pre-400 restore: [database/role recovery](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json); 401–402 evidence: [candidate retention rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json). Disposable migration 392–393 evidence: [mobile acceptance](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json); migration 394 evidence: [operator acceptance](builds/2026-10-14-recovery/operator-tenant-context-disposable.json); migrations 395–396 evidence: [runtime-role acceptance](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json); migration 396 evidence: [Gateway acceptance](builds/2026-10-14-recovery/gateway-tenant-context-disposable.json). |

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
remaining Gateway and worker paths, Directus/views, and application RLS remain
unresolved. Keep the database role and credential boundaries closed until the
remaining paths are covered.
Resolve these database role and credential boundaries before enabling RLS.
See PostgreSQL’s
[custom options](https://www.postgresql.org/docs/current/runtime-config-custom.html)
and [configuration-setting functions](https://www.postgresql.org/docs/current/config-setting.html).

## Worker execution and database identity trace — 17 October 2026

The supported execution allowlist is a code-execution boundary only. A mapped
worker subprocess can receive its dedicated identity, and individual worker
implementations establish their signed context; the allowlist itself does not
bind every scheduled module or event handler to a database role or tenant.

- In the standard Kernel profile, `services.core.runtime` starts the scheduler
  and event worker as child processes. The scheduler and EventBus control
  processes use the configured runtime identity. The supervisor supplies only
  the exact worker-secret keys needed by those control processes.
- `services.scheduler.engine.SchedulerEngine._execute_task` validates the
  configured module and command arguments, then checks the exact module against
  the source-controlled scheduled-worker map. Mapped children receive only
  their named DSN/credential and configured provider key; shared PostgreSQL
  identity variables and global geospatial provider secrets are removed.
  Unmapped legacy commands retain the shared runtime identity and receive no
  dedicated worker secrets.
- `services.events.bus.EventBus._invoke_handler` starts each allowlisted
  handler in a spawned process. Exact module/function mappings select the
  child identity; mapped children receive only their dedicated secrets and have
  shared PostgreSQL and global geospatial credentials filtered. Unmapped legacy
  children receive no dedicated worker secrets and retain their historical
  application environment. Notification enqueue has its own worker identity;
  provider delivery remains a separate outbox operation.
- The legacy worker overlay and portability worker remain legacy execution
  paths. The Kernel scheduler and EventBus control plane still use the shared
  runtime identity. Exact mapped children receive only their named worker
  identities; unmapped legacy handlers retain their current environment.
- Dedicated default-off integrations now exist for sensor anomaly, optional
  cache invalidation, notification enqueue, weather, weather forecast, NOI
  snapshot, market data, climate, sensor ingestion, and remote sensing. Their
  credentials/grants are not provisioned for live use, and their feature gates
  remain disabled until rollout and owner/provider prerequisites are satisfied.
- The four cache invalidation handlers now require and canonicalize a valid
  location UUID before selecting the cache adapter. Missing/malformed scope
  fails before provider construction, preventing an event from becoming an
  all-location invalidation. The durable bus records the handler failure and
  applies its existing bounded retry/dead-letter policy. This narrows one
  worker side effect. When signed cache invalidation is enabled, migrations
  415–416 and the handler adapter establish `computation_cache/invalidate`
  context through the dedicated `cache_invalidation` identity. Migrations
  415–416 are applied on the candidate, but the feature remains off and no
  credential/grant is provisioned.

The [worker operation map](worker-operation-map.md) now covers all 24
allowlisted scheduled modules and seven event-handler pairs, including their
source-visible data objects, source scope, external effects, and replay notes.
`tests/test_worker_operation_map.py` ensures the inventory matches both
executable allowlists and every entry has source references. The refreshed
graph covers 31 operation roots across 93 source files, with 632 function
memberships, 862 direct-call edges, and 20 dynamic-dispatch edges. Its SQL map
has 322 sites; 249 unique sites have static operation paths and 73 lack a
resolved function path. The boundary preflight remains `review_required`, with
identity/RLS readiness not established. These are source-navigation aids, not
an authorization inventory or grant list. Transitive effects and database-stored
command arguments still require review. The
new module-specific command schemas bound supported scheduler argv before
activation and dispatch, but do not establish tenant scope or worker grants;
the map must not be used as a worker grant list.

Therefore, the current allowlists protect against arbitrary module/function
dispatch but do not make worker SQL safe under application RLS. Do not assign a
single inferred tenant to a cross-location batch job, and do not enable RLS or
remove runtime grants on this evidence. The current source-level effect inventory now
records 36 candidate process, filesystem, HTTP, email, EVM, and dynamic-import
sites across 46 operation/site memberships and 31 roots
([inventory](worker-effect-inventory.json)).
It can overcount mutually exclusive CLI branches in other workers and miss
effects behind callbacks or provider adapters. The scheduled credit adjustment
path is now a separate read-only entrypoint, and its graph excludes the
interactive retirement/chain-sync code. The function graph does not follow
EventBus's `subprocess.Popen` request into the child. The separate effect
inventory traces `handler_runner`, its worker-secret filter, resolver,
allowlist validation, dynamic import, and all seven source-allowlisted handler
pairs. Persisted handler configuration and runtime dispatch remain unverified.
The actuation helper reachable from a worker only records an approval-gated
command; it does not publish MQTT. The function graph now follows callbacks
passed through the shared CLI `run(main)` wrapper. Remaining code-only work is
to reconcile each candidate against its exact scheduler command contract,
inspect dynamic/provider callbacks and transitive effect wrappers, then
reconcile persisted task rows with those contracts. The
The source-only JobSpec inventory now identifies eight accepted no-input templates,
six validated required-location inputs (anomaly, weather, climate, metrics,
credit adjustment, and remote sensing), and one missing sensor source contract. Native scheduled metric
computation uses `--compute --all --location-id` and rejects the old global
`--all-locations` command. Optional Prefect adapters preserve multi-location
behavior by querying active locations directly assigned to the
owner-confirmed `kokonut-network` organization and dispatching one location at a
time; climate and remote sensing use the same selector. Remote-sensing list,
create, job lookup, due-job claim, and provider dispatch now require the same
explicit location and reject cross-location job IDs before provider work. The
location filter is code-level scope only, not signed worker context or database
authorization. No persisted tasks or
external Prefect state were inspected. Remote sensing remains bounded to
sequential `--run-jobs --limit` batches of 1–10 and ClickHouse projection to one
bounded run-once operation ([inventory](worker-job-contract-inventory.json);
[schedule policy](schedule-ownership-inventory.md)). A
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
   schema migrations 392–432 have been rolled out but do not enable RLS.
   Keep RLS disabled if any access path or consumer remains unknown.

This audit combines source review, isolated migration-392–432
acceptance, candidate schema rollout through 432, and PostgreSQL 16 runtime-role
credential-grant checks. It does not claim Directus parity, live worker credential/grant provisioning,
a shared-organization API-key affiliation, a final app-table role allowlist,
database-role hardening across consumers, an RLS migration, or live candidate
RLS acceptance. See [runtime mobile role evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json).
