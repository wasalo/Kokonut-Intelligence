# Code-first refactor execution plan

**Updated:** 16 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68
**Batch base (last pushed head before this work):** `526857998c2bb6ca11eb9efd46113cf42ddde1ea` on PR #68.
**Current local batch:** Scheduled sensor pull now has a source contract across JobSpec dispatch, disabled schedule planning, CLI validation, and the driver registry. Each run needs one location UUID and one enabled sensor driver-instance UUID bound to that location; the code-installed pull driver must opt in. The built-in CSV pull is bounded to 100 sources/10,000 records, MQTT remains event-driven, and canonical reading/audit/event/outbox changes are transactional and idempotent by sensor timestamp/value. The focused sensor/scheduler/Prefect/inventory suite passes 162 tests, Ruff passes, and all eight generated worker inventory checks pass. No provider, configured driver instance, database, or external schedule was used or activated. The latest pushed head remains `526857998c2bb6ca11eb9efd46113cf42ddde1ea` (Security #94 passed; CI #370 was last observed pending). The checklist is now 419 checked / 20 open; the capability matrix remains at 66 rows with zero accepted MAN-CAP checks. Candidate remains through migration 403; signed worker context, configured source parity, candidate rollout, and production acceptance remain open.

This plan orders the remaining work so repository changes and reproducible
software checks happen before decisions that require production owners, live
provider accounts, populated reference data, or external infrastructure. It is
an execution map for the existing open items in [batches.md](batches.md), not a
second capability acceptance ledger. Keep the capability matrix's named
MAN-CAP checks open until each has its own retained evidence.

## Current accounting

The current local outbox batch gives canonical ingestion failures a typed
`OutboxEnqueueError` and rolls back or propagates it through weather, RPC,
remote-sensing provider dispatch, subgraph/EAS, and Gnosis transaction owners.
Nine producer helpers now have paired failure and connection-free fallback
regressions; 158 focused tests pass across outbox, weather, remote-sensing, and
attestation contracts. This does not close live provider/PostgreSQL recovery
acceptance ([evidence](builds/2026-10-16-recovery/ingestion-outbox-failure-atomicity.json)).

- ClickHouse outbox failures now use capped exponential retry delays (60 seconds
  through one hour), including client-setup failures; the retry schedule is
  derived from the persisted attempt count and retains the existing eight-try
  dead-letter bound and stable insertion token. Fifty-seven focused outbox,
  failure-injection, and producer tests pass with mocked boundaries. Live
  PostgreSQL/ClickHouse outage acceptance remains open
  ([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json)).

- The manual remote-sensing CSV path now requires a canonical location UUID or
  explicit `--all-locations`. Single-location SQL reads plots only within the
  selected location; every row must match plot/farm lineage, and accepted-row
  idempotency hashes use canonical IDs. Multi-location imports remain available
  behind the explicit aggregate selector. Fifty-five focused scope, outbox,
  smoke, and remote-sensing checks pass. This remains CLI/query-level scope,
  not operator authorization or RLS ([evidence](builds/2026-10-16-recovery/remote-sensing-csv-location-scope.json)).
- The weather-forecast producer now protects each location's complete forecast
  insert batch with a savepoint, propagates row errors for rollback, records
  success/failure audit entries on the same PostgreSQL transaction, and queues
  only successful batches for ClickHouse projection. Outbox enqueue failure
  propagates and closes without commit. Six new mocked regressions plus the
  forecast, scope, and shared producer suites pass 36 tests; Ruff, compilation,
  and diff checks pass. No provider or database was contacted, so live delivery
  and PostgreSQL transaction acceptance remain
  open ([evidence](builds/2026-10-16-recovery/weather-forecast-atomic-projection.json)).
- The execution checklist has **419 checked and 20 open items (439 total)**,
  counting nested implementation subtasks. The open items cover live provider
  setup, digests, browser/runtime acceptance, tenant and Directus boundaries,
  populated report parity, policy activation, external delivery,
  long-duration recovery, and release/cutover gates.
- An earlier batch at `4d46800` made the owner-selected
  Gateway-only farm-activity boundary explicit in the optional Directus role
  seed. Twenty-four focused tests and fresh Directus 12.1.1 runtime apply,
  replay, health, and login checks pass; zero of the nine managed policies
  retain farm-activity grants, while 14 unrelated curated permissions remain.
  Unknown custom policy rows are preserved. The candidate and legacy databases
  were not touched. This adds no accepted capability: the matrix remains 66
  rows (55 baseline-retained, 7 deployed, 4 prepared), with zero accepted
  MAN-CAP checks.
- Since the previous `8c7a053` accounting, commit `a1f45da` added the native
  Gateway farm-activity API and migration 404, with 13 focused service/HTTP/
  policy tests and 11 disposable PostgreSQL 16 checks passing. Commit `359e1d5`
  then added and pushed the separate operator-console panel; six focused console
  contract checks pass, including inline JavaScript syntax validation. Migration
  404 has not been applied to the candidate, and no MAN-CAP check was accepted.
  Security #66 passed and CI #342 failed on a seed UPDATE that migration 404
  correctly rejects. The local fix embeds immutable lineage in pilot INSERTs
  and removes the later alignment UPDATE; 16 focused source checks passed, then
  the fix was included in a subsequent push. The later pushes also add anomaly
  transaction boundaries and the signed worker-context adapter described in
  the current status above.
- When this local batch began, the remote PR head was
  [`6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f`](https://github.com/wasalo/Kokonut-Intelligence/commit/6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f)
  on `feat/mobile-offline-acceptance`, PR #68. CI #336 was pending and
  Security #60 passed. The pushed batch includes ARM64 optional-profile checks
  and KGP worker restart/lease recovery with guild/domain/task projection and
  simulated reorg rebuild. The current local extension replays all 394 ordered
  schema sources, adds source-linked governance target/selector/guild-scope
  policy projections, and verifies seven-event canonical replay and rebuild on
  a simulated chain-tip change. The same disposable check verifies PostgreSQL
  restart reconnect and lease reclaim against the real cursor table. A fresh
  encrypted candidate checkpoint was restore-rehearsed before migration 403
  was applied; the candidate now has 394 applied schemas and zero pending,
  health 200, and protected-route 401. Its app image was not rebuilt, the policy
  table is empty, and RLS remains off. These synthetic rows and stubbed chain
  behavior use no seed, live RPC, or provider calls. Other event types, real
  chain reorgs, ARM64 hardware behavior, and live KGP RPC/event processing remain
  unverified. This batch is now pushed as `8c7a053`; CI #337 and Security #61
  are running. Earlier owner, tenant,
  report, retention, Directus, and worker-boundary work remains in the PR.
- The report generator now rejects read-only escapes through transaction
  settings, autocommit, and `cursor.connection`. Nine focused tests and an
  isolated PostgreSQL check pass; the latter proved rejected calculations
  leave no rows and the approved writer can still create the draft afterward.
  The database role remains capable of writes outside this guarded path, and
  populated report output parity remains open. An AST-only inventory now maps
  all 94 registered generators to source locations and declared inputs. A
  second inventory maps 177 direct query sites: 126 show a bound location-scope
  signal, including attestation queries bound by `subject_type='location'` and
  `subject_id`. Conditional, mixed, no-signal, and helper-only report paths
  still need scope-contract review. Neither inventory proves tenant isolation
  or semantic parity. Direct queue/detail service tests
  also verify the OIDC report-review tenant-context and cleanup contract.
- The scheduler now obtains a fresh bounded-timeout connection for each tick
  while preserving one worker ID. Ten focused scheduler tests pass. An earlier
  disposable PostgreSQL stop/start check used a stub engine; the current check
  replays scheduler/event migrations and uses the real SchedulerEngine to claim,
  launch, and complete bounded `services.events --process --batch-size 10`
  tasks before and after restart. A separate probe kills the real engine after
  it commits a due task lease but before subprocess dispatch; forced expiry in
  the disposable database lets a replacement worker mark the first run failed
  and finish the task as attempt two. It uses an empty synthetic EventBus queue
  and no provider. This covers claim-to-dispatch recovery only; a crash after
  task effects, full-ledger parity, and long-duration recovery remain open
  ([evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json)).
- A local EventBus worker slice now creates and closes its bus per iteration,
  recreates bounded-timeout notification connections, and retries logged
  failures. Twenty focused event-worker/EventBus tests pass with Ruff and
  compilation. A disposable PostgreSQL stop/start check replays migrations
  116, 165, and 375 and confirms the actual worker completes synthetic
  events before and after restart under one worker identity while invoking the
  real allowlisted alert-notification child handler. A fake webhook bound to
  `127.0.0.1` returned one synthetic `503`; the outbox recorded retryable/failed
  and then recovered to succeeded/succeeded after retry with the same
  idempotency key. The post-restart notification also succeeded with a distinct
  ID. A third request was received while its worker awaited the response; after
  the worker was killed and the fixture expired its lease, a replacement
  reclaimed the notification with attempt history `lease_lost,succeeded` and
  reused the idempotency key. No remote provider was contacted. Full
  migration-ledger parity, real provider delivery, production-duration lease
  recovery, and long-duration recovery remain open
  ([evidence](builds/2026-10-16-recovery/event-worker-postgres-reconnect.json)).
- A local KGP indexer change reconnects with a five-second timeout for each
  scan cycle, preserving lease ownership/reclaim semantics while containing
  rollback and failure-recording errors on a broken database connection.
  Fifteen focused KGP/guild tests pass. The current disposable check replays
  all 393 ordered PostgreSQL schema sources in separate transactions and
  records checksums. The real indexer processes synthetic `GuildCreated`,
  `DomainCreated`, and `TaskCreated` logs, confirms each projection links to its
  source event, and verifies canonical replay is idempotent. A stubbed tip
  change exercises reorg reset: all three events become noncanonical, dependent
  domain/task projections are removed, and retaining the configured guild key
  lets the replacement branch rebuild all three projections. The same check
  verifies PostgreSQL restart reconnect and expired-lease reclaim against the
  real cursor table. Deployment/cursor/contract/guild rows are synthetic; no
  seed, live RPC, or provider call is made. Other event types, real chain
  reorgs, production-duration lease reclaim, and live event recovery remain
  open
  ([evidence](builds/2026-10-16-recovery/kgp-worker-postgres-reconnect.json)).
- Directus source permissions now align with organization/location grants: the
  seed removes its obsolete user-level location filter while preserving other
  predicates, the grant hook covers `revenue_event`, and the isolated API
  fixture prepares a synthetic mapped operator. Five focused Python checks,
  61 extension tests, the TypeScript build, and a disposable PostgreSQL 16 SQL
  replay/fail-closed check pass. Pinned-image Field Note own/cross reads pass
  through the loaded tenant hook. Field Worker `farm_activity` permissions are
  hidden by the unlicensed Directus custom-permission boundary, so that API
  slice remains denied; license versus Gateway-only operational access is an
  open product decision. Role/field/relationship and hook-dispatch parity
  remain open. This slice is included in the latest pushed head ([evidence](builds/2026-10-15-recovery/directus-org-location-permission-contract.json)).
- The capability matrix contains 66 capabilities: 55 baseline-retained, 7
  deployed, and 4 prepared. None of the 66 named MAN-CAP checks is accepted.
- The local candidate has 394 applied schemas through migration 403, six applied
  seed ledger entries, 115 pending source migrations (all are unselected seeds),
  zero failed ledger rows, and application-table RLS is disabled. Migration 403's
  governance policy table is empty; its app image was not rebuilt. The five
  owner-approved reference catalogs and migrations 401–402 are applied; other
  seed files remain held. It still uses the `kokonut` superuser because a separate
  runtime credential is not provisioned. The seed approval does not authorize
  RLS or production import.
- The owner selected self-hosted ZITADEL, organization/location authorization,
  Kokonut Network operation of Genesis, Seeds, Adelphi, Terra Viva, and V1,
  reference catalogs only with pilot rows held, USA and Dominican Republic as
  retention jurisdictions, and a 24-hour recovery target. Retention windows and
  legal-hold rules must be runtime-configurable; no durations are hardcoded or
  selected now. Policy configuration, approval roles, and hold operations are
  deployment gates. ZITADEL host/client settings, remaining operator/location
  mapping, R2 credentials, and external alert routing remain open.
- ARM64 Buildx/QEMU acceptance now exercises all 393 current schema files
  through migration 402, with matching logical-restore fingerprints, zero
  pending migrations, PostGIS geometry, health, protected-route denial,
  database-restart health recovery, and explicit Compose recovery after an app
  SIGKILL. The current refresh had no explicit CPU/memory caps and started the
  app before migrations, so workers logged missing-schema errors during
  bootstrap. This does not certify physical Raspberry Pi performance,
  power/storage/network failure, or production failover ([evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-402.json)).
  The default, OIDC, gRPC, and MQTT application targets also build for ARM64;
  network-disabled QEMU checks import their runtime/stubs, the pinned Mosquitto
  binary reports `aarch64`, and merged planner configs select ARM64 for every
  enabled service. No gRPC/PostgreSQL server or MQTT traffic/mTLS was tested
  ([transport evidence](builds/2026-10-16-recovery/kernel-arm64-transport-smokes.json)).
- Encrypted checkpoints now authenticate their manifests and have an optional
  S3/R2-compatible transfer CLI. Fake-store checks cover staged byte verification,
  create-only completion, idempotency, tamper rejection, and private no-overwrite
  restore. No live credentials or remote objects were used; R2 acceptance remains
  open ([contract](backup-object-storage.md); [offline evidence](builds/2026-10-15-recovery/backup-object-transport-offline.json)).

## Selected open gates: code batches before owner inputs

The owner selected the remaining open items in `batches.md` on 14 October.
On 15 October the owner supplied additional product/deployment decisions; see
the record below. Work through code batches first, then close only the live
provider, populated-data, and operational gates that cannot be established from
the repository.

## Owner decisions recorded 15 October 2026

- **Tenant ownership:** Kokonut Genesis, Kokonut Seeds, Kokonut Adelphi,
  Kokonut Terra Viva, and Kokonut V1 are operated by Kokonut Network. Adelphi
  and Genesis remain confirmed exclusive. No sharing was specified for the
  other three, so do not create shared grants without a later explicit mapping.
  The four existing farms have owner-held data for post-build ingestion;
  Terra Viva is still in design. This is an operating-tenant mapping, not a
  claim about legal land title. Other locations remain unassigned until mapped.
- **Tenant model:** Directus-compatible access follows organization/location
  grants. The Gateway remains the authorization authority; Directus parity
  must consume the same grant model.
- **Reports/providers:** port all repository-verified Kokonut report, dashboard,
  provider, and scheduled-job capabilities first. The owner will decide what to
  retain, remove, or improve after review. Validate semantic report output
  after the four farms' data is ingested. The archive's generic e-commerce
  sample-H2 Metabase cards are not to be mislabeled as Kokonut product assets.
- **R2:** production account `7219a605e3c2144a30987e20fd4cf397`, endpoint
  `https://7219a605e3c2144a30987e20fd4cf397.r2.cloudflarestorage.com`, buckets
  `kokonut-production` and `kokonut-backups`. No credentials were supplied;
  provision them through SOPS or at production deployment. Test-prefix,
  least-privilege, and lifecycle acceptance remain open.
- **Production/recovery:** target hostname `hub.kokonut.network`; 24-hour
  recovery target; replica/failover work is deferred to production. Cutover is
  approved once all readiness gates pass. Public ingress, TLS, trusted proxy
  hops, and production RPO details remain to be established.
- **Retention:** the owner requested industry-standard periods and legal holds,
  and identified the United States and Dominican Republic. There is no single
  duration to apply across these record types: Dominican Republic Law 172-13
  governs personal-data protection, and FTC guidance recommends keeping
  personal information only as long as needed; record-specific duties still
  need a reviewed schedule. Keep no-prune behavior until purpose-specific
  periods, archive access, legal-hold ownership, and erasure approval are
  defined ([Dominican Republic Law 172-13](https://www.consultoria.gov.do/Consulta/Home/FileManagement?documentId=3371232&managementType=1),
  [FTC data-retention guidance](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business),
  [NIST SP 800-92 log-management guide](https://csrc.nist.gov/pubs/sp/800/92/final)).

### Self-hosted OIDC options

Kokonut's own Gateway session, tenant-scope, and authorization layer remains
self-hosted. OIDC is the protocol used to verify an operator's initial identity;
the OIDC provider can also be self-hosted. Choosing an IdP does not make
Directus mandatory or move Kokonut's org/location authorization into that IdP.

| Option | Fit | Trade-off |
|---|---|---|
| **ZITADEL (selected)** | Self-hosted OIDC, PostgreSQL-backed, supports Caddy as a reverse proxy, and Redis is optional. Treat its identity database and credentials as a separately backed-up security boundary; shared PostgreSQL is only acceptable with a dedicated database/role and verified privileges. | Adds a separately operated identity service and its own data/backup lifecycle. The current Compose guide lists 2 GB RAM as a prerequisite; the process alone is described at about 512 MB, so do not use the process figure as whole-stack or Raspberry Pi sizing. ([Compose guide](https://zitadel.com/docs/self-hosting/deploy/compose), [production guide](https://zitadel.com/docs/self-hosting/manage/production)) |
| **Authentik** | Self-hosted OIDC provider with authorization-code and PKCE support and an administrator-facing workflow UI. ([OIDC provider docs](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)) | Good option when its identity workflows and admin interface are desired; deployment/service footprint should be checked against the lightweight profile before adoption. |
| **Keycloak** | Mature self-hosted identity and access-management server; official container and production docs cover PostgreSQL and production operation. ([container docs](https://www.keycloak.org/server/containers), [supported configurations](https://www.keycloak.org/server/supported-configurations)) | Broad capabilities and ecosystem, with a larger operational surface than the Kernel itself needs for its current OIDC client contract. |
| **Kokonut-managed credentials** | Keep account credentials and login entirely in Kokonut's own service. | Maximum control, but Kokonut would own password storage, MFA/passkeys, recovery, abuse defense, security patching, and identity lifecycle. Implementing an OIDC server from scratch is not recommended. |

The owner selected **self-hosted ZITADEL** on 15 October. Keep it as an
optional, replaceable identity profile behind Caddy, while retaining Kokonut's
current session/scope/tenant layer. The identity hostname, issuer/client
details, test accounts, and secret provisioning remain open; no IdP has been
installed or configured. See the [ZITADEL provider plan](zitadel-provider.md).

### What the originally proposed 30 candidate seeds would write

The originally proposed action was a **data write to the local migration-400 candidate
database**, not a schema migration and not a production action. It would add
metric definitions and governance frameworks, dashboard/report datasets,
business capability and roadmap catalogs, plus Adelphi pilot stakeholder,
governance, coordination, funding, and reserve records. Some are explicitly
examples or pilot claims (including stakeholder proxy parties and 2021–2024
funding/participation rows), so these would appear as candidate data for owner
review. They are not measurements imported from Genesis, Seeds, Adelphi, or V1.

The earlier proposal was limited to the exact 30 curated seed files through
the ordered runner, with checksum/ledger tracking. It skipped already-applied
`seed:140_mobile_forms.sql`, excludes `seed:064-068_impact_network.sql` because
it contains pilot upserts and a location-owner update, and leaves the other 90
pending sources alone. A source review found that several “pilot/example” seeds
write records that can be mistaken for real evidence: `105` creates a consent
row described as `operator-approved` with `legal_basis='consent'` via
`system_migration`; `109` and `110` create Adelphi governance circles/roles with
`active` status; `114` marks 2021–2024 funding rounds closed and participations
executed, including a “Genesis farm launch capital” round attached to Adelphi;
and `115` creates active reserves, including a 20,000-tonne carbon buffer and
balances derived from those funding rows. These are not established by the
owner's message and must not be treated as real consent, governance, funding,
or farm data. The owner selected reference catalogs only and held pilot rows. The new
`scripts/seed.sh --catalog-only` path selects five files: expense categories,
metric definitions and governance metadata, flow metrics, and carbon reference
factors/benchmarks/protocols. Dashboard records marked published/verified,
business assumptions, mixed framework/organization seeds, and pilot records
remain outside this selection; see the exact [scope and held-file
rationale](reference-seed-scope.md). The earlier preflight restore checkpoint
predated migrations 392–400. On 15 October, a fresh checkpoint of the current
migration-400 candidate was restore-rehearsed in an isolated `template0`
database, then used as the rollback reference for the separately approved five-file write. Archive and parity details are in [the preflight](builds/2026-10-15-recovery/candidate-reference-seed-checkpoint-preflight.json); applied checksums and resulting counts are in [the rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json). Other curated and pilot seeds remain held.

| Batch | Selected checklist items | Code work to complete first | Owner or external gate held open |
|---|---|---|---|
| API and transport parity | 1, 3, 12, 14 | Finish REST/gRPC method and error parity, authenticated CORS, SDK contract coverage, and synthetic auth/scope checks. The enabled gRPC loopback slice now registers both generated services and exercises key/scope decisions; the Directus fixture preflight now blocks without writes when its required identity field is absent. | Real OIDC, trusted HTTPS certificate, Directus runtime identity/schema and effective permissions, tenant-specific parity, and release authorization. |
| Tenant and database boundaries | 9, 12 | Extend transaction-bound tenant context across remaining Gateway routes and worker jobs; audit direct SQL and direct-database role access; add synthetic owner/share and denial checks. Migrations 405–414 integrate the sensor-anomaly handler with its dedicated DSN/credential, signed tenant context, bounded operations, and one caller-owned transaction. Forty-five focused anomaly/EventBus tests and eight end-to-end disposable PostgreSQL checks pass, including child crash after commit and attempt-two retry without duplicate effects ([delivery evidence](builds/2026-10-16-recovery/sensor-anomaly-worker-delivery-disposable.json]). Existing context, role-isolation, owner-transfer/revocation/expiry, signature/replay-denial, and transaction-lock checks also pass ([acceptance](builds/2026-10-16-recovery/worker-tenant-context-disposable.json)). Remaining code work covers control-plane separation and other worker/Gateway scopes; a real worker login, credential, and active location grant still need deployment provisioning before activation or RLS. |
| Recovery and delivery | 1, 4, 6 | Continue provider-off/failure, lease reclaim, retry/idempotency, duplicate prevention, process outage, and rollback checks with fake endpoints or disposable databases. | Production provider state, external delivery destination, schedule/operator inventory, alert/on-call owner, and a 24-hour run window. |
| Reports and dashboards | 1, 5, 6, 10 | Port all repository-verified Kokonut surfaces, finish query safety and synthetic parity, and document migration boundaries. Do not infer saved-query ownership from the archived Metabase database or represent generic sample-H2 e-commerce cards as Kokonut product reports. | The owner supplied the common cross-lifecycle review audience: liquidity providers, DAO members, guild members, and the wider community. This does not grant blanket report access. Per-report visibility/scope, populated semantic fixtures, external/operator-edited consumers, and DB roles follow farm-data ingestion. |
| Field Collector | 11, 13 | Expand isolated browser/API checks for retired forms, consent, queue behavior, and cleanup; no-network OIDC checks now cover login/session/logout, invalid claims before DB access, discovery metadata URL, requested scopes, and configured S256 PKCE. | Configure selected ZITADEL after the owner supplies the identity hostname and the secrets are provisioned; trusted HTTPS browser origin and human disposition/retention decisions remain open. |
| Deployment and cutover | 1, 7, 15, 16 | Keep ARM64 code assessment and local profile/route checks current; complete non-disruptive restart/recovery checks. | 24-hour recovery target and conditional cutover approval are supplied. Schedule/resource budget, public ingress/TLS/trusted proxies, physical power/device behavior, production replicas/failover, and production schedule owners remain open or deferred. |
| Curated seed write | 8 | **Complete:** the five owner-approved catalog migrations applied successfully through the explicit candidate Compose target; ledger checksums and resulting counts are recorded ([rollout evidence](builds/2026-10-15-recovery/candidate-reference-catalog-seed-rollout.json)). | The owner approved and completed this local reference write. Remaining pilot/curated seed files stay held; production import is not authorized by this operation. |
| Retention policy | 2 | Keep no-prune as the default; runtime policy, audited holds, optional jurisdiction/purpose codes, synthetic PostgreSQL acceptance, and candidate migrations 401–402 are complete. Unresolved scoped policies fail closed. | USA and Dominican Republic were supplied. Periods are deliberately runtime-configured, not hardcoded; deployment still needs approved policy data, accountable approval/hold roles, archive access, a scope resolver, and erasure procedures. |

## Work order

### Batch A — Close the current CI result

**Purpose:** establish the exact baseline for further local work.

**Repository surface:** `.github/workflows/ci.yml`, `scripts/run-github-ci.sh`,
and the focused test named in any failure log.

**Action:** At batch start, CI #336 was pending and Security #60 passed on
  pushed SHA `6edc14ebe12fa1b983bf74fcb0e3b03d69d28b9f`. The local disposable
  KGP check replays all 394 ordered PostgreSQL schema sources, processes seven
  guild/domain/task/governance events through the real indexer, verifies source
  links and idempotent replay, simulates a reorg and replacement-branch
  projection rebuild, then checks restart and lease reclaim against the real
  cursor table. Forty-eight focused migration/KGP/guild tests, Ruff,
  compilation, capability-matrix, and JSON evidence checks pass. A fresh
  encrypted checkpoint and isolated restore preceded candidate migration 403;
  the candidate is healthy with zero pending schemas, but its app image was not
  rebuilt and RLS remains disabled. No live RPC, seed, or provider is used.

**Acceptance:** require passing CI and Security on the current PR head before
merging. The scheduler runtime acceptance is source/disposable evidence only;
the report guard disposable database does not establish populated output
parity or least-privilege role behavior outside that integration.

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
  [worker operation map](worker-operation-map.md) inventories all 15 scheduled
  modules and seven event-handler pairs, with a test guarding allowlist parity.
   It records source-visible effects and known replay boundaries; transitive
   service/provider calls and existing persisted schedule reconciliation remain
   open. The source-only effect index now records 33 unique direct effect sites
  (36 operation/site memberships) across 22 worker roots. The scheduled carbon
  adjustment check has its own read-only entrypoint; the interactive
  credit-management CLI is excluded from scheduler allowlisting. The function
  graph now follows the shared `services.common.cli.run(main)` callback. A separate comparison
  covers 15 shared JobSpecs: eight no-input defaults pass, while anomaly,
  climate, weather, metrics, credit adjustment, and remote sensing require a
  schema-validated location per scheduled task; scheduled sensor ingestion now requires one location-bound registered driver
  instance; no active source instance or schedule has been configured.
  The manual sensor CLI now requires a canonical `--location-id` for reads and
  writes and binds sensor lookup, inventory, and calibration SQL to that
  location. One hundred ten focused sensor/scheduler checks pass. This is a
  query filter only; it does not authenticate the caller or establish signed
  context/RLS ([evidence](builds/2026-10-16-recovery/sensor-ingestion-cli-location-scope.json)).
  The adjacent device-manager CLI now also scopes listing, health lookup,
  registration, and health updates; its registration upsert cannot move an
  existing slug across locations. Sixty-one focused device/IoT tests pass;
  these UUID filters also do not grant caller identity or database isolation
  ([evidence](builds/2026-10-16-recovery/device-manager-location-scope.json)).
  The optional Prefect adapters preserve multi-location behavior by dispatching
  one task per active Kokonut Network location. Remote sensing is available only as a
  bounded sequential batch (1–10 jobs, default one) and now requires the
  location for manual and scheduled calls, and ClickHouse projection
  is limited to a bounded run-once contract. No task or provider was activated.
  Neither report inspects persisted tasks or
   provider state, and neither proves runtime identity or tenant context. New
   module-specific operation schemas validate values and option
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
   pass. The console ignores responses from older inventory requests after a
   location switch; live OIDC/database and browser race acceptance remain open.
   The report-review queue/detail services now also have five direct source
   regressions for same-connection context-before-query, repeated location
   grants, legacy-context denial, rollback/close, and the detail-size bound.
   Synthetic connections do not verify the PostgreSQL signing functions or
   final database role ([evidence](builds/2026-10-15-recovery/operator-report-review-tenant-context-source.json)).
3. Complete runtime-role restrictions for remaining public tables and verify
   existing handlers still work through their narrow grants/functions.
   **Partial:** the opt-in bootstrap still grants broad DML on existing public
   tables outside reviewed exceptions, but it now revokes both global and
   `public`-schema default privileges for future tables and sequences. The
   disposable PostgreSQL 16 role acceptance still passed current-handler SQL
   and proved a table/sequence created after provisioning is inaccessible to
   the runtime login. A new whole-services SQL inventory covers all 807 Python
   source files and identifies direct execution sites and candidate relation
   names without becoming an ACL. The current generated inventory covers 3,863
   SQL execution sites across 815 source files, including 268 worker-linked
   sites; literal query wrappers are unwrapped while parameter values remain
   unobserved. The report is static
   evidence, not an ACL. The next review classifies API, worker, CLI, and
   indirect-query surfaces before deriving explicit grants; worker, Directus,
   and RLS boundaries remain open ([role evidence](builds/2026-10-14-recovery/runtime-role-default-privileges-disposable.json); [SQL inventory](runtime-sql-inventory.json); [latest inventory check](builds/2026-10-15-recovery/runtime-sql-inventory-refresh.json)).
4. Add a machine-readable preflight that detects unbounded callers, unsafe
   grants, missing migration prerequisites, and pending tenant mappings without
  printing personal or secret values. **Partial:** the static-only worker
  preflight confirms all 20 allowlisted roots and imports, reports the shared
  runtime identity and 64 SQL sites without static function matches,
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
  isolation. The CLI now requires the dedicated `kokonut_tenant_preflight`
  login through `KOKONUT_TENANT_PREFLIGHT_DSN`, checks it is direct/read-only
  with no public DML/ownership or object creation, and inspects the configured
  application role separately. The CLI also requires `BYPASSRLS` to be enabled
  exactly when an inventory relation has RLS, preventing filtered global
  counts. The connection path has source tests only; no credentials or database
  role were provisioned. Owner mapping, remaining
  runtime role restriction, active-schedule reconciliation, and complete worker context remain open
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
Those checks passed offline. A response-shape follow-up now requires array data
for list reads and object data for detail reads in both clients; malformed
shapes produce the same normalized envelope error. Two new focused regressions
per language pass, as does the complete 11-test JavaScript SDK suite and its
TypeScript build. Gateway route/auth and tenant-scope parity remain open; see
the [acceptance record](builds/2026-10-14-recovery/sdk-public-api-parity.json).
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
The Directus parity fixture also checks its historical identity-scope column
before creating synthetic users or activity rows. A missing
`directus_users.location_id` returns a blocked precondition with no fixture
writes (three source checks and one fake-schema execution pass, with Ruff and
Python compilation). The owner has since selected organization/location
grants; the next code step must bind Directus identities to Kokonut operator
identities and enforce those grants. Runtime read/write, field, hook, and
schedule parity remain open ([evidence](builds/2026-10-14-recovery/directus-schema-preflight-guard.json)). The create-time tenant-reference hook now rejects explicitly malformed `location_id` values instead of silently skipping its reference checks; the extension TypeScript build passes. This is input validation only and does not authorize a caller's tenant scope ([source](../../extensions/kokonut-hooks/src/tenant-validation.ts); [parity inventory](directus-parity-inventory.md)).
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
that can be decided from the repository. Use the owner-supplied stakeholder
review audience (liquidity providers, DAO members, guild members, and wider
community), but do not infer per-report visibility, owner scopes, measures,
or production semantics; those require report-owner review and reference data
in OFU-04/14. Directus source and permission
contracts can be improved locally, but supported-version runtime-role parity
needs the disposable identity/schema fixture in OFU-09.

**Progress (15 October 2026):** the report snapshot CLI now requires explicit
location scope for bulk generation, rejects conflicting selectors before
opening PostgreSQL, and accepts standalone hash verification. All 94 report
generator keys remain available. Eleven focused checks and Ruff pass without
database or provider access ([evidence](builds/2026-10-15-recovery/report-generator-cli-scope.json)). All single and bulk calculations use a session-level PostgreSQL read-only default, and draft persistence starts after calculation. A disposable PostgreSQL probe found that switching to autocommit after changing the default could permit a write. The connection facade now denies autocommit changes directly and through `cursor.connection`; direct DML still receives SQLSTATE `25006`, and the draft write succeeds after calculation. Nine focused tests, Ruff, compilation, and the disposable check pass. The application connection remains a writer, so this is a guard rather than a database-role boundary. Populated output parity remains open ([calculation evidence](builds/2026-10-15-recovery/report-generator-read-only-calculation.json); [disposable evidence](builds/2026-10-15-recovery/report-generator-readonly-disposable.json)).

The AST-only helper-scope inventory now follows statically imported and
same-module local functions for all 94 registered reports. It finds helper
query sites in 34 report types, with 167 report-to-helper query-site
memberships and 63 visible location-scope signals. The trace corrected several
invalid relative analytics imports in the report modules; its source coverage
does not prove runtime behavior, tenant isolation, authorization, or output
parity ([inventory](report-generator-helper-scope-inventory.json)).

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

**Outbox retry backoff (16 October 2026):** failed delivery outcomes now use a
60-second exponential base, doubling by persisted attempt number and capping at
one hour. ClickHouse setup failures use the same schedule; the existing
eight-attempt dead-letter bound, lease fence, and idempotent insert token are
unchanged. Fifty-seven focused outbox, failure-injection, and producer tests
pass. The checks use mocks and source contracts only; no database or ClickHouse
service was contacted ([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json)).

**Scheduler crash-after-effect recovery (16 October 2026):** the disposable
PostgreSQL acceptance now kills the real SchedulerEngine after an allowlisted
event-processing child commits a notification outbox effect but before task
completion is recorded. Attempt two observes the completed durable event and
keeps a single outbox row and one successful handler delivery. This also found
and fixed the handler-runner stdout protocol bug caused by INFO logs emitted
after a committed effect. Five focused tests, Ruff, compilation, and the
disposable PostgreSQL run pass; no provider delivery or candidate/legacy access
occurred ([runner](../../scripts/check-scheduler-engine-reconnect-disposable.py);
[evidence](builds/2026-10-16-recovery/scheduler-engine-postgres-reconnect.json);
[protocol regression](../../tests/test_event_handler_runner.py)). Broader
provider, worker-process, and long-duration recovery remain open.

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

**Dynamic retention source implementation (15 October 2026):** migration 401
adds nullable runtime policy windows, draft/approval state, and an audited,
append-only record-level legal-hold ledger. Event cleanup no longer accepts a
caller-selected `--days`; it requires exactly one approved active global
`event_bus` / `platform_event` policy, checks pending dead letters, unsuccessful
handler deliveries, and active holds, and remains default-off behind its feature
gate. Generic data-governance cleanup also requires its independent feature gate,
approved policy metadata, and no active hold. No periods or schedules have been
configured, and no fixed duration is proposed. The candidate has now applied migrations 401 and 402 after a fresh checkpoint
and restore rehearsal of its post-seed state. Disposable migration/hold
acceptance also passed on an isolated synthetic PostgreSQL fixture through the
ordered migration runner. It verifies the legacy-policy transition,
policy history, holds and event cleanup protections. The focused source/unit set also
passes 94 tests plus four subtests. Acceptance caught an undersized history
action column and the migration was corrected. No policy was configured and
cleanup remains disabled; deployment still needs approved policy data and
accountable operating roles ([database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json); [source evidence](builds/2026-10-15-recovery/retention-policy-source-checks.json); [migration](../../schemas/postgres/401_dynamic_retention_and_legal_holds.sql); [operations](retention-policy-operations.md)).

**Dynamic retention scope metadata (15 October 2026):** migration 402 adds
nullable owner-defined jurisdiction and purpose codes without defaults or
hardcoded legal meaning. The CLI and audited policy snapshots preserve these
codes. Auto-enforcement is rejected for unresolved codes, the generic sweeper
skips scoped policies, and EventBus cleanup rejects ambiguous active policy
state. Sixty-two focused source tests and four subtests pass; migrations 401
and 402 pass against an isolated synthetic PostgreSQL fixture. The candidate now includes these schema changes; no retention values or
policies were configured ([migration](../../schemas/postgres/402_retention_policy_scope_codes.sql);
[scope evidence](builds/2026-10-15-recovery/retention-policy-scope-source-checks.json);
[database evidence](builds/2026-10-15-recovery/retention-policy-disposable.json)).

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

**Prior schema-400 refresh (15 October 2026):** the isolated profile planner
built the app and PostGIS images as linux/arm64, applied all 391 schemas through
migration 400 with zero failures, restored a logical backup with matching
migration fingerprints and zero pending migrations, and passed HTTP health,
anonymous protected-write denial, database restart, and app SIGKILL recovery.
Spatial and manually enabled raster functions also passed. The database
restart caused the scheduler child to exit on a closed connection; the Kernel
supervisor restarted the app processes and health recovered. The scheduler
source now opens a fresh connection per tick; a separate loopback-only
disposable PostgreSQL stop/start check confirmed its worker process reconnects
after database recovery, with the task engine stubbed. Repeated/long provider
outage behavior, lease recovery, and physical Pi limits remain open. The earlier
restricted command shell could not access the Docker Desktop socket; host-
authorized access reached the healthy daemon and completed this check
([prior evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-400.json)).

**Schema-402 refresh (15 October 2026):** a fresh, uniquely named ARM64 project
applied all 393 schema files through migration 402, with zero failures or
pending migrations. A 5,220,702-byte custom-format dump restored into a second
template0 database with a matching 393-row SHA-256 migration fingerprint and
zero pending migrations. PostGIS geometry, `/health` 200, anonymous protected
write 401, health after database restart, and health after app SIGKILL followed
by Compose `up` passed. The app started before migration, so workers logged
missing-schema errors during bootstrap; this refresh did not apply explicit
resource limits or seeds. Raspberry Pi hardware, 24-hour recovery, and real
provider/lease outages remain open
([evidence](builds/2026-10-15-recovery/arm64-qemu-current-schema-402.json)).

**Schema-gated startup follow-up (15 October 2026):** the image default and
standard-role commands now pass `--require-schema`. In a new ARM64 QEMU project,
the app remained child-free while the ledger was empty; after 393 ordered
schemas applied and a zero-pending plan, API/scheduler/event children started,
health returned 200, a protected write returned 401, and Docker reported the
app healthy. The app was limited to 1 GiB/two CPUs and PostgreSQL to 1.5
GiB/two CPUs. The disposable project and volumes were removed. This closes the
worker-before-migration source/runtime path under emulation, not physical Pi,
24-hour, or provider-outage acceptance
([evidence](builds/2026-10-15-recovery/kernel-schema-startup-guard.json)).

### Batch G — Reconcile ledgers, then request only owner decisions

Update `batches.md`, `progress.md`, `capability-matrix.md`, the relevant
evidence records, and this plan after each batch. Keep raw checklist counts
separate from capability acceptance. Before production/candidate rollout,
present the owner only with unresolved inputs or separately gated writes.

## Owner-input gates after code work

These do not block the code-first batches above, but they block the associated
deployment or semantic acceptance:

- **Ownership and access:** the owner mapped Kokonut Genesis, Kokonut Seeds,
  Kokonut Adelphi, Kokonut Terra Viva, and Kokonut V1 to the Kokonut Network
  operating tenant (OFU-01). Adelphi and Genesis are confirmed exclusive;
  do not infer legal land title. Other locations stay unassigned. Operator-to-
  organization grants and legacy account reconciliation remain open (OFU-02).
- **Governance and reporting:** USA and Dominican Republic are the selected
  retention jurisdictions. Runtime-configurable policy support is implemented
  in source; no periods are hardcoded. Approved policy data, accountable
  approval/hold roles, and deployment verification remain open (OFU-03). The owner selected all repository-backed
  reports and provider jobs for code-first porting; populated reference
  outputs follow the planned farm-data ingestion (OFU-04/14). Directus should
  consume organization/location grants; supported consumers and runtime
  identity still need isolated parity evidence (OFU-09/15).
- **Production operations:** alert destination/on-call (OFU-05), public
  ingress, trusted proxy hops, TLS, and production recovery topology (OFU-06),
  active scheduler inventory/operators (OFU-16), and scheduling the
  owner-selected 24-hour recovery window (OFU-13). Replica/failover checks are
  deferred to production.
- **Provider setup:** identity hostname, issuer/client settings and test
  identities for the selected self-hosted ZITADEL provider (OFU-07); R2
  credentials and lifecycle policy (OFU-08); browser vault and trusted local
  HTTPS certificate when browser acceptance is scheduled (OFU-10/11).
- **Candidate-only writes:** the five selected reference catalogs (OFU-17) were
  applied to the local candidate after separate approval. The earlier 30-file
  proposal is superseded; pilot rows remain held. Migrations 392–403 are rolled
  out; migrations 404 onward have not been applied. Runtime credential
  provisioning remains tracked under OFU-19. The candidate has six recorded
  seed entries; 115 unselected seed sources remain pending.

There is no active Raspberry Pi request: OFU-12 records the completed code-only
scope and lack of hardware. If the owner later supplies a Pi, add a separate
physical acceptance record rather than revising emulation evidence.

## Push and release cadence

Keep related changes in local commits and push reviewable batches, as
requested. The latest pushed head is `54d84d8` on PR #68. Security run #93
passed; CI #369 was in progress when queried on 17 October 2026 at 01:06 UTC.
Continue independent code-first work while hosted checks run.
Never push directly to `main`. Keep each candidate database rollout separately
gated even when its migration and disposable acceptance are complete.
