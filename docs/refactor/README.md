# Kokonut Kernel implementation baseline

Phase 0 inventory, captured 9 October 2026.

**Current status (20 October):** the last recorded local Kernel candidate
rollout applied 425 schema entries through migration 434, with no pending or
failed entries at that checkpoint. It was a schema-only rollout following an
encrypted checkpoint and restore rehearsal; no application-table RLS,
worker credentials, location grants, providers, or schedules were enabled.
Candidate state has not been rechecked during the current console batch. PR #68
is on branch `feat/mobile-offline-acceptance` at pushed head
`d200c72cee37819a2d01948d9bf48072b955d7b6`; Security #282 passed and CI #558 is
pending. The current source builds for ARM64 and passes software-only QEMU
checks; physical Pi and power-loss acceptance remain open. See
[rollout evidence](builds/2026-10-18-recovery/candidate-migration-434-rollout.json),
[the phase ledger](progress.md), and
[capability progress](capability-matrix.md).
The baseline sections below preserve historical observations, not current
phase-completion claims.

## Source and repeatability

Baseline commit: ad806f504bfef15cba41446d777cb22f6bd8fe6a.
Implementation branch: feat/kernel-architecture-refactor, created from main.
The initial worktree change was the requested root plan ignore rule. The root
implementation plan remains a local, ignored file; these smaller execution
records are kept in the repository for review. Implementation is under PR #68;
the latest pushed head and hosted check state are recorded above. No merge or
release is recorded.

The local checkout replaces the cached browser snapshot used to write the plan.
Regenerate static evidence with:

    python3 scripts/kernel-inventory.py --output docs/refactor/repository-inventory.json

The script uses the Python standard library. It parses source without importing
application code, connecting to a database, loading .env, or recording secret
values. Output records the commit, 66 README capabilities, 66 service groups,
383 Python test files, import edges, environment variable names, literal HTTP
routes, domain ownership references, and SQL filenames. All Python files parsed.
Test references are candidates; they do not prove coverage or passing behavior.
Dynamic imports, indirect service calls, CLI forwarding, and SQL lineage still
need review. The frozen JSON records this baseline rather than a current HEAD
assertion after later commits.

## Execution records

- [Current phase and capability progress](progress.md): Phase 7 public reads active;
  earlier acceptance gates and ARM64/scale certification remain open. Keep this
  ledger and capability-matrix.md updated with every implementation/deployment slice.
- [Public relation readiness](public-relation-readiness.md): catalog gate for
  migrated public read relations/columns; deployed to AMD64 API and worker.
- [ARM64 public-read refresh](arm64-public-reads.md): current native read/contracts
  source built for ARM64; runtime and Pi certification pending.
- [Public response models](public-response-models.md): explicit native read
  schemas and payload validation; deployed to AMD64, payload acceptance pending.
- [Public summary contracts](public-summary-contracts.md): replace unresolved
  CRISP/portfolio imports with governed persisted reads; deployed to the private AMD64 API.
- [Native metric read execution](native-metric-reads.md): bounded read-only
  catalog query, async offloading, UUID validation, and Decimal JSON encoding.
- [Crop-cycle NOI reconciliation](noi-snapshot-reconciliation.md): SAFE seed
  verification, stale-snapshot finding, additive uniqueness migration and
  isolated native reconciliation evidence.
- [Public location API contract](location-api-contract.md): scoped Directus
  migration map and bounded native read execution; parity acceptance pending.
- [Portability workers](portability-workers.md): optional separate native worker
  role shares API provider/schema policy; idle AMD64 startup recorded.
- [Isolated portability runtime](portability-runtime.md): fresh AMD64 database
  applied 364 schemas through 373; private API/database healthy and native worker running.
- [Paired readiness image builds](builds/2026-10-10-readiness/README.md): latest
  AMD64/ARM64 Kernel artifacts contain readiness checks and matching package inventories.
- [Application package inventories](application-package-inventory.md): future
  images retain resolved dependencies for architecture and release comparison.
- [ARM64 application build](arm64-application.md): current-source app/PostGIS
  startup, schema, restore, health, and short recovery passed under QEMU; physical
  Pi certification and optional image architectures remain open.
- [Portability database preparation](portability-database.md): separate private
  PostGIS/API evaluation manifest with an opt-in schema startup gate; runtime
  acceptance pending.
- [ARM64 candidate profile](arm64-database.md): the planner selects a separate
  custom PostGIS/app overlay for minimal, edge, and standard; current-schema
  QEMU replay passed and physical Pi acceptance remains open.
- [Kernel release inputs](kernel-release-inputs.md): build inputs are SHA-256
  locked and GitHub Actions is configured to build/compare the minimal app and
  PostGIS targets across AMD64/ARM64; transitive dependency locks and a
  successful CI run remain open.
- [PostgreSQL rate limits](postgres-rate-limits.md): explicit shared-budget
  adapter and migration 373; unapplied, with scale/availability acceptance pending.
- [Rate-limit boundary](rate-limit-boundary.md): injectable gateway contract and
  explicit local selection; shared adapters and scale acceptance remain pending.
- [Projection failure boundaries](projection-failure-boundaries.md): durable
  client-setup failure outcomes and separate database completion errors; runtime pending.
- [Explicit projection job](projection-job.md): catalog operation and meaningful
  outbox CLI exit codes; no scheduler authority or automatic dispatch added.
- [Shared sensor projection](sensor-projection.md): common HTTP/MQTT outbox
  payload and failure boundary; runtime lineage/compatibility acceptance pending.
- [Sensor quality parity](sensor-quality-parity.md): MQTT signed quality and
  bounded payload fields; transport and receipt runtime acceptance pending.
- [Sensor device authorization](sensor-device-authorization.md): active-device
  checks and transaction-scoped rotation/revocation serialization; runtime pending.
- [Optional HTTP sensor role](http-sensor-overlay.md): private MQTT-independent
  receiver deployment; ingress and transport parity acceptance pending.
- [HTTP sensor request limits](http-sensor-limits.md): bounded pre-parse request
  bodies and batch dimensions; signature and runtime acceptance pending.
- [Sensor timestamp identity](sensor-timestamp-identity.md): opt-in shared UTC
  parsing for HTTP/MQTT; historical reconciliation and parity acceptance pending.
- [HTTP sensor transactions](http-sensor-transactions.md): source/outbox failure
  propagation, transaction cleanup, and batch identity preflight; parity pending.
- [Profile command planner](profile-selection.md): explicit manifest selection
  and reviewable commands; unsupported scale selection is rejected.
- [Optional Kernel proxy](kernel-proxy.md): Caddy ingress without Directus
  fallback and explicit forwarding boundary; TLS/runtime acceptance pending.
- [Standard role separation](standard-profile.md): same-package API and durable
  worker roles; Compose parsed, deployment and recovery acceptance pending.
- [MQTT readiness](mqtt-readiness.md): local connection/subscription health
  reporting; container health transitions and runtime checks pending.
- [MQTT recovery](mqtt-recovery.md): private outcomes, bounded processing
  attempts, and operator replay/disposal; migration/runtime gates pending.
- [MQTT delivery](mqtt-delivery.md): opt-in persistent QoS 1 consumer and
  acknowledgement after commit; runtime replay and disposition gates pending.
- [MQTT transaction boundary](mqtt-transactions.md): enqueue failure propagation
  and per-message cleanup; runtime delivery and recovery checks pending.
- [Optional MQTT overlay](mqtt-overlay.md): separately provisioned mTLS broker
  and subscriber; Compose validated, image/runtime gates pending.
- [gRPC shutdown](grpc-shutdown.md): explicit transport/pool lifecycle and
  startup validation; runtime drain and cancellation checks pending.
- [gRPC authentication](grpc-authentication.md): caller context during execution
  and exact colon-bearing scope matching; runtime checks pending.
- [gRPC pooled database](grpc-database.md): shared query interface and
  transaction cleanup for RPC handlers; runtime acceptance pending.
- [Optional gRPC overlay](grpc-overlay.md): private transport and separate
  image target; Compose validated, image/runtime acceptance pending.
- [Scheduler activation](scheduler-activation.md): transactional task/graph
  validation and activation commands, not yet invoked or runtime validated.
- [Scheduler graph audit](scheduler-graph-audit.md): read-only checks for
  dependency cycles and disabled run-window alignment; runtime gates pending.
- [Scheduler run windows](scheduler-run-windows.md): opt-in matching against
  prerequisite runs from the same UTC window; migration and runtime gates pending.
- [Scheduler job planning](scheduler-job-planning.md): disabled schedule
  definitions from shared jobs, with dependency and cutover gates pending.
- [Schedule ownership inventory](schedule-ownership-inventory.md): source-level
  Prefect/cron/database job mapping and per-job cutover/replay policy; live
  provider ownership and runtime acceptance remain open.
- [Shared orchestration jobs](orchestration-jobs.md): provider-independent
  operations and corrected Prefect task submissions; runtime gates pending.
- [Edge profile](edge-profile.md): encrypted local media and conservative
  resource limits, with hardware certification and recovery checks pending.
- [Local private media](local-private-media.md): opt-in encrypted filesystem
  adapter with adoption, reconciliation, and recovery checks still pending.
- [Analytics overlay](analytics-overlay.md): opt-in private ClickHouse candidate,
  isolated storage, driver-only build selection, and pending projection gates.
- [Kernel supervision](kernel-supervision.md): API and durable workers in one
  app container, with shutdown and recovery validation still pending.
- [Native location reads](native-location-reads.md): conservative governed public
  PostgreSQL reads when Directus is disabled; runtime parity still pending.
- [Kernel candidate](kernel-candidate.md): isolated image/Compose preparation,
  with build, schema, worker, and capability gates still open.
- [Candidate dependency groups](../../requirements/README.md): additive manifests
  for image slimming, with legacy installs preserved and validation still pending.
- [Provider configuration](provider-configuration.md): first Phase 1 settings
  and health reporting slice, with remaining runtime validation gates.
- [Capability matrix](capability-matrix.md): all 66 README capabilities, owning
  code area, candidate tests, implementation status, and named manual parity
  checks. `python3 scripts/check-capability-matrix.py` validates row coverage,
  status labels, and referenced source/test paths; fast-fail CI runs the same
  check.
- [Sensor anomaly delivery](sensor-anomaly-delivery.md): exact source-reading
  evaluation, per-reading/rule receipts, atomic alert/claim/outbox/approval
  records, and synthetic crash/replay evidence; provider and overall Batch 2
  acceptance remain partial.
- [PostgreSQL runtime-role policy](runtime-role-policy.md): opt-in non-owner
  application role and isolated privilege-denial evidence.
- [Optional database consumer roles](optional-database-roles.md): separate
  Directus, Metabase metadata, and analytics-source identities; isolated
  populated-role checks and the pinned Metabase startup against populated
  metadata passed. Structural review identifies the saved board as generic
  e-commerce demo content over sample H2; preserve it only as an explicitly
  labeled demo/compatibility fixture. Kokonut-specific source views and card
  output parity remain open; see the [source and disposition report](metabase-source-inventory.md).
- [Metabase reporting source contract](metabase-reporting-contract.md): proposed
  PostgreSQL-only `kokonut_reporting` view surface, eligibility rules, role
  boundary, implementation sequence, acceptance criteria, and rollback.
  Source-aligned scratch applied all 369 migrations through 378 and passed the
  actual-view role fixture; its plan reported zero pending. The archived clone
  plan found zero checksum drift and 25 pending migrations, none applied.
  A transactional replay also verified all 369 sources with zero pending and
  rolled back an injected DDL failure and ledger write (`0|0`). Populated-row
  parity and the Metabase source/cards remain open. A separate clone accepted
  all 25 migrations pending on the archived clone, preserving fingerprints for
  16 populated tables; the archived clone itself remains unchanged. See [the
  per-migration review](pending-migration-compatibility-review.md), [current source-aligned
  evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json)
  and [transaction evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json),
  [clone replay](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json),
  and [row fingerprints](builds/2026-10-11-recovery/application-migration-review-fingerprints.json).
  See [sanitized verification evidence](builds/2026-10-11-recovery/kokonut-reporting-contract.json).
- [Archived migration checksum drift](migration-checksum-drift.md): exact
  historical source recovered from the stopped legacy worker image and matched
  to the archived ledger; clone remains unchanged pending a reviewed disposition.
- [Dependency decisions](decisions.md): provider boundaries and ordered gates.
- [Local data inventory](local-data-inventory.md): observed Docker state,
  persistent volumes, row counts, and recovery requirements.
- [Static source inventory](repository-inventory.json): exact source paths.
- Existing [domain registry](../data-model/domain-ownership.md): tables,
  migrations, and ownership. Reuse it rather than introducing competing owners.

## Corrections to the original plan

1. Metabase already has the metabase Compose profile and
   tests/test_compose_metabase_profile.py. Preserve that work.
2. services/cache/cache.py already implements PostgreSQL ComputationCache.
   Redis primarily serves Directus cache and rate limits in the inspected
   Compose file; no Python Redis imports were found. A new cache abstraction
   must preserve existing persisted result/provenance behavior.
3. services/ingestion/clickhouse_outbox.py already implements a PostgreSQL
   projection outbox. Weather, sensors, EAS, and Gnosis producers enqueue
   there. Audit remaining producers before replacing any paths.
4. Directus is optional behind the provider flag. Public Gateway location
   list/detail routes now use the governed native view; Directus administrative
   CRUD, field/row permissions, hooks, and reviewer UI parity remain incomplete.
5. The checkout has 361 PostgreSQL SQL files through #370, six ClickHouse
   SQL files, and 119 seed SQL files. The plan's older counts are stale.
   Numbering gaps are intentional evidence to preserve, not repair.
6. requirements.txt combines API, orchestration, RPC, GIS, ML, and analytics
   dependencies. Both API and worker images install that entire list.
   pyproject.toml currently configures tools rather than distribution extras,
   and uv.lock is ignored. Do not assume a package/extras setup exists.
7. The worker image starts cron. Its only active crontab entry is the health
   alert script; database scheduler and event worker are separate opt-in
   services in docker-compose.worker.yml. Do not silently duplicate dispatch.
8. services/flows/pipelines.py full_pipeline imports
   monitoring_pipeline and analytics_pipeline sibling modules which are
   absent; the functions exist in pipelines.py itself. The .submit calls on
   flow functions also need validation against the installed Prefect version.
   These are baseline concerns to resolve in the orchestration slice, not
   evidence that replacing Prefect is already safe.

## Baseline next-slice recommendation (historical)

The following Phase 1 recommendation belongs to the frozen baseline. For the
current Phase 7 focus, delivered work and remaining gates, use [progress.md](progress.md).

Phase 1 should add provider/settings interfaces while preserving the current
default deployment. Start at services/core/features.py, services/core/health.py,
services/common/database.py, services/ingestion/base.py, and the existing cache.
Use the matrix to select focused contract tests; establish a clean baseline for
those tests before changing behavior.

Before a minimal runtime cutover, reconcile local migration backlog, take a
verified backup, select one scheduler owner, and implement native location
reads with explicit field/row policy. Merely disabling Directus or removing
ClickHouse environment settings cannot satisfy current gateway behavior.

Phase 0 has no production cutover. Static inventory is complete; capability
parity, restore rehearsal, image architecture certification, and remaining
live storage measurements are explicitly unvalidated. Each provider's gate
must close before that provider or its state is removed.
