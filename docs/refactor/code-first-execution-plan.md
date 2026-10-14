# Code-first refactor execution plan

**Updated:** 14 October 2026
**Branch/PR:** `feat/mobile-offline-acceptance`, PR #68
**Last CI-verified pushed head:** `7953afe4d5267b040392a8fe52e1ae38c236cfd4`
**Last passing release checks:** CI #308 and Security #32 passed on pushed head
`7953afe4d5267b040392a8fe52e1ae38c236cfd4`.

This plan orders the remaining work so repository changes and reproducible
software checks happen before decisions that require production owners, live
provider accounts, populated reference data, or external infrastructure. It is
an execution map for the existing open items in [batches.md](batches.md), not a
second capability acceptance ledger. Keep the capability matrix's named
MAN-CAP checks open until each has its own retained evidence.

## Current accounting

- The execution checklist has 307 checked and 20 open items (327 total).
- The latest pushed implementation batch is `26edad1`; CI #310 is in progress
  and Security #34 passed. The last CI-verified head remains `7953afe` (CI #308
  and Security #32 passed).
- The local batch retires the unscoped legacy mobile-offline CLI, tenant-binds
  protected Data Stream creation, and rejects unscoped cache invalidation from
  event handlers. A separate reporting slice now runs opt-in saved SQL through
  an ACL-verified, read-only reader role. The worker operation inventory covers
  every current scheduled/event allowlist entry. Module-specific scheduler
  argument contracts now fail closed at activation and dispatch; transitive
  call effects, enabled legacy rows and worker identity/context remain open.
  The metrics entry now references all 20 registered calculator modules with a
  registry-parity test and records direct query tables and composed calculator
  calls. The freshness operation's seven source tables are also tied to its
  fixed query map; broader helper/provider effects and worker identity remain
  open.
  Data-freshness queries use fixed table/timestamp maps, bind location values,
  and report unknown configured sources as errors; 29 focused source tests pass.
  The climate compatibility path stores schema-aligned `latitude_proxy_v1`
  estimates; migrations 392–397 passed ordered PostgreSQL 16 application and
  replay on a restored candidate checkpoint, including migration 397's
  location fallback and duplicate rollback. A clean `template0` bootstrap of
  all 388 schema sources also passed; candidate rollout remains open.
  The registered native and Field Collector API routes now have an exact
  resource/action/public-policy inventory and unknown route/method cases are
  verified protected; broader tenant, OIDC, transport, and SDK parity remain.
  The disabled gRPC adapter now has focused coverage proving `serve()` and
  health checks fail before importing optional gRPC packages or the server;
  enabled transport parity remains open.
  Focused source/disposable checks pass;
  remote CI has not run for these newer changes.
- The capability matrix has 66 capabilities: 56 baseline-retained, 7 partial,
  and 3 prepared. None of the 66 named MAN-CAP checks is accepted.
- Candidate migrations 392–397 and the remaining curated seeds are prepared
  but have not been applied to the local candidate. Migrations 392–397 passed
  ordered application on an encrypted-checkpoint restore, with a clean second
  migration-runner pass. All 388 schema sources also passed on an empty
  PostgreSQL database through the isolated clean-bootstrap verifier. The
  candidate remains at migration 391; candidate rollout and curated seeds
  remain separately gated under OFU-17 and OFU-18.
- Seeded demo ownership for Kokonut Adelphi and Kokonut Genesis is already
  confirmed as exclusive to Kokonut Network. Do not ask for that mapping again.
- There is no Raspberry Pi available. The code-only ARM64 assessment passed
  Buildx/QEMU build, constrained-container startup, bootstrap, restore,
  migration, health, and restart checks. Physical performance, thermal,
  storage, power-loss, network, and on-device restart behavior remain
  unverified; no hardware result is claimed.

## Work order

### Batch A — Close the current CI result

**Purpose:** establish the exact baseline for further local work.

**Repository surface:** `.github/workflows/ci.yml`, `scripts/run-github-ci.sh`,
and the focused test named in any failure log.

**Action:** CI #308 finished successfully on `7953afe`; Security #32 also
passed on the same commit. The CI #307 OIDC Compose fixture failure was fixed
before this run by supplying the test-only operator-auth password before
checking the missing issuer configuration.

**Acceptance:** satisfied for pushed head `7953afe`: CI #308 and Security #32
both passed. The check status and commit are recorded in this plan,
`batches.md`, `progress.md`, and the capability-matrix verification note. Do
not count the earlier CI #307 failure as current-head coverage.

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
   [the tenant call-site audit](mobile-tenant-rls-callsite-audit.md).
3. Complete runtime-role restrictions for remaining public tables and verify
   existing handlers still work through their narrow grants/functions.
4. Add a machine-readable preflight that detects unbounded callers, unsafe
   grants, missing migration prerequisites, and pending tenant mappings without
   printing personal or secret values.
5. Keep application RLS disabled until all code paths and data ownership inputs
   pass. Isolated forced-RLS fixtures can prove policy behavior; they do not
   authorize turning it on in the candidate or a populated deployment.

**Acceptance:** disposable PostgreSQL tests cover owner/shared scope, denial,
revocation, stale context, cleanup, least-privilege grants, worker/CLI behavior,
and migration replay. Candidate rollout remains a separate OFU-18 operation.
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
The native and Field Collector routers now also have a pinned full method/path
policy inventory. A 27-test focused Gateway run confirms exact resource/action/
public policy coverage, 401 for every registered private route when anonymous,
and 401 for unknown routes, wrong methods, and near-miss paths ([route inventory evidence](builds/2026-10-14-recovery/gateway-route-policy-inventory.json)).
The OIDC operator router now has a separate exact inventory for all 28 registered
method/path policies, including scoped grants, secondary grants, public login
endpoints, and six governed farm-activity actions. Unknown operator paths and
method mismatches return 401 in the source test ([evidence](builds/2026-10-14-recovery/operator-route-policy-inventory.json)).
The operator console's cookie-authenticated draft edit now passes both its
credentialed CORS preflight and successful-response checks; PATCH was added to
the explicit CORS method allowlist. Browser/runtime ingress acceptance remains
open ([CORS evidence](builds/2026-10-14-recovery/gateway-cors-patch-preflight.json)).

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

**Migration replay (14 October 2026):** ordered migrations 392–397 and the
runner's no-op replay passed on a restored, age-encrypted candidate checkpoint
using PostgreSQL 16.4. The same 388 current schema sources also passed from an
empty PostgreSQL database in a separate internal-only Compose project. These
records verify clean bootstrap and populated upgrade paths; candidate rollout
remains separately gated ([restore replay](builds/2026-10-14-recovery/candidate-migration-392-397-restored-replay.json); [clean bootstrap](builds/2026-10-14-recovery/clean-bootstrap-388-migrations.json)).

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
- **Candidate-only writes:** approval to apply the 30 curated seeds (OFU-17)
  and a separate approval to roll out migrations 392–397 (OFU-18). Migration
  397 has isolated PostgreSQL acceptance against a synthetic schema fixture;
  full-bootstrap acceptance is still open. Neither rollout is implied by
  code/test approval.

There is no active Raspberry Pi request: OFU-12 records the completed code-only
scope and lack of hardware. If the owner later supplies a Pi, add a separate
physical acceptance record rather than revising emulation evidence.

## Push and release cadence

Keep related code changes in local commits and push in reviewable batches, as
requested. CI #308 passed on pushed head `7953afe`; accumulate the next
coherent batch before pushing so the repository does not start CI for each
small commit. Never push directly to `main`. Keep each candidate database
rollout separately gated even when the corresponding migration and disposable
acceptance are complete.
