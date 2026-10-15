# Code-first refactor execution plan

**Updated:** 14 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68
**Latest pushed head:** `f8d90ea0b6af817e91db6758ff293d3c309f29de`
**Latest pushed head status:** Security #42 passed; CI #318 is in progress.

This plan orders the remaining work so repository changes and reproducible
software checks happen before decisions that require production owners, live
provider accounts, populated reference data, or external infrastructure. It is
an execution map for the existing open items in [batches.md](batches.md), not a
second capability acceptance ledger. Keep the capability matrix's named
MAN-CAP checks open until each has its own retained evidence.

## Current accounting

- The execution checklist has 328 checked and 20 open items (348 total).
- The latest pushed implementation is `f8d90ea`. Security #42 passed; CI #318
  is in progress on that head. The earlier Security #39 SHA-256
  false-positive fix is included and passes both local full-history Gitleaks
  and hosted Security #41.
- The pushed head includes the Directus preflight, supervisor, ClickHouse and
  notification outbox CLI regressions, and a nine-check disposable PostgreSQL
  ClickHouse fixture. Focused unit/runtime checks and full-history Gitleaks pass;
  CI #317 and Security #41 are green.
- The latest pushed batch adds provider-aware PostgreSQL-only backup/restore,
  gRPC streaming-auth lifecycle fixes, and focused RPC policy and
  optional-provider inventories. Earlier pushed work retires the unscoped
  legacy mobile-offline CLI, tenant-binds protected Data Stream creation, and
  rejects unscoped cache invalidation from event handlers. A separate reporting
  slice now runs opt-in saved SQL through
  an ACL-verified, read-only reader role. The worker operation inventory covers
  every current scheduled/event allowlist entry. Module-specific scheduler
  argument contracts now fail closed at activation and dispatch; a static local
  import closure now covers each allowlisted operation, and a direct-SQL
  inventory identifies 196 execution sites (30 composed/variable and three
  with unknown statement kind after conservative local-prefix inference). The dynamic sites have source-pattern review;
  `query()`/`query_one()` have no direct operation callers, and the only direct
  `DatabaseConnection.execute()` call is the literal metrics reconciliation
  query. The worker graph now connects 31 executed/allowlisted entry functions
  to 341 function memberships across the same 17 operations, with 483 direct
  calls and 20 explicit metric-registry dispatches. A companion report links
  175 of 196 SQL sites to a static operation path; the remaining 21 belong to
  functions absent from all current worker-root graphs and are not labeled dead
  code. Other dynamic dispatch,
  callbacks, external calls, enabled legacy rows, and worker identity/context
  remain open.
  The metrics entry now references all 20 registered calculator modules with a
  registry-parity test and records direct query tables and composed calculator
  calls. The freshness operation's seven source tables are also tied to its
  fixed query map; broader helper/provider effects and worker identity remain
  open.
  Data-freshness queries use fixed table/timestamp maps, bind location values,
  and report unknown configured sources as errors; 29 focused source tests pass.
  A new whole-services SQL inventory records 3,747 direct execution sites
  across 802 Python modules and 1,028 regex-derived relation-name candidates,
  without storing SQL text or runtime values. It safely unwraps literal
  SQLAlchemy `text()` and psycopg `SQL()` query wrappers; 92 statement kinds
  remain unknown. Its 67 package summaries isolate the largest service
  surfaces and dynamic-heavy modules. This is a review input, not a grant
  allowlist; dynamic statements and indirect ORM/provider paths remain open
  ([inventory](runtime-sql-inventory.json); [check record](builds/2026-10-14-recovery/runtime-sql-inventory-check.json)).
  Field Collector device revocation now uses a fixed database function that
  revalidates tenant, location, and exact credential/session scope before
  clearing a device token. Runtime direct UPDATE is limited to telemetry
  columns. The role bootstrap repairs private-function ACLs after DB-only
  restore. Migration 400 restores six restricted function-owner roles, their
  narrow privileges, SECURITY DEFINER ownership, and runtime/operator-auth
  schema access. A restored pre-398 clone replayed migrations 398–400; synthetic
  owner/ACL-loss forced-RLS acceptance passed. The exact pre-400 checkpoint is
  now restore-rehearsed, migration 400 replayed, and runtime/operator-auth role
  bootstrap accepted on the exact restored database clone. That archive had
  1,010 public tables but zero public location rows, so farm-data parity remains
  open. The candidate has 391
  applied schemas through 400 and its app is healthy, but still uses the
  `kokonut` superuser because candidate runtime credentials are absent;
  authenticated HTTP under that role remains an owner-input gate ([rollout evidence](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json); [restore evidence](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json)).
  The climate compatibility path stores schema-aligned `latitude_proxy_v1`
  estimates; migrations 392–397 passed ordered PostgreSQL 16 application and
  replay on a restored candidate checkpoint, including migration 397's
  location fallback and duplicate rollback. A clean `template0` bootstrap of
  all 388 schema sources also passed. The candidate later advanced through
  migrations 398–400 after encrypted checkpoints and restore rehearsal; its
  current state is 391 applied schemas through 400, one curated seed, zero
  pending migrations, and application-table RLS remains disabled.
  The registered native and Field Collector API routes now have an exact
  resource/action/public-policy inventory and unknown route/method cases are
  verified protected; broader tenant, OIDC, transport, and SDK parity remain.
  The disabled gRPC adapter now has focused coverage proving `serve()` and
  health checks fail before importing optional gRPC packages or the server;
  a source inventory pins all 55 application RPC methods to their handlers and
  scopes, with scope checks before database access. An enabled loopback test
  now starts the registered health, Ecocredit, and Data services, exercises
  API-key and scope allow/deny decisions, and checks generated-message names
  across both handlers. The five focused gRPC suites pass 37 tests. TLS, live
  database, tenant, and native Gateway parity remain open. Streaming RPC auth
  context now resets before each yielded response and on cancellation/errors, covered in all
  handler cardinalities by the focused gRPC suite. Encrypted checkpoints now
  support a PostgreSQL-only profile, record provider inclusion, and preflight
  required services before writing/restoring data; fake-Compose checks cover
  both ClickHouse-disabled and ClickHouse-enabled paths.
  Focused source/disposable checks pass. The latest pushed head `f8d90ea` has
  Security #42 passed and CI #318 in progress. The local event-cleanup
  retention-safety commit and the new scoped Field Collector operator
  inventory are not pushed yet.
- The capability matrix has 66 capabilities: 56 baseline-retained, 7 partial,
  and 3 prepared. None of the 66 named MAN-CAP checks is accepted.
- Candidate migrations 392–400 were applied schema-only after encrypted
  checkpoints and isolated restore/replay work. The current candidate has 391
  applied schemas through 400, one curated seed, zero pending/failed schema
  migrations, and no application-table RLS. The exact pre-400 checkpoint is
  retained and restore-rehearsed in an isolated clone; it contained zero
  public location rows, so farm-data parity remains open. The candidate app was
  not recreated for migration 400; health remains 200 and anonymous protected
  device revocation returns 401. See [migration 400 evidence](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json) and [restore evidence](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json).
  The separate 30-seed candidate rollout remains approval-gated under OFU-17;
  the other 90 sources were not selected.
- Seeded demo ownership for Kokonut Adelphi and Kokonut Genesis is already
  confirmed as exclusive to Kokonut Network. Do not ask for that mapping again.
- There is no Raspberry Pi available. The code-only ARM64 assessment passed
  Buildx/QEMU build, constrained-container startup, bootstrap, restore,
  migration, health, and restart checks. Physical performance, thermal,
  storage, power-loss, network, and on-device restart behavior remain
  unverified; no hardware result is claimed.

## Selected open gates: code batches before owner inputs

The owner selected the remaining open items in `batches.md` on 14 October.
Work through these code batches first; keep the named human/runtime gates open
until the relevant inputs or authorization arrive.

| Batch | Selected checklist items | Code work to complete first | Owner or external gate held open |
|---|---|---|---|
| API and transport parity | 1, 12, 14 | Finish REST/gRPC method and error parity, authenticated CORS, SDK contract coverage, and synthetic auth/scope checks. The enabled gRPC loopback slice now registers both generated services and exercises key/scope decisions. | Real OIDC, trusted HTTPS certificate, Directus runtime identity/schema, tenant-specific parity, and release authorization. |
| Tenant and database boundaries | 9, 12 | Extend transaction-bound tenant context across remaining Gateway routes and worker jobs; audit direct SQL and direct-database role access; add synthetic owner/share and denial checks. | Confirm non-demo ownership and legacy operator affiliations; provision runtime identities before enabling RLS. |
| Recovery and delivery | 1, 4, 6 | Continue provider-off/failure, lease reclaim, retry/idempotency, duplicate prevention, process outage, and rollback checks with fake endpoints or disposable databases. | Production provider state, external delivery destination, schedule/operator inventory, alert/on-call owner, and a 24-hour run window. |
| Reports and dashboards | 1, 5, 6, 10 | Finish repository-owned query safety and synthetic fixture parity; inventory consumers and document safe migration boundaries. | Accountable owners must choose retained reports, audiences/measures, populated reference fixtures, and external database roles. |
| Field Collector | 11, 13 | Expand isolated browser/API checks for retired forms, consent, queue behavior, and cleanup; retain the mocked-offline limitations. | Real OIDC credentials/test identities, trusted HTTPS browser origin, and human disposition/retention decisions. |
| Deployment and cutover | 1, 7, 15, 16 | Keep ARM64 code assessment and local profile/route checks current; add deterministic restart/failover tests where they can run without production. | Physical power/device behavior, certificate trust, replica/public ingress topology, 24-hour availability/resource budget, production schedule owners, and reviewed cutover authorization. |
| Curated seed write | 8 | Prepare a fresh encrypted migration-400 checkpoint and restore rehearsal procedure; verify the exact 30-file allowlist and rollback command. | Applying the selected seeds is a separate candidate data write and remains gated for explicit approval after the fresh checkpoint/rehearsal. |
| Retention policy | 2 | Keep the existing no-prune behavior and test that pending/retryable/undisposed records remain protected. | Jurisdiction/product owner must set terminal notification, attempt, and operator-audit retention/archival periods. |

## Work order

### Batch A — Close the current CI result

**Purpose:** establish the exact baseline for further local work.

**Repository surface:** `.github/workflows/ci.yml`, `scripts/run-github-ci.sh`,
and the focused test named in any failure log.

**Action:** Current pushed head `f8d90ea0b6af817e91db6758ff293d3c309f29de`
has Security #42 passed and CI #318 in progress. The gRPC loopback fix, outbox CLI and disposable PostgreSQL
acceptance are included in that batch. The Gitleaks
allowlist fix for the earlier Security #39 SHA-256 source-digest false positive
is included in the pushed head and Security #41 passes. The CI #307 OIDC Compose fixture failure was fixed earlier by
supplying the test-only operator-auth password before checking the missing
issuer configuration.

**Acceptance:** current pushed head `f8d90ea` has Security #42 passed; CI #318 is in progress.
The focused local outbox checks pass and are included in that batch.

### Batch B — Finish software tenant boundaries before considering RLS

**Purpose:** make every supported caller establish verified tenant context
before protected reads and writes, and make direct database access fail closed.

**Likely code surface:**

- `services/gateway/` authentication, route dependencies, and tenant context;
- `services/scheduler/`, event workers, and job handlers that access tenant
  data directly;
- `services/analytics/mobile_offline.py` and other legacy CLI entry points;
- `services/mobile/` and Gateway API-key/mobile credential paths;
- `services/migration/`, `scripts/check-*disposable.py`, and the runtime-role
  bootstrap for privilege boundaries;
- `tests/test_gateway_auth.py`, `tests/test_mobile_api.py`, tenant-context,
  worker, CLI, and migration tests.

**Code tasks:**

1. **Complete for tenant-bound mobile-device writes and the Data Stream
   create route:** migration 396 verifies
   API-key and capability-token activity, expiry/revocation, exact
   resource/action/location scope, and current location ownership before
   signing context for that transaction. Scope denial clears prior context;
   credential and owner rows stay locked until transaction end. API keys with
   wildcard or location-free scopes fail closed. The runtime role can read only
   reviewed authentication columns and cannot manage API keys. Focused Gateway,
   mobile, tenant-context, and role tests plus isolated forced-RLS acceptance
   pass. The Data Stream route now uses the same DB-verified transaction
   context before its draft INSERT, and uses the database-derived actor UUID.
   Its isolated forced-RLS probe verifies matching owner/location/actor writes
   and cross-location denial. This source-only slice does not cover other
   Gateway routes, shared organization affiliation for API keys, candidate
   credential provisioning, or application RLS.
2. Trace each worker and legacy CLI query to its service identity and tenant
   context. **Partial:** `services.analytics.mobile_offline` helpers and CLI
   commands now fail before database access because there is no authenticated
   tenant identity, and no repository runtime caller depends on them. Equivalent
   capture/sync uses the consent-aware Gateway. Continue the same trace across
   workers and other CLIs; give workers only required database functions and
   columns, and reject unscoped paths before mutation. Allowlisted cache event
   handlers now require a valid location UUID before invalidating entries,
   preventing malformed events from triggering a global cache flush. The
   [worker operation map](worker-operation-map.md) inventories all 12 scheduled
   modules and five event-handler pairs, with a test guarding allowlist parity.
   It records source-visible effects and known replay boundaries; transitive
   service/provider calls and existing persisted schedule reconciliation remain
   open. New module-specific operation schemas validate values and option
   combinations at activation, run-now, generated job plans, and subprocess
   dispatch; they reject human-review actions, unsafe cleanup, unbounded event
   loops and recurring sensor ingestion without a source. Scheduler and event
   allowlists still inherit the shared runtime environment; they are not
   DB-identity or RLS boundaries. The broader code trace is recorded in
   [the tenant call-site audit](mobile-tenant-rls-callsite-audit.md). A new
   location-scoped OIDC operations overview supplies device inventory and
   aggregate queue counts only when both `mobile_device:read` and
   `mobile_collection_review:read` apply. Its query sets signed tenant context
   and repeats both grant checks; focused service, route, and console checks
   pass. Live OIDC/database acceptance remains open.
3. Complete runtime-role restrictions for remaining public tables and verify
   existing handlers still work through their narrow grants/functions.
   **Partial:** the opt-in bootstrap still grants broad DML on existing public
   tables outside reviewed exceptions, but it now revokes both global and
   `public`-schema default privileges for future tables and sequences. The
   disposable PostgreSQL 16 role acceptance still passed current-handler SQL
   and proved a table/sequence created after provisioning is inaccessible to
   the runtime login. A new whole-services SQL inventory covers all 802 Python
   service modules and identifies direct execution sites and candidate relation
   names without becoming an ACL. Literal query wrappers are unwrapped while
   parameter values remain unobserved; the report now has 92 unknown statement
   kinds, 22 `WITH` statements, 305 sites without relation candidates, and 436
   non-literal sites. The next review classifies API, worker, CLI, and
   indirect-query surfaces before deriving explicit grants; worker, Directus,
   and RLS boundaries remain open ([role evidence](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json); [SQL inventory](runtime-sql-inventory.json); [inventory check](builds/2026-10-14-recovery/runtime-sql-inventory-check.json)).
4. Add a machine-readable preflight that detects unbounded callers, unsafe
   grants, missing migration prerequisites, and pending tenant mappings without
  printing personal or secret values. **Partial:** the static-only worker
  preflight confirms all 17 allowlisted roots and imports, reports the shared
  runtime identity and 21 SQL functions outside current worker-root graphs,
  and keeps RLS blocked. The complementary aggregate tenant preflight now
  reports pending/current-source checksum drift counts, connected-role
  superuser/BYPASSRLS and public DML/RLS indicators, and enabled scheduler
  contract and known-unbounded-scope counts without returning identifiers, task
  names, or arguments. Four focused source tests plus six existing tenant
  preflight tests pass (10 total). A separate disposable PostgreSQL 16 run
  exercised the actual catalog queries with synthetic rows on a no-egress,
  internal-only Docker network: 388 schema sources, two matched ledger rows,
  one checksum drift, one removed source, a pending migration count, an
  RLS-disabled DML table, an owned table without FORCE RLS, and valid/rejected
  scheduled commands. Output-leak assertions passed and the database/network
  were removed. Neither candidate nor legacy data was touched and no migration
  was applied. The output also encodes that a dedicated read-only preflight role
  is required before the CLI runs after RLS. These reports do not prove worker
  isolation. Owner mapping, remaining runtime role restriction, active-schedule
  reconciliation, and complete worker context remain open
  ([static report](worker-boundary-preflight.json); [source evidence](builds/2026-10-14-recovery/tenant-database-readiness-check.json); [PostgreSQL evidence](builds/2026-10-14-recovery/tenant-database-readiness-postgres.json); [test evidence](builds/2026-10-14-recovery/worker-boundary-preflight-check.json)).
5. Keep application RLS disabled until all code paths and data ownership inputs
   pass. Isolated forced-RLS fixtures can prove policy behavior; they do not
   authorize turning it on in the candidate or a populated deployment.

**Acceptance:** disposable PostgreSQL tests cover owner/shared scope, denial,
revocation, stale context, cleanup, least-privilege grants, worker/CLI behavior,
and migration replay. The candidate rollout of migrations 392–400 and the
populated pre-400 restore/runtime-role replay are complete; worker, remaining
runtime-role, Directus/view, ownership, and RLS gates remain open.
Non-demo location owners and legacy OIDC affiliations are human inputs under
OFU-01/02; use only the already-confirmed Kokonut Network demo mapping in
synthetic tests.

### Batch C — Close the API and client contract gaps

**Purpose:** demonstrate that native Gateway, optional transports, and SDKs
enforce the same authorization and payload contract.

**Likely code surface:** `services/gateway/router.py`, `services/gateway/app.py`,
`services/grpc/`, `proto/`, `sdk/python/`, `sdk/javascript/`, generated OpenAPI
artifacts, and their tests under `tests/` and each SDK package.

**Code tasks:** exercise public and protected route parity, method/action
policies, tenant scopes, response models, error envelopes, pagination, payload
limits, and bounded shutdown across REST and gRPC. Expand the existing fake
adapter parity checks to remaining supported methods, including streaming
authorization where applicable. Preserve gRPC as an optional transport and
make a disabled-provider response explicit.

**Acceptance:** offline SDK tests plus ASGI/disposable-database checks show the
same allow/deny decisions, schema, and error behavior across each supported
transport. Live identity-provider login and delivery of enrollment codes stay
under OFU-07 and OFU-10.

**Progress:** the five generated native v1 reads now have durable Python and
TypeScript fake-transport regression tests for method/path parity, encoded path
segments, API-key/accept headers, typed payloads, and normalized failure cases.
Those checks passed offline. Gateway route/auth and tenant-scope parity remain
open; see the [acceptance record](builds/2026-10-14-recovery/sdk-public-api-parity.json).
The gRPC adapter now also has focused tests for the disabled-provider boundary:
both server startup and health checks return the explicit disabled error before
loading optional gRPC dependencies. This does not establish enabled transport
parity or runtime acceptance ([evidence](builds/2026-10-14-recovery/grpc-disabled-provider-import-boundary.json)).
The two gRPC service protos now have a source inventory pinning 55 RPC methods
to their handlers and exact resource/action scopes. Every protected handler
checks scope before acquiring a DB connection; the one public content-hash
helper is confirmed DB-free. This source check does not establish API-key,
tenant, streaming, TLS, or native Gateway parity
([evidence](builds/2026-10-14-recovery/grpc-rpc-policy-inventory.json)).
The interceptor also had a streaming context leak: `ContextVar` identity stayed
set in the caller after a response yielded. The wrapper now scopes identity to
generator creation/advancement and cleanup, resets before returning control to
gRPC, and closes canceled iterators under the authenticated context. The five
new lifecycle regressions and existing gRPC tests pass (33 total)
([evidence](builds/2026-10-14-recovery/grpc-auth-context-lifecycle.json)).
The native and Field Collector routers now also have a pinned full method/path
policy inventory. A 27-test focused Gateway run confirms exact resource/action/
public policy coverage, 401 for every registered private route when anonymous,
and 401 for unknown routes, wrong methods, and near-miss paths ([route inventory evidence](builds/2026-10-14-recovery/gateway-route-policy-inventory.json)).
The OIDC operator router now has a separate exact inventory for all 29 registered
method/path policies, including scoped grants, secondary grants, public login
endpoints, and six governed farm-activity actions. Unknown operator paths and
method mismatches return 401 in the source test ([evidence](builds/2026-10-14-recovery/operator-route-policy-inventory.json)). The new location-scoped Field Collector overview requires both device-read and collection-review grants and returns no tokens or payloads; focused route, query, and console checks pass.
The operator console's cookie-authenticated draft edit now passes both its
credentialed CORS preflight and successful-response checks; PATCH was added to
the explicit CORS method allowlist. Browser/runtime ingress acceptance remains
open ([CORS evidence](builds/2026-10-14-recovery/gateway-cors-patch-preflight.json)).
The Directus parity fixture also checks its required identity-scope column
before creating synthetic users or activity rows. A missing
`directus_users.location_id` now returns a blocked precondition with no fixture
writes (three source checks and one fake-schema execution pass, with Ruff and
Python compilation). This
does not resolve whether Directus should use that legacy single-location field
or an explicit grant model; runtime read/write, field, hook, and schedule
parity remain open ([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)).
The enabled gRPC loopback acceptance also found and corrected service methods
that constructed service request/response messages from `types_pb2` instead of
`service_pb2`. All handler protobuf references now resolve against their
generated modules; a real ephemeral loopback call verifies API-key rejection,
scope denial before service DB acquisition, a correctly scoped response, and
the unauthenticated health exemption. This does not close TLS, real database,
tenant, or cross-transport parity ([evidence](builds/2026-10-14-recovery/grpc-enabled-loopback-transport.json)).

### Batch D — Complete code-verifiable capability slices and reporting

**Purpose:** move the 56 baseline rows through small, evidence-backed slices
without treating retained source code as migrated capability.

**Likely code surface:** domain modules named in
[capability-matrix.md](capability-matrix.md), `services/analytics/`,
`services/export/`, `services/data_stream/`, `services/credit_class/`,
`services/governance/`, `services/ingestion/`, `services/core/`, the native
Gateway, and scoped fixtures in `tests/`/`scripts/fixtures/`.

Work by domain family and keep each change narrow:

1. Core farm, agriculture, ecology, and process workflows (CAP-002–017).
2. Governance, finance, strategy, organization, and agent safety
   (CAP-018–038).
3. Ingestion, dMRV, Web3, reserves, markets, geospatial and interoperability
   (CAP-040–063).
4. Reporting, business model, State of Kokonut, and gRPC integration
   (CAP-064–066, plus CAP-001/007/031/039 where shared reporting is involved).

For each slice, identify the canonical data contract, optional provider
boundary, lifecycle/human-review boundary, minimum-dependency execution path,
and source tests before changing code. Add synthetic fixtures for behavior
that can be decided from the repository. Do not invent expected report
measures, audiences, owner scopes, or production semantics: those need the
report owners and reference data in OFU-04/14. Directus source and permission
contracts can be improved locally, but supported-version runtime-role parity
needs the disposable identity/schema fixture in OFU-09.

**Acceptance:** the slice's source tests pass and its contract/evidence path is
documented. The matrix remains `B`, `D`, or `P` until its named MAN-CAP
acceptance is completed with representative scoped data and retained output.

### Batch E — Native scheduler, providers, and recovery code

**Purpose:** finish the code-level replaceability and resilience checks before
production configuration is supplied.

**Likely code surface:** `services/core/jobs.py`, `services/scheduler/`,
`services/flows/`, `services/events/`, `services/analytics/backend.py`,
provider adapters under `services/core/`, `services/storage/`, Compose
profiles, and `scripts/fixtures/`.

**Code tasks:** complete synthetic parity for scheduler planning/dispatch,
leases, idempotency, retries and dead-letter operations; prove one-dispatcher
and duplicate prevention; exercise provider absent/disabled/failure paths;
cover backup/media restore and outbox behavior with fake endpoints and
disposable databases. Improve the report/query safety boundary for
repository-owned surfaces. The legacy saved-query runner remains disabled by
default; when explicitly enabled, a dedicated identity may read only the three
curated reporting views in a read-only transaction, while the application
identity updates refresh metadata. External/operator-edited queries, retained
dashboard selection, and tenant-scoped report parity remain open.

**Progress (14 October 2026):** the saved-query runner is isolated from the
application database connection, checks its live role attributes and ACLs,
uses statement/lock timeouts, counts results without fetching them, and refuses
to write stale refresh metadata if the saved SQL changed during execution. The
disposable PostgreSQL proof and focused checks are retained in
[`saved-reporting-reader-disposable.json`](builds/2026-10-14-recovery/saved-reporting-reader-disposable.json).

**Supervisor tests (14 October 2026):** four focused tests cover graceful
shutdown, signal escalation, unexpected clean child exit, and cleanup after a
partial launch. One POSIX integration case verifies SIGTERM reaches a child
and grandchild; database outage and lease recovery remain open
([evidence](builds/2026-10-14-recovery/kernel-supervisor-unit-contract.json)).

**Projection failure injection (14 October 2026):** ten unit tests cover the
ClickHouse outbox's disabled-provider, client-setup, partial-batch, completion,
fencing, and cleanup behavior. They mock both database and provider boundaries;
real lease recovery and process-level outage behavior remain open
([evidence](builds/2026-10-14-recovery/clickhouse-outbox-failure-injection.json)).

**Provider-aware recovery (14 October 2026):** encrypted Compose checkpoints now
declare their PostgreSQL and ClickHouse contents. PostgreSQL-only backup and
restore no longer require ClickHouse credentials or a running ClickHouse
service. When ClickHouse is selected, backup preflights it before creating
artifacts, and restore validates the manifest and required services before
restoring PostgreSQL; rollback runs the same read-only restore preflight before
stopping app services. Fake-Compose acceptance covers provider-off backup,
restore/preflight, enabled backup/restore, and missing-service fail-fast
([evidence](builds/2026-10-14-recovery/provider-aware-backup-restore.json)).

**Migration replay (14 October 2026):** ordered migrations 392–397 and the
runner's no-op replay passed on a restored, age-encrypted candidate checkpoint
using PostgreSQL 16.4. The same 388 current schema sources also passed from an
empty PostgreSQL database in a separate internal-only Compose project. The
candidate then received migrations 392–397 through the ordered schema-only
runner after a fresh encrypted checkpoint and restore rehearsal. The app alone
was recreated; candidate health and anonymous route protection passed, and the
temporary restore project was removed. RLS stayed disabled and no seed SQL ran
([restore replay](builds/2026-10-14-recovery/candidate-migration-392-397-restored-replay.json); [clean bootstrap](builds/2026-10-14-recovery/clean-bootstrap-388-migrations.json); [candidate rollout](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json)).

**Acceptance:** deterministic isolated checks pass without external provider
credentials and preserve rollback evidence. Actual schedule inventory and
operators (OFU-16), alert destination/on-call owner (OFU-05), report retention
policy (OFU-03), R2 account/live objects (OFU-08), and production topology
(OFU-06) remain owner gates.

### Batch F — Code-only ARM64 and constrained-runtime assessment

**Purpose:** assess Raspberry Pi suitability from reproducible software
checks while clearly recording the physical limitation.

**Likely code surface:** `Dockerfile.kernel`, `docker-compose.yml`,
`docker-compose.*.yml`, `.github/workflows/ci.yml`,
`scripts/kernel-inventory.py`, `scripts/run-github-ci.sh`, migration/restore
scripts, and image/profile tests.

**Checks:** build the minimal and selected optional targets for ARM64 under
Buildx/QEMU; run container startup, migrations, health/readiness, backup and
restore in emulation; apply a 4 GB memory limit and representative CPU quotas
to software fixtures where practical; capture image/package inventories and
startup/resource measurements; test orderly restart and simulated process or
container loss. Keep PostgreSQL and optional stores private. Treat emulation
and cgroup limits as compatibility checks, not a hardware benchmark.

**Result (14 October 2026):** the minimal app and PostGIS images built and ran
as `linux/arm64`; all 386 schema migrations applied with zero failures; PostGIS
topology/raster functions were available; `/health` returned 200; a 4.9 MB
logical backup restored to a second database with matching SHA-256 migration
fingerprint and successful Kernel schema readiness; database restart and
simulated app-container loss recovered. Container limits were 1.5 GiB for
PostgreSQL and 1 GiB for the app, two CPUs each, with no host ports. The focused
Compose architecture contract passed. See the retained
[acceptance record](builds/2026-10-14-recovery/arm64-qemu-runtime-acceptance.json).

**Acceptance:** passed for the minimal app/PostGIS runtime under QEMU, with
emulator conditions, resource limits, migration and restore evidence recorded.
Actual Pi storage wear, thermals, power-loss behavior, physical network
reliability, and sustained device performance stay unverified until hardware is
available; no human input is needed for this code-only assessment.

### Batch G — Reconcile ledgers, then request only owner decisions

Update `batches.md`, `progress.md`, `capability-matrix.md`, the relevant
evidence records, and this plan after each batch. Keep raw checklist counts
separate from capability acceptance. Before production/candidate rollout,
present the owner only with unresolved inputs or separately gated writes.

## Owner-input gates after code work

These do not block the code-first batches above, but they block the associated
deployment or semantic acceptance:

- **Ownership and access:** residual location ownership and sharing
  (OFU-01; demo farms already confirmed), and operator-to-organization grants
  (OFU-02).
- **Governance and reporting:** retention/legal hold/disposition (OFU-03),
  retained report/dashboard owners and expected outputs (OFU-04), sanitized
  reference data (OFU-14), and Directus consumer/runtime fixture decisions
  (OFU-09/15).
- **Production operations:** alert destination/on-call (OFU-05), topology and
  cutover owner (OFU-06), active scheduler inventory/operators (OFU-16), and
  the 24-hour availability window (OFU-13).
- **Provider setup:** production OIDC inputs and test identities (OFU-07), R2
  bucket/credentials/policy (OFU-08), browser vault and trusted local HTTPS
  certificate when browser acceptance is scheduled (OFU-10/11).
- **Candidate-only writes:** approval to apply the 30 curated seeds (OFU-17).
  Migrations 392–400 are rolled out; runtime credential provisioning remains
  tracked under OFU-19. The candidate still has only its original curated seed
  ledger entry; no new seed SQL was applied.

There is no active Raspberry Pi request: OFU-12 records the completed code-only
scope and lack of hardware. If the owner later supplies a Pi, add a separate
physical acceptance record rather than revising emulation evidence.

## Push and release cadence

Keep related code changes in local commits and push in reviewable batches, as
requested. The latest push `f8d90ea` has Security #42 passed and CI #318
in progress. The pushed batch includes enabled gRPC loopback acceptance and
the earlier ClickHouse/notification CLI regressions with disposable
PostgreSQL outbox acceptance. The current local batch adds EventBus
dead-letter cleanup protection and the scoped Field Collector operator
inventory; focused local checks are passing.
Accumulate the next coherent
batch before pushing so the repository does not start CI for each
small commit. Never push directly to `main`. Keep each candidate database
rollout separately gated even when the corresponding migration and disposable
acceptance are complete.
