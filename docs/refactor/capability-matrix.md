# Capability preservation matrix

Frozen from README Core Capabilities at commit ad806f504bfef15cba41446d777cb22f6bd8fe6a.

Each row assigns a code/domain owner and a named manual acceptance check. Existing Python test names are verified source paths, not passing results. The domain registry and repository-inventory.json provide table, migration, route and service-group references. Broad owners require collection-level refinement before their implementation slice.

All 66 named MAN-CAP acceptance checks remain **not accepted**; implementation and deployment progress are tracked separately in the progress column. Some source, unit, disposable-database, and local-runtime checks have run and are recorded below, but none substitutes for a named capability acceptance unless its exact result is recorded. Execute each with a representative scoped fixture and retain outputs, identifiers, evidence links, and audit history before provider cutover. Chain write behavior is evaluated with local/mocked contracts; these checks do not authorize mainnet transactions. Contract capabilities also retain the existing Foundry suite in contracts/test/.

The six-column matrix is checked by `python3 scripts/check-capability-matrix.py`
and the fast-fail CI workflow. This verifies all 66 IDs, row shape, named manual
checks, status labels, and referenced source/test paths. It does not evaluate
capability behavior or mark any MAN-CAP check accepted.

The repository owner authorized ongoing focused test execution. Current
owner-only decisions and external acceptance inputs are listed in [Open Follow
Ups](open-follow-ups.md). Passing source tests do not close the named manual
acceptance rows.

**14 October 2026 Directus parity preflight (CAP-001 / CAP-047 / CAP-053):**
the disposable Directus parity fixture now stops before synthetic user or farm
activity writes when the historical `$CURRENT_USER.location_id` scope cannot
exist in the cloned `directus_users` schema. The owner later selected
organization/location grants as the Directus target model. Three source checks
and one fake-schema preflight execution pass, but this guard only avoids
unsafe/inapplicable fixture writes; it does not establish Directus permissions
or accept a named MAN-CAP check
([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)).

**15 October 2026 Directus extension host contract (CAP-001 / CAP-047 / CAP-053):**
the hook package now declares compatibility with the exact pinned Directus
12.1.1 image, enforced by a source regression check. Collection listeners now
use the documented `collection.items.create` / `collection.items.update`
event names; a registration test invokes the extension and checks all
registered item events. The 54-test extension suite and TypeScript build pass.
This is source evidence only; runtime hook dispatch, organization/location
authorization, and named MAN-CAP acceptance remain open. A fresh isolated
Directus 12.1.1 runtime loaded both discoverable extensions, returned the
Field Collector endpoint redirect, and rejected a malformed location create
with `400 INVALID_PAYLOAD` without inserting a row. Kokonut identity/grant and
full permission parity remain open
([host evidence](builds/2026-10-15-recovery/directus-extension-host-contract.json); [event evidence](builds/2026-10-15-recovery/directus-hook-event-registration.json); [runtime evidence](builds/2026-10-15-recovery/directus-extension-runtime.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 Directus principal/grant guard (CAP-001 / CAP-047 / CAP-053):**
the hook now resolves an authenticated Directus user's OIDC subject only under
the exact configured issuer, maps it to an enabled `operator_identity`, applies
the current organization-qualified collection/action/location grant to list
reads and returned read records plus each create, update, or delete target,
excludes legacy grants without organization scope, and rejects bulk partial
access and row moves. Focused
extension tests and the TypeScript build pass. This is source-level protection
only: the issuer/operator/grants are not provisioned, Directus role/field and
expanded-relation behavior is not yet accepted, the legacy Directus service
still uses the database superuser, and this does not establish signed tenant
context or RLS. MAN-CAP checks remain unaccepted
([unit evidence](builds/2026-10-15-recovery/directus-tenant-authorization-unit.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 Directus permission seed repair (CAP-001 / CAP-047 / CAP-053):**
the seed no longer depends on the nonexistent `directus_users.location_id`;
it removes only the obsolete filter and create validation, preserves other
business predicates, and aborts on an unexpected legacy shape. The grant hook
now covers all 11 tenant-scoped collections, including `revenue_event`. Five
focused Python checks, 61 extension tests, the TypeScript build, and a
network-disabled PostgreSQL 16 seed-repair/replay check pass. The isolated
Directus 12.1.1 API check confirms that the loaded hook allows an own-location
Field Note read and hides a cross-location row. It also confirms the Field
Worker's `farm_activity` read/create/update requests remain denied: those
stored rules include custom source filters, field limits, or lifecycle filters
that the unlicensed Directus API hides. Do not broaden them to get a passing
probe. Operational Directus use now requires either a valid custom-permission
license or routing operations through the Kokonut Gateway with Directus kept
optional. Role/field/relation parity and all named MAN-CAP checks remain
unaccepted ([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json); [inventory](directus-parity-inventory.md)).

**15 October 2026 optional Directus database identity (CAP-001 / CAP-047 / CAP-053):**
the candidate now has an opt-in Directus overlay with a loopback-only
`cli.js start` runtime, separate owner-backed metadata bootstrap, extension
mounts, and a DML-only `kokonut_directus_runtime` provisioner. It denies
database/schema ownership and DDL, limits the login to the dedicated candidate
database, and keeps Directus out of the default profiles. Focused role-input and
profile-planner checks pass. The role bootstrap revokes `PUBLIC CONNECT` across
its dedicated PostgreSQL instance, so it must not run on a shared/legacy
server. Seventeen focused role/planner tests and internal-only PostgreSQL
acceptance pass; a fresh-volume run through the actual Compose overlay also
passed owner bootstrap, runtime health, synthetic admin login, and runtime
database-identity checks. This closes a deployment identity gap only; Directus
API role/field/row/relation/hook parity remains open ([profile](kernel-directus-profile.md);
[role policy](optional-database-roles.md); [role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json); [profile evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)).

**15 October 2026 sensor source contract guard (CAP-040 / CAP-047):** the
sensor CLI now rejects absent, incomplete, or conflicting operation inputs
before loading database/SOPS configuration, and `--help` remains available
without secrets. The shared `sensors` scheduled command already rejects the
missing recurring source contract before launching the legacy no-op CLI. Sixty-
nine focused source/command checks and Ruff pass. No sensor provider or
schedule ran. This prevents false success but does not define a recurring
sensor source or accept MAN-CAP-040/047
([evidence](builds/2026-10-15-recovery/sensor-ingester-explicit-input-contract.json); [schedule inventory](schedule-ownership-inventory.md)).

**15 October 2026 shared dispatcher contract (CAP-040 / CAP-047):** focused
checks confirm each catalog operation uses its fixed interpreter, module,
arguments, and timeout, retains nonzero exit codes with diagnostics capped at
500 characters, requires climate location scope, and blocks recurring sensor
dispatch before process creation. Sixty-eight
dispatcher/command checks and Ruff pass with subprocesses substituted. The
runtime SQL inventory now covers 806 service source files. A follow-up worker
inventory refresh after dynamic-retention, projection, and remote-sensing
contracts now records 257 SQL sites across 20 roots, including four
event-retention queries. The source-only JobSpec inventory now distinguishes
10 accepted default argument lists, four validated per-schedule location
inputs for climate, weather, metrics, and credit adjustment, and the still-missing
recurring sensor source contract. External-provider operations remain limited to explicit
bounded contracts. No provider, database, Prefect server, or schedule was accessed
for this source refresh. Live retry/recovery, provider outcomes, and
MAN-CAP-040/047 remain
open ([dispatcher evidence](builds/2026-10-15-recovery/job-dispatch-contract.json);
[inventory evidence](builds/2026-10-15-recovery/sql-inventory-refresh.json)).

**16 October 2026 scheduler worker outage recovery (CAP-040 / CAP-047):** a
current-source disposable PostgreSQL stop/start check confirms the scheduler
worker remains alive through the connection outage and completes ticks before
and after recovery. The scheduler engine was stubbed, so the check does not
exercise task SQL, lease ownership/reclaim, provider delivery, or long-duration
recovery. No MAN-CAP status changed
([evidence](builds/2026-10-16-recovery/scheduler-worker-postgres-reconnect.json)).

**15 October 2026 ARM64 candidate profile (CAP-047):** the planner now selects
an isolated ARM64 app/PostGIS profile for minimal, edge, and standard; analytics
and optional service images remain blocked pending architecture verification.
Planner tests, merged Compose configuration, and a current-source QEMU runtime
pass. The ARM64 app/PostGIS images applied all 391 schemas through migration
400; a logical restore matched all migration fingerprints and had zero pending
schemas. Health returned 200, a protected write returned 401, and short
database/app restart checks recovered. `postgis_raster` was enabled manually in
the disposable database because the ordered schema does not currently install
it. Physical Pi performance is not claimed ([profile evidence](builds/2026-10-15-recovery/kernel-arm64-profile-config.json);
[runtime evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-400.json);
[deployment record](arm64-database.md)).

**16 October 2026 current-source ARM64 smoke (CAP-047):** Buildx exported the
default Kernel target for `linux/arm64` from the current source. The loaded
image reported ARM64 and its configured non-root user; runtime CLI help and
the image-manifest command passed in a network-disabled QEMU container. This
does not claim Raspberry Pi performance, power-loss, storage, or full service
acceptance ([evidence](builds/2026-10-16-recovery/kernel-arm64-qemu-smoke.json)).
The optional Kokonut OIDC application target also built and passed its
network-disabled CLI/manifest smoke on ARM64; this does not verify ZITADEL's
service images or the full identity profile
([evidence](builds/2026-10-16-recovery/kernel-arm64-oidc-smoke.json)).
The selected ZITADEL API/Login, identity PostgreSQL, and Caddy digest-pinned
defaults expose ARM64 manifests. The planner now composes their explicit ARM64
overlays and the merged profile config passes with synthetic, process-only
values. Live provider, login, secret, and browser acceptance remain open
([evidence](builds/2026-10-16-recovery/zitadel-arm64-profile.json)).

**16 October 2026 ARM64 optional transport smoke (CAP-047):** Buildx built the
gRPC and MQTT subscriber targets for `linux/arm64`; network-disabled QEMU runs
passed CLI help, generated gRPC stub imports, and the Paho MQTT import. The
pinned Mosquitto image exposes an ARM64 child and its broker binary reported
`aarch64`. Compose/planner checks confirm every selected gRPC/MQTT service is
configured for ARM64. No gRPC/PostgreSQL server, MQTT traffic, credentials, or
mTLS session was exercised. The ARM64 software image/profile path is now
prepared; live adapter behavior, physical Pi operation, and the named MAN-CAP
checks remain open ([evidence](builds/2026-10-16-recovery/kernel-arm64-transport-smokes.json)).

**15 October 2026 Kernel startup schema gate (CAP-047):** the default and OIDC
image commands and both standard-profile roles now require complete schema
readiness before spawning API or worker processes. A focused supervisor test
proves a readiness failure launches no child, and profile checks cover the
image/Compose commands. The isolated linux/arm64 QEMU replay confirmed zero
child starts against an empty ledger and API/scheduler/event startup after 393
schemas; health was 200, anonymous write was 401, and the app reached Docker
healthy under a 1 GiB/two-CPU limit. The disposable volume was removed. This
does not accept MAN-CAP-047 or physical Pi behavior
([evidence](builds/2026-10-15-recovery/kernel-schema-startup-guard.json)).

**15 October 2026 fake-provider route contract (CAP-001 / CAP-047 / CAP-053):**
six no-network tests cover OIDC login state handoff, callback rejection,
opaque session/CSRF cookie issuance, scope response, CSRF-gated logout, and
actual-adapter rejection of invalid issuer/subject claims before database access.
This pins route wiring and a pre-database claim guard only; Authlib/provider verification, identity/session SQL,
real grants, browser acceptance, and the named MAN-CAP checks remain open
([evidence](builds/2026-10-15-recovery/operator-oidc-provider-contract.json)).

**15 October 2026 self-hosted ZITADEL deployment contract (CAP-001 / CAP-047 /
CAP-053):** an opt-in Compose selection now combines the Gateway OIDC client,
HTTPS Caddy ingress, ZITADEL API and Login V2, and a dedicated PostgreSQL
service with a bounded non-superuser role. Compose/planner source checks pass
26 tests, and the database bootstrap was exercised against an isolated,
network-disabled PostgreSQL 17 container. No IdP container, secret, operator
identity, grant, or browser session was created; all three named MAN-CAP checks remain open
([profile](zitadel-provider.md); [evidence](builds/2026-10-15-recovery/zitadel-compose-profile.json)).

**15 October 2026 report CLI scope contract (CAP-001 / CAP-047):** bulk
generation across the 94-source report registry now requires an explicit
location or `--all`; ambiguous and conflicting selectors fail before opening a
database. Snapshot verification works without a report-generation type. Eleven
focused checks and Ruff pass without database/provider access. This closes a
CLI safety gap only: report output parity, report ownership, external consumer
authorization, and all named MAN-CAP checks remain open
([evidence](builds/2026-10-15-recovery/report-generator-cli-scope.json)).

**15 October 2026 event-retention gate (CAP-047):** completed-event pruning is
was disabled by default and required a caller-supplied positive retention
window. The later dynamic policy/hold implementation below removes that
caller-selected window and adds active-hold eligibility. The cleanup query
continues to protect undisposed dead letters and non-success durable handler
deliveries. One focused source-unit regression for the handler-delivery guard
passed; prior 34-test/Ruff evidence predates that SQL change
([focused evidence](builds/2026-10-15-recovery/event-retention-handler-delivery-guard.json)).
USA and Dominican Republic were selected as jurisdictions, but no category
schedule is configured, so cleanup remains disabled and this safety gate does
not authorize pruning or accept MAN-CAP-047
([evidence](builds/2026-10-15-recovery/event-retention-cleanup-gate.json)).

**15 October 2026 generic retention gate (CAP-051):** the separate
data-governance CLI blocks before opening PostgreSQL and its service fails
closed before creating a cursor unless
`KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT=true`; dry-run and help remain
available; new policies default to `auto_enforce=false`, and nonpositive or
noninteger windows and unsupported actions fail before database access. Forty-two
focused checks cover default denial, dry-run access, help, CLI connection
avoidance, legal-hold skip, and policy-input validation. No schedule, policy owner, or
entity-level hold model was inferred. The switch must remain off until those
controls are approved and implemented; MAN-CAP-051 remains open
([implementation](../../services/analytics/retention.py); [evidence](builds/2026-10-15-recovery/data-retention-enforcement-gate.json)).

**15 October 2026 dynamic retention policy and legal-hold model (CAP-047 / CAP-051):** migration 401 removes period defaults from policy/category reference data, permits an unset window, and demotes policies lacking explicit approval. New schedules are drafts; an operator must approve a positive configured window before activation, and auto-enforcement plus the independent feature flag remain separate gates. Record-level holds require an actor and reason, retain append-only placement/release history, and are checked by the generic sweeper and event cleanup. Event cleanup derives the window only from exactly one approved global `event_bus` / `platform_event` policy and fails closed on none or ambiguity. CLI actor and approver fields provide attribution but do not authenticate or authorize the caller. No period, policy, or hold has been configured. Migrations 401/402 are now applied on the candidate after an encrypted checkpoint and isolated restore/replay; the disposable migration/hold acceptance remains separate evidence. Notification/attempt/operator-audit pruning remains unimplemented. This prepares a dynamic policy path; it does not select legal periods or accept MAN-CAP-047/051. [Operations](retention-policy-operations.md)

**15 October 2026 worker reconnect contract (CAP-047):** scheduler ticks now
use fresh bounded-timeout PostgreSQL connections while keeping a stable worker
identity; two fault-injection tests prove that connection and tick failures do
not prevent a later tick from succeeding. The EventBus worker now recreates its
event bus and notification database connection for each iteration and retries
logged failures with a five-second connection timeout; 10 scheduler tests and
20 event-worker/EventBus tests pass,
with Ruff clean. The continuous KGP indexer now also opens a fresh bounded
connection for each scan cycle and survives rollback/failure-record errors in
its source loop; 14 focused KGP service/indexer tests pass with Ruff and
compilation. A stronger scheduler check replays migrations 116, 117, 164, 165,
337, and 371 and uses the real SchedulerEngine to claim and complete bounded
EventBus tasks before and after restart under one worker ID. The task used an
empty queue and no provider. A separate SchedulerEngine check kills the real
claimant after lease commit but before subprocess dispatch; after forced lease
expiry, a replacement worker records the first run failed and completes the
task as attempt two. This proves claim-to-dispatch recovery only. The EventBus
worker check replays migrations 116,
165, and 375, invokes the real allowlisted alert-notification handler, and
completes synthetic events before and after restart. A fake webhook bound to
`127.0.0.1` returns one synthetic `503`; the outbox records a failed attempt
and retryable row, then succeeds on retry with the same idempotency key. A
worker is also killed after the fake receiver gets a third notification but
before it can return the HTTP response. After fixture lease expiry, a
replacement reclaims the row; attempt status advances from `lease_lost` to
`succeeded`, with the same idempotency key. A second event is delivered after
the database restart with a distinct notification ID. No remote provider is
contacted. The KGP acceptance replays all 394 current ordered PostgreSQL
schema files, then uses the real `kgp_protocol_deployment`,
`kgp_indexer_cursor`, and migration-403 governance-policy table with synthetic
rows. The real indexer processes seven `GuildCreated`, `DomainCreated`,
`TaskCreated`, target/selector permission, and guild-scope policy logs and links
each state row to its source event. A repeated target permission event
confirms the latest value wins. Duplicate canonical replay creates no rows. A
simulated tip change orphans all seven events and removes their projections;
the stable local guild-key anchor and canonical replay rebuild the guild,
domain, task, and governance policy state on the replacement branch. The
governance table is informational; the smart contract remains authoritative
for execution. The worker stays alive through a PostgreSQL stop/start and
advances its lease heartbeat; after the worker is killed and its lease expires,
a replacement owner advances the heartbeat. Live RPC, seeds, and providers
are not used. This does not establish other event-type parity or live-chain
behavior. A separate fresh encrypted checkpoint and isolated restore rehearsal
then preceded candidate application of migration 403; the candidate now has 394
applied schemas and zero pending, but its app image was not rebuilt, the policy
table is empty, and application-table RLS remains off
([rollout evidence](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json)).
Production-duration lease/RPC/event processing, real-provider delivery,
scheduler recovery after task side effects, and long-duration acceptance remain
open.
MAN-CAP-047 is not
accepted
([scheduler unit evidence](builds/2026-10-15-recovery/scheduler-worker-connection-recovery.json); [stub-engine runtime evidence](builds/2026-10-16-recovery/scheduler-worker-postgres-reconnect.json); [real-engine runtime evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json); [event worker evidence](builds/2026-10-15-recovery/event-worker-connection-recovery.json); [EventBus runtime evidence](builds/2026-10-16-recovery/event-worker-postgres-reconnect.json); [KGP evidence](builds/2026-10-15-recovery/kgp-worker-connection-recovery.json); [KGP runtime evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json); [KGP crash-recovery script](../../scripts/check-kgp-worker-reconnect-disposable.py)).

**14 October 2026 supervisor contract (CAP-047):** four focused tests cover
graceful shutdown, process-group escalation, unexpected zero exit, and
partial-launch cleanup; one POSIX integration case verifies SIGTERM delivery
to a child and grandchild. Database-outage and lease-recovery acceptance remain
open, and MAN-CAP-047 is not accepted
([evidence](builds/2026-10-14-recovery/kernel-supervisor-unit-contract.json)).

**14 October 2026 projection delivery failures (CAP-007 / CAP-047):** twelve
focused unit tests cover optional-provider no-claim behavior, client setup and
outcome failures, partial batches, completion errors, stale fences, cleanup,
and one-shot CLI exit codes. A separate disposable-PostgreSQL fixture passes
nine checks, including durable retry/success state and actual CLI exit behavior;
it uses controlled ClickHouse outcomes and does not prove live-provider
interoperability or cross-store crash deduplication. This does not accept either
named MAN-CAP check ([unit evidence](builds/2026-10-14-recovery/clickhouse-outbox-failure-injection.json);
[PostgreSQL evidence](builds/2026-10-14-recovery/clickhouse-outbox-cli-disposable.json)).

**14 October 2026 notification delivery failure boundaries (CAP-047):** eight
focused mocked tests cover exception-class-only provider failure recording,
independent batch progress, completion database failure propagation, stale
lease accounting, SMTP idempotency headers/closure, and real CLI argument
parsing with failure/lease-loss exit codes. No real provider or database was
used; this does not accept MAN-CAP-047 or provider availability
([evidence](builds/2026-10-14-recovery/notification-outbox-failure-injection.json)).

**14 October 2026 runtime default-privilege boundary (CAP-047 / CAP-053):**
the opt-in runtime bootstrap now removes default table and sequence privileges
for future public objects while retaining existing-table behavior. The
disposable PostgreSQL 16 role check passed the existing handler and credential
checks and confirmed a post-provisioning synthetic table and its sequence are
inaccessible to the runtime login. Broad grants on existing public tables,
worker identity, and RLS remain open; this does not accept either MAN-CAP row
([evidence](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json)).

**14 October 2026 candidate schema rollout (CAP-047 / CAP-053):** migrations
392–397 were applied to the local candidate after a fresh encrypted checkpoint
and isolated restore rehearsal. This historical rollout had 388 applied schemas
through 397 and no application-table RLS. The later candidate state is recorded
below; implementation progress does not accept any named MAN-CAP check
([historical evidence](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json)).

The current runtime SQL inventory covers 3,799 direct execution sites across
807 service modules, includes summaries for 67 packages, and identifies 1,034
regex-derived relation-name candidates. Literal SQLAlchemy `text()` and
psycopg `SQL()` wrappers are unwrapped; 111 statement kinds, 23 `WITH`
statements, 335 sites without relation candidates, 456 non-literal sites, and
dynamic or indirect paths require review before narrowing runtime grants. The
report is not an ACL and does not accept a MAN-CAP check ([inventory](runtime-sql-inventory.json);
[latest evidence](builds/2026-10-16-recovery/runtime-sql-inventory-refresh.json);
[previous evidence](builds/2026-10-14-recovery/runtime-sql-inventory-check.json)).

**Last recorded GitHub status (CAP-001 / CAP-047 / CAP-053), checked 15 October:**
PR #68 is at `4ad4b06ed19629f1ec71c25c47ef78597fdf2322`. Security run
[#44](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38681693883)
passed on this head. CI #320
([run](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38681693999))
is in progress. This head adds reference-only seed scope, the selected
self-hosted ZITADEL provider contract, and code-first mapping of remaining
gates. The earlier Security #39 source-digest false positive was corrected
with a file-scoped allowlist; local full-history Gitleaks and hosted Security
#44 pass. The earlier
CI #307 OIDC fixture failure was corrected in `7953afe`; runs #308/#32 are
historical, not current-head coverage. The named MAN-CAP checks remain open.
See [the code-first execution plan](code-first-execution-plan.md) for the
remaining work order and the Raspberry Pi code-only assessment scope.

**14 October 2026 database restore/bootstrap (CAP-047 / CAP-053
implementation follow-up):** the exact encrypted pre-400 candidate checkpoint
was restored into an internal-only template0 clone, migration 400 was replayed
with zero pending/drift, and the runtime/operator-auth bootstrap passed its
repeatability, grant, denial, and synthetic DML checks. The archive had 1,010
public tables but zero public location rows; this proves database/role recovery
and not farm-data parity. The recovery volume is retained with its container
stopped. It does not provision candidate credentials, enable RLS, or accept
either named MAN-CAP check ([evidence](builds/2026-10-14-recovery/candidate-pre400-restore-runtime-role-acceptance.json)).

The preceding CI #304 on `8aa33e24f169f15afb249a53ae3d281ed8d843a2`
completed with five failures, 4,632 passed tests, and 75 passed subtests; its
local fix batch passed the focused regression, operator-auth, and Compose
checks. The approved eight-suite platform-integrity suite now passes 290 tests
on local commit `238e2ef` ([verification record](builds/2026-10-14-recovery/platform-integrity-290-tests.json));
the earlier 288-test record remains historical.

The focused reviewer-note service/auth slice also passed 14 service and three
route tests, including rollback/connection cleanup on tenant denial. Directus
parity, worker/direct-database isolation, RLS, and named manual acceptance
checks remain open; no full capability acceptance is implied.

**14 October 2026 Gateway mobile mutation context (CAP-053):** API-key and
capability enrollment/revocation handlers now require the authenticated
Gateway's internal `mobile_device` action/location marker, then establish
current-owner transaction context before the write. Owner lookup is locked in
the same transaction; missing/stale owner context fails before mutation. The
tenant-context, mobile API, and OIDC operator-auth suites passed 126 tests;
Ruff and Python compilation passed. This closes those application call paths,
not a database identity boundary: the ordinary app role can still set custom
PostgreSQL context values, so worker/direct-database isolation and RLS remain
open ([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/gateway-mobile-tenant-context.json)).

**14 October 2026 mobile credential lookup boundary (CAP-053):** the local
migration 392 source moves token-hash resolution and single-use enrollment
redemption behind narrow PostgreSQL functions owned by a dedicated
NOLOGIN/NOBYPASSRLS role. The existing owner-binding trigger now uses a fixed
search path and schema-qualified relations. A network-isolated PostgreSQL 16
acceptance passed direct-table denial, migration replay, current/legacy/unknown
token outcomes, enrollment conflict/expiry/single-use behavior, a concurrent
redemption race (exactly one device/code consumption), and owner transfer. The
56-test mobile API/tenant suite and Ruff pass. Migration 392 has
not been applied to the candidate; RLS and MAN-CAP-053 remain open
([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/mobile-credential-functions-disposable.json)).

**14 October 2026 signed mobile tenant context (CAP-053):** migration 393
replaces trust in caller-set mobile tenant labels with a database-signed HMAC
proof bound to the PostgreSQL backend and transaction. Its private key is
unreadable by the application role, and `current_tenant_context()` verifies
the signature before returning tenant scope. Narrow definer-role row-lock
policies were required for forced RLS and are dormant until an operator enables
RLS separately. PostgreSQL 16 disposable acceptance applied and replayed
migrations 392–393, forced RLS only on its synthetic tables, and passed
cross-tenant filtering, forged/tampered context rejection, invalid-token
clearing, transaction cleanup, key/table denial, and credential operations
under forced RLS. Seventy-six focused Python tests, Ruff, Python compilation,
and ordered migration validation (505 source files) pass. The candidate remains
at migration 391 and RLS remains disabled; operator/Gateway context, worker,
Directus/view access, candidate rollout, and MAN-CAP-053 remain
open ([audit](mobile-tenant-rls-callsite-audit.md); [evidence](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json)).

**13 October 2026 local source update (CAP-053):** migration 391 and the
working tree now pin new mobile device enrollments to the current verified
owner. Device forms, media writes, sync, and sync-status validate that identity
inside their PostgreSQL transaction. After owner transfer the old device is
denied until re-enrollment; its local encrypted queue is preserved and
quarantined from upload under a replacement device. Legacy rows remain
unbound and require re-enrollment. Sixty-seven focused Python checks, two
offline-shell Node checks, Ruff, Python syntax, dependency alignment, and
provider-boundary checks passed. A disposable PostgreSQL 16 fixture replayed
migration 391 twice and checked legacy NULL preservation, wrong-owner rejection,
binding immutability, and old-owner denial after transfer. The candidate rollout
completed on 14 October after an encrypted checkpoint; live authenticated
re-enrollment remains open and RLS remains disabled
([rollout evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)). An isolated Chrome browser check also passed actual client-offline behavior: `navigator.onLine=false`, service-worker shell reopen, encrypted note capture, preservation through a synthetic 503, and queue clearing after a synthetic retry success. Because all mobile API calls were intercepted, live authenticated sync and MAN-CAP-053 remain open ([browser evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)).

**14 October 2026 legacy CLI boundary (CAP-053):** all historic
`services.analytics.mobile_offline` service helpers and CLI commands now fail
closed before database access because the legacy path has no authenticated
tenant identity and bypasses form/consent policy. Enrollment, capture and sync
continue through the consent-aware Gateway. Focused boundary tests cover every
helper and command and verify no connection is opened. The OIDC console now
provides a location-scoped device inventory and content-free queue summary;
both device-read and collection-review grants for that location are required.
The 83-test focused route/service/console run passes, but live OIDC and database
acceptance remain open. Worker and other CLI review also remain open. This
source change does not accept the named capability check.
MAN-CAP-053 stays partial pending live OIDC and reconnect, human disposition,
database-role-backed tenant isolation, and retention acceptance. The source-only
[tenant/RLS call-site audit](mobile-tenant-rls-callsite-audit.md) records why
pre-context device/enrollment lookups and non-OIDC mutation paths must be
closed at both application and database-role boundaries before enabling row
policies.

**14 October 2026 tenant readiness source slice (CAP-053 / CAP-047):** the
aggregate tenant preflight now compares schema sources with the applied ledger,
reports connected-role privilege/RLS indicators, and validates enabled
scheduler arguments using counts only, and requires a dedicated read-only
preflight role before running after RLS is enabled. Four new focused source
checks plus six existing tenant-preflight tests pass with Ruff. A separate
disposable PostgreSQL 16 acceptance ran the actual catalog queries against
synthetic migration-ledger, privilege, RLS, and scheduled-command rows on an
internal network with egress blocked and no published ports. Its sanitized
output detected the expected matched, pending, drifted, and removed-source
migration states; DML/RLS bypass risks; and valid/rejected/unbounded
scheduled-command counts. Identifier-leak assertions and cleanup passed. No
candidate or legacy database was accessed and no migration was applied. This
does not establish worker isolation or RLS readiness ([source evidence](builds/2026-10-14-recovery/tenant-database-readiness-check.json); [PostgreSQL evidence](builds/2026-10-14-recovery/tenant-database-readiness-postgres.json)).

**14 October 2026 seed-ledger preflight (CAP-053):** the migration runner
previously omitted the range-prefixed `064-068_impact_network.sql`; source
discovery now includes all 121 candidate-pending seeds and validates 503 total
migration files. The curated `seed.sh` list now goes through selective ordered
migration execution and checksummed ledger writes. A pending form seed accepts
only empty state or a full match of the source columns and active revision
snapshots; the check runs before the curated batch and repeats under table locks
inside the seed transaction. A read-only comparison found the candidate's five
active 1.2.0 forms and five matching active revisions exact, with five retired
1.1.0 revisions preserved. The follow-up candidate reconciliation then
recorded `seed:140_mobile_forms.sql` as applied without changing business rows;
At the 14 October checkpoint, 120 other seed files remained pending. See the
[preflight evidence](builds/2026-10-14-recovery/candidate-seed-ledger-reconciliation-preflight.json)
and [ledger reconciliation evidence](builds/2026-10-14-recovery/candidate-mobile-form-seed-ledger-reconciliation.json). A subsequent read-only inventory found 50 empty curated target tables; only the already-tracked mobile forms and base service catalog contain rows. The full 31-seed ordered list applied to an isolated checkpoint restore and skipped cleanly on a second invocation. A separate `template0` bootstrap then passed all 382 schemas through 391 and all 31 curated seeds. At the 14 October checkpoint, the candidate had one recorded seed and 90 non-curated seeds remained unselected ([inventory](builds/2026-10-14-recovery/candidate-curated-seed-target-inventory.json); [snapshot replay](builds/2026-10-14-recovery/curated-seed-disposable-replay.json); [fresh bootstrap](builds/2026-10-14-recovery/fresh-curated-seed-bootstrap.json)). A fresh encrypted checkpoint was restore-rehearsed with matching migration and extension fingerprints and selected form/service counts. The old 30-file rollout proposal was superseded on 15 October: only the five reference catalogs in [the selected scope](reference-seed-scope.md) were approved and applied to the local candidate; pilot rows stay held. The separate rollout evidence is linked below.

The current migration-400 checkpoint for that five-file scope was then restored
transactionally into a fresh isolated `template0` database. Migration and
extension fingerprints, all 1,010 public tables, the five catalog target
counts, and selected mobile-form/service counts matched the candidate. The
checkpoint remains encrypted; the temporary restore container/network were
removed and its isolated recovery volume is retained. At this preflight stage it was recovery evidence only; owner approval and candidate seed execution
followed and are recorded below ([preflight](builds/2026-10-15-recovery/candidate-reference-seed-checkpoint-preflight.json)).

**15 October 2026 reference catalog rollout (CAP-001 / CAP-053):** after
separate owner approval, the exact five selected seeds were applied to the
local migration-400 candidate through the ordered checksummed runner. All five
ledger rows are applied with no failed/pending migration rows; target counts
are 19 expense categories, 20 metric definitions, 19 emission factors, 8
benchmarks, and 5 protocols. Existing mobile forms, form versions, and service
catalog counts were preserved. The candidate remains healthy (`/health` 200),
and an unauthenticated protected review route returns 401. The other curated,
pilot, and unselected seeds remain held. These are reference definitions/model
defaults, not farm observations, verified outcomes, report-owner acceptance,
tenant/RLS acceptance, or a MAN-CAP pass ([rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json); [scope](reference-seed-scope.md)).

**13 October 2026 source update (CAP-001 / CAP-053):** migration 386 and
current-use filters now cover canonical Field Collector activity reporting,
analytics, process metrics, repository-owned dashboards, and exports; ineligible rows stay visible to
authorized operators for disposition, while edits and forward lifecycle
transitions are blocked. Focused PostgreSQL 16 synthetic migration checks
passed with Directus present and absent; 56 focused application/query/console
tests passed (18 skipped). The Directus permission seed repair also passed a
second-run no-change check with nested location scopes and NULL permissions.
The final ordered/checksummed migration replay passed on a fresh populated
archive clone with zero pending schemas and no checksum drift. All 8/8 existing
Directus read permissions route Field Collector reads through scoped Gateway
paths. MAN-CAP-001 and MAN-CAP-053 remain not run. The separately approved
migration-386 rollout is now complete on the
local Kernel candidate: 377 applied schemas, zero pending, app health 200, and
anonymous farm-activity/review routes return 401. Its database checkpoint was
restore-rehearsed with matching migration fingerprints, extension versions, and
selected row counts. See [rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json).

**13 October 2026 tenant-owner decision (CAP-001 / CAP-053):** the repository
owner confirmed that Kokonut Network exclusively owns the two seeded locations,
Kokonut Adelphi and Kokonut Genesis. Source now includes ordered migration 387,
a final pilot ownership seed, and updated legacy seed assignments. A network-
disabled PostgreSQL 16 compatibility fixture passed clean-bootstrap ordering,
idempotent replay, legacy owner-link deactivation, exact owner assertions, and
refusal/rollback for an unrelated owner ([evidence](builds/2026-10-13-recovery/tenant-ownership-disposable-acceptance.json)). This closes the owner-decision and
focused source acceptance gates for those two records only. A read-only review
found no source-grounded location/tenant mapping for the 38 unlocated dashboard
definitions or three report snapshots, so those records remain unassigned
([lineage evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).
The clean full-schema replay of all 380 ordered migrations has passed,
including the 384–385–389 trigger stack
([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
Migration 390 transfer and tenant-context acceptance passed 14 disposable
PostgreSQL checks, and eight context unit tests passed
([acceptance](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
The ownership/transfer rollout applied migrations 387–390 after a fresh
age-encrypted checkpoint; the follow-up device-binding rollout applied 391 from
a separate checkpoint. All 382 schema migrations are now applied with zero
pending, while 121 seed files remain pending in the ledger. Five mobile-form rows and
ten revisions exist without applied seed history and require reconciliation
before any seed rollout. Only the app was recreated in each rollout;
app/database/Metabase are healthy and anonymous protected routes return 401
([ownership rollout](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json),
[device-binding rollout](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)).
Worker isolation, RLS, and MAN-CAP-001 / MAN-CAP-053 remain open.
This mapping does not establish user access or end-to-end tenant isolation.

**14 October 2026 Gateway context progress (CAP-001 / CAP-053):** report-review
queue and detail reads now validate tenant-qualified scope and set transaction-
local context on the same connection as their protected query. The routes keep
the existing location/grant predicates and return 403 for legacy NULL-tenant
grants. Route-specific verification is pending; this is a first bounded
integration only. Seventeen disposable PostgreSQL acceptance checks and two
focused Gateway HTTP denial checks passed, including owner/shared reads,
same-transaction context, legacy denial, and cleanup. The broader operator-auth
file yielded 33 passed and three older `Vary` assertion failures, which remain
open for follow-up. Other Gateway/worker paths, direct-database boundaries,
and RLS remain open, so both capabilities remain partial and their manual
acceptance checks remain not run.

The Field Collector review queue and detail query paths now set tenant context
within their read transaction and map legacy-grant denial to HTTP 403. Twenty-
two synthetic disposable PostgreSQL checks and 31 focused context, mobile
service, and route checks pass, including owner/shared reads, same-connection
context, cleanup, pre-query legacy denial, and same-tenant/cross-tenant
multi-grant behavior for the content-free disposition inventory. Human
retention/erasure decisions, other Gateway and worker paths, direct-database
boundaries, and RLS remain open; tenant isolation remains partial.

Append-only reviewer-note writes now set context before the INSERT on the same
connection and require the `review` and `read_detail` grants to resolve to one
tenant. Fourteen mobile-review service checks, eleven tenant-context checks,
and three focused auth-route checks pass. The tests confirm context precedes
the INSERT, scope denial rolls back and closes the transaction without writing,
and the route returns HTTP 403 for cross-tenant denial. Candidate and legacy
databases were not used. This closes only the reviewer-note write path;
remaining Gateway/worker paths and RLS are still open.

OIDC participant-link creation and revocation now use same-origin
`/operator/api/mobile/.../participants` routes so the operator session cookie is
sent to the endpoint. Each route requires its location-scoped action and CSRF;
its service transaction sets tenant context before the party lookup or link
write. Tenant denial returns 403 before those queries. The original
`/api/mobile/.../participants` endpoints retain Gateway API-key/capability
authorization. Five focused operator route and transaction tests plus one
API-key regression check pass, and both success and error responses are
no-store. Real OIDC/browser acceptance,
other Gateway and worker paths, direct-database boundaries, and RLS remain open.

The farm-activity intake and canonical list/detail reads, draft promotion,
draft correction, and lifecycle transitions now establish transaction-local
context before protected queries or writes. Multi-grant operations require all
grants to resolve to the same tenant; route handlers map context denials to
HTTP 403. The workflow service suite passed 10 tests, the lifecycle suite 31,
and 26 focused auth-route checks passed. Ruff and syntax checks pass; no
database was accessed. CAP-001 and CAP-053 remain partial pending the other
Gateway/worker paths, tenant ownership reconciliation, and direct-database/RLS
gates.

OIDC operator enrollment and revocation for mobile devices now validate the
`mobile_device:enroll` or `mobile_device:revoke` tenant-qualified grant in the
same transaction as the write. The public API-key enrollment contract stays
unchanged. Ten focused operator-route tests and the public enrollment
authorization test pass; Ruff and syntax checks pass. Remaining operator/API
and worker paths still need a bounded tenant-context review.

The tenant-aware source foundation is now present in migrations 388–389:
explicit operator organization memberships, verified seed-location ownership,
revocable organization shares, tenant-qualified resource/action grants, and
Field Collector write-trigger checks. Actual migrations 387–389 and focused
authorization/trigger cases passed on a network-disabled disposable PostgreSQL
16 schema; migrations 388–389 also passed idempotent replay
([evidence](builds/2026-10-13-recovery/tenant-grants-migrations-disposable.json)).
Legacy NULL-tenant grants remain compatible and unbackfilled. The operator CLI
membership/share lifecycle and in-place legacy owner-grant conversion passed
against disposable migrations 387–389
([evidence](builds/2026-10-13-recovery/tenant-grants-cli-disposable.json)). A
separate migration-390 CLI/database acceptance passed its ten transfer,
authorization, rollback, cancellation, revocation, audit immutability, and
replay checks with synthetic records only
([evidence](builds/2026-10-13-recovery/tenant-owner-transfer-disposable.json)). A
clean full-schema replay then validated and applied all 380 ordered migrations
with zero pending or failed, including the combined 384–385–389 trigger stack
(11 registered activity/workflow triggers); the candidate remained healthy and
untouched ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
This was not a populated/archive or pilot-seed replay. The local candidate
rollout is now complete, but worker/direct-database isolation, RLS, and
MAN-CAP-001 / MAN-CAP-053 remain open.

The Directus source inventory and isolated runtime probe map the CAP-001/CAP-053
boundary, but do not establish API parity. The archived `directus_users` table
has no `location_id` despite staff filters using `$CURRENT_USER.location_id`;
synthetic Field Worker requests returned 403 with no rows visible, which is
fail-closed but does not prove own-location access or cross-location isolation.
Field/write visibility, hook, and schedule acceptance remain open
([inventory](directus-parity-inventory.md); [runtime evidence](builds/2026-10-13-recovery/directus-api-parity.json)).

**13 October 2026 Phase 4 reporting safety update:** legacy
`dashboard_dataset.query_sql` execution now has an explicit
`KOKONUT_FEATURE_LEGACY_DATASET_SQL` gate that defaults off; read-only dataset
listing remains available. This reduces the default Kernel execution surface,
and the compatibility switch reaches candidate, portability, and standard app
and worker profiles. Twenty-three focused core and Compose-profile tests pass,
with Ruff, shell syntax, and whitespace checks clean. It does not establish
saved-dashboard ownership, query safety, least-privilege
grants, location scoping, or report parity ([implementation](provider-configuration.md);
[inventory](reporting-parity-inventory.md)).

**14 October 2026 follow-on:** the first-party legacy saved-query refresher now
uses a dedicated analytics login restricted to the three curated reporting
views, with live ACL verification, a read-only bounded transaction, and
metadata-only writes through the application connection. Its synthetic
PostgreSQL acceptance passed, and the feature remains disabled by default.
This narrows the repository-owned runner boundary; external dashboard roles,
report ownership/reference fixtures, and tenant scope remain open. No
MAN-CAP status or acceptance count changes ([evidence](builds/2026-10-14-recovery/saved-reporting-reader-disposable.json)).

**15 October 2026 bounded carbon-credit scheduler operation (CAP-040 / CAP-047):**
the existing `credit_adjustment` job was initially restricted to a read-only
operation. The dedicated entrypoint and required single-location check are
recorded in the 16 October follow-on. Automatic adjustment and retirement
review actions remain rejected. No job was registered or activated.

**16 October 2026 location-scoped carbon-credit scheduler follow-on (CAP-040 / CAP-047):**
the dedicated check now requires exactly one location in the CLI, shared job
dispatcher, disabled schedule planner, and database-driven command contract.
The scheduler contract rejects missing scope before process creation, and the
CLI rejects it before opening a database connection. Ninety-three focused
command/contract checks pass; the generated JobSpec inventory now distinguishes
10 default jobs, four required-location jobs, and one source-less sensor job.
This remains a source contract: workers inherit the shared runtime identity
without signed tenant context, RLS remains blocked, and no MAN-CAP status or
acceptance count changes ([evidence](builds/2026-10-16-recovery/worker-credit-adjustment-location-scope.json);
[operation map](worker-operation-map.json);
[JobSpec inventory](worker-job-contract-inventory.json)).

The read-only check reads verified/published credit and carbon-balance inputs
and performs no writes. No job was registered or activated. MAN-CAP-020 credit
custody/retirement parity, worker identity, and tenant context remain unaccepted
([historical command evidence](builds/2026-10-15-recovery/scheduled-credit-adjustment-command-contract.json)).

**16 October 2026 per-location metric schedule contract (CAP-040 / CAP-047):**
the native scheduled `metrics` JobSpec now uses `--compute --all` with one
required `--location-id`; its command contract rejects `--all-locations`.
Disabled plan generation requires one UUID. The optional Prefect adapter
preserves its prior aggregate intent by invoking the scoped job once for each
active location assigned to `kokonut-network`; the weather, credit, and climate
adapters use the same location selector. Synthetic tests cover the owner filter,
empty inventory, one-location dispatch, and schedule planning. The selection is
code-level scope only: workers have no signed tenant context, RLS remains
blocked, and none of the 66 manual capability checks is accepted ([evidence](builds/2026-10-16-recovery/prefect-location-scoped-job-fanout.json);
[schedule inventory](schedule-ownership-inventory.md)).

**14 October 2026 worker boundary update:** a machine-readable inventory now
matches the scheduler and event-handler allowlists and records their
source-visible data effects, scopes, providers, and replay limits. A regression
test prevents a new allowlisted entry from appearing without an inventory row.
Module-specific argument schemas now validate scheduler operations at
activation and dispatch, excluding unsupported human/destructive operations.
The source graph now follows locally inferred instance methods and all 20
literal metrics-registry entries. Its SQL join has a static function path for
175 of 196 unique execution sites; the remaining 21 belong to functions absent
from all current worker-root graphs, which does not prove they are dead code.
This improves code review but is not an authorization boundary:
other dynamic calls, existing task reconciliation, worker-specific identity,
and RLS remain open. The new static-only boundary preflight reports all 17 roots
as lacking signed tenant context and explicitly leaves live grants, migrations,
active schedules, and ownership unassessed. No MAN-CAP status or acceptance
count changes ([map](worker-operation-map.md); [function graph](worker-function-reachability.json); [SQL reachability](worker-sql-reachability.json); [static preflight](worker-boundary-preflight.json); [worker check evidence](builds/2026-10-14-recovery/worker-function-reachability-check.json); [SQL join evidence](builds/2026-10-14-recovery/worker-sql-reachability-check.json); [preflight evidence](builds/2026-10-14-recovery/worker-boundary-preflight-check.json); [inventory evidence](builds/2026-10-14-recovery/worker-operation-map-check.json); [argument-contract evidence](builds/2026-10-14-recovery/scheduled-command-contract-check.json)).

**13 October 2026 OIDC configuration update (CAP-001 / CAP-053):** the optional
OIDC overlay remains disabled unless explicitly selected. `.env.example` now
lists the required provider settings and identifies client/state secrets as
SOPS-only inputs; Compose checks confirm the default profile omits OIDC and the
selected overlay fails closed when settings are missing. The profile planner
now exposes `--oidc` only alongside the HTTPS proxy selection. The contract
suite also covers the minimal, edge, standard, analytics, and portability
manifests; 18 profile checks pass, including the explicit ARM64 guard. No real
provider credentials or browser session were configured, so login, grant
provisioning, CSRF, and console acceptance remain open.

**13 October 2026 platform-integrity source check (CAP-047):** the focused
migration, Gateway authorization, scheduler durability, event-bus durability,
carbon-credit, threatcasting, backcasting, and Delphi suites pass 279 tests.
Host-run Gateway app tests now use a private temporary audit journal, matching
the container's writable-spool contract. Ruff passes. The current source also
passes provider-boundary review (17 vendor import sites), and 12 dependency
groups/32 requirements align. Release-input locks match; no OCI archives were
supplied to the local release checker. This source-level evidence does not close
live provider state, external delivery, or broader recovery gates.

**13 October 2026 Phase 8 update:** the minimal app/PostGIS build inputs now
have a SHA-256 lock, and GitHub Actions is configured to build AMD64/ARM64 OCI
archives and compare resolved Python/PostGIS package versions. The current
local AMD64 app build succeeded; its ARM64 counterpart stopped at package-host
DNS failure. The first GitHub CI run built the images but failed archive
validation because the OCI index omitted platform labels; the checker now reads
missing labels from each image config and awaits a fresh run. Security surfaced
544 Gitleaks matches. Review traced them to
vendored OpenZeppelin fixtures, public EVM addresses, reproducibility hashes,
test identifiers, and documented credential placeholders. A narrow checked-in
Gitleaks allowlist and explicit config invocation now cover those reviewed
patterns; the full-history Security workflow passed on 13 October 2026. Two CI
runs exposed nested OCI indexes that the checker did not traverse; the current
PR fix recursively inspects nested manifests and falls back to image config
metadata. CI run 287 passed the AMD64/ARM64 app and PostGIS builds, locked
package comparison, and complete test workflow on commit `6549043`. Later PR
changes postdate that run, so current-head CI acceptance remains open.
Deployment settings remain pending, and no ARM64 runtime is certified
([release-input contract](kernel-release-inputs.md);
[local attempt evidence](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).
Hash-locked Python closures for the default app and optional ClickHouse profile
are now wired into the Kernel image; multi-architecture acceptance is pending.
The PostGIS build uses a dated Debian snapshot and exact PGDG package versions.
[CI run 284](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38449176283)
confirmed the signed-snapshot CA bootstrap and built both architecture images.
The inventory check then found the amd64-only `libquadmath0` package; its exact
version and absence on arm64 are now part of the SHA-256-locked package
contract. The checker permits only that exact reviewed difference and still
fails on any other package inventory mismatch. A clean CI rerun and hardware
acceptance remain open.

| ID | Capability | Owning code area | Named manual check and required result | Existing Python test candidates | Implementation / deployment progress |
|---|---|---|---|---|---|
| CAP-001 | Governed farm operations | schemas/postgres/; extensions/kokonut-hooks/ | MAN-CAP-001: Scoped farm draft, submit, independent verification and public eligibility | tests/test_phase5_source_of_truth.py | D — additive OpenAPI-backed `/api/v1/locations` list/detail routes use strict native response envelopes; legacy unversioned location routes now use the same governed five-field native projection and preserve their wrapper regardless of Directus feature flag. The `farm_activity_v1` source map and declarative workflow define human publication and rejection rework/exception disposition. Feature branch implements the OIDC/location-scoped private intake queue/detail, content-reviewed canonical draft promotion, and submit/verify/reject/rework/publish/exception-close transitions. Migration 383 adds source idempotency and draft evidence; migration 384 guards native 1.2.0 source lineage, legal status changes, active operator grants, independent submitter/verifier/rejection reviewer/publisher actors, immutable post-submission content, and append-only events while preserving legacy Field Collector rows. 77 focused migration, workflow, service, and OIDC tests passed; Ruff passed; migration and successful/denied lifecycle behavior passed in disposable PostgreSQL. Candidate migrations 383–384 and the lifecycle-write app are deployed to the healthy local candidate; 375 schemas and zero pending, with an exact-target encrypted checkpoint and isolated restore parity [rollout](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json). Latest source adds location-scoped canonical activity list/detail reads, explicit draft promotion and lifecycle controls, plus migration 385 and a native draft editor validated against the exact immutable form revision. The 95-test focused migration/workflow/lifecycle/OIDC/console suite and Ruff pass; all 376 ordered schemas replayed in disposable PostGIS 16, where a synthetic edit verified its changed-field list and content digest, append-only event protection, and rollback after injected event failure. Migration 385 is applied on the local candidate (376 applied schemas, zero pending) after a fresh encrypted checkpoint restore with matching migration fingerprints, extension versions, and workflow counts. Only the app was rebuilt from `f854d47`; health returned 200, unauthenticated review/activity/draft-edit routes returned 401, and PostgreSQL, Metabase, and proxy stayed up. The candidate has no farm-activity workflow rows. Migration 386 is now applied on the local candidate (377 applied schemas, zero pending) after a separate encrypted checkpoint restore rehearsal; only the app was rebuilt from `d22fa49`, health returned 200, and anonymous farm-activity/review routes returned 401 ([rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)). See [source evidence](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json) and [rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json). The Directus create-time reference hook now rejects malformed explicit `location_id` values; the extension TypeScript build passes, but this does not authorize the user's tenant scope. CAP-001 remains partial pending configured-provider acceptance, populated workflow acceptance, and MAN-CAP-001. Report/metric implementation and full-schema PostGIS 16 integration pass; the expanded Batch 3 suite passes 91 tests and Ruff, including wrong-location query guards and injected event-write rollback; a real PostgreSQL trigger failure also rolled back the transition status and both event ledgers after all 375 schema migrations were applied to disposable PostGIS. Two simultaneous PostgreSQL duplicate-promotion calls passed; higher-contention stress, configured-provider acceptance, and MAN-CAP-001 remain open; capability is still partial. [Location contract](location-api-contract.md); [workflow map](farm-activity-workflow-map.md); [report/metric evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json) |
| CAP-002 | Precision agriculture | services/analytics/ | MAN-CAP-002: Yield, irrigation, crop simulation and nutrient outputs match frozen fixtures | tests/test_yield_monitoring.py; tests/test_precision_irrigation.py; tests/test_digital_twin.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-003 | Traceability | services/analytics/traceability.py | MAN-CAP-003: Forward/backward custody trace and quality records match reference batch | tests/test_traceability.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-004 | Extension & peer learning | services/analytics/ | MAN-CAP-004: Enroll, deliver and assess learning with peer-group scope preserved | tests/test_extension.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-005 | Farmer identity & cooperatives | services/analytics/ | MAN-CAP-005: Profile credentials, membership and asset-booking scopes remain isolated | tests/test_farmer_identity.py; tests/test_cooperative.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-006 | Energy, waste & landscape | services/analytics/ | MAN-CAP-006: Energy, waste, habitat and pollinator calculations preserve units and evidence | tests/test_energy_monitoring.py; tests/test_waste_management.py; tests/test_landscape_conservation.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-007 | Metrics & analytics | services/metrics/; services/analytics/ | MAN-CAP-007: Compute draft values; independent reviewer verifies; analytics totals match fixture | tests/test_metrics.py | D — native public metric reads/models deployed, now also exposed through the explicitly public `/api/v1/metrics/{location_id}` route; projection/job boundaries prepared; Directus and Metabase roles verified in isolated copies; pinned Metabase starts on populated metadata, with its only saved board classified as generic e-commerce demo content. The source-aligned scratch applied all 369 current migrations through 378, reported zero pending, and passed actual-view grants and rollback-only reporting probes. The transactional runner replay validated all 369 current schema checksums and rollback of injected DDL plus ledger state (both were zero after injected failure); the separate populated clone accepted all 25 pending archived migrations, with zero pending and unchanged original-column fingerprints across 16 tables. The archived app plan remains at zero checksum drift and 25 unapplied migrations. Focused migration suite: 22 passed. SAFE seed values were verified against Gnosis Chain. Six historical NOI snapshots were stale; migration 379 and the reconciliation path brought the isolated clone to zero view mismatches. The active candidate checkpoint and isolated restore passed; all 370 current schema sources also passed on a fresh scratch. The candidate's exact historical `schema:000_extensions.sql` checksum was repaired through the audited path after all six extension effects were verified; migrations 371–379 applied transactionally and the exact-target plan now reports zero pending across 370 applied schema files. Its reporting views and NOI unique index exist. The candidate API still uses its owner credential. A separate `kokonut_analytics_ro` login is provisioned and passed real-login checks for the three curated views, denial on application tables/private policy/DDL/temp tables, and denial on all other candidate databases. Eight extension metadata relations and 1,165 extension functions remain accessible through inherited PUBLIC grants; none of the public-executable extension functions is SECURITY DEFINER. The candidate Metabase profile now registers the read-only `Kokonut Reporting Views` source, filters it to `kokonut_reporting`, and lists only its three approved views. Three first-party cards and a dashboard execute successfully with zero rows on the empty candidate; exact exported card SQL passed populated-fixture output parity, including publication and date-window rules, and the full metadata restore matched inventory ([card output parity](builds/2026-10-11-recovery/metabase-card-output-parity.json)). The populated source has zero published metric policies; the rollback-only synthetic fixture passed the nonempty period/method/review-field probe. Farm-summary and Celo-attestation view parity passed on a disposable populated copy. All 94 report generators now have read-only calculation guards; a disposable PostgreSQL acceptance found and closed an autocommit escape, while the application identity remains a writer and populated output parity remains open ([report guard](builds/2026-10-15-recovery/report-generator-readonly-disposable.json)). [NOI reconciliation](noi-snapshot-reconciliation.md); [NOI evidence](builds/2026-10-11-recovery/noi-snapshot-parity.json); [NOI index migration](../../schemas/postgres/379_noi_snapshot_crop_cycle_key.sql); [Report contract](metabase-reporting-contract.md); [populated view parity](builds/2026-10-11-recovery/populated-report-view-parity.json); [candidate preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json); [compatibility review](pending-migration-compatibility-review.md); [drift triage](migration-checksum-drift.md); [reporting migration](../../schemas/postgres/377_kokonut_reporting_contract.sql); [reads](native-metric-reads.md); [roles](optional-database-roles.md); [source disposition](metabase-source-inventory.md); [reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json); [transaction evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json); [populated clone evidence](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json); [report/query source map](reporting-parity-inventory.md); [archive metadata](builds/2026-10-13-recovery/reporting-archive-inventory.json) |
| CAP-008 | Trend analysis & geostatistics | services/trends/; services/geostatistics/ | MAN-CAP-008: Forecast, variogram and spatial validation outputs match tolerance-defined fixtures | tests/test_geostatistics.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-009 | Systems thinking | services/systems/ | MAN-CAP-009: Causal-loop, leverage and stock-flow model outputs preserve linked evidence | tests/test_stock_flow_mental.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-010 | OODA loop & adaptive decisions | services/orientation/; services/decision/ | MAN-CAP-010: Observe/orient/decide outputs remain advisory until approved action | tests/test_ooda_cycles.py; tests/test_decision_policy.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-011 | Process intelligence | services/analytics/ | MAN-CAP-011: Variants, cycle times, conformance and SLA estimates match fixture | tests/test_process_mining.py; tests/test_predictive_bpm.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-012 | Process architecture & costing | services/analytics/process_architecture.py | MAN-CAP-012: Process maps, interfaces and cost totals preserve ownership and lineage | tests/test_process_architecture.py; tests/test_process_costing.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-013 | Impact accountability | services/analytics/; services/registry/ | MAN-CAP-013: Evidence maturity, impact claims, participation and CIDS public export enforce consent | tests/test_ebf_gates.py; tests/test_cids_export.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-014 | CRISP risk scoring | services/crisp/ | MAN-CAP-014: Five dimensions, configured weights and composite rating match baseline | tests/test_crisp_scoring.py | D — published-assessment GET and additive `/api/v1/crisp/{location_id}` alias are source-defined; five-dimension scoring/weight parity pending. [Contract](public-summary-contracts.md) |
| CAP-015 | Organic certification readiness | services/analytics/organic_certification.py | MAN-CAP-015: Input, buffer and segregation evidence produce same readiness score | tests/test_organic_certification.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-016 | True cost accounting | services/analytics/true_cost_accounting.py | MAN-CAP-016: Hidden costs, valuations and cross-capital flows match fixture | tests/test_true_cost_accounting.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-017 | Emergency response | services/analytics/ | MAN-CAP-017: Incident, response and recovery workflow retains approval/evidence history | tests/test_emergency_response.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-018 | EAS on Celo | services/attestation/ | MAN-CAP-018: Prepare and verify proof metadata without broadcasting or exposing private evidence | tests/test_attestation.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-019 | Ecocredit module | services/credit_class/ | MAN-CAP-019: Class, batch, basket, fee, enrollment and bridge state preserve supply and custody | tests/test_credit_batch_manager.py; tests/test_credit_balance.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-020 | Credit custody & retirement | services/analytics/carbon_credits.py; services/certificates/ | MAN-CAP-020: Atomic retirement reservation and independent confirmation prevent duplicate balance changes | tests/test_carbon_credits.py | B — baseline credit issuance/retirement capability remains unaccepted; scheduled adjustment review uses a separate database-enforced read-only entrypoint and requires one location per run, which does not verify custody or retirement parity. |
| CAP-021 | Linked data infrastructure | services/iri/; services/rdf/; services/storage/ | MAN-CAP-021: Resolve versioned IRI, hashes, RDF and lineage without private data disclosure | tests/test_linked_data.py; tests/test_evidence_lineage_integrity.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-022 | Data Stream | services/data_stream/ | MAN-CAP-022: Post, search, file references and proof verification preserve scope | tests/test_data_stream.py | B — baseline code retained. Protected Gateway draft creation now establishes signed DB tenant context before INSERT and attributes `created_by` to the database-verified Gateway credential. Focused route/service checks and disposable forced-RLS owner/location/actor insert and cross-location denial pass. Search, file, proof, broader output parity, and candidate credential provisioning remain open. |
| CAP-023 | Governance framework abstraction | services/governance/ | MAN-CAP-023: Read Baal configuration/proposals/members; legacy Moloch identity remains distinct | tests/test_governance_framework.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-024 | Governance circles & roles | services/analytics/ | MAN-CAP-024: Circle roles, tensions and tactical items enforce authority and approval | tests/test_governance_roles.py; tests/test_governance_role_authority.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-025 | Stakeholder ecosystem | services/analytics/ | MAN-CAP-025: Resolve stakeholder identity/trust while raw feedback stays private | tests/test_consent_privacy_p0.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-026 | Threatcasting & backcasting | services/threatcasting/ | MAN-CAP-026: Threat/cascade/backcast outputs remain advisory with evidence and acyclic milestones | tests/test_threatcasting.py; tests/test_backcasting_enhancements.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-027 | Real-time Delphi | services/delphi/ | MAN-CAP-027: Pseudonymous consultation and facilitator drafts require human approval | tests/test_delphi.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-028 | Strategy system | services/analytics/ | MAN-CAP-028: Plan, allocation, cascade, consultation, execution and gate behavior preserve lineage | tests/test_strategy_kernel.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-029 | Competitive landscape | services/analytics/ | MAN-CAP-029: Competitive observations and advantage outcomes match scoped fixture | tests/test_competitive_landscape.py; tests/test_advantage_assessment.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-030 | Management workflow | services/management/ | MAN-CAP-030: Work assignment, SLA and escalation preserve authority and audit | tests/test_management_workflow.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-031 | Planning & budgeting | services/planning/ | MAN-CAP-031: Budget variance, objectives, portfolio and S&OP results match fixture | tests/test_planning_budget.py; tests/test_portfolio.py | D — adjacent public location roll-up deployed; budgeting and internal portfolio workflows unassessed. [Contract](public-summary-contracts.md) |
| CAP-032 | Business architecture | services/analytics/ | MAN-CAP-032: Capability/value-stream/mission mappings retain governed relationships | tests/test_capability_map.py; tests/test_strategy_map.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-033 | Pitch & business planning | services/analytics/; services/export/ | MAN-CAP-033: Pitch, plan and canvas retain evidence links and report content | tests/test_pitch.py; tests/test_business_plan.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-034 | Coordination & alliance system | services/analytics/ | MAN-CAP-034: Alliance triggers, learning and integrity guards preserve approval boundaries | tests/test_coordination_end_to_end.py; tests/test_coordination_governance.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-035 | Solution lifecycle | services/innovation/ | MAN-CAP-035: Experiment, funding, adoption, scale and retirement follow sequential gates | tests/test_solution_lifecycle.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-036 | Sequential evidence & decisions | services/analytics/ | MAN-CAP-036: Ordered ledger, odds and decisions retain sequence and evidence integrity | tests/test_sequential_evidence.py; tests/test_sequential_integration.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-037 | Operating pilot | services/analytics/ | MAN-CAP-037: Capacity planning, work claims and competencies preserve scope and review | tests/test_operating_pilot.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-038 | Agent ecosystem | services/agents/ | MAN-CAP-038: Agents draft/submit only; self-verification/publication/attestation is denied | tests/test_agent_safety.py; tests/test_agent_tasks.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-039 | Unified meta-CLI | services/cli.py | MAN-CAP-039: Every existing service group help and argument-forwarding path remains callable | tests/test_cli.py | D — Kernel readiness CLI added to unified CLI and deployed; all legacy forwarding paths unassessed. [Readiness](portability-database.md) |
| CAP-040 | dMRV architecture | services/ingestion/ | MAN-CAP-040: Satellite, HTTP/MQTT, anomaly and proof preparation retain quality and review gates | tests/test_remote_sensing_automation.py; tests/test_iot_sensor_push.py; tests/test_ml_anomaly.py | P — normal single-reading and CSV source paths exercised; authenticated HTTP single/batch tested through in-process ASGI and over TCP between containers on the private fixture network. The five CSV/ASGI rows created five platform events and succeeded outbox deliveries; raw ClickHouse and v3 location/day/type aggregates match. A later listener run accepted three readings, rejected invalid HMAC (401) and URL/payload mismatch (400), and detected duplicate timestamp; at listener capture three events/outbox rows were pending. A follow-up delivered those three rows once each with exact sink parity; their platform events remain pending and have no handler receipts. One selected anomaly handler produced a warning; durable-receipt acknowledgement recovery skipped duplicate execution, with three earlier failed attempts retained. First read was immediate in one run, but prior five-second visibility delay remains unexplained. Local legacy sensor lineage is reconciled (15 PostgreSQL sources, zero outbox rows, zero retained ClickHouse raw rows); remote/populated-target ownership remains unassessed. A bounded Caddy localhost TLS smoke passed (200 health, 308 redirect, security headers, unknown route 401, certificate reuse, no proxy host bindings). A follow-up host-published check confirmed loopback-only bindings, a redirect to configured port 8448, and a verified TLS health response of 200. A custom-port check confirmed the 18448 override also aligned the binding and redirect, with verified TLS health 200. Direct gateway preflight allowed `http://localhost:3000` for GET/x-api-key (200) and rejected `https://untrusted.invalid` (400, no allow-origin). A follow-up auth-denial response returned 401 for both origins, adding allow-origin only for the configured origin; two exact denied audit records were retained. A network-isolated ASGI source harness first checked injected limiter behavior [with evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json). A rebuilt local-provider canary then allowed 127 health GETs in 2.766 seconds before 429/`Retry-After: 1`, decorated throttling with the configured CORS origin, passed OPTIONS after exhaustion, and returned 429 on the next GET. Exact durable audit contained 127 allowed and two `rate_limited` denials. The image is promoted to the healthy active candidate app; a rollback snapshot is retained [with runtime evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json). The promoted image's isolated local contract admitted exactly five of 100 concurrent checks, verified oldest-caller eviction and fresh-instance reset [with evidence](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json). The active candidate app restart reset the same synthetic identity to allowed 200; PostgreSQL stayed healthy and exact audit counts were retained [with evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json). Minimal/edge profiles use the process-local limiter; standard now defaults to the PostgreSQL shared limiter after migration 373. Direct, ASGI multi-process, and two-container HTTP evidence covers shared consumption; production multi-host failover and public ingress remain unaccepted. See [profile policy](rate-limit-boundary.md). Non-loopback/public ingress, mobile/upload parity, browser/runtime authenticated/credentialed CORS (successful cookie-authenticated source response is covered), shared/multi-replica rate limits, multi-hop trusted-proxy policy, broader handler/concurrency and full transport acceptance remain open. [Proxy evidence](kernel-proxy.md), [runtime result](builds/2026-10-10-recovery/kernel-proxy-runtime.json), [forwarding audit](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json), [loopback ingress](builds/2026-10-10-recovery/proxy-loopback-ingress.json), [custom port](builds/2026-10-10-recovery/proxy-custom-port.json), [CORS preflight](builds/2026-10-10-recovery/proxy-cors-preflight.json), [auth-denial CORS](builds/2026-10-10-recovery/proxy-cors-auth-response.json). [Sensor evidence](sensor-entrypoint-recovery.md), [local lineage](builds/2026-10-10-recovery/legacy-sensor-lineage.json), [listener evidence](builds/2026-10-10-recovery/sensor-http-listener.json), [listener outbox delivery](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json), [handler evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json), [HTTP contract](http-sensor-transactions.md), [visibility evidence](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json), [CSV/HTTP evidence](builds/2026-10-10-recovery/sensor-csv-http.json); [HTTP optional profile](http-sensor-overlay.md); [MQTT optional profile](mqtt-overlay.md); original persisted broker backlog inventory empty: [Recovery](analytics-broker-recovery.md); source-level freshness-query checks now report unknown configured sources as errors rather than `no_data`; 29 tests pass ([evidence](builds/2026-10-14-recovery/freshness-query-contract-check.json)).; the `--worldclim` compatibility path now stores explicit `latitude_proxy_v1` estimates in schema-aligned fields, commits the upsert, and supplies location-level fallback to plot consumers; 51 climate/migration tests pass, but PostgreSQL migration execution remains unverified ([evidence](builds/2026-10-14-recovery/climate-worldclim-schema-alignment.json)) |
| CAP-041 | Digital soil mapping | services/analytics/ | MAN-CAP-041: SOC features and geographic cross-validation match model fixture | tests/test_dsm_soc_prediction.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-042 | Guild protocol | contracts/; services/guilds/ | MAN-CAP-042: Registry, domains, tasks, evidence and governance projections preserve chain identities | tests/test_guild_services.py; tests/test_kgp_worker_durability.py; scripts/check-kgp-worker-reconnect-disposable.py | B — baseline code retained; synthetic guild/domain/task and governance target-policy projections, idempotent replay, and seven-event simulated reorg rebuild are exercised on the Kernel schema. Candidate migration 403 is applied after checkpoint/restore rehearsal; its app image was not rebuilt and the table remains empty. Other event types, live-chain behavior, and overall capability parity remain unassessed. [Migration](../schemas/postgres/403_kgp_governance_target_policy_projection.sql); [disposable runtime evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json); [candidate rollout evidence](builds/2026-10-16-recovery/candidate-migration-403-kgp-governance-target-rollout.json) |
| CAP-043 | Credit Token | contracts/; services/credit_class/ | MAN-CAP-043: ERC-20/proxy integration preserves roles, supply, pause and custody | tests/test_credit_balance.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-044 | Price Oracle | contracts/; services/ingestion/ | MAN-CAP-044: Price-feed consensus and updater permissions preserve baseline | tests/test_oracle_infrastructure.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-045 | Selective Disclosure | contracts/ | MAN-CAP-045: Selective disclosure proof verifies while private claims remain hidden | tests/test_attestation.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-046 | KokonutResolver | contracts/; services/attestation/ | MAN-CAP-046: Resolver permits approved attesters only with existing schemas and owner | tests/test_attestation.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-047 | Platform integrity | services/migration/; services/gateway/; services/events/; services/scheduler/ | MAN-CAP-047: Migration drift rejection, default-protected routes and lease/retry recovery hold | tests/test_migration.py; tests/test_gateway_auth.py; tests/test_scheduler_durability.py; tests/test_event_bus_durability.py | D — 364 fresh schemas applied through 373; API/idle workers and readiness gates deployed; drift/auth/retry/recovery acceptance pending. [Runtime](portability-runtime.md); scoped empty-workload PostgreSQL restore completed; populated restore exercised; optional consumer role boundaries and Directus startup verified: [Recovery](recovery-preparation.md), [roles](optional-database-roles.md); all attached legacy storage encrypted and retained: [Preservation](legacy-storage-preservation.md); legacy Redis/PG clones retained: [Inventory](provider-clone-inventory.md); four DB logical restores and 13 table fingerprints match: [Restore](legacy-logical-restore.md); synthetic paired restore, scheduler stale-owner/window and event lease/retry/replay/disposal checks passed; selected sensor anomaly handler/receipt recovery passed; same-event timeout/lease takeover and crash-after-effect retry passed for one idempotent CRISP cache handler, with other handlers and broader platform integrity acceptance open: [Fixture](recovery-fixture-setup.md), [sensor evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json), [crash/retry evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json); source-level scheduler ownership/cutover inventory published; live provider and activation state remain unverified [inventory](schedule-ownership-inventory.md). Candidate scheduler status returned zero tasks in the earlier read-only snapshot [evidence](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json); external Prefect state remains unknown. The refreshed JobSpec contract now also requires an explicit location for scheduled weather, matching climate; 86 focused scheduler/dispatch/inventory checks pass. Persisted tasks were not re-read, and no MAN-CAP acceptance is implied ([evidence](builds/2026-10-15-recovery/worker-weather-location-contract.json)). |
| CAP-048 | Strategic reserve | services/strategic_reserve/ | MAN-CAP-048: Adequacy/trigger/drawdown reports match; release proposals remain drafts | tests/test_strategic_reserve.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-049 | Capital accounting | services/capital/ | MAN-CAP-049: Eight-capital accounting, deferred ledger, capacity and diversion preserve totals | tests/test_capital_accounting.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-050 | Tactical layer & simulation | services/simulation/; services/systems/ | MAN-CAP-050: Tactical models and seeded Monte Carlo outputs match agreed tolerance | Manual check required; refine test mapping in owning slice | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-051 | Data governance | services/analytics/ | MAN-CAP-051: Consent, access history, retention and portability preserve audit/privacy | tests/test_data_governance.py; tests/test_consent_append_only.py | P — migration 401 and source implementation prepare nullable runtime policy windows, explicit policy approval, audited record-level holds, and hold-aware generic/event eligibility. New schedules remain drafts and auto-enforcement stays off unless approved; destructive enforcement also has an independent feature gate. Focused source checks and ordered disposable PostgreSQL migration/hold acceptance pass; migrations 401/402 are applied on the candidate after checkpoint/restore rehearsal; no jurisdiction period is configured. Consent/disposition parity, policy ownership, and end-to-end disposition remain open. [Migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql); [database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json); [candidate rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json); [gate](builds/2026-10-15-recovery/data-retention-enforcement-gate.json) |
| CAP-052 | Platform upgrade system | scripts/upgrade.sh; scripts/rollback.sh | MAN-CAP-052: Isolated upgrade/rollback preserves authority, checksum and recovery history | tests/test_upgrade.py; tests/test_upgrade_integration.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-053 | Field data collection | services/mobile/; docs/field-data-collection-guide.md | MAN-CAP-053: Offline capture, enrollment, private media and sync dedupe preserve device/farm scope | tests/test_mobile_api.py; tests/test_mobile_form_validation.py; tests/test_mobile_offline.py; tests/test_mobile_media_storage.py | D — migration 381 provides immutable revisions, reviewer-scoped participant links, consent checks, and downstream eligibility. Sync validates each payload against its exact revision schema; undeclared fields fail with non-echoing errors, and remote `$ref` retrieval is rejected. Focused mobile/schema checks passed (60); four CORS cases passed in the previous slice. A fresh encrypted pre-rollout checkpoint restored into a network-isolated template0 database with matching 372 migration fingerprints, extension versions, and schema inventory; five immutable 1.2.0 forms are active, five 1.1.0 revisions retired, and the app/database/Metabase are healthy. `/api/mobile/app` served five 1.2.0 fallbacks (200); anonymous forms returned an empty list (200), while location query without token and invalid token returned 401 ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)). Legacy rows remain unassessed. Source-level OIDC console routes now issue and revoke location-scoped enrollments/devices with CSRF and no-store code responses; five route/auth tests pass. A synthetic live HTTP enrollment→registration→forms→sync check passed against the restored clone: enrollment 201, derived registration 200, five 1.2.0 forms, and one valid field note accepted (200); all synthetic rows were removed. Eligibility correctly remained false as `transport_pending`. Real-provider OIDC/browser scope acceptance and retired-form browser consent acceptance remain open. A live Gateway ASGI/HTTP check with a synthetic reviewed retired required-consent revision returned 403 after withdrawal despite regrant and wrote no collection or success log; seeded retired `1.1.0` revisions are `not_required` and were not used for that policy branch ([retired Gateway evidence](builds/2026-10-12-recovery/field-collector-retired-form-gateway-http-consent-withdrawal.json)). A temporary process used the encrypted local media adapter: upload 201, AES-GCM ciphertext at mode 0600, wrong-key rejection, authenticated head verification, and attachment during sync passed; synthetic files and rows were removed. The running candidate provider configuration was unchanged and no public download route is defined. A one-object age-encrypted local media checkpoint/restore rehearsal passed with AES-GCM authentication, plaintext digest verification and wrong-key rejection. A second synthetic replay previously verified only the supplied SOPS age identity. Since then, with owner approval, a random 32-byte `MOBILE_MEDIA_LOCAL_KEY` was added to `.env.sops`; targeted readback matched without emitting the value, and a one-object KKM1 checkpoint/restore using that exact SOPS key and age identity passed AES-GCM authentication, plaintext digest, and wrong-key rejection ([current provisioning/recovery evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-provisioning.json); [historical key availability evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-availability.json); [first evidence](builds/2026-10-12-recovery/field-collector-media-backup-restore.json); [age-only evidence](builds/2026-10-12-recovery/field-collector-media-sops-age-restore.json)). The candidate now runs local media through the edge overlay; the source and base Compose profile still default to S3. The isolated edge overlay also passed synthetic SOPS-keyed named-volume recovery across two disposable app containers ([edge volume evidence](builds/2026-10-12-recovery/field-collector-edge-media-volume-recovery.json)). Synthetic PostgreSQL/upload-row parity and actual candidate app recreation/restart are verified; production migration/recovery and live S3/R2 inventory/deletion acceptance remain open. Free-text/photo semantic review and retention/erasure remain open; tenant-aware grant source (migrations 388–389) is implemented and passed focused disposable PostgreSQL authorization and trigger checks; operator-CLI membership/share lifecycle and legacy-grant conversion passed disposable acceptance; clean full-schema replay of all 380 migrations, including the 384–385–389 trigger stack, passed ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)); migration 390 implements two-party audited transfers; 14 disposable PostgreSQL transfer/context checks and eight context unit tests pass ([acceptance](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)); migrations 387–390 are deployed on the candidate after an encrypted checkpoint, with zero pending schemas and 120 seed files pending in the ledger (five mobile-form rows and ten revisions exist without applied seed history); the app-only rollout is healthy and protected routes return 401 ([rollout](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json)); operator-affiliation reconciliation, worker integration, direct-database isolation, and RLS remain open under the target boundary documented in [mobile-tenant-isolation.md](mobile-tenant-isolation.md). The read-only ownership/lineage preflight ran against the empty candidate and a migrated populated archive copy. All 32 pending schemas through migration 385 applied transactionally with zero failures and the final plan has zero pending. The corrected complete-schema inventory found two locations, no active organization-member rows, one direct organization assignment not confirmed by an active owned-primary relationship, and one unassigned location; it counted four mobile devices and five location-scoped dashboard datasets, plus three report snapshots and 38 dashboard datasets without a location. An initial false-reference result exposed UUID-array string decoding; the query now returns text arrays and fails closed on an unexpected shape. No owner was inferred or backfilled. Accountable owner review, unlocated-row lineage, tenant-aware grants, and RLS remain open ([replay evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json)). A secure-origin service worker caches only static app HTML and the vault helper; `/mobile` now redirects to `/mobile/` so relative worker and vault paths remain inside the existing Gateway proxy route (33 mobile API tests and 2 Node offline-shell checks pass); the candidate app-only rebuild returned 308/200 for the redirect/canonical page and 200 JavaScript for the worker, with PostgreSQL and Metabase healthy; local candidate Caddy ingress passes route, worker, health, and security-header checks; an isolated browser stopped at ERR_CERT_AUTHORITY_INVALID and the interstitial was not bypassed; browser-through-proxy and external Traefik/public ingress remain open; a real-browser origin-outage run reopened this shell, retained one encrypted field note across reload, then accepted one mock sync and cleared the queue ([browser evidence](builds/2026-10-12-recovery/field-collector-browser-offline-reconnect.json)). A later online candidate-Gateway browser run enrolled from a one-time synthetic fixture, synced two synthetic 1.2.0 notes, and verified that the pending badge clears automatically without page navigation or manual sync. Aggregate DB evidence recorded two successful uploads; both rows remained `transport_pending` and `eligible_for_use=false`. Candidate location/device/enrollment/collection/log fixture rows were removed. A local-vault reset is now available from the locked-browser gate: after explicit browser confirmation it deletes the encrypted IndexedDB database and known legacy keys, while warning that server enrollment must be revoked separately. Focused adapter deletion, blocked-delete, cross-tab-lock, and reopen checks pass; the candidate browser showed the control, which was not invoked; the repository owner later unlocked the vault. New mocked API regression tests reject retired required-consent photo uploads after withdrawal and reject retired-record sync after withdrawal even when a later grant exists; both assert rollback and no private media or collection write (62 focused mobile tests pass; rollback-only PostgreSQL view acceptance confirms active-grant eligibility and persistent ineligibility after withdrawal/regrant ([source evidence](builds/2026-10-12-recovery/field-collector-withdrawal-source-tests.json), [database evidence](builds/2026-10-12-recovery/field-collector-postgres-consent-eligibility.json)). A live PostgreSQL-backed direct sync-handler call and a separate Gateway ASGI/HTTP request both rejected withdrawal after regrant with 403 and wrote no collection or upload log ([handler evidence](builds/2026-10-12-recovery/field-collector-postgres-sync-withdrawal.json), [Gateway evidence](builds/2026-10-12-recovery/field-collector-gateway-http-consent-withdrawal.json)). Focused rerun of the mobile/API/CORS Python suites passed 83 tests, with 11 Node shell/vault checks also passing ([evidence](builds/2026-10-12-recovery/field-collector-consent-source-regressions.json)). A synthetic retired-required-consent browser client check passed: native minlength blocked a short reference, and one valid-reference record remained encrypted and pending after the mock returned 403. The isolated test vault retains that synthetic record; the mock server is stopped. This does not test candidate Gateway consent withdrawal. The Directus-independent manifest CLI validates/previews offline and supports explicit transactional publication through `mobile_form`; apply requires a distinct operator and expected-version/absence guard. Twenty-nine focused form/schema checks and Ruff pass with a fake transaction adapter. A separate no-volume PostGIS fixture passed snapshot/actor/retirement, stale/reuse/location rejection, rollback, and historical-content checks; it applied the migration 381 publication prefix only ([evidence](builds/2026-10-12-recovery/mobile-form-publication-transaction.json)). The OIDC-scoped queue/detail source and console UI use separate list/detail grants; append-only reviewer notes require both `review` and `read_detail`, and migration 382 enforces eligibility, evidence shape, attribution, and immutability. Twenty-two focused route/query/auth tests pass; migration 382 and the actual Gateway service functions passed isolated PostGIS checks for queue list/detail, append/history, unchanged collection state, cross-location and revoked-grant denial, malformed/missing evidence, unsynced rows, update, and delete behavior ([migration evidence](builds/2026-10-12-recovery/mobile-review-event-migration-isolated.json)). A clean ordered replay of all 373 schema migrations through 382 passed with zero pending; migration 382 is applied to the candidate and the rebuilt app is healthy; real-provider/browser, live disposition, retention/erasure, and tenant/RLS acceptance remain open ([candidate evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json)) ([form contract](mobile-form-operations.md); [console contract](kernel-operations-console.md)). Browser consent withdrawal, offline capture/reconnect from a client whose path to the Gateway is severed, real OIDC, production media backup/retention, live S3/R2 inventory/deletion acceptance, and human disposition remain open. Two disposable full-runtime instances on the candidate network passed health and named-volume recovery while the main services remained untouched ([evidence](builds/2026-10-12-recovery/field-collector-media-runtime-volume-recreation.json)). Isolated migration-358 upload-row/object parity passed with one synthetic object ([evidence](builds/2026-10-12-recovery/field-collector-media-db-object-parity.json)). The dry-run-default cleanup CLI now expires only expired unattached uploads; 44 focused mobile/media/API/CLI tests and disposable PostGIS/provider acceptance passed; standard and security Ruff checks passed. Provider-neutral orphan reconciliation is implemented; 31 focused tests and an isolated local apply check passed, and the local candidate dry-run found zero objects ([candidate evidence](builds/2026-10-12-recovery/field-collector-media-orphan-reconcile.json); [isolated apply evidence](builds/2026-10-12-recovery/field-collector-media-orphan-apply-isolated.json)). Live S3/R2 listing/deletion and production retention remain open. A brief approved Wi-Fi-off probe against localhost kept reporting Online and is not offline acceptance ([probe](builds/2026-10-12-recovery/field-collector-wifi-off-probe.json)). [Live browser evidence](builds/2026-10-12-recovery/field-collector-browser-candidate-gateway.json). [Access contract](mobile-access-contract.md); [policy decisions](mobile-form-classification-review.md); [media](local-private-media.md); [recovery](work-media-recovery.md); [fixture](recovery-media-fixture.md)  Candidate edge media is active on the running local candidate: the app-only recreation and restart preserved a synthetic encrypted object with authenticated SHA-256; the upload table remains empty ([evidence](builds/2026-10-12-recovery/field-collector-candidate-edge-media-activation.json)).  The latest live browser outage retry exposed and fixed blank optional fields serialized as null; with empty fields omitted, the encrypted queue held one note while the candidate app was unavailable, then background retry received HTTP 200 and cleared the queue after recovery. A guarded cleanup revoked/removed the synthetic fixture; the accepted row stayed ineligible as `transport_pending` ([outage/reconnect evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json)). This kept host Wi-Fi online and does not verify `navigator.onLine=false` or OS airplane mode. This slice now prevents generic retention sweeps from mutating protected mobile and governed activity tables; restricted pending disposition is documented, while human erasure execution and jurisdiction-owned periods remain unimplemented. A separate `mobile_collection_retention:inventory` route and console action now expose content-free counts/statuses for known direct collection/media/canonical-activity/review lineage; it requires queue-read plus the separate inventory grant, and does not confer payload access or perform dispositions. Focused dual-grant authorization, query-scope/read-only, and console checks pass (49 focused operator auth/review/console tests; Ruff clean); complete lineage, human disposition, and jurisdiction-owned retention remain open. |
| CAP-054 | Silvi tree tracking | services/analytics/tree_tracking.py | MAN-CAP-054: GPS tracking, growth/pest analytics and exports preserve locations and units | tests/test_tree_tracking.py; tests/test_spatial_export.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-055 | Oracle infrastructure | services/ingestion/ | MAN-CAP-055: Feed consensus and actuator dispatch retain safety/authorization gates | tests/test_oracle_infrastructure.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-056 | Revenue model & channels | services/analytics/ | MAN-CAP-056: Revenue, pricing and channel delivery preserve partner scope and approved execution | tests/test_revenue_model.py; tests/test_channel_health.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-057 | Environmental scanning | services/analytics/ | MAN-CAP-057: PESTEL, regional readiness and segment results match evidence fixture | tests/test_pestel.py; tests/test_env_scanning.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-058 | Marketplace | services/analytics/marketplace.py | MAN-CAP-058: Listings, orders and cooperative orders preserve lifecycle and account custody | tests/test_marketplace.py; tests/test_marketplace_integration.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-059 | Abundance Protocol | services/abundance/ | MAN-CAP-059: Impact validation/voting/credit adjustment preserves lifecycle and approval | tests/test_abundance_protocol.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-060 | Schema.org alignment | services/linkml/ | MAN-CAP-060: Schema mappings, JSON-LD context and graph exports retain URI vocabulary | Manual check required; refine test mapping in owning slice | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-061 | Regen Network parity | services/credit_class/; services/data_module/ | MAN-CAP-061: Regen-compatible enums/project/claim/credit representations remain compatible | tests/test_data_module_all.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-062 | ARKIV parity | services/data_module/; services/credit_class/ | MAN-CAP-062: Expiry, transaction origin and fee distribution preserve documented representations | tests/test_credit_fees.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-063 | GeoNode parity | services/csw/; services/geostory/; services/maps/; services/thesaurus/ | MAN-CAP-063: GIS/KML/raster import, metadata, CSW, map and geostory access match fixture | tests/test_gis_import.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-064 | gRPC API | services/grpc/; proto/; sdk/ | MAN-CAP-064: Generated protocol, API-key scope and streaming behavior match REST policy | tests/test_grpc.py | P — optional target, scoped auth, pooled DB and bounded shutdown prepared; private-only/insecure-network, API-key, runtime-role and health limits documented. The Python SDK includes optional namespaced generated stubs that passed an isolated wheel import. The TypeScript gRPC SDK's clean build/archive include the five required proto files and exclude tests; both service clients loaded from an extracted package and closed without RPC calls. An enabled loopback test now covers registered service stubs, API-key allow/deny, scope allow/deny, health exemption, connection release, and all handler protobuf symbols; five focused suites pass 37 tests. TLS, real DB/runtime roles, tenant scope, and REST parity remain unassessed. [gRPC contract](grpc-overlay.md); [loopback evidence](builds/2026-10-14-recovery/grpc-enabled-loopback-transport.json) |
| CAP-065 | Business Model Canvas | services/analytics/business_model_canvas.py | MAN-CAP-065: One-click canvas and thirteen-section status retain evidence and scope | tests/test_bmc_oneclick.py; tests/test_comprehensive_status.py | B — baseline code retained; Kernel capability path and parity unassessed. |
| CAP-066 | State of Kokonut | services/export/ | MAN-CAP-066: Network report, funding rollup and timelines match baseline exports | tests/test_state_of_kokonut.py; tests/test_state_of_kokonut_graphs.py | P — exporter ClickHouse construction moved behind optional adapter; a separate OIDC-scoped read-only console lists location-specific submitted `report_snapshot` records and can read their detail in source. Login, scope denial, payload, and report parity remain unverified; this does not certify State of Kokonut outputs. The owner supplied a cross-lifecycle review audience of liquidity providers, DAO members, guild members, and the wider community; this grants no blanket access. AST direct and helper-query scans identify source-scope review targets, not tenant isolation. [Providers](provider-configuration.md); [console contract](kernel-operations-console.md); legacy CH objects inventoried and encrypted, report parity open: [Inventory](analytics-broker-recovery.md); [report/query source map](reporting-parity-inventory.md); [query-scope scan](report-generator-query-scope-inventory.json); [helper-scope scan](report-generator-helper-scope-inventory.json); [archive metadata](builds/2026-10-13-recovery/reporting-archive-inventory.json) |

**16 October 2026 Directus relation-expansion guard (CAP-001 / CAP-047 / CAP-053):** tenant-scoped Directus reads now fail closed when a request includes a non-empty `deep` object, dotted relation paths, nested wildcards, or malformed field selectors. Seven focused authorization tests pass, and the Directus hook extension builds with TypeScript checking. This prevents unreviewed related records from crossing the existing grant-filtered root query at the source hook; it does not establish runtime enforcement in the pinned image, field privacy, or a cross-collection grant model. Directus parity and all MAN-CAP statuses remain open ([source evidence](builds/2026-10-15-recovery/directus-relation-expansion-denial.json); [inventory](directus-parity-inventory.md)).

## Progress snapshot — 13 October 2026

**CAP-047 event-effect slice — 14 October 2026:** cache invalidation handlers
require a valid location UUID and fail closed instead of issuing an all-location
cache invalidation when event scope is absent or malformed. Focused cache,
architecture, and durable event-delivery checks pass (59 tests); Ruff and
syntax checks pass. This does not complete the platform-integrity acceptance
row or provide worker DB isolation; see the source audit in
[`mobile-tenant-rls-callsite-audit.md`](mobile-tenant-rls-callsite-audit.md).

Current focus: **Phase 7, native public API reads**. CAP-053's tenant preflight
now gates counts on schema completeness; the guard passed against a populated
archived restore, reported 11 missing columns, and skipped lineage counts; its
complete-schema path passed against the empty candidate at migration 385. The candidate has since advanced through migration 386 (377 applied schemas, zero pending), with app health 200 and anonymous farm-activity and review routes returning 401.
See the [incomplete](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-gate.json)
and [complete](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-complete.json)
evidence, and [phase progress](progress.md)
for the implementation ledger and the [runtime record](portability-runtime.md) for
exact deployed images. Seven capabilities have a deployed partial/adjacent integration
(D), three have prepared partial integration (P), and 56 retain their baseline code
with their Kernel access path unassessed (B). **0 of 66 capabilities are certified
for end-to-end Kernel parity.** B does not mean removed, migrated, or working in the
minimal image: optional dependencies and full access paths still require assessment.
D/P describe only the named slice, never completion of the whole capability.

The JavaScript SDK package now compiles with TypeScript 5.8.3 after aligning its
Directus adapter calls with the installed SDK command API and matching Python's
pagination presence/precedence behavior. Its ESM package
preflight includes the license and excludes test output; npm's dry-run lists 27
files. The locked Vitest 5.0.3 toolchain now audits with zero vulnerabilities.
The Python SDK's version 0.1.0 wheel and source archive build and contain the
README, Apache license, typed marker, and 16 `.py` files for the optional,
namespaced generated gRPC package. The wheel and optional gRPC runtime imported
successfully in a temporary environment, including both REST clients and all
10 generated modules; no live request was made.
The TypeScript gRPC package's clean build and npm archive include the five-file
service proto import closure in `dist/proto` and exclude test output. Both
service clients loaded from an extracted archive and closed without RPC calls;
server/client API parity remains unassessed. The separate JavaScript REST SDK
artifact also imported from an extracted tarball; both clients instantiated and
the HTTP guard recorded zero calls. An offline fake-adapter parity slice now
covers the five generated v1 reads and Directus pagination across both SDKs,
including route encoding, headers, response values and error handling. This
slice is now locked by persistent Python and TypeScript tests (6 passing in each
suite), including typed response payloads and stable malformed-response errors.
The fake transports make no network calls. This
partial evidence applies to CAP-001, CAP-007, CAP-014 and the adjacent CAP-031
public summary slice; live route/auth, tenant scope and broader SDK parity remain
unassessed. The 6 D / 4 P / 56 B / 0 accepted counts do not change.
See the [JavaScript ledger](progress.md#phase-7-javascript-sdk-package-preflight--11-october-2026)
and [Python import ledger](progress.md#phase-7-python-sdk-isolated-wheel-import-check--11-october-2026).

An optional OIDC identity/session adapter and a same-origin principal/report
review page are implemented in source. The queue reads only submitted
`report_snapshot` records under an explicit per-location grant; details remain
read-only. OIDC is disabled pending provider settings and migration 380; login,
CSRF, session revocation, scope denials, and audit behavior are unverified. The
Cloudflare preview remains synthetic-only. This infrastructure slice does not
certify any capability or change the totals. See the
[console contract](kernel-operations-console.md).

The active AMD64 Kernel candidate has a private database and healthy app. Its
rebuilt image matches all 1,294 bundled source hashes in the checkout, and its
schema-only migration plan reports zero pending across 370 applied migrations
through 379. The app liveness endpoint returns 200; its scheduler currently has
zero enabled, disabled or running tasks. No numbered seeds or pilot fixture were
loaded. These are operational checks, not proof of a complete
farm/metric/reviewer/mobile workflow. Legacy remains stopped with volumes
retained. The previous app image is preserved under a rollback tag. The active
candidate app still uses its owner login; the verified read-only analytics login is separate. The opt-in Metabase profile is healthy with credential encryption enabled. It retains the H2 demo separately and adds a read-only PostgreSQL source filtered to the three `kokonut_reporting` views, plus three first-party cards and a dashboard. The candidate is empty, so all cards return zero rows; exact exported card SQL passed independent output parity on a copied populated fixture. All MAN-CAP acceptance gates remain open.

Shared infrastructure changes (provider flags, adapters, requirement groups,
scheduler/events/cache ports, images and migrations) support many rows but do not
certify unchanged domains. Test paths remain candidates, not passing results.
Implementation-time lint, static boundary checks and Docker startup must not be
reported as domain parity. No Python/Solidity/extension acceptance suites were run
in the implementation slices recorded here.

**Update rule:** every subsequent Kernel implementation/deployment slice updates
this column for directly affected IDs and the phase ledger, linking its evidence
and remaining acceptance gates. When acceptance is actually performed, retain its
fixture/provider/image identity and result in the evidence record; only then mark
that capability accepted. Preserve the 66 baseline IDs and their original checks.

## Acceptance evidence record

For each ID, attach fixture identity, provider/profile, source commit, selected tests and their results, manual output comparison, authorization/tenant checks, audit evidence and recovery/rollback result. Preserve domain-specific vocabularies; a report or advisory capability does not acquire verification authority simply because the transport changes.

Candidate test mapping is deliberately conservative: missing guessed names are excluded. Expand mappings using the static service-group test references and the domain registry before changing that capability. CLI/API compatibility and frontend workflows require separate assertions; a Python import reference alone cannot establish them.

## Infrastructure gates

- Migration history/checksums remain intact; additive schema revisions only.
- Database/outbox leases, idempotency, retry limits and operator replay remain durable.
- Public views keep verified farm/record eligibility and consent restrictions.
- Existing SDK/protobuf/CLI contracts remain versioned and compatible.
- A capability can use an optional/offloaded adapter, but its supported access path must be documented and tested.
- Profile and ARM64 certification is a separate release gate after relevant parity checks pass.

## Batch execution — 10 October 2026

[Six-batch checklist](batches.md). **Batch 1 complete:** matching AMD64/ARM64
minimal artifacts now bundle source inventories and the public relation readiness
gate. [Build evidence](builds/2026-10-10-batch1/README.md). Running images are unchanged.
No new capability acceptance gates closed; counts remain 6 D / 4 P / 56 B / 0 accepted.
**Next: Batch 2, baseline data ownership and isolated backup/recovery preparation.**

### Batch 2 preparation update — 10 October 2026

Read-only aggregates recorded for five legacy stores; anonymous Redis and broker
log volumes now have explicit owners. Added a scoped age-encrypted PostgreSQL
checkpoint script, standalone recovery Compose destination, retention/restore
procedure and Adelphi fixture outline. [Evidence and gaps](recovery-preparation.md).
Shell syntax and Compose parsing passed; no checkpoint/restore or test suites ran.
Batch 2 remains in progress; full provider ownership and recovery acceptance open.
Running deployments unchanged; capability acceptance counts unchanged.

### Batch 2 scoped recovery performed — 10 October 2026

Portability PostgreSQL encrypted checkpoint restored successfully into a fresh,
isolated database. All 364 migration fingerprints, extension versions and eight
selected aggregate counts match. Selected workload/media tables are empty; active
work and media recovery remain unproven. Stopped legacy Redis/broker files archived
with age encryption; logical session/message inventory and archive restore pending.
Recovery container stopped with volume retained; source deployments unchanged.
[Retained evidence](builds/2026-10-10-recovery/README.md). No acceptance suites run. Batch 2 stays open
for complete provider ownership, independent backup copy and populated recovery.

### Batch 2 legacy preservation — 10 October 2026

All ten locally attached legacy volumes and selected configuration captured in
a finalized age-encrypted archive; source containers remained stopped. Sizes and
image/volume mappings retained. External-setting presence inspected without values;
no configured Prefect/mobile storage settings found in the inspected local scope.
[Preservation scope and restore procedure](legacy-storage-preservation.md). Logical provider
state and populated job/media recovery remain open; no capability acceptance closed.
User deferred independent R2 production backups and authorized a local development
mirror under backups/development-mirror/. Same-disk copies are not independent
production protection. Running Kernel services unchanged; no test suites ran.

### Batch 2 provider clone inventory — 10 October 2026

Isolated copied Redis/PostgreSQL engines loaded successfully: Redis has four string
keys without expiry; Metabase contains 39 cards and one dashboard. Four PostgreSQL
databases and globals captured into age-encrypted logical archives, with matching
development mirror checksums. Broker clone counters are ambiguous/anomalous and
do not certify application backlog. [Evidence and limits](provider-clone-inventory.md).
All clones stopped; original legacy services/storage unchanged. No test suites ran.
Batch 2 remains open for populated recovery, provider semantics and logical archive
restore. No capability acceptance counts changed.

### Batch 2 populated legacy database restore — 10 October 2026

All four legacy logical archives restored into fresh isolated databases on the
compatible recorded image. Counts and whole-row comparison fingerprints match for
13 selected tables, including populated events, sensors, weather, wallets,
attestations and Metabase cards/dashboard. [Restore evidence](legacy-logical-restore.md).
Both recovery engines stopped and volumes retained. Original legacy and running
Kernel deployments unchanged. Globals/grants were not applied; no active workload
or uploaded media exists in the selected source. Batch 2 remains open for those
recovery gates, broker/ClickHouse and external ownership. No acceptance suites ran
and no complete capability acceptance counts changed.

### Batch 2 analytics and broker inventory — 10 October 2026

Compatible isolated ClickHouse copy loaded: 34 analytics objects in default, zero
active non-system rows/parts, expected kokonut_analytics empty. Schema definitions
encrypted and mirrored; complete object metadata retained. Original broker file
scanned offline: version 6, one configuration chunk, zero message/client/subscription
chunks. [Evidence and limits](analytics-broker-recovery.md). Original services remain stopped;
ClickHouse clone stopped with volume retained. No acceptance suites ran. Full
analytics output/restore and transport recovery remain open; capability counts
unchanged. Redis semantics, active work/private media and permissions still pending.

### Batch 2 work/media recovery preparation — 10 October 2026

Added quiesced local-media checkpoint and exclusive staged restore commands, with
ciphertext/object hashes, database checkpoint binding and secret custody labels.
Defined exact isolated lease/window/event/delivery/dead-letter/device/media fixture.
[Commands, fixture and gates](work-media-recovery.md). Both scripts passed Ruff; no media
commands, fixture records or acceptance suites executed. AES/key/DB-reference
authentication and active-work recovery remain open. Running deployments unchanged.

### Batch 2 guarded fixture preparation — 10 October 2026

Added standalone private fixture deployment and guarded transactional disabled
durable-work seed loader. Checks dedicated project/image/volume/network/roles and
all bundled migration checksums before insertion. [Setup and limits](recovery-fixture-setup.md).
Ruff and Compose parsing passed. Deployment not started, SQL not applied, no
acceptance suites run. Device/media loader and exercised recovery gates remain
open; no phase/capability acceptance counts changed.

### Batch 2 device/media loader preparation — 10 October 2026

Added authenticated two-object synthetic media loader and transactional device/
collection/reference seed. Shared full target/schema guard extracted for both
loaders. AES-GCM associated-data, JPEG size/hash and exact scope validated before
insertion; no device/enrollment authority minted. [Inputs and limits](recovery-media-fixture.md).
Ruff passed. No fixture provisioned or SQL applied; acceptance suites not run.
Paired recovery, stale ownership, replay/disposal and enrollment/consent remain open.

### Batch 2 exercised synthetic recovery — 10 October 2026

With explicit user authorization, provisioned the private fixture and restored
364 checksummed schema records. Applied disabled work and two authenticated
synthetic media records. Captured a quiesced paired encrypted DB/media checkpoint;
restored DB into fresh `recovery_roundtrip` and media into an unused private directory.
All 12 selected whole-row count/fingerprints match. Both restored objects authenticate
with the separately age-encrypted development AES key. Wrong key, changed associated
data, duplicate work/media seeds, reused restore destination and capture without
quiescence were rejected. Actual scheduler code recovered the expired lease,
retained its original window, advanced retry to 2 and rejected stale completion;
no job dispatched. Fixture stopped after checks; volumes and checkpoints retained.

[Sanitized results](builds/2026-10-10-recovery/fixture-roundtrip.json).
Backups/key custody: ignored `backups/recovery-fixture-20261010/`; the key itself
is only persisted as `media-key.age`. This is a local development recovery exercise.
Live enrollment/consent, handler effects/replay/disposal, role/grant policy,
external provider ownership, production/Pi certification and full recovery acceptance
remain open. Batch 2 stays active; no capability is fully accepted.

### Batch 2 event recovery exercised — 10 October 2026

After the host restart, started only the retained private recovery fixture for
this slice. Host project/image/volume/network/schema guard passed. Eight synthetic
event checks passed against real PostgreSQL: expired lease reclaim/stale owner
rejection; successful delivery skipped on retry; bounded retries to dead letter;
audited replay with duplicate rejection and successful-delivery preservation;
orphan replay rejection; operator identity/reason requirements; audited disposal
with duplicate rejection. Handler invocation used controlled outcomes; no domain
handler or external effect ran. Synthetic handlers disabled again on exit.

[Evidence](builds/2026-10-10-recovery/fixture-events.json).
Reproducible guarded launcher: `bash scripts/kernel-recovery-event-checks.sh`
after loading encrypted secrets and starting the fixture. This mutates the exact
seeded event fixture and is intentionally not repeatable against completed state:
restore the retained pre-exercise checkpoint into a separately reviewed fresh
fixture before another run. Never rerun its seed into existing work tables.
The first attempt stopped before claiming work because a check assumed no standard
handler registrations; corrected to inspect the synthetic event type only.

Fixture stopped afterward; volumes/backups retained. Legacy stack remains stopped.
Candidate services restarted automatically; portability services remain stopped
following the host restart. No deployment promotion occurred.
Actual handler side effects/idempotency, child-process timeouts, concurrent workers,
roles/grants and provider ownership still require evidence. Batch 2 remains active;
no capability becomes fully accepted.

### Batch 2 legacy authorization recovery — 10 October 2026

Read-only metadata from all four isolated source databases excludes password hashes.
One custom role (`kokonut`) is superuser with create-role/create-database,
replication and bypass-RLS privileges. No custom memberships, default ACLs or
row-security tables were found. Ownership and explicit object ACLs matched all
four logical restores. Main database schema ACLs initially differed because
no-privileges dumps omit grants. Rehearsed two explicit schema grants only on
the isolated logical restore; all selected main-database catalog fields then matched.
Both recovery clones stopped; original databases and encrypted globals unchanged.

[Inventory](builds/2026-10-10-recovery/legacy-authorization.json),
[before comparison](builds/2026-10-10-recovery/legacy-authorization-comparison.json),
[grant rehearsal](builds/2026-10-10-recovery/legacy-authorization-grants-rehearsal.json).
Recovery compatibility policy: create the recorded database owner under private
operator custody, restore no-owner/no-privileges archives, review source catalog
metadata, then apply only explicitly reviewed grants. Never replay encrypted
globals blindly or print their credentials. The isolated SQL fixture is not a
production migration and must not be added to ordered schema files.

Production policy remains open: separate migration/operator and runtime roles,
restrict privileges to actual service needs, and verify runtime denial of DDL,
role creation and unrelated databases alongside required domain workflows.
Legacy superuser parity does not satisfy that gate. Batch 2 remains active.

### Batch 2 Redis ownership assessment — 10 October 2026

Inspected the retained no-network Redis clone without printing key identities or
values. Four db0 string keys have no Redis expiry. Three are source-mapped against
the exact retained Directus image: two API request telemetry counters and one
collaboration instance registry. These are not evidence of governed domain state
or queued jobs. One opaque key remains unclassified; retain the encrypted RDB and
original volume, and leave Redis retirement blocked pending its ownership review.

[Sanitized evidence](builds/2026-10-10-recovery/redis-ownership.json).
Pinned source paths: `middleware/request-counter.js`,
`telemetry/counter/use-counters.js`, `websocket/collab/messenger.js`,
`websocket/collab/store.js`, `utils/store.js` in the retained Directus image.
Telemetry counters stay archived; they must not become native rate-limit state.
Collaboration presence is runtime state: archive it, reconnect clients and recreate
instance identity when restoring the optional adapter. Do not import stale
presence into Kernel domain tables. No Redis keys deleted or rewritten; clone stopped.

Kernel computation cache remains PostgreSQL-backed (`services/cache/cache.py`),
and native gateway rate-limit state has its own provider boundary and PostgreSQL
schema. Directus Redis settings remain optional-adapter concerns; clustered Directus
cache/collaboration/limit behavior still needs adapter acceptance before changing
its deployment. Source mapping is not live Redis-free Directus certification.
Batch 2 remains active; no capability promoted to fully accepted.

### Batch 2 final Redis key mapped — 10 October 2026

All four retained db0 keys now have source-backed owners. The remaining `rlflx`
namespace is the pinned rate-limiter-flexible default. Directus authentication
constructs a limiter with `duration: 0` and consumes by `user.id`; privately matched
the retained UUID to `directus_users` in the isolated legacy PostgreSQL clone.
Only a boolean match is retained, with hashed key identity; no UUID or counter
value is published. This is a persistent failed-login counter, not disposable
cache or native gateway rate-limit state. No source keys/grants/data modified.
Both recovery clones stopped after inspection.

[Updated evidence](builds/2026-10-10-recovery/redis-ownership.json).
Redis ownership inventory is complete for the retained local snapshot. Retirement
remains open: optional Directus must preserve this security counter in compatible
Redis state, or use an explicitly reviewed transfer/reset policy with login lockout
acceptance checks. Native gateway token buckets do not replace failed-login policy.
Do not clear Redis wholesale or promote a Redis-free Directus deployment based
on the telemetry/presence classifications. Original volume and encrypted archives
remain the rollback source. Live lockout behavior and provider parity remain open.
Batch 2 stays active; no capability fully accepted.

### Batch 2 ClickHouse database reconciliation — 10 October 2026

Found the bootstrap selecting no database while repository SQL uses unqualified
object names. Legacy objects therefore reside in `default`, whereas service
clients/analytics profiles select `kokonut_analytics`. Corrected `scripts/seed.sh`
to validate a simple `CH_DB` identifier and explicitly select it for readiness
and schema application; no historical SQL files edited. Shell syntax passed.
In the isolated retained clone, the configured database was empty. Applied all
six repository schema files twice successfully, creating 34 objects; default
name/engine/row inventory unchanged. This is a rehearsal, not deployment promotion.

[Bootstrap evidence](builds/2026-10-10-recovery/clickhouse-target-bootstrap.json).
A synthetic sensor projection inserted values 10,20 and then 30 in separate blocks.
Raw and summary counts equal 3, but sum of per-block summary averages is 45 versus
raw average 20. `mv_daily_sensor_summary` uses SummingMergeTree with ordinary
average/min/max/uniq outputs; those statistics cannot safely be summed across
blocks. This is a failed analytics parity gate, not an accepted projection.
[Projection evidence](builds/2026-10-10-recovery/clickhouse-sensor-projection.json).

Batch 4 must introduce versioned corrected rollups using aggregate states or
sum/count plus proper min/max/distinct aggregates, audit all analogous views,
rebuild from retained raw data with explicit backfill, update consumers, and
exercise multi-block/merged output against PostgreSQL queries. Preserve old
views/data until parity passes; never silently replace their definitions.
Legacy physical application tables had zero rows, so no populated historical
transfer was inferred. New synthetic rows exist only in the recovery clone;
clone stopped afterward. Original legacy storage and running deployments unchanged.
Batch 2 remains active for external ownership and remaining recovery gates.

### Versioned sensor rollups exercised — 10 October 2026

Added schema 007 with aggregate-state materialized views and finalized v2 daily/
rate read interfaces; historical schemas/views unchanged. Isolated quiesced
backfill, subsequent separate blocks and FINAL merge outputs match raw aggregates
for all fields, including exact distinct sensors/locations and suspect readings.
No deployment promotion or consumer switch. [Migration, rollback and evidence](sensor-rollups-v2.md).
Batch 2 stays active; PostgreSQL/outbox/dashboard parity and other rollups remain open.

### Remaining analytics rollups corrected — 10 October 2026

Audited all 11 materialized definitions in schemas 002/003/006. Added versioned
raw read interfaces in schema 008 for monthly distinct wallets, both Digital Lego
rollups with missing merge-key dimensions, and remote-sensing non-additive
statistics. Historical definitions retained. Reapplication, separate-block fixtures,
nullable statistics, dimension preservation and before/after FINAL merge checks
passed in the isolated clone; clone stopped. [Interfaces, audit and evidence](analytics-read-views-v2.md).
No saved dashboard switch, running deployment promotion or full analytics acceptance.
PostgreSQL/outbox parity and raw-view resource measurements remain open.

### Durable outbox recovery exercised — 10 October 2026

Hardened enqueue: a reused event key requires identical hash, source/target,
columns and rows; conflicting projection raises for caller rollback. Completion
now requires an unexpired lease as well as owner/token. No SQL migration changed.
Seven PostgreSQL-backed isolated checks passed: caller rollback, matching-key
idempotency/conflict rejection, paused-provider retry preservation, expired lease
reclaim/stale completion rejection, eight-attempt dead letter, replay/duplicate
rejection and successful delivery not reclaimed. Ruff passed.
[Evidence](builds/2026-10-10-recovery/fixture-outbox.json).

Execution used pinned fixture operator plus a read-only mount of changed outbox
source; this does not certify the unchanged deployed image. Fixture retains one
synthetic succeeded outbox record; check intentionally refuses nonempty outbox
on rerun. Recovery checkpoint and volumes retained; fixture stopped afterward.
Transport results were controlled: no live ClickHouse driver delivery or
PostgreSQL-v2 output parity claimed. Cross-store crash after insert/before ack can
still duplicate analytics rows; requires explicit delivery identity and proven
sink deduplication/reconciliation. Outbox replay currently lacks actor/reason audit
and needs alignment with event dead-letter governance before acceptance.
Batch 2 stays active; these are preparatory Batch 4 durability checks.

### Outbox operator auditing exercised — 10 October 2026

Added ordered schema 374 and atomic audited replay/disposal with required actor/
reason, retained attempts/hash and duplicate rejection. Explicit host migration
runner applied one migration to fixture only (365 schemas); four isolated checks
passed, including forced audit insert failure rolling back state. Ruff passed.
[Interfaces, deployment and rollback](outbox-operator-audit.md).
Initial attempt to invoke the Compose-based migration CLI inside the operator
failed because Docker is absent there; no migration applied in that attempt.
Host invocation with explicit fixture selection succeeded. Running images unchanged.
Recovery fixture stopped and records retained; full operator role/identity policy,
concurrent actions and live sink crash deduplication remain open. Batch 2 active.

### Live outbox recovery exercised — 10 October 2026

Fixed ingestion CH_DB selection and JSON-persisted payload transport; added stable
insertion tokens/bounded raw-table block windows and NULL sensor plot handling.
Real driver crash-before-ack replay passed against new raw sensor v3 read views;
three outbox payloads yield three raw rows, average 20. V2 materialized summaries
failed replay parity even with dependent-view setting; failure slices retained.
[Exact limits, failure evidence and deployment](live-outbox-recovery.md).
Fixture roles stopped afterward; production/legacy unchanged. Canonical domain
source ingestion, restarts/concurrency/window eviction and full parity remain open.
Batch 2 stays active. Earlier sensor-v2 arithmetic checks did not cover this crash
case; v3 now supersedes v2 as the recommended sensor read interface.

### Canonical sensor ingestion recovery — 10 October 2026

Transactional producer now projects stored PostgreSQL precision/unit and actual
reading UUID through the shared outbox helper; enqueue failures propagate. Same
sensor/timestamp conflicting value/quality is rejected. Five real PostgreSQL/live
ClickHouse checks passed, including source rollback, retry identity and v3 parity.
Ruff passed. [Evidence, migration/rollback and limits](canonical-sensor-recovery.md).
Fixture roles stopped; running deployment unchanged. Legacy hash-keyed projections
require reconciliation before producer promotion; full CSV/HTTP, concurrent source
writes and field device authority remain open. Batch 2 still active.

### Batch 2 ClickHouse first-read visibility trace — 10 October 2026

Sanitized query-log evidence confirms inserts and 44 immediate reads targeted
`kokonut_analytics` without exceptions. The reads reported zero rows for five
seconds, followed by a later read containing both synthetic sensor-date rows.
Async inserts and query result cache were disabled; neither explains the delay.
Root cause remains unknown and no visibility SLA is claimed. [Evidence and limits](sensor-entrypoint-recovery.md#first-read-visibility).
Batch 2 remains open; CAP-040 stays P and acceptance counts are unchanged.

### Batch 2 CSV and authenticated HTTP sensor paths — 10 October 2026

FastAPI now resolves its nested request annotations, and HTTP publishes the
`sensor_reading` event atomically with source, health and outbox changes. The
isolated run accepted two CSV and three authenticated HTTP readings, rejected an
invalid timestamp and HMAC, delivered five outbox rows, and matched raw and v3
aggregates. Events are still pending for the enabled anomaly handler; network
listener/proxy and handler-effect acceptance remain open. [Evidence](builds/2026-10-10-recovery/sensor-csv-http.json).
CAP-040 remains P; counts and deployment selection are unchanged.

### Batch 2 local limiter process reset — 11 October 2026

Using the promoted image in one disposable container with networking disabled,
the first Python process exhausted its default local bucket (100 allowed, one
denied); a second Python process selected the local provider and admitted the
same identity again. This verifies local state resets across an OS process
boundary. The candidate gateway/container was not restarted, and no PostgreSQL,
audit, or domain state was touched. [Evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json).
CAP-040 remains P; actual service restart, shared/multi-replica limits and other
listed parity gates remain open.

### Batch 2 candidate gateway restart — 11 October 2026

Exhausted a synthetic credential bucket through the active candidate gateway,
then restarted only its app container in place. The container returned healthy;
the same identity received 200 after restart. PostgreSQL kept its container ID
and start time. Exact audit results were 124 allowed and one `rate_limited`
denial; the 125 synthetic records remain retained. [Evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json).
This accepts local limiter reset for the single candidate app. CAP-040 remains
P; shared PostgreSQL/multi-replica behavior, host/public ingress and the other
listed parity gates remain open.

### Batch 2 PostgreSQL shared limiter consumption — 11 October 2026

On the isolated migration-373 portability database, the shared adapter denied
an over-capacity request, returned a 10-second retry estimate, and gave a
different caller an independent bucket. Two backend instances handled 140
concurrent same-caller checks (121 allowed, 19 denied in 2.193 seconds), within
the refill-aware bound. Synthetic rows were deleted and the table returned to
zero rows; the candidate database was untouched. [Evidence](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json).
This is bounded connection-concurrency evidence only; PostgreSQL outage,
multi-process/multi-replica and gateway 503/audit acceptance remain open.

### Batch 2 gateway limiter update — 11 October 2026

CAP-040 remains P. In addition to local-provider and shared-consumption
checks, a network-disabled source ASGI probe explicitly selected
PostgresRateLimiter, simulated an unreachable database, and confirmed the
gateway returned 503 with Retry-After: 30 while attempting one denied audit
callback in memory. It confirmed no fallback to local state.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-outage.json).
The two-second PostgreSQL row-lock timeout has also been exercised: a synthetic
held lock returned SQLSTATE 55P03 after 2.124 seconds and the temporary bucket
was deleted. [Evidence](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json).
Four OS processes also shared one bucket across 160 direct adapter calls:
114 allowed and 46 denied in 1.653 seconds, within the refill-aware bound; the
synthetic row was deleted. [Evidence](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json).
The real GatewayAudit path was also exercised with PostgreSQL unreachable: it
attempted the write, logged OperationalError, and allowed the gateway's 503
response to complete; no durable denial record was possible.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json).
Four gateway ASGI processes also shared PostgreSQL state across 160 requests:
121 returned 200 and 39 returned 429 with Retry-After, within the refill-aware
bound; the synthetic bucket was removed.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json).
Two private-network API containers also shared the PostgreSQL limiter over
160 HTTP requests: 119 returned 200 and 41 returned 429 with Retry-After; the
refill-aware cap was 126 and the synthetic bucket was removed.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json).
Audit replay after database recovery, production ingress, replica failover/scale,
and candidate provider activation remain open.

### CAP-040 gateway audit journal update — 11 October 2026

The earlier stop/restart observation below characterized the original behavior
and is superseded for current source by the bounded local journal. In the later
real-ASGI recovery probe, a PostgreSQL-outage denial returned 503 with
`Retry-After: 30` and queued one event. After replacing the app container on the
same retained volume, the startup replay worker committed exactly one audit
row, preserved its original timestamp and drained the journal. Duplicate event
IDs remained one row; the configured one-event queue limit rejected a second
event; the SQLite file was mode 0600. [Implementation and recovery evidence](gateway-audit-spool.md).

CAP-040 remains partial. Journal saturation/volume loss, installing a restored
copy into a live Compose volume,
candidate provider activation, replica failover/scale, production ingress, and
the other transport and handler parity gates remain open. A new CLI reports
counts/integrity, checkpoints online to a new private file, and restores only
to a new destination. Process exit around a committed/uncommitted SQLite write,
live-source checkpoint consistency, restore identity, 0600 output permissions,
and overwrite rejection passed in a synthetic fixture.
[Checkpoint evidence](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).
The rebuilt image's unified CLI also passed status and temporary-bind
checkpoint/restore invocation without a database or persistent volume.
[Image evidence](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).
The active candidate still uses the local rate limiter. The isolated synthetic
audit row, temporary app containers and temporary journal volume were removed;
the portability database returned to its prior stopped state. No schema
migration, domain data write or pytest suite ran.
[ASGI replay evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).

### CAP-040 local SQLite contention update — 11 October 2026

The first cold-start probe found three `database is locked` failures among eight
simultaneous writers. WAL/schema initialization now retries transient lock
errors. Three later cold starts each committed all 144 events from 12 processes;
10 warm writers also completed. An online checkpoint captured 166 valid events
while all eight writers were active; the source subsequently reached 481 events.
Temporary synthetic files were removed.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json).

CAP-040 remains partial. This closes only local process-level SQLite contention
and checkpoint consistency; volume/device/host loss, power loss, external alert
delivery, approved retention, live-volume restore, candidate-provider activation
and replica failover/scale remain open.

### CAP-040 audit saturation alert and write guard — 11 October 2026

The queue alert threshold defaults to 80% of its configured cap, with an
absolute-count override exposed by both Compose profiles. Unified CLI status
reports pending count, cap, threshold, alert and restriction state without
event payloads. `/health` reports `audit_capture` as `ok`, `degraded` or
`unavailable`. Before a non-read handler, middleware replays the journal and
checks both capacity and local SQLite writeability; unavailable storage or a
queue at/above threshold returns 503 with `Retry-After: 30` before handler
execution. A storage-path failure, injected `ENOSPC`, a missing journal after
in-process observation, threshold rejection, recovery below threshold, and the
no-event status output passed against private synthetic fixtures. The capacity
probe's temporary record was not retained; no physical disk was filled.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json).

CAP-040 remains partial: in-flight operations can finish if storage fails after
preflight; an empty replacement volume after restart requires external volume
monitoring to distinguish it from first use. Physical-device/power failure,
external alert delivery, production retention ownership, live-volume restore,
candidate activation and replica failover/scale remain open.

### Historical CAP-040 audit recovery boundary — 11 October 2026

The initial isolated PostgreSQL stop/restart probe found that the then-current
GatewayAudit writer dropped outage events while new post-recovery writes
succeeded. That result is retained as baseline evidence, not the current
implementation status. [Historical evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).

### CAP-040 audit admission addendum — 11 October 2026

Mutating gateway requests reserve spool threshold headroom in SQLite until
handler completion and audit capture. Sixteen local worker processes sharing
one journal at 3/4 pending yielded one reservation; a forced worker exit left a
reservation that the next preflight safely reaped. ASGI success/error paths
released only after audit capture; a forked worker used a distinct owner lock,
and an injected release failure was reaped on the next preflight. Multi-host
filesystems, independent replica failover and headroom consumed by read/denial
events remain open.
[Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).

### CAP-040 concurrent event-handler effect — 11 October 2026

On a fresh restored PostgreSQL fixture, four independent workers processed 16
synthetic `metric_computed` events. One real cache handler invalidated the 16
target-location entries, preserved three sentinel entries, and recorded 16
single-attempt successful receipts/logs. This narrows the handler/concurrency gap
for one cache effect; other handler types, same-event retry/crash recovery,
runtime-role policy and provider recovery remain open. CAP-040 stays partial and
the capability counts do not change. [Details](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/event-handler-concurrency.json).

### CAP-040 CRISP cache-handler addendum — 11 October 2026

Four independent operator containers processed 16 synthetic `crisp_scored`
events, with four completed events assigned to each worker. The real allowlisted
CRISP handler invalidated all 16 target `crisp` cache entries, preserved three
sentinel entries, and wrote 16 successful one-attempt delivery receipts/logs;
all leases were released. The helper also reverified the earlier metric run.
The in-flight observer failed on an ambiguous joined `status` column, so this
run has no in-flight snapshot; the earlier metric run retains its own. Same-event
retry/crash, other handler types, production runtime-role policy and provider
recovery remain open. CAP-040 remains partial and counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/crisp-handler-concurrency.json).

### CAP-040 same-event active lease addendum — 11 October 2026

While the real CRISP cache handler was held at a synthetic cache write, worker A
owned the event with one processing delivery attempt. A second real worker
processed no event; PostgreSQL still showed worker A as owner and attempt count
one. After releasing the lock, worker A completed the event once, wrote one
successful receipt/log, invalidated only its target cache row and preserved the
sentinel. This confirms an unexpired active lease excludes another claimant for
the same event. Expired-lease takeover while the original handler remains live,
crash after an external side effect, runtime-role policy and provider recovery
remain open. CAP-040 stays partial and capability counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-claim-exclusion.json).

### CAP-040 same-event timeout and retry addendum — 11 October 2026

One synthetic CRISP event timed out while its cache write was blocked, returned
to pending with one retry, then completed successfully on its second delivery
attempt. The timeout and success logs were both retained; the target cache row
was invalidated and its sentinel remained valid. This verifies timeout retry
for one idempotent cache effect. The handler deadline expired before the
planned second worker started, so this timeout/retry probe did not test stale
lease takeover; the later CAP-040 stale-lease addendum covers that case. Crash
after side effect, other handler types, runtime-role policy and provider
recovery remain open. CAP-040 stays partial and capability counts do not
change. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json).

### CAP-040 same-event expired-lease takeover addendum — 11 October 2026

With worker A's synthetic CRISP cache update blocked, the lease was expired and
worker B reclaimed the same event before A's handler returned. PostgreSQL
observed two blocked handler updates, followed by two successful handler logs.
Worker A lost completion ownership; worker B completed the event and performed
the single target invalidation while the sentinel stayed valid. This confirms
reclaim and duplicate invocation for one idempotent cache effect. It does not
prove safety for other handler types or external side effects; crash-after-effect
recovery, runtime-role policy, stale-worker lease-loss reporting semantics and
provider recovery remain open. Worker A's CLI counted one failure although B
completed the event; whether CLI/metrics should label lease loss separately
remains a follow-up. CAP-040 stays partial and capability counts do not change.
[Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json).

### CAP-040 stale-worker reporting correction — 11 October 2026

The event bus now returns a separate `lease_lost` count, skips stale-owner retry
updates, and preserves `failed` for handler errors/timeouts. The one-shot CLI
returns success when lease loss is the only outcome; persistent workers back off
instead of immediately polling again. The focused lease-loss regression
function passed by direct invocation, and modified Python files compile; the
host has no pytest installation, so the regular test runner did not execute.
The earlier concurrent takeover evidence remains historical evidence of the old
counter output; it was not rewritten. A live rerun is still useful confirmation.
This reporting fix does not expand handler-effect or exactly-once guarantees;
CAP-040 remains partial. [Implementation details](event-handler-concurrency.md).

### CAP-040 crash after handler side effect addendum — 11 October 2026

A synthetic crash worker exited after the allowlisted CRISP cache handler
committed its effect but before the delivery receipt update. The event remained
processing with a processing receipt at attempt one and no handler log. A
guarded lease expiry enabled the real event CLI to reclaim it. The handler ran
again and completed attempt two; the second cache update changed zero rows. The
target remained invalidated once and the sentinel remained valid. This covers
retry after a lost receipt for one idempotent local cache effect, not exactly-once
effects for other handlers. The fixture database is stopped and its volumes are
retained. CAP-040 remains partial. [Machine evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json).

### CAP-047 registered handler replay-risk inventory — 11 October 2026

Inspected all five effective event registrations and their allowlisted callable
implementations. The metric and CRISP cache handlers have isolated concurrent
and crash/retry evidence. The sensor anomaly handler can write alert/claim rows,
emit another platform event, notify email/Directus and dispatch configured
actuator commands; existing cooldown checks are not per-event idempotency
receipts. The stale-data and threshold handlers share best-effort webhook and
Directus sends without durable notification receipts, so they can duplicate a
successful send or mark delivery successful after a caught send failure. No
endpoint or actuator was contacted. Durable notification/idempotency contracts,
anomaly crash recovery, runtime-role policy and remaining provider recovery
remain open. This source audit closes only the handler-inventory checklist item;
CAP-047 and CAP-040 remain partial and capability counts do not change.
[Details](event-handler-concurrency.md).

### CAP-047 notification outbox implementation — 11 October 2026

Added migration `375_notification_outbox.sql` and a PostgreSQL delivery adapter
for the event-driven webhook/Directus notification paths. The handler uses the
platform event UUID with channel and destination identity so event redelivery
does not create another queue row. Delivery attempts have committed leases,
bounded retry/backoff, stable receiver idempotency headers, dead-letter state,
and actor/reason audit for replay or disposal. The event worker now dispatches
the queue; provider-disabled rows remain unclaimed. URLs and credentials stay
in worker environment variables. Source compilation and whitespace checks pass.
The migration was applied twice in a fresh internal-only scratch DB. All nine
fake-transport checks passed, including stable source event-id propagation through
the handler, duplicate-handler enqueue suppression, provider pause, retry/backoff,
crash-after-send reclaim with the same idempotency key, CLI help, and operator
replay/disposal audit. Six fake requests were recorded; no real endpoint was
contacted. The candidate and legacy DBs were not migrated. [Implementation report](event-handler-concurrency.md); [machine evidence](builds/2026-10-11-recovery/notification-outbox-check.json).
Real provider acceptance, outbox retention/capacity, recovery coverage for other
event-handler paths and broader CAP-040 acceptance remain partial; capability
counts do not change.

### CAP-047 notification outbox capacity reporting — 11 October 2026

The read-only notification stats command now includes total/open row counts,
oldest open age, and combined table/index bytes for queue, attempt, and operator
audit relations. Default advisory thresholds are 256 MiB warning and 512 MiB
critical, configurable in Compose or the worker environment. Thresholds do not
block enqueue/delivery and the implementation does not prune rows. The interim
retention rule keeps all rows and evidence until an owner approves temporal
retention and archive semantics; active and undisposed work is never eligible
for deletion. The capacity query and critical-state calculation passed in an
isolated rerun. This closes capacity visibility only; provider acceptance,
retention-period approval and broader recovery remain open. The scoped sensor
anomaly event-worker recovery now has separate evidence below. [Policy](notification-outbox-operations.md); [machine evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json).

### CAP-047 dynamic retention and legal-hold source contract — 15 October 2026

The owner selected runtime-configurable retention windows and legal-hold rules;
no durations are embedded. Migration 401 adds nullable policy windows, draft
and approved states, and an append-only audited record-hold ledger. Event
cleanup now requires one approved active global event policy, checks active
holds and incomplete delivery/disposition state, and remains disabled by
default. Generic cleanup also requires an explicit approval and feature gate.
The candidate has now applied migrations 401 and 402 after a fresh checkpoint and isolated restore rehearsal. No policy is configured. Ninety-four
focused source/unit tests and four subtests
pass, including the legal-hold skip path. Ordered migration 401 and synthetic
PostgreSQL assertions verify policy demotion, audited immutable holds, and
hold-aware generic/event cleanup; acceptance corrected an undersized action
column. Those earlier isolated checks did not access the candidate or legacy database. The later candidate schema rollout changed no policy rows; no MAN-CAP status or count changes. Pruning remains disabled until approved policy data and accountable operators are in place ([migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql);
[database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json);
[source evidence](builds/2026-10-15-recovery/retention-policy-source-checks.json);
[operations](retention-policy-operations.md)).

The general EventBus cleanup path now rejects nonpositive retention windows
and preserves an aged parent event while its dead-letter disposition remains
pending. Fifteen focused durability tests pass. This avoids orphaning an
operator-actionable dead letter; it does not change notification-outbox pruning
(none is implemented) or close owner-approved retention periods. [Evidence](builds/2026-10-14-recovery/event-cleanup-pending-disposition.json).

**15 October 2026 retention scope metadata (CAP-047):** migration 402 adds
optional owner-defined jurisdiction and purpose codes with no defaults or
legal interpretation. Approval cannot enable auto-enforcement for unresolved
scope; the generic sweeper skips scoped policies, rejects overlapping active
scopes, and event cleanup refuses ambiguous global policy state. Sixty-two
focused data-governance/EventBus tests and four subtests pass. The ordered
migration acceptance for 401 and 402 passes on an internal-only synthetic
PostgreSQL fixture. The candidate now has both migrations applied after a fresh
restore-rehearsed checkpoint; no periods, scoped policies, or holds are active,
and named MAN-CAP checks remain unaccepted. The generic sweeper now explicitly
skips the notification outbox, attempts, and operator audit until an
archive/idempotency workflow exists; dry runs do not mark policies as enforced
([source evidence](builds/2026-10-16-recovery/retention-notification-sweeper-guard.json)).
Retention enforcement also rejects missing, oversized, or non-string actors and
non-boolean dry-run modes before opening PostgreSQL. This source guard does not
enable pruning or change capability status
([migration](../../schemas/postgres/402_retention_policy_scope_codes.sql);
[operations](retention-policy-operations.md);
[evidence](builds/2026-10-15-recovery/retention-policy-disposable.json);
[candidate rollout](builds/2026-10-15-recovery/candidate-retention-401-402-rollout.json)).

The same pre-database validation now applies to policy creation, approval,
retirement, and legal-hold placement/release. Actor values are trimmed and
bounded to the persisted 200-character columns; blank or non-string reasons
are rejected before a cursor opens. Fifty-two focused tests and 49 subcases pass;
retention periods remain unconfigured and MAN-CAP acceptance is unchanged
([evidence](builds/2026-10-16-recovery/retention-audit-input-validation.json)).

### CAP-047 sensor anomaly crash/replay — 11 October 2026

Migration `376_sensor_anomaly_delivery.sql` adds per-reading/rule effect receipts,
enables the email outbox channel, and permits the existing `requires_approval`
actuation state. The event handler now evaluates only the reading referenced by
its source event; its alert, optional draft claim, ingestion log, webhook/Directus/
email intents keyed to the actual downstream event ID, actuator approval record,
and downstream `sensor_alert` event share the database transaction. In an
internal-only synthetic fixture, the actual EventBus worker exited with code 86
after handler commit and before receipt acknowledgement. A replacement worker
reclaimed the expired source-event lease and completed attempt two; the event
receipt moved from `processing` to `success` with one success log. The retry
preserved one alert, draft claim, effect receipt, three notification intents,
downstream event, ingestion log, and critical actuation record. Critical work
remained unapproved with `human_approval_required=true`. Email formatting used a
fake SMTP transport; no provider endpoint or actuator was contacted. Migration
376 was re-applied twice successfully. The fixture used only the relevant schema
set, no ports or egress, and its volume was retained after shutdown. [Details](sensor-anomaly-delivery.md);
[machine evidence](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json).

This closes one scoped sensor anomaly event-worker crash/retry check. Provider
acceptance, operator approval policy, retention ownership, recovery coverage for
additional handlers/runtime conditions and broader CAP-040 acceptance remain
open. CAP-047 and Batch 2 remain partial; capability counts do not change.

### Batch 2 PostgreSQL runtime-role boundary — 11 October 2026

Added an opt-in bootstrap for a distinct, non-owner application role. The role
has no superuser, role/database creation, replication, RLS bypass, or inherited
membership privileges; it can connect only to its configured database, use the
public schema, and perform table DML plus sequence access. Persistent DDL,
`CREATE ROLE`, `CREATE DATABASE`, admin-role switching, and connections to
unrelated databases were denied in an internal-only synthetic PostgreSQL
fixture. Provisioning passed twice, including default grants for a table created
after provisioning. The scratch container is stopped and its volume retained;
the running candidate and legacy database were not modified. [Policy](runtime-role-policy.md);
[machine evidence](builds/2026-10-11-recovery/runtime-role-isolation.json).

This validates the role primitive on a populated restore as well. A fresh copy
of the populated legacy archive accepted the opt-in role twice. The native
`public_locations()` query returned two governed public rows, a PostGIS function
returned SRID 4326, and an admin-created synthetic table supported runtime DML
and sequence use. Persistent DDL, role/database creation, admin-role switching,
and connections to the other two databases were denied. The public query emitted
only a count, and no restored domain rows were changed. [Populated-restore evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json).

The candidate still uses its owner-backed credential. Legacy Directus and
Metabase still use the `kokonut` superuser in the legacy Compose file and are not
included in the candidate runtime-role overlay; separate service roles and
grants remain open. Full domain workflow acceptance is also open. No capability
count changes; Batch 2 remains partial.

### CAP-007 candidate analytics-source ACL review — 11 October 2026

Before migrations 371–379, the candidate was reviewed in a read-only
database session. `kokonut` was its only login/superuser role; no runtime,
analytics-source, or Metabase metadata role existed, and migration 377's
reporting schema/views were absent. `PUBLIC` could connect to the application
database and create temporary objects. No roles, grants, schemas, source, or
data were changed by that review. Migrations 371–379 have since been applied;
the reporting views and the verified `kokonut_analytics_ro` login now exist.
The candidate-only Metabase metadata database/login are also provisioned, with
real-login metadata CREATE success and application-database denial. Metabase
is healthy under the explicit profile with saved-credential encryption enabled;
the default manifest still lists only `database` and `app`, and PostgreSQL has
no host port. It retains the built-in H2 demo with 39 generic cards and one dashboard, plus
a separate read-only PostgreSQL source filtered to the three approved
`kokonut_reporting` views and three Kokonut cards in a dedicated dashboard.
The Metabase card SQL now passes populated output parity on an isolated copy;
the active candidate remains empty and CAP-007 acceptance remains open. [Card
parity evidence](builds/2026-10-11-recovery/metabase-card-output-parity.json);
[ACL evidence](builds/2026-10-11-recovery/candidate-reporting-acl-review.json);
[migration evidence](builds/2026-10-11-recovery/candidate-migration-apply.json);
[analytics role evidence](builds/2026-10-11-recovery/candidate-analytics-role.json);
[profile evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json);
[profile contract](metabase-kernel-profile.md).

The encrypted metadata backup also passes a full restore in a matching,
network-disabled disposable PostGIS 16 target. Source/card/dashboard/user counts
and all dashboard placements match the live candidate; 14 H2 virtual tiles
remain alongside 25 saved-card placements. The target was removed and live
metadata was unchanged. Card-output parity also passed on an isolated populated
copy. [Restore
manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json).

### CAP-053 source-audit update — 13 October 2026

The repository-owned Field Collector consumer audit found and fixed an
unguarded farm-activity timestamp lookup in
`services/analytics/process_interfaces.py`. Other repository-owned report,
export, metric, analytics, process-trace, Gateway, hook, and seeded dashboard
consumers use the shared eligibility predicate. This source-only update does
not close CAP-053: external/operator-edited dashboard parity, populated output
validation, real OIDC, browser offline/withdrawal acceptance, disposition,
retention, and RLS remain open. Migration 389 adds source-level tenant-aware
grant checks to the database write triggers. The actual 387–389 migrations,
388–389 replay, CLI membership/share lifecycle, and legacy-grant conversion
passed in disposable PostgreSQL. The subsequent clean full-schema replay
applied all 380 ordered migrations with zero pending or failed and registered
all 11 relevant 384–385–389 activity/workflow triggers; candidate rollout and
populated/archive replay remain open
([replay evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
See the [consumer audit](field-collector-downstream-source-audit.md).

### CAP-053 aggregate operator preflight — 13 October 2026

The ownership preflight now reports database-wide counts of enabled and
disabled operator identities and active organization memberships, plus
location-scoped active grants split into legacy, tenant-qualified, currently
authorized, and invalid counts. It evaluates tenant-qualified grants with the
shared `operator_scope_grant_allows` predicate and returns aggregate counts
without operator identity attributes or raw IDs. Five focused checks and Ruff
passed; actual migrations 388 and 391 passed on a schema-targeted disposable
PostgreSQL fixture with exact synthetic counts and verified zero-row cleanup
([evidence](builds/2026-10-13-recovery/tenant-preflight-operator-access-disposable.json)).
This helps quantify the operator affiliation migration but does not map real
operators to organizations or convert legacy grants. CAP-053 remains partial;
worker integration, direct-database isolation, populated production lineage,
retention/disposition, and RLS remain open.

**14 October 2026 signed OIDC operator tenant context (CAP-053):** migration
394 makes PostgreSQL validate the active session, enabled identity,
tenant-qualified grant, active operator membership, and current location owner
or unexpired share before signing context for the current backend/transaction.
Additional scopes must resolve to the same tenant. The shared context accessor
verifies the signature; diagnostic GUC values and tampered payloads do not
grant rows. Disposable PostgreSQL 16 replay and forced-RLS acceptance passed
owner/shared access, denials, context cleanup, share revocation, and concurrent
grant-revocation locking. Twenty focused tenant/OIDC tests passed (one skipped);
Ruff and Python compilation passed. This does not complete CAP-053 or enable
RLS: migration 395 now removes session-table access from the general runtime
role and gives OIDC a separate bounded auth connection. Its isolated forced-RLS
acceptance verifies read/write/mint denial for the runtime role and bounded
session lifecycle for auth ([evidence](builds/2026-10-14-recovery/operator-session-role-disposable.json)).
Gateway API-key context, workers, Directus/views, broad runtime DML on other
public tables, and candidate rollout remain open. Candidate stays at
migration 391 under OFU-18.

**14 October 2026 runtime mobile credential grants (CAP-053):** the app runtime
now receives an explicit column allowlist on `mobile_device` and
`mobile_device_enrollment`. It cannot read device-token, push, or enrollment
hashes, use `SELECT *` across those tables, insert/delete devices, delete
enrollments, or edit enrollment hashes. Safe handler SQL for device reads,
enrollment issue/revoke and last-seen updates passed in a network-isolated
PostgreSQL 16 role check. The runtime login also called the
bounded token resolver and one-time enrollment redemption successfully. The
  focused mobile/auth/migration set passed 148 tests; Ruff and 507-source
migration validation passed. This check did not run the HTTP handlers through
the runtime login and does not close DML on other public tables,
database-verified Gateway capabilities, workers, Directus/views,
candidate rollout, or RLS ([policy](runtime-role-policy.md); [evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json)).

**14 October 2026 bounded device revocation (CAP-053):** migration 398 moves
status/token mutation behind a fixed database function that revalidates the
exact API-key, capability, or OIDC-session scope under forced RLS. Runtime
direct UPDATE is limited to telemetry columns. Migration 399 and the bootstrap
restore narrow security-schema/function access after a DB-only restore. The
exact pre-398 checkpoint restored, migrations 398–399 replayed, and synthetic
forced-RLS checks passed owner success, cross-tenant hiding, denial, token
clearing, and transaction cleanup. At that rollout the candidate had 390 applied schemas
through 399 and health 200, while application RLS remained disabled. It still
runs as the `kokonut` superuser because runtime credentials are not provisioned;
authenticated HTTP under the dedicated role remains open. This does not accept
CAP-053 or any MAN-CAP check ([evidence](builds/2026-10-14-recovery/candidate-migration-398-399-device-revocation.json)).

**14 October 2026 database-only restore owner repair (CAP-053 implementation
follow-up):** migration 400 recreates six bounded NOLOGIN function-owner roles,
restores their exact grants and SECURITY DEFINER ownership, and restores
runtime/operator-auth security-schema lookup after a database-only restore.
The runtime bootstrap now fails closed on unexpected function ownership. A
restored pre-398 clone replayed migrations 398–400; a separate synthetic
owner/ACL-loss fixture passed forced-RLS revocation and operator-auth checks.
The populated-clone bootstrap did not complete, so full restore acceptance is
still open. The local candidate has 391 schemas through 400, health 200, and no
application-table RLS; it still uses the `kokonut` superuser. No MAN-CAP check
is accepted ([evidence](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json)).

### CAP-040/047 worker source inspection addendum — 14 October 2026

The worker review now has a deterministic static import closure over all 12
scheduled modules and five allowlisted event-handler modules, plus a direct SQL
call-site inventory and direct-call graph for the 69 local source files. The
call graph follows 31 entry functions through 281 function memberships and 413
statically resolved call edges across 17 operations; dynamic dispatch,
callbacks and external effects remain open. The SQL inventory records
196 execution sites: 166 literal statement fingerprints, 30 composed or
variable statements, and three unknown statement kinds. The scanner infers
fixed local query prefixes and savepoint-control statements; the remaining
unknowns are generic adapter calls that accept SQL from their callers. The
output omits SQL text and values; regex-derived relation names are review hints
only. This adds source navigation and identifies the remaining function-level effect targets;
the 30 dynamic sites have source-pattern review, and a source regression traces
the generic wrappers currently used by the worker closure. It does not
establish full function reachability, complete effects, worker identity,
grants, or tenant isolation. CAP-040 and CAP-047 remain partial and capability
counts do not change ([source closure](worker-source-closure.json); [SQL inventory](worker-sql-inventory.json); [evidence](builds/2026-10-14-recovery/worker-sql-inventory-check.json)).

### CAP-040/047 worker effect source index — 15 October 2026

A deterministic inventory now scans the current worker function graph for
high-confidence direct effect calls. It records 43 unique source locations
across HTTP, email delivery, process lifecycle, EVM RPC/client setup,
filesystem, and dynamic import boundaries (49 operation/site memberships)
across 20 roots.
The graph overapproximates mutually exclusive CLI branches and can miss
provider callbacks; it does not establish runtime behavior, authorization,
replay safety, or tenant context. The graph follows the EventBus process target
to its local resolver; the callback trace records the validator, dynamic
import, and five allowlisted handlers, but does not verify persisted dispatch
configuration.
Worker identity, role/context, and live recovery gates remain open, so no
MAN-CAP status or count changes ([inventory](worker-effect-inventory.json);
[worker map](worker-operation-map.md)).

### CAP-047 scheduler template preflight — 15 October 2026

A source-only comparison covers all 15 shared JobSpecs. Thirteen default
argument lists satisfy the current Kernel command contracts; sensor and
climate defaults are rejected for missing source/location inputs. Remote
sensing is optional and runs one due job at a time, with a validated batch
limit of 1–10 (the JobSpec defaults to one). ClickHouse projection remains
limited to one bounded `--run-once` batch; manual list, replay, disposal, and
reconcile actions are rejected. No task or provider was activated. This does
not inspect persisted tasks, Prefect state, provider outcomes, or grant boundaries, so it is inventory
progress and not scheduler acceptance ([JobSpec inventory](worker-job-contract-inventory.json);
[projection evidence](builds/2026-10-15-recovery/projection-job-contract.json);
[remote-sensing evidence](builds/2026-10-15-recovery/remote-sensing-job-contract.json)).

### CAP-047 authenticated backup object transport — 15 October 2026

Local encrypted checkpoint manifests are now authenticated with a
PBKDF2-derived HMAC. The optional S3/R2 transport stages objects under a unique
prefix, verifies remote bytes, and uses a conditional create-only manifest as
the completion marker. Downloads verify the authenticated manifest and
artifact hashes into a new private directory. Twenty-eight focused tests use
fake Compose and object-store adapters; no R2 credentials or objects were
accessed, and no remote delete or lifecycle action is implemented. This is
recovery tooling evidence only; provider backup/restore and MAN-CAP-047 remain
open ([contract](backup-object-storage.md); [tests](../../tests/test_backup_remote.py); [offline evidence](builds/2026-10-15-recovery/backup-object-transport-offline.json)).

### CAP-001/047 operator report-review tenant-context regression — 15 October 2026

Five direct service tests now verify that the report queue and detail readers
establish operator tenant context on the same connection before their scoped
queries, retain location-qualified grant rechecks, stop before querying when
tenant context is denied, and roll back/close on denial or oversized payload.
These use synthetic connections and do not execute PostgreSQL's signed context
functions. Live identity/database-role behavior, populated report parity,
application RLS, and all named MAN-CAP acceptances remain open; capability
status and counts do not change
([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)).

### CAP-001/047 registered report source map — 15 October 2026

The source inventory links all 94 registered report types to their defining
callable, source line, and declared inputs across 15 modules. All declare a
`location_id` parameter and 93 declare a period boundary, but this does not
prove those values constrain every query or that output measures match domain
expectations. The AST-only inventory and freshness checks pass without
executing report code. Populated output parity and owner selection remain open;
capability status and counts do not change
([inventory](report-generator-source-inventory.json); [evidence](builds/2026-10-15-recovery/report-generator-source-inventory.json)).

### Phase 8 optional ARM64 service/profile coverage — 16 October 2026

The profile planner and explicit Compose overlays now cover HTTP sensors,
Directus, and ClickHouse analytics on ARM64 in addition to the previously
verified core, proxy, OIDC/ZITADEL, gRPC, and MQTT selections. A ClickHouse-
enabled Kernel image built under QEMU and passed a no-network ARM64 import of
`clickhouse-connect`; the pinned ClickHouse image reports version 25.8.28.1.
The pinned Directus image's Node runtime reports `arm64` and version 22.23.1.
All selected services in the affected Compose configurations resolve to
`linux/arm64`, and 27 focused planner/Compose tests pass. This verifies code and
image compatibility only. No live ClickHouse profile, projection parity,
Directus bootstrap/hooks/authorization, or physical Raspberry Pi behavior was
tested; capability row statuses and MAN-CAP acceptance counts are unchanged
([evidence](builds/2026-10-16-recovery/kernel-arm64-optional-profiles.json)).
