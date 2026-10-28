# Kokonut Kernel refactor TODO

Updated: 28 October 2026. This is the active cross-phase work queue for the
owner-provided [architecture implementation plan](implementation-plan-alignment.md).
The detailed, historically preserved acceptance records remain in
[batches.md](batches.md); this file groups their remaining gates into work that
can proceed now and gates that need an owner, provider, populated source data,
or production environment. Check an item only when its evidence is recorded in
the batch log and the affected capability/progress records are updated.

## Completed in the current continuation

- [x] Add strict OpenAPI/runtime response contracts for farm-activity list and
  published-list reads, including exact location, source-system, and published
  lifecycle checks.
- [x] Validate pollution-incident resolution results against the requested
  incident and location, with a fixed resolved status and no undeclared fields.
- [x] Add a strict private governance-tension detail contract for its
  location/tension identity, bounded event history, and safe reviewer
  projection.
- [x] Validate driver-catalog responses against the generated page and entry
  contracts in both native REST SDKs, rejecting malformed types, bounds, and
  undeclared fields while retaining the HTTP response on SDK errors.
- [x] Add a strict OpenAPI/runtime success contract for Delphi study-open
  readiness. Bind study/location IDs, validate the fixed SQL-derived blocker
  order and eligibility facts, and return a sanitized no-store error for
  malformed projections.
- [x] Align Python and JavaScript native REST SDK error objects by preserving
  the received HTTP response for status, JSON, and envelope failures; transport
  errors without an HTTP response remain unchanged.
- [x] Add a strict OpenAPI/runtime contract to the private stakeholder identity
  resolution read. It returns only the requested location, canonical party ID,
  and aware resolution timestamp; malformed service projections fail with a
  sanitized no-store error.
- [x] Add a strict OpenAPI/runtime success contract to the location-scoped
  governance-tension review queue. Validate its enums, severity bounds,
  timestamps, exact projection, descending order, location, and cursor binding;
  invalid projections return the existing sanitized no-store error.
- [x] Correct the weekly Prefect flow description and add a regression proving
  the currently deployed flow runs climate refresh only. The legacy ML
  retraining path remains outside the Kernel job catalog until it receives a
  signed, bounded identity and retry/idempotency contract.
- [x] Add a strict, location/study/page-bound contract for the Delphi
  participant-invite inventory. Private invite tokens and participant identity
  remain outside the projection; continuation stops at the existing offset
  ceiling.
- [x] Validate `mrv_claim.sensor_device_id` and `sensor_alert_id` through the
  referenced device's location in the optional Directus tenant hook. The
  polymorphic source-record array remains unresolved because it has no table
  discriminator; no broader Directus parity is claimed.
- [x] Convert all four State-of-Kokonut funding/actor queries from conditional
  SQL fragments to static named-bind predicates. Explicit selected-location
  calls remain location-bound; `None` preserves the deliberate network rollup.
  The helper inventory now resolves 169/169 query sites with zero unresolved
  SQL sources.
- [x] Add strict location, ordering, cursor, count, and projection contracts
  for threatcasting backcast-plan list/detail reads while retaining their
  advisory-only semantics.
- [x] Repair the Kernel release-input lock after the OIDC Dockerfile added its
  shared HTTP client requirement. The hash gate now covers the updated
  `Dockerfile.kernel` plus `requirements/oidc.txt` and
  `requirements/http-client.txt`. The local release-input check and 36 focused
  Kernel profile/release-gate tests pass. Hosted CI #71 failed on the stale
  Dockerfile hash; Security passed. A new hosted CI run is still required to
  confirm the repair. See
  [evidence](builds/2026-10-28-recovery/ci-kernel-release-lock-repair.json).
- [x] Keep the migration-seeded `market_reference_data` catalog readable but
  immutable to `kokonut_runtime`. Schema 142 defines commodity categories and
  unit labels, and no service or extension writes the table. Migration 678 and
  runtime-role provisioning deny table and residual column writes while
  preserving the separate Directus administration grant. Focused native and
  ARM64/QEMU PostgreSQL checks pass migration replay, compatibility-grant
  reapplication, read access, write denial, and Directus-role preservation.
  The full native replay and two-tenant probe pass through all 669 schemas;
  candidate and legacy databases remain untouched. See
  [evidence](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-disposable.json).
- [x] Keep the schema-seeded `quantity_unit` vocabulary readable but immutable
  to `kokonut_runtime`. Migration 112 defines and seeds the shared unit labels;
  source and runtime SQL inventories found no application writer or relation
  reader. Migration 679 and runtime-role provisioning deny table and residual
  column writes while preserving Directus administration. Focused native and
  ARM64/QEMU PostgreSQL checks pass migration replay, read access, write
  denial, provisioner reapplication, and Directus grant preservation. The full
  native replay and 34-check two-tenant probe pass through all 670 schemas;
  candidate and legacy databases remain untouched. See
  [native evidence](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-disposable.json).
- [x] Remove stale Directus workflow-role authorization caching. The hook now
  resolves the current role name on each non-admin authorization check, so a
  role rename takes effect immediately; server accountability remains required
  and payload-supplied accountability is ignored. The role/error-safety/workflow
  selection passes 46 tests, and the extension build/typecheck passes. No live
  Directus or database was used ([evidence](builds/2026-10-28-recovery/directus-role-resolution-freshness.json)).
- [x] Bind Delphi worker output to the normalized requested study as well as
  the requested location. An unexpected row returned by the source view now
  fails closed, rolls back the transaction, and closes the connection. The
  focused Delphi worker selection passes 3 tests with targeted Ruff and
  compilation ([evidence](builds/2026-10-28-recovery/delphi-source-study-scope-match.json)).
- [x] Require explicit location scope for the adoption-barrier report before
  database access and remove its unscoped SQL branch. Its location-bound public
  projection still includes reviewed global rows. The focused report selection
  passes 456 tests with Ruff, query-scope inventory, Python compilation, and
  diff checks ([evidence](builds/2026-10-28-recovery/adoption-barriers-location-scope.json)).
- [x] Re-run all schema migrations through 679 on ARM64/QEMU with a 1.5 GiB,
  two-CPU database limit. All 670 schemas applied on `aarch64`, with zero
  pending or failed migrations, no seeds, no OOM, and successful cleanup. This
  remains software portability evidence only; physical Pi, populated-data, and
  production recovery gates remain open ([evidence](builds/2026-10-28-recovery/arm64-resource-limited-schema-679.json)).
- [x] Reconcile C4 provider-job sources. The 23-entry native job catalog matches
  its generated contract and five Prefect deployments; the legacy health-check
  flow is not deployed, and the forecast worker remains default-off. Do not
  invent an active schedule; C4 still needs owner/runtime-state reconciliation
  ([inventory](worker-job-contract-inventory.json)).
- [x] Align Python and TypeScript `get_item` projection serialization. Python
  now omits `fields` for `None`, emits JSON `[]` for an explicit empty list,
  and sends populated field lists as CSV, matching the pinned TypeScript SDK.
  Three mocked wire-contract cases, targeted Ruff, compilation, and diff checks
  pass ([evidence](builds/2026-10-28-recovery/sdk-empty-fields-projection-parity.json)).
- [x] Require explicit location scope in the four location-lineaged stakeholder
  report generators before database access. Their direct-call and CLI behavior
  now agrees with the report registry; `--all` is rejected for these reports.
  The combined nine-module report suite passes 507 tests with four database-
  dependent skips, plus generated query-scope inventory, Ruff, compilation, and diff
  checks ([evidence](builds/2026-10-28-recovery/stakeholder-report-explicit-location.json)).
- [x] Align the TypeScript `ReportSnapshot` model with the canonical SQL and
  Python model; removed three unsupported TypeScript fields. Focused schema
  tests pass (13), and the full parity check covers 109 models/2,150 columns
  ([evidence](builds/2026-10-28-recovery/report-snapshot-types-canonical-schema-parity.json)).
- [x] Require explicit location scope for direct `bio_recipe_library` calls
  before opening a cursor and remove the unscoped SQL branch. Reviewed global
  public catalog rows remain visible under the selected-location query; the
  focused check passes 349 tests with inventory, Ruff, compilation, and diff
  checks ([evidence](builds/2026-10-28-recovery/bio-recipe-library-location-scope.json)).
- [x] Reject booleans for notification-outbox batch-size and lease-duration
  bounds before database access. Python's `bool` subclassing of `int` had
  admitted `True` as a one-second lease; 40 mocked outbox/delivery tests pass
  ([evidence](builds/2026-10-28-recovery/notification-outbox-rejects-boolean-bounds.json)).
- [x] Require explicit location scope for direct `community_governance`
  report calls before cursor creation; the selected-location query preserves
  reviewed public global rows. The focused suite passes 341 tests, and the
  combined nine-module report selection passes 507 with four database-
  dependent skips ([evidence](builds/2026-10-28-recovery/community-governance-location-scope.json)).
- [x] Require explicit locations for `governance_inclusion` and
  `governance_throughput` before cursor creation; their selected-location
  queries retain reviewed public global rows. Dedicated tests pass 290 and 11
  cases respectively. The integrated nine-module report suite passes 507 with
  four database-dependent skips; the generated inventory has 171 direct query
  sites, 170 positional bind sites, and zero unresolved sites. See
  [inclusion evidence](builds/2026-10-28-recovery/governance-inclusion-location-scope.json)
  and [throughput evidence](builds/2026-10-28-recovery/governance-throughput-location-scope.json).
- [x] Publish existing `1..100` pagination limits in the Gateway OpenAPI
  contract for operator ecocredit-batch and attestation list routes. Invalid
  values fail before service invocation; the focused plus existing route suite
  passes 21 tests ([evidence](builds/2026-10-28-recovery/gateway-pagination-openapi-bounds.json)).
- [x] Extend Gateway pagination bounds to Field Activity, nutrient-balance,
  irrigation, crop-simulation, traceability, geostatistics, trend-analysis,
  extension-learning, pollinator health, Delphi consultation, competitive
  landscape, business-architecture, business-planning, Delphi recommendation
  draft, recommendation review, stakeholder identity, stakeholder-trust, and
  Delphi minority-review lists, including AI-summary review, strategy,
  sequential decisions, governance roles, planning budgets, business-planning
  history, threatcasting, Delphi participant invites, consent notices,
  operating-pilot, solution-lifecycle, and pollution-incident queues. The
  endpoints publish validated limit/offset constraints in OpenAPI and reject
  invalid values before service access. Focused suites pass 6, 19, 13, 24, 15,
  73, 34, 12, 74, 21, 50, 18, 32, 15, 18, 13, 20, 21, 28, 14, 20, 8, 20, 23, 14, 29, 35, 243, 448, and 25 tests respectively; bounds match each service's existing maximum
  ([Field Activity](builds/2026-10-28-recovery/farm-activity-pagination-openapi-bounds.json),
  [nutrients](builds/2026-10-28-recovery/nutrient-pagination-openapi-bounds.json),
  [irrigation](builds/2026-10-28-recovery/irrigation-pagination-openapi-bounds.json),
  [crop simulations](builds/2026-10-28-recovery/crop-simulation-pagination-openapi-bounds.json),
  [traceability](builds/2026-10-28-recovery/traceability-pagination-openapi-bounds.json),
  [geostatistics](builds/2026-10-28-recovery/geostatistics-pagination-openapi-bounds.json),
  [trend analysis](builds/2026-10-28-recovery/trend-analysis-pagination-openapi-bounds.json),
  [extension learning](builds/2026-10-28-recovery/extension-learning-pagination-openapi-bounds.json),
  [pollinator health](builds/2026-10-28-recovery/pollinator-pagination-openapi-bounds.json),
  [Delphi consultation](builds/2026-10-28-recovery/delphi-consultation-pagination-openapi-bounds.json),
  [competitive landscape](builds/2026-10-28-recovery/competitive-landscape-pagination-openapi-bounds.json),
  [business architecture](builds/2026-10-28-recovery/business-architecture-pagination-openapi-bounds.json),
  [Delphi recommendation drafts](builds/2026-10-28-recovery/delphi-draft-study-pagination-openapi-bounds.json),
  [stakeholder identity](builds/2026-10-28-recovery/stakeholder-identity-pagination-openapi-bounds.json),
  [business planning](builds/2026-10-28-recovery/business-planning-pagination-openapi-bounds.json),
  [stakeholder trust](builds/2026-10-28-recovery/stakeholder-identity-trust-pagination-openapi-bounds.json),
  [Delphi minority review](builds/2026-10-28-recovery/delphi-minority-review-pagination-openapi-bounds.json),
  [AI-summary review](builds/2026-10-28-recovery/ai-summary-review-pagination-openapi-bounds.json),
  [strategy](builds/2026-10-28-recovery/strategy-pagination-openapi-bounds.json),
  [sequential decisions](builds/2026-10-28-recovery/sequential-decision-pagination-openapi-bounds.json),
  [governance roles](builds/2026-10-28-recovery/governance-role-pagination-openapi-bounds.json),
  [planning budgets](builds/2026-10-28-recovery/planning-budget-pagination-openapi-bounds.json),
  [business-planning history](builds/2026-10-28-recovery/business-planning-edit-history-pagination-openapi.json),
  [threatcasting](builds/2026-10-28-recovery/threatcasting-pagination-openapi-bounds.json),
  [Delphi participant invites](builds/2026-10-28-recovery/delphi-participant-invite-pagination-openapi.json),
  [Delphi consent notices](builds/2026-10-28-recovery/delphi-consent-notice-pagination-openapi-bounds.json),
  [operating pilot](builds/2026-10-28-recovery/operating-pilot-pagination-openapi-bounds.json),
  [solution lifecycle](builds/2026-10-28-recovery/solution-lifecycle-pagination-openapi-bounds.json),
  [waste incident offset](builds/2026-10-28-recovery/waste-incident-offset-bounds.json)).
- [x] Close two more report input-scope mismatches: `replication_readiness`
  and `scaling_roadmap` were location-required by the registry/CLI but their
  direct generators accepted missing locations and queried all public-view
  rows. Both now fail before opening a cursor while keeping reviewed global
  rows inside a selected-location query. The integrated report selection
  passes 516 tests with four database-dependent skips; the fresh inventory
  has 169 direct query sites, 168 positional bind sites, and zero unresolved
  ([replication readiness](builds/2026-10-28-recovery/replication-readiness-location-scope.json),
  [scaling roadmap](builds/2026-10-28-recovery/scaling-roadmap-location-scope.json)).
- [x] Restore typed-list extension query parity across the Python and
  JavaScript SDKs. Python `ListOptions.extra_params` now matches TypeScript
  `ListOptions.extraParams`; representative scoped Field Note reads preserve
  extension parameters while standard options and the required location filter
  remain authoritative. The focused Python SDK/method-parity suite passes 107
  tests, JavaScript passes 56, the TypeScript build and targeted Ruff pass, and
  mocked checks use no database, provider, or network ([evidence](builds/2026-10-28-recovery/sdk-typed-extension-query-parity.json)).
- [x] Keep calculated NOI snapshots read-only in both SDKs. Source review found
  no SDK mutation callsites; generic writes could supply final financial values
  without calculation provenance. Preserve list/detail/crop-cycle reads and
  leave generation in the existing worker/service integrations. Python SDK,
  parity, and report-governance tests pass 111; JavaScript passes 55; the
  TypeScript build, Ruff, and compilation pass. Existing service and Directus
  extension writers were not changed or runtime-validated. See
  [evidence](builds/2026-10-27-recovery/sdk-noi-snapshot-read-only-contract.json).
- [x] Remove generic attestation-record writes from both SDKs and correct the
  workflow examples. `attestation_record` represents governed workflow state
  and chain-indexer projections; direct collection CRUD can create a database
  row without EAS publication or independent review. Preserve list/detail,
  pending-state, and subject-filtered reads. Real chain submission/revocation
  remains in the dedicated EAS service and governed signing workflow. Python SDK,
  parity, and report-governance tests pass 109; JavaScript passes 54; the
  TypeScript build, Ruff, and compilation pass. No database/provider was used.
  See [evidence](builds/2026-10-27-recovery/sdk-attestation-read-only-contract.json).
- [x] Cross-reference the original plan's Phases 0–8 against the repository
  ledger and sprint scope.
- [x] Replay the current 642 ordered schema files on an isolated database and
  run the two-tenant signed-context probe. The probe exposed 1,101 public
  tables with runtime DML and RLS disabled; it does not prove isolation for
  those tables.
- [x] Start a fresh isolated ZITADEL API/Login stack and confirm internal OIDC
  discovery. Fix and record safe permissions for its Login UI token volume.
- [x] Keep these findings and acceptance limits in the sprint, phase and
  capability records. Local commits: `020a5279`, `be1c2c2e`, `968a49fc`,
  `e6bee5ae`, `2f7e0c0a`, `97317dfc`, `263a6d19`, `03d215b2`, `cd7a02bc`.
- [x] Add relation-level runtime ACL/default-ACL capture to the isolated probe
  and a source-callsite/revoke join at
  [`scripts/runtime-privilege-callsite-report.py`](../../scripts/runtime-privilege-callsite-report.py).
  The 26 October full-schema report covered all 1,511 public relations and
  matched 92 source-declared runtime boundaries. The current 27 October replay
  through migration 652 covers the same 1,511 relations and matches 93
  boundaries with zero gaps. It records 1,026 ordinary/partitioned relations
  with effective table-level DML while RLS is off; one now has insert-only
  append-log access, so the count is not a count of UPDATE/DELETE exposure.
  The SQL callsite join remains heuristic. Candidate and legacy privileges
  were untouched.
- [x] Source-audit migration-seeded `waste_type` and `disposal_method`: current
  services use their values on `waste_stream` and have no application write
  target against either lookup catalog. Migration 660, runtime provisioning,
  and the disposable acceptance harness now keep them readable while denying
  runtime mutation. The source/migration/ARM64-contract selection passes 121
  tests; Ruff, compilation, SQL/worker inventories, dependency/provider
  boundaries, matrix validation, and diff checks pass. Database acceptance
  remains open because a read-only Docker query timed out after eight seconds.
  Candidate and legacy databases were not contacted.
- [x] Implement the source-declared C1 runtime ACL repair in role provisioning:
  after the compatibility grant, deny direct runtime access to the 79 private
  tables, deny writes on 12 migration-defined mutation-only tables, and keep
  the append-only farm-activity ledger SELECT-only. The provisioner verifies
  the resulting table and column ACLs. Static comparison covers 91 private or
  mutation-denied relations plus the separate API-key read-only column
  allowlist, with no policy gap. The focused runtime-role suite passes 48
  tests, and a disposable PostgreSQL fixture confirms the scoped ACL outcomes
  plus column-grant detection; full migration-installed acceptance is recorded
  immediately below.
- [x] Complete the 26 October full-schema runtime-role acceptance against all 642 ordered
  migrations through 651: the provisioner installs and verifies all 79 private
  and 12 mutation-denied relation boundaries, with zero residual table or
  column privileges; the general runtime retains the farm-activity audit read.
  Two real restricted operator sessions establish correct synthetic tenant
  context through the bounded function, reject cross-location access, and clear
  context on denial and transaction end. No seeds or farm data were loaded;
  cleanup succeeded; candidate and legacy databases were untouched. The
  probe also verifies API-key reads are limited to seven reviewed columns and
  all writes are denied. The separate ARM64 full-schema replay also passes,
  while this role probe ran natively with matching AMD64 images. The refreshed
  26 October report covered 92 declared boundaries; the current 27 October
  report covers 93 (92 table policies plus the API-key column allowlist) with
  zero gaps across 1,511 relations. See
  [full-schema role evidence](builds/2026-10-26-recovery/runtime-role-full-schema-disposable.json).
- [x] Create a reproducible, read-only source-line inventory for C1's remaining
  analytics write candidates. It links 275 currently unprotected relations to
  425 unique candidate SQL sites across 89 source files (437 relation/site
  references) and reports any unmatched source relation; none are missing.
  Every entry stays marked for caller/source review, and the report explicitly
  forbids inferring authorization or revoking privileges from static matches.
  No database, candidate, or legacy service was accessed. See the
  [inventory](builds/2026-10-27-recovery/analytics-runtime-write-candidate-inventory.json)
  and [generator](../../scripts/runtime-analytics-write-candidate-inventory.py).
- [x] Correct third-party data-portability audit writes to use the existing
  `data_access_log` contract from migration 144. The previous insert targeted
  `access_audit_log` with columns and a status value that table does not have;
  it now records an export/success event in the correct transaction. The
  focused data-governance and analytics-inventory suites pass. No schema change
  or database rollout was needed.
- [x] Enforce the append-only runtime boundary for `data_access_log`. Migration
  652 clears table and residual column grants, restoring only `SELECT` and
  `INSERT`; the provisioner reapplies and verifies that policy after its
  compatibility grant. Disposable PostgreSQL 16 confirms migration replay,
  successful read/append, denial of update/delete/truncate, and removal of stale
  column grants. The refreshed native full-schema probe passes all 643
  migrations through 652 and two-tenant signed-context acceptance with zero
  seeds; no candidate/legacy state was used. The policy report covers 93
  declared boundaries with zero gaps across 1,511 relations. Its 1,026
  table-level DML/RLS-disabled count includes the intentionally insert-only
  audit ledger; it does not mean all those relations allow UPDATE/DELETE. See
  [migration](../schemas/postgres/652_runtime_append_only_data_access_log.sql),
  [isolated acceptance](builds/2026-10-27-recovery/runtime-append-only-data-access-log-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Replay the complete current schema through migration 652 under Docker
  linux/arm64 QEMU. All 643 migration files applied with zero pending/failed,
  no seeds, no host ports, and successful cleanup. This is software portability
  evidence only. See the [ARM64 replay record](builds/2026-10-27-recovery/arm64-schema-652-disposable.json).
- [x] Build the current Kernel app OCI image for AMD64 and ARM64 and validate
  the release lock: all 72 Python packages match across architectures. The
  ARM64 image smoke imports the Gateway factory and migration-652 runtime-role
  policy in a no-network, read-only container; temporary artifacts were
  removed. See the [build/smoke record](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json).
- [x] Build and validate the optional ClickHouse dependency superset for both
  architectures: 75 locked Python packages match. The ARM64 smoke imports
  `clickhouse_connect` offline. The minimal, edge, standard, and analytics
  Compose selections also pass ARM64 `config --quiet` with synthetic
  placeholders; no services or profile resources were started. See the same
  [build/profile record](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json).
- [x] Replay all 643 schema migrations through 652 on ARM64/QEMU with the
  disposable database limited to 1.5 GiB memory, no additional swap, and two
  CPUs. All migrations applied with zero failures/pending, no seeds, no OOM
  kill, and successful temporary-resource cleanup. See the
  [resource-limited evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-652.json).
- [x] Exercise migration 653's read-only advisory-rule ACL on the local ARM64
  PostgreSQL image. The disposable synthetic-table check replays the migration,
  verifies reads, denies insert/update/delete and references, and confirms the
  runtime provisioner removes simulated broad and column grants. This validates
  the migration slice on Docker's ARM64 platform; the full ARM64 schema chain
  remains through migration 652 ([evidence](builds/2026-10-27-recovery/advisory-rule-runtime-read-only-arm64-disposable.json)).
- [x] Launch the current Kernel Gateway on ARM64 under a 512 MiB memory, one-CPU,
  64-PID, no-network, read-only-root container budget. Docker reports the exact
  limits, and `/health` returns `status=ok`, `service=gateway`, and
  `audit_capture=ok`; the checker removes its temporary container and image.
  This is process liveness with no PostgreSQL/provider connectivity, not schema
  readiness or Pi hardware acceptance ([checker](../../scripts/check-kernel-app-resource-disposable.py);
  [evidence](builds/2026-10-27-recovery/kernel-app-arm64-constrained-runtime.json)).
- [x] Verify age-encrypted single-database dump/restore plumbing using two
  synthetic rows, a wrong-key rejection, and restoration into a fresh
  `template0` database. The checker uses network-disabled containers and
  removes its uniquely labeled volumes. This does not exercise the full
  `kernel-checkpoint.sh`/role-bootstrap recovery sequence or provider/media
  state ([checker](../../scripts/check-kernel-backup-restore-disposable.py);
  [evidence](builds/2026-10-27-recovery/kernel-synthetic-backup-restore.json)).
- [x] Exercise the actual `kernel-checkpoint.sh` plus fresh-cluster role
  prerequisites and full database restore. All 643 migrations through 652
  restore atomically from the age-encrypted checkpoint with matching migration
  fingerprint and synthetic sentinel. The recovery Compose target raises
  `max_locks_per_transaction` to 4096 to accommodate the full schema. The
  uniquely named, internal-only source and target projects and temporary
  checkpoint were removed. No seeds, farm data, candidate, or legacy state was
  used ([evidence](builds/2026-10-27-recovery/kernel-checkpoint-restore-disposable.json);
  [recovery procedure](recovery-preparation.md)). This is synthetic local
  acceptance only; populated data, external media/providers, R2, full platform,
  constrained restore runtime, and 24-hour recovery remain open.
- [x] Make the analytics write-candidate inventory distinguish DML targets
  from tables read by a statement. Runtime SQL inventory version 2 now records
  conservative targets for simple leading INSERT/UPDATE/DELETE/MERGE statements;
  the analytics join uses those targets and keeps unmatched ACL candidates
  visible. This corrected two `INSERT ... SELECT` false positives: `advisory_rule`
  and `farm` are source reads, not the insert targets. The report now covers 275
  ACL candidate relations and 425 target sites identified by the conservative
  matcher across 89 files; those two rows are explicitly unmatched for source
  review. No grants or database
  state changed ([inventory](builds/2026-10-27-recovery/analytics-runtime-write-candidate-inventory.json);
  [scanner](../../scripts/worker_sql_inventory.py)).
- [x] Keep shared advisory rule configuration readable but immutable to the
  general runtime role. Source review found the application reads
  `advisory_rule` to create farm recommendations; no application writer was
  found, and seed/admin processes remain the configuration path. Migration 653
  removes table and residual column write/reference grants, restores `SELECT`,
  and the runtime provisioner reapplies that boundary after compatibility
  grants. Disposable PostgreSQL 16 confirms migration replay, read success,
  insert/update/delete denial, and stale grant cleanup. A clean 644-migration
  replay through 653 passed full runtime provisioning and the two-tenant
  signed-context probe. The refreshed report covers 94 boundaries with no
  gaps; 1,025 relations retain effective DML while RLS is disabled, so broader
  C1 work remains open. The analytics inventory now has 274 candidate ACL
  relations and 425 write-target sites across 89 files; `farm` is the remaining
  unmatched source candidate. Source review traced the analytics reference to
  `INSERT ... SELECT` statements that write other tables; the complete writer
  set and optional Directus behavior for this core relation are not established,
  so its grants remain unchanged. See [migration](../schemas/postgres/653_runtime_advisory_rule_read_only.sql),
  [disposable ACL check](builds/2026-10-27-recovery/advisory-rule-runtime-read-only-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-653-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Make the shared `crop_family` taxonomy read-only to the general runtime.
  Source review found eight analytics SELECT sites and no service, extension,
  app, script, or migration writer after seed initialization; taxonomy changes
  remain a seed/admin operation. Migration 654 clears table and residual
  column INSERT/UPDATE/REFERENCES grants and restores SELECT. The provisioner
  reapplies the same rule after compatibility grants. A focused disposable
  PostgreSQL check confirms migration replay, read success, write/truncate and
  reference denial, and stale-grant cleanup. A clean native replay through all
  645 migrations passes runtime provisioning and the two-tenant signed-context
  probe. The report now covers 95 boundaries across 1,511 relations with zero
  gaps; 1,024 relations retain effective DML while RLS is disabled. The
  analytics candidate inventory remains 274 relations and 425 target sites
  across 89 files, with `farm` unmatched pending complete writer/Directus
  review. The focused 129-test selection, Ruff, compilation, source inventory,
  and matrix validation pass. Candidate and legacy databases were untouched.
  Rollback may revert application code while retaining migration 654; restoring
  writes requires a separately reviewed forward migration. See
  [migration](../schemas/postgres/654_runtime_crop_family_read_only.sql),
  [disposable ACL check](builds/2026-10-27-recovery/crop-family-runtime-read-only-disposable.json),
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-654-disposable.json),
  and [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json).
- [x] Verify migrations 652–654 and the read-only `crop_family` boundary on
  the local ARM64 PostgreSQL image. The loopback-restricted disposable synthetic
  ACL check confirms migration apply/replay, SELECT success, mutation,
  REFERENCES, and stale table/column grant denial for all three policies.
  Docker reports `linux/arm64`; temporary resources were removed. This is
  focused QEMU software-portability evidence, not a full schema replay through
  654 or Raspberry Pi hardware acceptance ([evidence](builds/2026-10-27-recovery/crop-family-runtime-read-only-arm64-disposable.json)).
  The full ARM64/QEMU chain subsequently passed all 645 files through 654
  under the resource limits recorded below.
- [x] Keep `crop_nutrient_removal_factor` readable but immutable to the general
  runtime. Source audit found the relation is initialized by migration 151 and
  read by `services/analytics/nutrient_budget.py`; no application writer was
  found. Migration 655 clears table and column mutation/reference grants, and
  the runtime provisioner reapplies the policy after compatibility grants. A
  disposable PostgreSQL 16 check confirms replay, SELECT success, and mutation,
  truncate, reference, and stale-column-grant denial. A clean native replay of
  all 646 migrations through 655 passes provisioner setup and the two-tenant
  signed-context probe. The refreshed source report covers 96 declared
  boundaries with zero gaps; 1,023 relations retain effective table-level DML
  while RLS is disabled. The target-aware analytics inventory remains 274
  relations and 425 write sites across 89 files, with `farm` unmatched pending
  source/Directus review. All 130 focused tests pass, along with Ruff,
  compilation, source inventories, dependency/provider checks, and capability
  validation. Candidate and legacy databases were untouched. Retain migration
  655 on code rollback; restoring runtime writes requires a separately reviewed
  forward migration ([migration](../schemas/postgres/655_runtime_crop_nutrient_removal_factor_read_only.sql);
  [ACL evidence](builds/2026-10-27-recovery/crop-nutrient-factor-runtime-read-only-disposable.json);
  [full-schema evidence](builds/2026-10-27-recovery/runtime-role-full-schema-655-disposable.json);
  [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Replay the complete 645-file schema through migration 654 on ARM64/QEMU
  under a verified 1.5 GiB memory/swap and two-CPU database limit. All files
  applied with zero failures or pending migrations, no seeds or farm data, no
  OOM kill, and successful temporary-resource cleanup. This is software
  portability evidence only; it is not a full replay through 655 or physical
  Raspberry Pi acceptance ([evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-654.json)).
- [x] Verify the read-only `crop_nutrient_removal_factor` ACL on ARM64/QEMU
  together with migrations 652–654. The disposable PostgreSQL check confirms
  migration apply/replay, SELECT success, and table/column mutation, truncate,
  REFERENCES, and stale-grant denial for the 15 mutation-denied relations; all
  79 private relations remain inaccessible. Temporary resources were removed.
  This is focused software portability evidence, not Raspberry Pi hardware
  acceptance ([evidence](builds/2026-10-27-recovery/crop-nutrient-factor-runtime-read-only-arm64-disposable.json)).
- [x] Keep migration-seeded `certification_type` lookup data read-only to the
  general runtime. The service/Gateway callsites only resolve the shared
  reference; migration 143 initializes it, and no application or extension
  writer was found. Migration 656 removes table and residual column
  mutation/reference grants and restores `SELECT`; the runtime provisioner
  reapplies that contract after compatibility grants. Disposable PostgreSQL 16
  checks pass on native AMD64 and ARM64/QEMU. A clean native replay of all 647
  migrations through 656 passes full runtime provisioning and the two-tenant
  signed-context probe. The refreshed report covers 97 declared boundaries
  with zero gaps, and 1,022 public relations retain effective table DML while
  RLS is disabled. The 131-test focused selection and static boundary checks
  pass. Candidate and legacy databases were untouched. Retain migration 656 on
  code rollback; restoring runtime writes requires a separately reviewed
  forward migration ([migration](../schemas/postgres/656_runtime_certification_type_read_only.sql);
  [native ACL check](builds/2026-10-27-recovery/certification-type-runtime-read-only-disposable.json);
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-656-disposable.json);
  [source-policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Verify migration 656's read-only `certification_type` policy on ARM64/QEMU.
  The synthetic PostgreSQL 16 fixture confirms migration apply/replay, SELECT
  success, write/truncate/reference denial, and stale table/column-grant
  removal after provisioner reapplication. All 79 private relations remain
  inaccessible and all 16 mutation-denied relations remain read-only. This is
  focused software portability evidence, not a full ARM64 replay through 656
  or physical Raspberry Pi acceptance ([evidence](builds/2026-10-27-recovery/certification-type-runtime-read-only-arm64-disposable.json)).
- [x] Protect migration-seeded `cooperative_type` and
  `dfs_insurance_product_type` reference catalogs from runtime mutation. Their
  service callsites only read the shared catalogs, the schema migrations seed
  them, and no service, extension, or script writer was found. Migration 657
  clears table and residual column INSERT/UPDATE/REFERENCES grants, restores
  SELECT, and the runtime provisioner reapplies the boundary after compatibility
  grants. Native and ARM64/QEMU disposable PostgreSQL 16 checks pass migration
  replay, reads, mutation/truncate/reference denial, stale-grant cleanup, and
  provisioner reapplication. A clean native replay of all 648 migrations
  through 657 passes full runtime provisioning and the signed two-tenant
  context probe. The refreshed report covers 99 boundaries with zero gaps;
  1,020 public relations still retain table DML while RLS is disabled. All 132
  focused migration/runtime-boundary/report/inventory tests pass, along with
  Ruff, compilation, SQL/worker inventories, dependency/provider checks, and
  matrix validation. Candidate and legacy databases were untouched. Retain
  additive migration 657 on code rollback; restoring writes requires a
  separately reviewed forward migration ([migration](../schemas/postgres/657_runtime_reference_catalogs_read_only.sql);
  [native ACL](builds/2026-10-27-recovery/reference-catalogs-runtime-read-only-disposable.json);
  [full-schema acceptance](builds/2026-10-27-recovery/runtime-role-full-schema-657-disposable.json);
  [policy report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).
- [x] Verify migration 657's reference-catalog ACL on ARM64/QEMU. The synthetic
  PostgreSQL 16 fixture confirms apply/replay, SELECT success,
  mutation/truncate/reference denial, and stale table/column-grant removal
  after provisioner reapplication across 18 mutation-denied relations. All 79
  private relations remain inaccessible. The full ARM64 schema chain remains
  through 654; this is focused software-portability evidence, not Raspberry Pi
  hardware acceptance ([evidence](builds/2026-10-27-recovery/reference-catalogs-runtime-read-only-arm64-disposable.json)).
- [x] Keep private Gateway routes out of the versioned public OpenAPI and SDK
  generation path. The exporter now retains only policy-approved public GET
  reads and fails closed if a public operation is not a read. A regression
  checks the exported contract against the checked-in snapshot and asserts
  that private Baal governance operations are excluded. The public API, route
  policy, and governance-focused selections pass 39 tests. The broader Python
  SDK method/schema/gRPC selection passes 118 tests; JavaScript passes 56 and
  TypeScript passes 35, with both JS/TS packages building successfully. The
  generated Python/TypeScript public SDK files match the OpenAPI snapshot;
  Ruff, Python compilation, and schema parity checks pass. No provider or
  database was contacted ([exporter](../../scripts/export_public_api_openapi.py);
  [regression](../../tests/test_public_api_openapi.py)).
- [x] Validate retirement-certificate location references for `retirement_id`,
  `credit_id`, and `credit_batch_id` on Directus create/update; the shared
  credit-class reference remains global. Focused tenant-hook checks pass (21)
  and TypeScript checking passes.
- [x] Require UUID location scope for location-required strategy reports before
  database access while retaining network-scoped behavior. The regenerated
  inventory covers 94 report types and 167 query sites with no unresolved or
  bind-mismatch sites; the focused report selection passes 107 tests with four
  database-dependent skips.
- [x] Enforce the operating-pilot resource-category page response contract,
  binding location and requested pagination and checking ordering, continuation,
  and small-count suppression. The focused Gateway selection passes 15 tests.

The combined batch also passes Ruff, Python compilation, report-query inventory
validation, TypeScript checking, and `git diff --check`. The capability matrix
remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and now records
62 strict private Gateway response endpoints. No migration, database, provider,
candidate, or legacy service was used. Evidence:
[batch](builds/2026-10-28-recovery/kernel-directus-operating-report-contracts.json).
Checklist: 1,446 complete / 25 open; TODO: 153 checked / 16 open.
- [x] Validate the `revenue_event` sales and financial-transaction references
  against the event's location for create and update. Leave optional
  global-capable treasury/value-flow references unchanged pending an explicit
  cross-scope contract.
- [x] Require an explicit UUID location for direct forecast-report calls before
  cursor creation; report query inventory remains at zero unresolved or
  bind-mismatch sites.
- [x] Make malformed Python Directus error responses use the JavaScript SDK's
  stable `HTTP <status>` fallback rather than arbitrary response text; retain
  valid server messages and attached response metadata.
- [x] Add strict request-bound response validation for Delphi draft-study pages
  and suppress `has_more` when pagination cannot continue within the 10,000
  offset ceiling.
- [x] Validate the Comprehensive Status `crop_noi` section against the
  generator's exact nested projection and selected location; retain the
  sanitized section error contract and leave other section bodies pending audit.
- [x] Validate `expense_event.farm_task_id` against the same location on Directus
  create/update; schema 061 and migration 361 establish the relationship.
- [x] Reject invalid, `all`, and multi-location IDs for direct climate-impact
  report generation before database/helper access; keep the shared protocol
  lookup unchanged.
- [x] Type the Comprehensive Status environmental section from its four
  explicit SQL projections, including PostgreSQL Decimal normalization and
  selected-location binding. Existing unfiltered lifecycle selection, ignored
  period arguments, and free-text notes/causes still need semantic review.

This batch passes 459 focused Python tests, 90 JavaScript tests, 24 Directus
tenant-hook tests, TypeScript builds/checks, Ruff, compilation, report-query
inventory validation, and diff checks. Evidence:
[parallel contract batch](builds/2026-10-28-recovery/kernel-parallel-tenant-report-sdk-contracts.json).

- [x] Reject malformed location UUIDs before cursor or analyzer access across
  eleven operations reports plus ecological-modeling, trophic-pyramid, and
  adaptive-stewardship reports.
- [x] Preflight location UUIDs before database setup for cooperative creation,
  credit enrollment listing, spreadsheet export, energy monitoring, digital
  finance, marketplace, extension, pest management, data governance, and
  optional farmer-identity location filters.
- [x] Enforce strict request-bound success projections for the private
  Governance tactical-item queue and Data Stream attestation read; align
  action-text bounds with migration 445.
- [x] Add read-only, grant-scoped Directus tenant handling for
  `digital_lego_usage`; unassigned/out-of-grant rows fail closed.
- [x] Regenerate report source and query-scope inventories after source-line
  changes from the report preflight guards.

This parallel batch passes 715 focused Python tests and 143 Directus extension
tests. Build/typecheck, Ruff, Python compilation, report inventories,
capability-matrix validation, and diff checks pass. Checklist: 1,487 complete /
25 open; TODO: 193 checked / 16 open. The matrix remains 67 rows (24
baseline-retained, 7 deployed, 36 prepared) with 75 strict private Gateway
response endpoints; the optional Directus adapter covers 28 location-scoped
collections. No database, provider, live Directus runtime, candidate, legacy
service, or live network was used. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-report-cli-gateway-directus-guards.json).

- [x] Reject malformed location UUID scope before cursor access across the 19
  remaining registered location-scoped report generators in Bio Factory,
  Liberation, Stewardship, Scaling, Wellbeing, and Core Environmental reports.
- [x] Add a strict request-bound OpenAPI/runtime response contract for the
  private operating-pilot own-resource-request history page, matching the
  migration 567/568 field bounds, item order, location, and continuation.
- [x] Audit the optional Directus adapter after adding `digital_lego_usage`;
  no further managed-read collection with direct location lineage is safe to
  add. Polymorphic approval, workflow-history, and file-like collections still
  need a verified source-lineage contract.
- [x] Regenerate report source and query-scope inventories after report guard
  changes shifted registered source locations.

The combined focused report and Gateway selection passes 712 Python tests
with 7 skips. Ruff, compilation, inventories, capability-matrix validation,
and diff checks pass. Checklist: 1,491 complete / 25 open; TODO: 197 checked /
16 open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared) with 76 strict private Gateway response endpoints; the optional
Directus adapter covers 28 location-scoped collections. No database, provider,
live Directus runtime, candidate, legacy service, or live network was used.
Evidence: [batch](builds/2026-10-28-recovery/kernel-parallel-report-gateway-acceptance.json).

## Code work to continue without owner input

Work in this order. Each item is a bounded implementation batch, not a claim
that its full source-plan phase is complete.

- [ ] **C1 — Replace broad runtime database privileges with scoped contracts.**
  Initial pre-provisioning inventory remains a historical baseline: 1,101
  relations had runtime DML and RLS disabled. The latest native, network-
  disabled replay applies all 672 ordered schema files through migration 681
  and passes the synthetic two-tenant/operator scope probe. It verifies 128
  declared controls (79 private relations, 46 mutation-denied relations, two
  append-only relations, plus the API-key column boundary), with zero direct
  table/column privilege violations. The observed report still has 992
  relations with effective DML while RLS is disabled, so broad runtime access
  and universal application tenant isolation remain open. ARM64/QEMU now also
  replays all 672 schema files through migration 681 under network-disabled
  1.5 GiB/two-CPU limits, with zero pending/failed files and cleanup complete.
  That run did not execute the optional operator-scope probe; it is
  schema/portability evidence only, not ARM64 ACL-probe or physical Raspberry
  Pi evidence.

  Migrations 676 and 677 keep governed `reference_class` and seeded
  `farmer_credential_type` guidance readable but immutable to
  `kokonut_runtime`; source review found prediction readers but no reference-
  class writer, and credential records keep their type as free text. Both
  migrations and role provisioning preserve the separate Directus/admin grant
  path. Migration 678 applies the same boundary to schema-defined
  `market_reference_data` commodity and unit labels; source inventory found no
  application writer, and separate Directus/admin grants remain intact. Native
  and ARM64/QEMU disposable ACL checks pass apply/replay, table
  and residual-column denial, provisioner reapplication, and Directus-grant
  preservation. Migration 679 applies the same runtime-only read boundary to
  schema-seeded `quantity_unit` labels; source review found no application SQL
  writer or relation reader, and native/ARM64 checks pass with Directus grants
  preserved. Migration 680 adds a narrowly supported read-only boundary for
  `yield_benchmark`: one location-scoped analytics reader and no application
  write path were found; its DML is denied to `kokonut_runtime`, while the
  optional Directus role remains unchanged. This does not establish RLS or
  tenant isolation. The conservative SQL inventory now records 4,936 execution
  sites across 974 files, 1,223 relation candidates, and 588 write-target
  relations. It resolves 53 SQL templates stored in one unambiguous local
  assignment; dynamic identifiers, reassigned variables, and ambiguous/helper
  expressions remain unresolved. It surfaced `service_registry` INSERT/UPDATE
  in `services/analytics/service_catalog.py`; repository search found no
  internal API, CLI, SDK, or scheduled caller, but the public helper and
  bootstrap/catalog ownership still need reconciliation, so grants remain
  unchanged. `process_benchmark` has no repository reader/writer, seed, or
  Directus rule; its location-linked schema does not establish immutability or
  exclude external imports, so grants also remain unchanged. The
  `farm_task_framework_step` relation is an operational many-to-many edge with
  cascades and no direct location key; historic reconciliation found 20
  unresolved scope edges among 41 links, and the owner deferred those links.
  A separate unresolved-write review ledger now tracks 37 existing candidates
  (eight unresolved direct DML targets and 29 conservative `WITH` statements).
  Its legacy fingerprint set is pinned in source. Scope-AST fingerprints and
  per-scope ordinals catch same-scope source-binding edits and distinguish
  duplicate calls; hosted `ci-check.sh` invokes the inventory gate and fails
  when a new candidate lacks reviewed metadata that explicitly disclaims ACL
  approval. Twenty-two scanner tests pass. Parameter, import, mutable-global, and helper-provided values
  remain beyond fingerprint reach. This is source drift detection only: it
  does not change grants, classify existing debt as safe, or establish
  tenant isolation
  ([evidence](builds/2026-10-28-recovery/runtime-sql-unresolved-write-drift-gate.json)).
  It cannot be treated as a static catalog. A follow-up source audit also
  reviewed the seed-managed `sdg`, `pillar_of_value`, `form_of_capital`, and
  `regeneration_principle` tables. Repository code reads these labels but does
  not write them outside the seed; however, their Kokonut-specific definitions
  may be intentionally owner-customizable, and `sdg` has signed-worker RLS
  policy. They remain review candidates rather than safe runtime revocations
  until the management path and ownership are confirmed. These are
  heuristic/source audits, not proof that external writes are absent or
  tenant-authorized. The three pest-reference catalogs also have service
  writers reachable from the pest-management CLI; their runtime DML remains
  part of current customization behavior, so no read-only migration is safe
  ([audit](builds/2026-10-28-recovery/pest-reference-runtime-write-audit.json)).
  Migration 681 now applies a narrow read-only boundary to
  `metric_definition`: its 25 service SQL sites across 15 files are reads,
  while curated changes remain on the admin seed/migration path. It revokes
  table and residual column mutation/reference privileges, restores SELECT,
  and preserves the separate Directus role. Runtime provisioning reapplies
  the boundary after compatibility grants. The disposable PostgreSQL 16
  acceptance applies/replays the migration, reads a synthetic definition,
  rejects writes and residual privileges, and verifies Directus grants remain
  unchanged. The harness covers 127 synthetic relations (79 private, 46
  mutation-denied, two append-only); this does not establish RLS or tenant
  isolation. The fresh native full-schema ACL replay now reaches migration 681
  ([migration](../schemas/postgres/681_runtime_metric_definition_read_only.sql);
  [focused acceptance](builds/2026-10-28-recovery/runtime-scoped-write-boundary-disposable.json);
  [full-schema replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json)).
  The source review found
  dynamic curriculum definitions in `competency_framework` with no source-owned
  management contract; its grants remain unchanged until the Gateway or
  optional Directus administration path is explicit. Other unresolved
  candidates include dynamic configuration/retention registries and
  `process_benchmark`, `farm_task_framework_step`, and governed reference data
  without complete caller/consumer ownership proof. Review remaining callers
  and management paths before changing grants. Do not blanket-revoke based on
  static absence. A 28 October follow-up also found that `app_role` has only a
  read callsite in the source inventory, but it stores application
  authorization data and its editor/consumer ownership is unknown; it is not a
  safe revoke candidate without that reconciliation. Preserve rollback and
  distinguish table grants from RLS, worker, Directus, and production
  enforcement. A fresh source audit also examined `consent_data_type`: although
  no application callsite or Directus hook/permission seed uses it and the
  runtime currently has DML with RLS disabled, schema 148 reseeds rows with
  `ON CONFLICT DO UPDATE` and migration 401 changes retention fields. Its Data
  Governance/Consent ownership means this is not a safe fixed-catalog revoke
  without owner confirmation. A second audit rejected
  `bio_ingredient_composition_reference`: its status lifecycle and explicit
  agent-write allowlist contradict an immutable-catalog assumption, and
  Directus/admin mutation paths are not proven absent. No migration was added.
  The current report shows
  245 unprotected DML relations without an inventoried callsite and 420 without
  an inventoried write-target site; the report does not include all Directus,
  external, ownership, security-definer, column-ACL, or populated-runtime paths.
  Trace signed-context/write boundaries for the remaining 281 analytics and 25
  credit-class write-target relations, then reconcile unlocated Directus and
  external callers before selecting further revocations. The first credit-
  class trace found gRPC `CreateBatch` accepts a global
  `ecocredit:batch:write` API-key scope and writes a caller-supplied location
  without signed tenant context; the SQL setter supports exact-location grants
  but this RPC is not wired to it. Other credit-batch writers and the lack of
  active-client/API-key inventory mean changing this path or revoking runtime
  DML could break deployed clients, so no code change is safe until the
  contract is reconciled.
  Sources: [runtime boundary](batches.md#c1-market-reference-catalog-acl--28-october-2026),
  [full native schema replay through 681](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json),
  [ARM64 schema replay through 681](builds/2026-10-28-recovery/arm64-resource-limited-schema-681.json),
  [market-reference ACL](builds/2026-10-28-recovery/market-reference-data-runtime-read-only-arm64-disposable.json),
  [quantity-unit ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-arm64-disposable.json),
  [analytics candidate inventory](builds/2026-10-28-recovery/analytics-runtime-write-candidate-inventory.json),
  [local SQL template resolution](builds/2026-10-28-recovery/runtime-sql-local-query-resolution.json).
  The refreshed ACL report observes the full schema and source policy through
  migration 681, including the `metric_definition` read-only boundary. It
  records 128 migration-backed controls and 992 relations retaining DML while
  RLS is disabled; external writers, populated tenant isolation, and
  production state remain outside the report
  ([report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json)).
- [ ] **C2 — Finish Gateway and SDK contract parity.** Audit registered routes,
  auth/action/scope policy, pagination, error models and SDK behavior; close
  source-verifiable gaps without exposing generic CRUD or weakening default
  denial. The public OpenAPI exporter now excludes private policy routes and
  allows only public GET/read operations in the generated contract. Python and
  TypeScript report and export SDK surfaces now expose read-only collection
  methods. Attestation records likewise remain read-only projections of
  governed workflow and indexed chain state; dedicated EAS workflows retain
  publication and revocation. Calculated NOI snapshots also expose read-only
  SDK methods; reconciliation remains in service/worker paths. Typed list
  accessors now share arbitrary Directus query extensions; Python detail reads
  also preserve explicit `fields=[]` like the pinned TypeScript transport. The
  TypeScript `ReportSnapshot` model now matches canonical SQL and Python. A
  further audit found no additional static SDK mismatch across the 109-model/
  2,150-column check and 15 method/public API tests. Parallel route work now
  aligns service-backed pagination bounds across 32 Gateway list families,
  including all 25 solution-lifecycle routes and 21 operating-pilot routes;
  invalid paging fails before readers run. The expanded changed-route and
  operator integration selection now passes 732 tests, including the Delphi
  participant workspace and six operator list routes. The additional
  data-stream attachment route now publishes `limit=1..100` and
  `offset=0..5,000`; its focused Gateway/auth selection passes 52 tests.
  The public federation-node route now uses `limit=1..100` and
  `offset=0..10,000`; its `nodes` payload now includes exact continuation and
  offset-ceiling metadata, with 36 focused route/error-redaction checks passing.
  The trusted CLI retains its full-list behavior. Data-stream post lists now publish `limit=1..100`
  (default 20) and `offset=0..5,000` (three route checks); Baal proposal lists
  publish `limit=1..100` (default 50) and reject invalid values before reading
  (26 governance checks). The JavaScript SDK now has the Python client's default
  10-second deadline; `timeoutMs` accepts only finite values in the timer-safe
  range 1..2,147,483,647, and explicit `null` is rejected. This prevents Node's
  overflow clamp from aborting a request after 1 ms. Fake-timer coverage checks
  success, rejection, timeout, and cleanup; 18 JavaScript tests, 8 Python
  tests, and the TypeScript build pass. The credit-custody summary now has an explicit response model
  matching its existing service fields; seven focused checks pass and auth
  behavior is unchanged. A fresh list-route sweep found the pollution-incident
  queue is already capped at 100 rows and exposes its bounded offset; it has no
  configurable limit, so no new parameter was invented. Produce traceability
  list/detail reads now have explicit strict response models derived from their
  service projections and schema enums; the models exclude actor names/IDs,
  GPS, notes/reasons, evidence URLs, and arbitrary JSON. Eleven focused checks
  pass while auth and no-store error behavior stay unchanged. Authorization
  parity, authenticated live runtime behavior, and broader SDK route/auth
  runtime parity remain open. The OIDC location-attestation list now has a
  strict 100-record OpenAPI/runtime response model that preserves its current
  payload and `no-store`/`Vary: Cookie` headers while excluding claim, evidence,
  and reviewer data; the focused route selection passes 20 checks
  ([model evidence](builds/2026-10-28-recovery/attestation-response-model-contract.json)).
  The detailed `/api/health/services` route now requires `service_health:read`
  before it probes optional infrastructure; anonymous access is denied while
  public `/health` liveness remains available. Two focused auth/policy checks
  pass ([evidence](builds/2026-10-28-recovery/detailed-health-route-auth-boundary.json)).
  The ecocredit batch list now also has a strict bounded response contract that
  excludes undeclared service fields while preserving tenant authorization and
  cache headers; 13 focused route/OpenAPI tests pass
  ([evidence](builds/2026-10-28-recovery/ecocredit-batch-response-contract.json)).
  Python SDK timeouts now reject boolean, nonnumeric, non-finite, nonpositive,
  and overflow-sized values before networking while preserving the 10-second
  default; 17 focused tests pass
  ([evidence](builds/2026-10-28-recovery/sdk-python-public-api-timeout-parity.json)).
  The enabled driver catalog now also has a versioned `/api/v1/drivers`
  contract with generated typed Python/TypeScript clients, bounded pagination,
  and a generic no-store 500 on registry failure; it no longer reports a false
  empty page. The 47-test Gateway/OpenAPI/Python-SDK selection and full 73-test
  JavaScript SDK suite pass ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
  The private cooperative summary now publishes a strict OpenAPI success
  model and validates the projection before returning its raw response; its
  ten-test selection covers undeclared fields and preserved error/cache
  contracts ([evidence](builds/2026-10-28-recovery/cooperative-summary-response-contract.json)).
  The yield-monitoring summary now has the same explicit boundary for its
  grouped aggregates and bounded recent-harvest projection; fourteen route
  tests verify its OpenAPI schema, malformed-field rejection, and unchanged
  authorization/error headers
  ([evidence](builds/2026-10-28-recovery/yield-summary-response-contract.json)).
  The coordination-governance summary now publishes its migration-458 schema
  with 19 strict nonnegative counts; 16 route tests cover projection, OpenAPI,
  and existing auth/error/cache behavior
  ([evidence](builds/2026-10-28-recovery/coordination-governance-response-contract.json)).
  The emergency-response summary now publishes bounded aggregate models with
  schema-backed incident/severity enums, strict counts and percentages, and
  sanitized failure for invalid projections; 18 route tests preserve its
  existing authorization/error/cache behavior
  ([evidence](builds/2026-10-28-recovery/emergency-response-summary-contract.json)).
  Comprehensive Status validates its one-location envelope and exact canonical
  section set, with strict typed contracts for `crop_noi` and the
  environmental section; other section bodies remain JSON-compatible pending
  generator audits. The environmental model binds its four explicit SQL arrays
  to the enclosing location and accepts PostgreSQL Decimal values. It preserves
  current lifecycle, period, and narrative-field behavior pending report review.
  The farm-summary audit found
  `SELECT *` over location, farm, plot, and crop-cycle tables, exposing future
  schema fields in the response, and financial rows do not share the same
  verification filters as other sections. Define an explicit field allowlist
  and reconcile lifecycle semantics before making that section strict. The
  envelope has 20 route tests ([evidence](builds/2026-10-28-recovery/comprehensive-status-response-contract.json)).
  Energy monitoring validates nested source, renewable, efficiency, and cost
  aggregates against schema values and query bounds; 23 route tests include
  request-location matching ([evidence](builds/2026-10-28-recovery/energy-summary-response-contract.json)).
  True-cost validates all six nested aggregate sections, schema categories,
  finite numeric values, extra-field rejection, and request-location matching;
  12 route tests pass ([evidence](builds/2026-10-28-recovery/true-cost-summary-response-contract.json)).
  Business architecture now validates mission/mapping fields, schema enums,
  nullability and page continuation; 31 route/pagination tests pass
  ([evidence](builds/2026-10-28-recovery/business-architecture-summary-response-contract.json)).
  Extension learning now validates both the module catalog and its aggregate
  summary, including enum-derived bounds and requested location identity; 20
  route/pagination tests pass
  ([evidence](builds/2026-10-28-recovery/extension-learning-response-contract.json)).
  Waste management now validates all nested summary sections, domain enums,
  count/finite-number rules, period and location identity; 22 route tests pass
  ([evidence](builds/2026-10-28-recovery/waste-summary-response-contract.json)).
  Export-log fields
  match the canonical table; the earlier pending-
  create API was removed because the table lacks its request fields and no
  worker consumes pending rows. Report snapshots remain generated by the
  exporter and preserve governed lifecycle through review surfaces. Gateway-
  backed export requests and broader route/SDK parity remain open. Sources:
  [API/SDK gates](batches.md#L3226),
  [Phase 7](implementation-plan-alignment.md#L27).
- [ ] **C3 — Finish the optional Directus adapter boundary.** Close code-verifiable
  role, field, row and hook gaps for collections still retained; keep native
  farm activity in Gateway. Workflow-role authorization cache freshness is
  fixed; a source audit found unfiltered reads for `workflow_history` and
  `approval` without tenant-scoped hooks. These permissions also expose wildcard
  fields, including notes and rejection reasons. A source-only aggregate
  preflight now maps 24 direct-location sources plus the explicit protocol
  intent-to-location relation, sanitizes unsupported collection names, and
  emits no row identifiers or contents. Eight offline tests pass. Its
  disposable schema check replayed all 671 schema migrations through migration
  680, found all 29 required relations and 60 columns, and executed both queries
  in a read-only repeatable-read transaction. The empty database returned no
  historical rows; it does not prove populated lineage or effective Directus
  permissions. Select a populated read-only copy and inspect aggregate
  unresolved/unsupported counts before designing tenant filters. Avoid
  revoking an existing operator feature based on schema-only evidence. Record
  surfaces that cannot be proven without a live runtime separately. Tenant
  reads now also reject relationship traversal in filters, `_some`/`_none`,
  sorting, and grouping until the related collection has a tenant contract;
  scalar/logical filters and JSON containment remain supported. The focused
  hook suite passes 12 tests and the TypeScript check. This closes the
  source-level relation-query oracle but does not prove live API permissions
  or populated-row parity
  ([evidence](builds/2026-10-28-recovery/directus-relation-query-boundary.json)).
  The known writable-reference lookups now carry the requested location and
  return the same unavailable error for missing and foreign valid UUIDs; 14
  focused predicate/non-disclosure tests and the extension build pass
  ([evidence](builds/2026-10-28-recovery/directus-tenant-reference-nondisclosure.json)).
  A follow-up audit confirms the typed direct-location references now have
  explicit validators, including the recent MRV sensor-device and sensor-alert
  mappings; polymorphic `source_record_ids` remains unresolvable without a
  discriminator. A 28 October collection audit found no further safe managed
  read candidate with direct location lineage: all such collections are in the
  28-collection adapter. `approval`, `workflow_history`, and file-like reads
  still rely on polymorphic source links without a verified tenant join. No
  further safe field mapping was found. Pinned-runtime permissions and
  populated-row parity remain open. Sources:
  [Directus parity](batches.md#L2117),
  [preflight](directus-polymorphic-lineage-preflight.md),
  [transport/Directus gates](batches.md#L3320).
- [ ] **C4 — Port repository-defined provider jobs and workflows.** Compare each
  source module against the owned scheduler/job contract, add missing adapters
  and operator controls, and keep external schedules disabled until ownership
  and active state are reconciled. The 23-entry catalog matches its generated
  contract, and five Prefect deployments use catalog-backed pipelines; the
  legacy health-check flow is undeployed and weather-forecast remains
  default-off. The signed forecast worker now consumes its dedicated
  `KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY`, routed through standard
  and portability Compose profiles; live provider/scheduler acceptance remains
  open ([evidence](builds/2026-10-28-recovery/weather-forecast-provider-key-routing.json)).
  A source audit of climate ingestion found manual dataset/UUID
  preflight and the scheduled location-bound default-off signed worker already
  align; its 174-test climate/CLI/scheduler selection passes without contacting
  a provider or database. No owner or production schedule was inferred.
  A follow-up inventory review found the legacy Yahoo price-feed flow is not a
  safe new JobSpec: it writes audit rows but no `price_observation`, reports an
  empty fetch as success, and its documented attestation step is never invoked.
  Defer registration until persistence/retry semantics and separate human
  attestation approval are defined ([audit](builds/2026-10-28-recovery/yahoo-price-feed-contract-audit.json)).
  A separate source review found the unmatched legacy health-check flow assumes
  the full legacy PostgreSQL/Directus/ClickHouse/Docker topology and has no
  Kernel scheduler CLI contract, so it also remains unregistered until a
  profile-aware health contract exists
  ([audit](builds/2026-10-28-recovery/prefect-health-check-contract-audit.json)).
  A new source audit also confirmed the 23-entry native job inventory already
  matches its generated contract. The legacy weekly flow claimed ML model
  retraining although the scheduled Prefect function only refreshed climate
  data; that description is corrected. The underlying legacy retraining path
  uses the shared database role and has no signed bounded task contract, so it
  remains unregistered pending an isolated design. No owner schedule was
  inferred.
  Sources: [provider/job inventory](batches.md#L2288),
  [worker recovery](batches.md#L2358).
- [ ] **C5 — Close source-verifiable analytics and reporting gaps.** Port
  registered queries/cards and deterministic projections, fix correctness and
  access gaps, and preserve ClickHouse as rebuildable optional projection.
  Direct report generators now reject missing location scope before database
  access, consistent with the registry and CLI; reviewed global rows remain
  visible only under a selected location, and unlineaged network rows are
  omitted from farm-scoped reports. The integrated report suite passes 563
  tests with four database-dependent skips. Its generated inventory records 94
  report types, 167 direct query sites, 166 positional-bind sites, and zero
  unresolved sites or bind mismatches. `climate_impact`,
  `revenue_multiplier`, `environmental`, and `ecological_modeling` also reject
  missing location before opening a cursor or starting the analyzer; focused
  selections pass 2, 125, 2, and 2 tests respectively. The EBF scorecard now
  rejects a missing/empty location before cursor creation; the focused source
  selection passes 324 checks. The inventory's 13 entries with no visible
  location-bound SQL signal were reviewed: twelve are deliberate network
  reports with explicit network-scope guards, and `business_plan` rejects
  missing scope while its all-location mode is intentional. Do not infer
  populated-farm parity from synthetic fixtures. Tactical-layer companion
  lookups now keep target threats within the selected location, and the
  State-of-Kokonut actor/funding sections filter all four queries to selected
  locations while rejecting empty selections; network-wide mode is unchanged.
  Their focused suites pass 73 and 285 tests respectively, with report
  inventory freshness checks ([tactical scope](builds/2026-10-28-recovery/tactical-layer-companion-location-scope.json);
  [State of Kokonut scope](builds/2026-10-28-recovery/state-of-kokonut-selected-actor-scope.json)).
  The latest source audit found remaining location-unfiltered report cases are
  explicit network/public projections, an explicit all-location operation, or
  stakeholder/global surfaces whose audience and scope cannot be safely
  changed without populated fixtures and owner review; no additional query
  change was selected.
  Sources:
  [report/query parity](batches.md#L2334),
  [consumer scope](batches.md#L3139).
- [ ] **C6 — Complete source-only capability slices.** Continue unresolved
  route, lifecycle, lineage, provenance and review functionality for CAP-035,
  CAP-036, CAP-037 and CAP-038 where code can be completed without populated
  farm records or production identity. The latest audit found no further safe
  independent source-only slice: CAP-035 sharing/tranche custody needs policy
  decisions; CAP-036 already excludes unscoped sensitive events and needs a
  populated/archived corpus to establish additional subject lineage; CAP-037
  has no identified first-party workflow gap; CAP-038 needs live identity and
  populated-source acceptance. Sources: [CAP-035](batches.md#L3484),
  [CAP-036](batches.md#L3574), [CAP-037](batches.md#L3582),
  [CAP-038](batches.md#L3652).
- [ ] **C7 — Finish software-only ARM64 and recovery evidence.** The full
  ARM64/QEMU schema replay now passes all 672 files through migration 681
  under a verified 1.5 GiB/two-CPU database budget. The network was disabled,
  no ports, seeds, or farm data were used, no OOM occurred, and cleanup passed.
  That replay did not enable its optional operator-scope probe. The native full
  replay through 681 separately passes the synthetic two-tenant/operator
  assertions; candidate and legacy state stayed untouched. Focused native and
  ARM64/QEMU ACL checks cover migrations 672–680. A separate
  network-disabled schema check replayed all 671 schema files through migration
  680 and executed both Directus lineage queries; this demonstrates SQL/schema
  compatibility only, not ARM64 behavior, populated lineage, RLS, or effective
  Directus permissions. Both Kernel app images and profile selections have
  ARM64 build and
  import evidence. This remains software-only evidence: no physical Raspberry
  Pi, populated data, external provider/media, R2, whole-platform production
  recovery, or 24-hour RPO/RTO drill has been accepted. The minimal Gateway
  startup was also exercised with optional analytics, ML, GIS, Web3, ClickHouse,
  Prefect, Redis/MQTT, gRPC, OIDC, and S3 libraries blocked; 16 routes loaded
  with no attempted or loaded optional imports, and dependency/provider checks
  passed. This supports the existing profile boundary but does not replace
  ARM64 image build/runtime or physical-device acceptance.
  The new opt-in `core` image uses an independent hash-locked dependency
  closure, with Web3, spreadsheet/S3, and local-media overlays. The multiarch
  release gate validates both core-only and all-overlays images for AMD64 and
  ARM64; local profile/import checks pass, while hosted CI remains pending.
  Existing full-capability profiles are unchanged, and core OIDC is rejected
  until that composition is implemented. The edge Compose profile also has an
  offline regression locking its declared 1 GiB/two-CPU app and database caps;
  this checks configuration only and is not physical Raspberry Pi runtime
  acceptance ([evidence](builds/2026-10-28-recovery/edge-compose-resource-contract.json)).
  Resource-limit preflight now also rejects a positive CPU value that rounds to
  zero nanocpus before creating a disposable database container; normal 0.5 and
  2 CPU conversions retain exact Docker units. The focused runner selection
  passes 26 tests ([evidence](builds/2026-10-28-recovery/arm64-resource-limit-nanocpu-preflight.json)).
  Sources: [Phase 8](implementation-plan-alignment.md#L28),
  [latest native full replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json),
  [ARM64 full replay](builds/2026-10-28-recovery/arm64-resource-limited-schema-681.json),
  [core profile](builds/2026-10-28-recovery/kernel-core-profile-contract.json),
  [multiarch profile gate](kernel-release-inputs.md),
  [migration 679 ARM64 ACL](builds/2026-10-28-recovery/quantity-unit-runtime-read-only-arm64-disposable.json),
  [build and profile evidence](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json),
  [recovery gates](batches.md#L2159).
- [ ] **C8 — Reconcile all ledgers after each batch.** Keep the sprint TODO,
  `batches.md`, `progress.md`, capability matrix and migration/evidence links
  consistent. Preserve the 25 open composite checklist entries until their
  individual acceptance criteria close.

### Current batch — parallel Kernel hardening — 28 October 2026

This batch closed ten checklist/audit items without changing capability
classifications: the metric-definition runtime ACL, ecocredit response
contract, Python SDK timeout preflight, Directus relation-query boundary,
legacy health-check flow audit, edge-profile resource regression, detailed
health-route authorization, forecast-worker provider-key routing, runtime ACL
report provenance, and the next-catalog source review. The combined
Gateway/report selection passes 385 tests; Directus passes 12 focused tests
and TypeScript; the Python SDK passes 17 tests; the edge profile check passes
one test. The disposable PostgreSQL 16 role-boundary harness passes migration
681 apply/replay and verifies runtime read-only behavior plus preservation of
Directus grants. The full schema/ACL report remains through migration 679, and
no candidate or legacy database was changed.

This batch also protected `/api/health/services` behind `service_health:read`
while keeping `/health` public, fixed dedicated forecast-worker provider-key
routing, and corrected ACL-report provenance so migration-679 observations
are not confused with migration-681 policy. The TypeScript client is gRPC-only;
REST deadline parity does not justify imposing a default deadline on streaming
or long-running gRPC calls. The C5 re-audit found no additional safe
selected-location leak outside the report fixes already closed. C4 confirms the
legacy health-check flow is not profile-independent and remains unregistered.
C6 found no further source-only capability change that avoids populated data,
live identity, or owner decisions. The next C1 candidate,
`competency_framework`, remains unchanged pending its curator and supported
administration path. The C1 migration is a relation-specific DML restriction;
it does not establish RLS or tenant isolation. Checklist: 1,377 complete / 25
open (1,402 total);
the matrix remains 24 baseline-retained, 7 deployed, and 36 prepared across
67 rows. MAN-CAP acceptance is unchanged.

### Completed continuation — Gateway response and SDK catalog contracts — 28 October 2026

The private farm-activity summary routes, pollution incident resolution, and
governance-tension detail now validate their exact source projection and
request scope before returning a response. The native Python and JavaScript
REST SDKs now validate the public driver catalog against its generated bounds,
enum, and exact fields. The 92-test Python selection and 38-test JavaScript
selection pass; TypeScript build, Ruff, Python compilation, and diff checks
pass. The matrix records 61 strict private Gateway response endpoints across
67 capabilities (24 baseline-retained, 7 deployed, 36 prepared). No migration,
database, provider, candidate, or legacy service was used. See
[evidence](builds/2026-10-28-recovery/kernel-gateway-sdk-contract-batch.json).

Checklist: 1,446 complete / 25 open (1,471 total); TODO: 153 checked / 16 open.
MAN-CAP acceptance and capability classifications are unchanged.

## Owner or environment gates after code work

- [ ] **H1 — Live ZITADEL login:** confirm issuer discovery, provision/register
  the OIDC client and callback, create the test operator, supply generated
  secrets through SOPS, and run trusted-HTTPS browser login/session/logout and
  scoped-grant acceptance. Startup/discovery alone is complete.
  Source: [identity follow-up](open-follow-ups.md#L28).
- [ ] **H2 — Browser trust:** trust the local development CA or provide an
  approved certificate before Caddy HTTPS browser acceptance. Never bypass the
  browser warning. Source: [certificate follow-up](open-follow-ups.md#L32).
- [ ] **H3 — Populated data and report review:** ingest the owner-held Genesis,
  Seeds, Adelphi and V1 records, then compare repository-backed outputs and
  review access with the intended stakeholder audience. Terra Viva follows its
  design phase. The intended audience is not blanket authorization.
  Sources: [data follow-up](open-follow-ups.md#L40),
  [report owner review](batches.md#L2356).
- [ ] **H4 — Retention operations:** accountable owners configure dynamic
  purpose-specific periods, archive access, legal holds and erasure/disposition
  approval before any pruning is enabled. Do not hardcode a universal period.
  Source: [retention follow-up](open-follow-ups.md#L19).
- [ ] **H5 — External delivery and storage:** provide alert recipient/severity
  routing/on-call ownership; provision R2 access for the reviewed test prefix
  and rehearse restore before production backup claims. Source:
  [delivery](open-follow-ups.md#L21), [R2](open-follow-ups.md#L29).
- [ ] **H6 — Production topology and recovery:** supply trusted proxy hops,
  TLS, RPO and topology details; run the 24-hour recovery and scale check when
  the production target can be scheduled. Replicas/failover remain deferred
  until production. Sources: [topology](open-follow-ups.md#L22),
  [timed acceptance](batches.md#L3343).
- [ ] **H7 — Physical device check:** if a Raspberry Pi becomes available,
  measure power-loss, thermal, storage and device restart behavior. Until then,
  report software ARM64 evidence only. Source: [physical acceptance](batches.md#L2012).
- [ ] **H8 — Release and cutover:** obtain green required CI/Security checks on
  the exact PR head and perform the already-approved cutover only after all
  readiness gates pass. Protocol Bridge work remains deferred by owner request.
  Sources: [CI](batches.md#L3396), [cutover](batches.md#L3399).

## Working cadence

Implement C1–C8 in coherent local commits on the current feature branch. Group
pushes into reviewable PR batches targeting `develop`, as requested by the
owner. Do not mark a release/cutover gate complete from local source checks,
emulation, internal OIDC discovery, or synthetic-only parity.

### Previous continuation — C1 versioned graph type boundary

Migration 661 makes the versioned `graph_node_type` and `graph_edge_type`
registries read-only to `kokonut_runtime`; source review found their only
definitions in migration 173, while runtime projection code writes graph
generations and materialized nodes/edges. Native and ARM64/QEMU focused ACL
checks pass for apply/replay, read access, mutation/reference denial, stale
column-grant cleanup, and provisioner reapplication. The focused migration,
role, report, ARM64-contract, and migration suite passes 122 tests; Ruff,
dependency/provider boundaries, and SQL inventory checks pass. The static
report now declares 105 boundaries with no mapping gaps. The focused checks
were followed by a complete ARM64/QEMU replay through migration 662; the later
probe verifies all 106 declared boundaries on the full chain. Disposable checks
used no seeds or farm data and did not touch candidate/legacy databases.
Broader runtime DML/RLS boundaries and physical Raspberry Pi acceptance remain
open ([full-chain evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json)).
Checklist: 1,264 complete / 26 open (1,290 total). Capability
classifications remain 24 baseline-retained, 7 deployed, and 36 prepared
across 67 rows.

### Current continuation — C1 capability audit ledger boundary

Migration 662 makes `access_audit_log` SELECT/INSERT-only for
`kokonut_runtime`, after source review found only audit insert and read paths.
The role provisioner reapplies the policy after broad grants. Native and
ARM64/QEMU disposable checks pass migration replay, column-grant cleanup,
read/append success, and mutation denial. Focused suites pass 126 tests. The
full 653-file ARM64/QEMU schema replay through migration 662 now passes
under the verified 1.5 GiB/two-CPU budget. Its two-tenant probe passes all 17
assertions and verifies 106 declared boundaries, including the new append-only
audit policy, with zero direct table/column privilege violations. No retention
period is selected; cleanup stays outside runtime authority and must follow
the future configurable policy. The probe still reports 1,014 relations with
effective table DML while RLS is disabled, so C1 remains open. Checklist:
1,266 complete / 25 open (1,291 total); capability classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.

### Current continuation — C2 SDK parameter-name contract

- [x] Extend the Python/TypeScript method-parity regression to compare
  positional parameter names with an explicit alias map for the reviewed
  `itemId`/`id`, `sensorId`/`deviceId`, and attestation subject/entity naming
  pairs. The focused three-test suite, Ruff, compilation, and diff checks pass.
  No public method signatures changed. This closes only the static parameter-
  name inventory subgate; C2 remains open for parameter types and runtime
  serialization, authenticated route/action/scope and pagination/error
  behavior, broader SDK/runtime parity, live OIDC, and populated acceptance.
  See the [batch record](batches.md) and
  [progress evidence](progress.md#sdk-parameter-name-parity-contract--27-october-2026).
- [x] Historical interim step: align the Python `ExportFormat` type with the
  TypeScript union. A subsequent schema audit found `format` absent from the
  canonical table and no process consuming pending requests, so that type and
  create helper were then removed as part of the current read-only SDK contract
  ([current record](#current-continuation--c2-canonical-export-log-sdk-contract);
  [earlier batch history](batches.md#L4766)).

### Current continuation — C1 full-schema runtime-role revalidation

- [x] Revalidate the native full schema and runtime boundary through migration
  662 under a 1.5 GiB/two-CPU database limit. All 653 files applied, and all 17
  signed synthetic operator/scope assertions passed with zero direct table or
  column violations among 106 declared boundaries. The refreshed report
  distinguishes referenced relations from actual DML targets; the analytics
  inventory now has 273 target relations / 425 sites and no unmatched
  candidates. `farm` is only an `INSERT … SELECT` source for two other target
  tables. The probe still finds 1,014 public relations with effective DML while
  RLS is disabled, so C1 remains open and universal tenant isolation is not
  established. Thirteen report/inventory tests plus Ruff, compilation, SQL
  inventory freshness, capability validation, and diff checks pass. No seeds,
  candidate, or legacy database were used ([batch](batches.md); [evidence](progress.md#correct-analytics-dml-target-classification--27-october-2026)).
- [x] Separate SQL-referenced relations from actual DML targets in the C1
  reports. The false `farm` source classification is removed; the inventory
  now covers 273 write-target relations / 425 sites with no unmatched
  candidates. Thirteen focused report/inventory tests and static checks pass.
  C1 remains open because 1,014 public relations still retain effective DML
  while RLS is disabled ([batch](batches.md); [progress](progress.md#correct-analytics-dml-target-classification--27-october-2026)).
- [x] Track `TRUNCATE` SQL targets and effective runtime `TRUNCATE` privileges
  separately from ordinary table DML. The migration-662 native snapshot reports
  zero runtime `TRUNCATE` grants. The scanner, ACL report, and analytics
  inventory selection passes 41 tests plus static checks; this does not close
  broad table-DML or universal RLS gaps ([batch](batches.md); [progress](progress.md#track-runtime-truncate-targets-and-privileges--27-october-2026)).
- [x] Make the legacy `agent_action_log` read-only to `kokonut_runtime` while
  retaining export reads and the separate Directus role's existing writes.
  Migration 663 and the role provisioner revoke runtime table/column writes;
  native and ARM64/QEMU disposable checks, a 654-file full-schema replay, and
  the 17-check two-tenant probe pass. The six-module regression suite passes
  135 tests. C1 remains open because 1,013 relations retain effective DML while
  RLS is disabled ([batch](batches.md); [progress](progress.md#progress-addendum--agent_action_log-runtime-read-only-boundary--27-october-2026)).
- [x] Keep seeded `carbon_benchmark` references readable but immutable to the
  Kernel runtime. Migration 664, native/ARM64 disposable ACL checks, and the
  655-file full-schema replay pass; 136 focused tests pass. The report records
  108 declared controls and 1,012 relations with effective DML while RLS is
  disabled; C1 remains open ([batch](batches.md); [progress](progress.md#progress-addendum--carbon_benchmark-runtime-read-only-boundary--27-october-2026)).
- [x] Keep seeded `ghg_emission_factor` references readable but immutable to
  the Kernel runtime. Migration 665, native/ARM64 disposable ACL checks, and
  the 656-file native full-schema replay with 18 operator-scope checks pass;
  137 focused tests pass. The report records 109 declared controls and 1,011
  relations with effective DML while RLS is disabled; C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--ghg_emission_factor-runtime-read-only-boundary--27-october-2026)).
- [x] Keep shared seeded `operations_protocol` handbook entries readable but
  immutable to the Kernel runtime. Migration 666, native/ARM64 disposable ACL
  checks, and the 657-file native full-schema replay with 19 operator-scope
  checks pass; 138 focused tests pass. The report records 110 declared
  controls and 1,010 relations with effective DML while RLS is disabled; C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--operations_protocol-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `process_maturity_level` and `pollinator_species_reference`
  readable but immutable to the Kernel runtime. Migration 667 passes native and
  ARM64/QEMU focused PostgreSQL checks and a 658-file native replay with 21
  two-tenant scope checks; 139 focused tests pass. The report records 112
  controls and 1,008 relations with effective DML while RLS is disabled. C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--static-taxonomy-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the GRI reporting and governance-framework registries readable but
  immutable to `kokonut_runtime`. Migration 668 passes native and ARM64/QEMU
  focused PostgreSQL checks and a 659-file native replay with 23 two-tenant
  scope checks; 141 focused tests pass. The report records 114 controls and
  1,006 relations with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--reporting-and-governance-registries-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `impact_framework` and `impact_dimension` readable but immutable to
  `kokonut_runtime`. Migration 669 passes native and ARM64/QEMU focused ACL
  checks and a 660-file native replay with 25 two-tenant scope checks; 142
  focused tests pass. The report records 116 controls and 1,004 relations
  with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--impact-framework-catalogs-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the seeded `expense_category` taxonomy readable but immutable to
  `kokonut_runtime`. Migration 670 passes native and ARM64/QEMU focused ACL
  checks and a 661-file native replay with 26 two-tenant scope checks; 143
  focused tests pass. The report records 117 controls and 1,003 relations
  with effective DML while RLS is disabled. C1 remains open
  ([batch](batches.md); [progress](progress.md#progress-addendum--governed-expense-category-runtime-read-only-boundary--27-october-2026)).

- [x] Keep shared CRISP risk-dimension definitions readable but immutable to
  `kokonut_runtime` while retaining location-specific weight overrides.
  Migration 671 passes native and ARM64/QEMU focused ACL checks and a 662-file
  native replay with 27 two-tenant scope checks; the six-module focused suite
  passes 145 tests. The refreshed report records 118 runtime controls and
  1,002 relations with effective table DML while RLS is disabled. C1 remains
  open ([batch](batches.md); [progress](progress.md#progress-addendum--crisp-risk-dimension-runtime-read-only-boundary--27-october-2026)).

- [x] Encode caller-controlled collection and item IDs in the Python and
  JavaScript Directus SDKs as single path segments. The pinned Directus helper
  interpolates those values directly; focused regressions verify slashes and query/fragment delimiters staying encoded
  in the serialized route, with dot-segment rejection before transport. The
  full SDK suites pass (98 Python, 56 JavaScript), with TypeScript build, Ruff,
  and compilation clean. This closes one C2 serialization slice only;
  route/action/scope and runtime parity gates remain open
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-path-segment-parity.json)).

- [x] Align pagination serialization across Python and JavaScript SDK list calls.
  Merged options now use consistent offset/limit/page precedence, and invalid
  zero-limit offset requests fail before transport. The full SDK suites pass
  99 Python and 57 JavaScript tests; TypeScript build, Ruff, compilation, and
  109-model schema-parity checks pass. C2 remains open for route/auth, error and
  runtime parity ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-pagination-contract.json)).

- [x] Re-run the full schema on ARM64/QEMU through migration 671. All 662
  ordered files applied on `aarch64` under verified 1.5 GiB/two-CPU limits in a
  network-disabled disposable project, with no seeds, farm rows, host ports,
  OOM, or candidate/legacy access; cleanup passed. This replay did not include
  the operator-scope probe. C7 remains open for physical-device/power testing,
  populated data, and production recovery acceptance
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/arm64-resource-limited-schema-671.json)).

- [x] Make `dfs_currency` read-only to the general Kernel runtime. Migration 672
  and native/ARM64 disposable PostgreSQL checks cover reads, table/column write
  denial, provisioner reapplication, and preservation of Directus grants. The
  complete native schema through 672 passes all 28 two-tenant probe assertions;
  119 declared ACL policies have zero mismatches, while 1,001 relations still
  have effective DML with RLS disabled, so C1 remains open. The three focused
  regression modules pass 103 tests. This is software-only synthetic evidence;
  physical Pi, populated operational data, and production acceptance remain
  open ([batch](batches.md); [progress](progress.md#progress-addendum--currency-reference-catalog-runtime-read-only-boundary--27-october-2026)).

- [x] Keep the shared `crop_gdd_config` reference readable but immutable to
  `kokonut_runtime`. Migration 673 and native/ARM64 disposable PostgreSQL checks
  cover table and column mutation denial, reads, provisioner reapplication, and
  preservation of Directus grants. The 664-file native replay passes all 29
  two-tenant probe assertions. It loads no seeds, so populated GDD parity is
  still open. The three focused regression modules pass 104 tests; 120 ACL
  policies have zero mismatches while 1,000 relations still retain effective
  DML with RLS disabled, so C1 remains open. No candidate or legacy database
  was touched ([batch](batches.md); [progress](progress.md#progress-addendum--crop-gdd-configuration-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `pest_degree_day_config` readable but immutable to
  `kokonut_runtime`. Migration 674 passes native and ARM64/QEMU disposable ACL
  checks, including provisioner reapplication and Directus-grant preservation.
  The 665-file native replay passes all 30 two-tenant assertions and reads the
  schema-defined `fall_armyworm` default. The three focused regression modules
  pass 105 tests; 121 ACL policies have zero mismatches while 999 relations
  retain effective DML with RLS disabled, so C1 remains open. No candidate or
  legacy database was touched ([batch](batches.md); [progress](progress.md#progress-addendum--pest-degree-day-configuration-runtime-read-only-boundary--27-october-2026)).

- [x] Keep `revenue_multiplier_config` readable but immutable to
  `kokonut_runtime`. Migration 675 passes native and ARM64/QEMU disposable ACL
  checks, including provisioner reapplication and Directus-grant preservation.
  The 666-file native replay passes all 31 two-tenant assertions and confirms a
  runtime query succeeds. Optional seeds 015/069 were not loaded, so configured
  values are not covered by this replay. The three focused regression modules
  pass 106 tests and the service module passes 14; 122 ACL policies have zero
  mismatches while 998 relations retain effective DML with RLS disabled, so C1
  remains open ([batch](batches.md); [progress](progress.md#progress-addendum--revenue-multiplier-configuration-runtime-read-only-boundary--27-october-2026)).

### Current continuation — C1 governed reference-class runtime boundary

- [x] Keep governed `reference_class` records readable but immutable to
  `kokonut_runtime`. Migration 676 denies table and residual column
  INSERT/UPDATE/REFERENCES privileges, restores SELECT, and is reapplied by the
  runtime provisioner after compatibility grants. Native and ARM64/QEMU
  disposable checks pass replay, reads, mutation/TRUNCATE/REFERENCES denial,
  and synthetic Directus grant preservation. The complete native schema replay
  through 676 passes all 31 two-tenant assertions under verified 1.5 GiB/two-CPU
  limits. The refreshed ACL report has zero policy mismatches across 123
  controls; 997 relations still retain effective DML with RLS disabled, so C1
  remains open. The combined regression selection reports 173 passed and one
  skipped. No seeds, farm data, candidate, or legacy state was used ([batch](batches.md#L4810);
  [progress](progress.md); [native replay evidence](builds/2026-10-27-recovery/runtime-role-full-schema-676-native-disposable.json)).

### Current continuation — C2 canonical export-log SDK contract

- [x] Remove unsupported export-log mutation from both SDKs and match the
  model to all ten canonical `export_log` columns. Source audit found the
  previously advertised request payload included columns absent from the
  schema, and no worker consumes pending requests; the established exporter
  writes audit rows after generating files. The SDK now offers only `list` and
  `get`, while file generation remains available through the exporter CLI.
  Python/method-parity tests pass 100, JavaScript tests pass 53, TypeScript
  builds, and the 109-model/2,150-column SDK schema guard passes. Ruff,
  compilation and diff checks pass; calls were mocked, with no database or
  provider. The earlier C2 export-create lifecycle note is superseded. A
  Gateway-backed request queue, authenticated attribution and async processing
  remain open ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-export-audit-read-only-contract.json)).

### Current continuation — C2 report snapshot SDK boundary

- [x] Remove generic report-snapshot mutations from Python and TypeScript SDKs.
  The report generator creates hashed, unfrozen draft snapshots with public-
  interest context; lifecycle review is a separate governed operation. The
  Gateway review routes are read-only, and the SDK had no source callsites for
  create/update/delete. Both SDKs now expose list/detail/type-filtered reads
  only. The focused Python SDK, parity, and report-governance selection passes
  107 tests; JavaScript passes 53; TypeScript builds. Ruff, compilation, and
  diff checks pass; the SDK schema guard is checked in the same batch. All API
  clients are mocked; no database/provider was used. No capability status
  changes. A Gateway report-generation and reviewer decision workflow remains
  open ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-report-snapshot-read-only-contract.json)).

### Current continuation — C2 attestation record SDK boundary

- [x] Remove generic attestation-record mutations from Python and TypeScript
  SDKs. The table contains governed workflow rows and chain-indexer projections;
  inserting a row directly cannot publish or independently verify an EAS
  attestation. Keep list/detail, pending-state, and subject-filtered reads, and
  leave actual publish/revoke actions in the dedicated EAS service and approved
  signing flow. Both workflow examples now read indexed attestations instead of
  writing misleading draft rows. The focused Python SDK/parity/report-governance
  selection passes 109 tests; JavaScript passes 54; TypeScript builds; Ruff and
  Python compilation pass. No database/provider was used. This does not add a
  Gateway attestation-request workflow or change capability/MAN-CAP status
  ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-attestation-read-only-contract.json)).

### Current continuation — C2 calculated NOI snapshot SDK boundary

- [x] Remove generic NOI snapshot mutations from both SDKs. `noi_snapshot`
  stores calculated values with source inputs and calculation version; SDK
  callers had no repository mutation callsites and could supply outputs without
  running that calculation. Preserve list/detail/crop-cycle reads. Existing
  CLI, signed-worker, and Directus-extension writer paths were not changed or
  runtime-validated. The focused Python SDK/parity/report-governance selection
  passes 111 tests; JavaScript passes 55; TypeScript builds; Ruff and compilation
  pass. No database/provider was used. This does not establish tenant isolation
  or change capability/MAN-CAP status ([batch](batches.md); [evidence](builds/2026-10-27-recovery/sdk-noi-snapshot-read-only-contract.json)).

### Current continuation — CI Kernel release-input lock repair

- [x] Update the Kernel release input lock to match the existing OIDC Dockerfile
  dependency change and hash both OIDC requirement manifests. The local lock
  gate and 36 focused profile/release tests pass; the failed hosted run has not
  yet been rerun on the repaired commit ([batch](batches.md); [evidence](builds/2026-10-28-recovery/ci-kernel-release-lock-repair.json)).

### Current continuation — C1 farmer credential-type catalog boundary

- [x] Keep seeded `farmer_credential_type` guidance readable but immutable to
  `kokonut_runtime`. Schema migration 148 seeds the catalog; farmer credential
  records store `credential_type` as free text, with no foreign key or
  application SQL callsite using the guidance table. Migration 677 removes
  runtime table and residual column INSERT/UPDATE/REFERENCES grants, restores
  SELECT, and the role provisioner reapplies the boundary after compatibility
  grants. Native and ARM64/QEMU PostgreSQL 16 acceptance passes migration
  replay, read access, mutation/TRUNCATE/REFERENCES and column-grant denial,
  provisioner reapplication, and preservation of synthetic Directus grants.
  The full native schema replay through 677 passes all 32 two-tenant checks and
  reads the schema-seeded catalog row. The refreshed ACL report has zero
  mismatches across 124 controls; 996 relations still retain effective DML
  while RLS is disabled, so C1 remains open. The focused parser/migration tests
  pass 68 tests. No optional seeds or farm data were loaded; candidate and
  legacy databases were untouched. Directus API parity, populated credential
  records, physical Raspberry Pi, and production acceptance remain open
  ([batch](batches.md#L4814); [migration](../schemas/postgres/677_runtime_farmer_credential_type_read_only.sql);
  [native ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-disposable.json);
  [ARM64 ACL](builds/2026-10-27-recovery/farmer-credential-type-runtime-read-only-arm64-disposable.json);
  [full schema and tenant probe](builds/2026-10-27-recovery/runtime-role-full-schema-677-native-disposable.json);
  [source/ACL report](builds/2026-10-27-recovery/sprint-runtime-privilege-callsite-report.json)).

### Current continuation — parallel report-scope and Gateway contract batch — 28 October 2026

- [x] Require explicit location scope for the three location-only Kokonut
  Commons reports. Network-only federation and participatory-signal reports
  keep their explicit global contract. Focused tests and the integrated report
  suite pass; no database/provider was used
  ([evidence](builds/2026-10-28-recovery/kokonut-commons-report-location-scope.json)).
- [x] Require scope for all 18 location-only strategy reports. Remove the
  unscoped stakeholder-outcomes branch; network-wide value-stream links remain
  available through `stakeholder_value_streams`. Farm-scoped fork detection
  excludes `insight_transfer` until it has trustworthy location lineage, while
  network-wide detection retains it. Focused suite: 158 passed
  ([evidence](builds/2026-10-28-recovery/stakeholder-outcomes-direct-scope.json)).
- [x] Require location scope for direct `perpetual_value_stress` report calls
  before cursor creation. Preserve selected-farm and reviewed shared rows;
  focused report checks pass 285 cases
  ([evidence](builds/2026-10-28-recovery/perpetual-value-stress-location-scope.json)).
- [x] Publish FastAPI/OpenAPI bounds for the authenticated Delphi participant
  workspace (`limit=1..50`, `offset=0..10,000`) and reject invalid paging
  before service access. Twenty-two focused checks pass
  ([evidence](builds/2026-10-28-recovery/delphi-participant-workspace-pagination-openapi.json)).
- [x] Publish the existing `limit=1..100` bound (default `50`) on six operator
  list routes and reject invalid values before service access. The operator and
  farm-activity selection passes 138 checks
  ([evidence](builds/2026-10-28-recovery/operator-list-pagination-openapi-bounds.json)).
- [x] Reconcile report query inventory after removing unsafe unscoped branches.
  It now records 94 report types, 167 direct queries, 166 positional-bind
  sites, zero unresolved sites, and zero bind mismatches. The integrated report
  suite passes 563 tests with four database-dependent skips.
- [x] Validate the combined changed Gateway/operator contracts: 732 tests pass.
  The focused platform-integrity selection passes 374 tests and six subtests;
  changed Python Ruff and compilation, Directus hook tests/build, SDK tests/build,
  dependency/provider checks, matrix validation, and diff checks pass. No
  candidate or legacy database, migration, or provider was used.

Capability classifications remain unchanged at 67 rows (24 baseline-retained,
7 deployed, 36 prepared); no MAN-CAP is accepted. The current checklist is
1,350 complete / 25 open (1,375 total). Remaining human/runtime gates stay open
([combined evidence](builds/2026-10-28-recovery/parallel-report-gateway-contracts.json)).

### Completed continuation — parallel Kernel hardening — 28 October 2026

- [x] Bound the public driver catalog to enabled, display-safe entries with a
  stable database order, a 50-row maximum page, an offset ceiling, and
  continuation metadata. Loader paths, class names, and registration notes are
  excluded ([evidence](builds/2026-10-28-recovery/public-driver-catalog-projection.json)).
- [x] Require explicit location scope for location-only tactical analytics
  CLI operations and reject malformed or contradictory scope before database
  access ([evidence](builds/2026-10-28-recovery/analytics-tactical-cli-scope-preflight.json)).
- [x] Pass the ClickHouse password only to the isolated `clickhouse_outbox`
  worker while preserving the existing environment boundary for other worker
  identities ([evidence](builds/2026-10-28-recovery/worker-clickhouse-secret-routing.json)).
- [x] Derive operator-scope replay ACL expectations from the current runtime
  policy lists and reject stale hard-coded counts.
- [x] Replay all 672 ordered schema files through migration 681 on a
  network-disabled native PostgreSQL 16 container with verified 1.5 GiB/two-CPU
  limits, no host ports or seed/farm data, passing synthetic two-tenant checks,
  and successful cleanup. Refresh the ACL report to the observed source and
  migration head ([full replay](builds/2026-10-28-recovery/runtime-role-full-schema-681-native-disposable.json);
  [report](builds/2026-10-28-recovery/sprint-runtime-privilege-callsite-report.json)).

The combined focused selection passes 165 tests. This is synthetic evidence;
candidate/legacy state, production deployment, physical Raspberry Pi behavior,
and global tenant isolation are not established. The current checklist is
1,382 complete / 25 open (1,407 total); capability classifications and
MAN-CAP acceptance are unchanged. This TODO ledger now has 92 checked and 16
open entries.

### Completed continuation — public driver and tenant-reference contracts — 28 October 2026

- [x] Add the stable versioned public driver catalog route and typed Python/TypeScript SDK methods. Generated OpenAPI/SDK parity, pagination bounds, response allowlist, and mocked transport checks pass ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
- [x] Make Directus writable-reference lookups location-qualified and conceal whether a valid UUID is missing or belongs to another location. Fourteen focused predicate/non-disclosure tests, the full 124-test extension suite, and the extension build/type check pass ([evidence](builds/2026-10-28-recovery/directus-tenant-reference-nondisclosure.json)). Live Directus role/field/row parity remains open.
- [x] Replay the full schema on ARM64/QEMU through migration 681 with verified 1.5 GiB/two-CPU limits, network disabled, no seeds or host ports, and cleanup success. The optional operator-scope probe did not run, and no physical Raspberry Pi was used ([evidence](builds/2026-10-28-recovery/arm64-resource-limited-schema-681.json)).
- [x] Keep driver catalog database failures distinct from an empty catalog: failures propagate to a generic no-store Gateway 500. The 47-test Gateway/OpenAPI/Python-SDK selection, Ruff, compilation, and diff checks pass with fake database/transport behavior ([evidence](builds/2026-10-28-recovery/public-driver-catalog-v1-sdk-parity.json)).
- [x] Require source review for new unresolved direct SQL DML/`WITH` candidates through the runtime inventory check. Existing candidates remain explicitly tracked and the fingerprint baseline is pinned; this does not reduce the observed broad grants ([evidence](builds/2026-10-28-recovery/runtime-sql-unresolved-write-drift-gate.json)).
- [x] Publish and validate a strict success model for the private yield-monitoring summary, preserving the existing auth and error/cache contracts ([evidence](builds/2026-10-28-recovery/yield-summary-response-contract.json)).
- [x] Publish and validate a strict success model for the migration-458 coordination-governance summary, preserving its tenant and error/cache contracts ([evidence](builds/2026-10-28-recovery/coordination-governance-response-contract.json)).
- [x] Publish and validate a strict success model for the emergency-response aggregate summary, preserving its tenant and error/cache contracts ([evidence](builds/2026-10-28-recovery/emergency-response-summary-contract.json)).
- [x] Validate the Comprehensive Status location envelope, canonical section names, and existing response-size bound ([evidence](builds/2026-10-28-recovery/comprehensive-status-response-contract.json)).
- [x] Publish and validate the nested energy summary response against source schema and query bounds ([evidence](builds/2026-10-28-recovery/energy-summary-response-contract.json)).
- [x] Publish and validate the nested true-cost summary response and requested-location identity ([evidence](builds/2026-10-28-recovery/true-cost-summary-response-contract.json)).
- [x] Publish and validate the location-scoped business-architecture summary and pagination contract ([evidence](builds/2026-10-28-recovery/business-architecture-summary-response-contract.json)).
- [x] Publish strict response contracts for the extension-learning module catalog and aggregate summary ([evidence](builds/2026-10-28-recovery/extension-learning-response-contract.json)).
- [x] Publish and validate the nested waste-management summary response ([evidence](builds/2026-10-28-recovery/waste-summary-response-contract.json)).

The batches checklist is 1,398 complete / 25 open (1,423 total). This TODO
ledger now has 106 checked and 16 open entries; capability classifications and
MAN-CAP acceptance remain unchanged.


### Completed in the current continuation — three private Gateway summaries

- [x] Add a strict irrigation status response contract, including nested row
  allowlists, schema-backed state values, requested-location identity, and
  consistent bounded pagination.
- [x] Add strict landscape-conservation and pollinator aggregate contracts
  with nested allowlists, bounded groups, source-aligned enums, finite numeric
  values, and requested-location identity.
- [x] Refresh the shared route fixtures and run the combined selection: 77
  tests pass; Ruff, Python compilation, capability-matrix validation, and diff
  checks pass. No database or provider was used. Evidence is recorded in
  [the batch log](batches.md).

The checklist is now 1,401 complete / 25 open (1,426 total). This TODO ledger
has 109 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance remain unchanged; live OIDC, populated-data parity, and broader
tenant isolation remain open.

### Completed continuation — nutrient, strategy, and competitive-landscape response contracts — 28 October 2026

- [x] Validate nutrient-balance projections, including strict aggregates,
  request binding, and safe pagination at the 10,000-offset ceiling.
- [x] Add a schema-aligned, privacy-limited response model for location-scoped
  strategy plans and enforce SQL-consistent page and offset bounds.
- [x] Add a strict aggregate-only competitive-landscape response contract
  that excludes participant identities and private evidence/content fields.
- [x] Make runtime-SQL review fingerprints stable across Python 3.11 and 3.12
  without changing the pinned digest or existing unresolved-write ledger.

The combined Gateway response selection passes 182 tests and the runtime SQL
inventory suite passes 24. Ruff, compilation, capability-matrix validation,
and inventory freshness on Python 3.11/3.12 pass. Candidate/legacy databases
and providers were not used ([evidence](builds/2026-10-28-recovery/gateway-nutrient-strategy-competitive-response-contract-batch.json)).
The checklist is now 1,405 complete / 25 open (1,430 total); this TODO ledger
has 113 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance are unchanged.

### Completed parallel continuation — six private Gateway response families — 28 October 2026

- [x] Add strict source-derived response models and request binding for crop
  simulation run list/detail; correct `has_more` at the 10,000 offset ceiling.
- [x] Add the spatial-autocorrelation response model with source enums,
  numeric bounds, and request-bound location/page metadata.
- [x] Enforce response contracts for the five private trend-analysis GET
  endpoints, including metric and pagination identity.
- [x] Validate the management workload summary's SQL projection, counts,
  timestamp, privacy allowlist, and location.
- [x] Validate business-planning canvas list content and bounded continuation.
- [x] Validate planning-budget summaries and stop pagination beyond the
  supported offset ceiling.

The combined selection passes 188 tests; crop-specific offset-boundary tests
pass at 9,975, 9,976, and 10,000. Ruff, compilation, capability-matrix
validation, JSON evidence parsing, runtime SQL inventory checks on Python
3.11/3.12, and diff checks pass. The 37-entry unresolved-write ledger is
unchanged. No candidate/legacy database or provider was used
([evidence](builds/2026-10-28-recovery/gateway-private-response-contracts-batch-2.json)).
The checklist is now 1,411 complete / 25 open (1,436 total); this TODO ledger
has 119 checked and 16 open entries. Capability classifications and MAN-CAP
acceptance remain unchanged.


### Completed continuation — geostatistics and pollinator detail contracts — 28 October 2026

- [x] Publish strict OpenAPI/runtime contracts for all remaining private
  geostatistics GET routes, including nested folds, summaries, and bounded
  point projections; bind location/run/page identity and stop continuation at
  the offset ceiling.
- [x] Publish strict review-queue, habitat, and hive response contracts for
  pollinator reads; retain record-type-specific detail validation, location
  grants, and sanitized no-store errors.

The combined focused Gateway selection passes 158 tests. Ruff, Python
compilation, capability validation, runtime-SQL inventory tests (24), current
inventory checks on Python 3.11/3.12, and diff checks pass. The 37-candidate
inventory keeps two source-reviewed SELECT-only `WITH` scopes in `reviewed_sites`;
this review does not approve ACLs or change grants. No live database/provider,
candidate, or legacy service was used ([evidence](builds/2026-10-28-recovery/gateway-geostatistics-pollinator-response-contracts.json)).

The checklist is now 1,414 complete / 25 open (1,439 total); this TODO ledger
has 121 checked and 16 open entries. Capability classifications remain
24 baseline-retained, 7 deployed, and 36 prepared across 67 rows.


### Completed parallel continuation — private read response contracts — 28 October 2026

- [x] Add an AI-summary review-list response contract that accepts the full
  migration-backed source catalog, preserves network/location scope labels,
  and recognizes worker-attribution blockers.
- [x] Add a strict business-canvas version-history contract, including the
  canonical snapshot blocks and bounded response size.
- [x] Add strict sequential-evidence summary and event response contracts
  aligned to their current SQL projections and pagination bounds.
- [x] Add strict nutrient soil-test and input/removal response contracts,
  including source enums, totals, cost classification, and offset-ceiling
  behavior.

The combined Gateway selection passes 157 tests; Ruff, compilation, capability
validation, Python 3.11/3.12 runtime-SQL freshness, and the 24-test inventory
regression pass. Evidence is recorded in [the batch log](batches.md). This
ledger now has 125 checked / 16 open entries; the batches checklist records
1,418 complete / 25 open. Capability classifications and MAN-CAP acceptance
remain unchanged.


### Completed continuation — private Delphi, stakeholder, and incident reads — 28 October 2026

- [x] Add strict request-bound response validation for private Delphi consent
  notices and consultation reads, including nested aggregate privacy.
- [x] Add bounded response and continuation checks for the Delphi independent
  minority-report and recommendation review queues.
- [x] Add cursor-order and exact location/party binding for stakeholder
  identity and trust review pages.
- [x] Add the exact bounded response contract for the pollution-incident
  review queue and parse the nested Delphi JSONB timestamp wire value.

The combined focused Gateway selection passes 198 tests. Ruff, compilation,
capability-matrix validation, runtime SQL inventory freshness on Python
3.11/3.12, and diff checks pass. No database, provider, candidate, or legacy
service was used. Evidence is recorded in [the batch log](batches.md). This
ledger has 129 checked / 16 open entries; the batches checklist records
1,422 complete / 25 open. The matrix now records 51 strict private Gateway
response endpoints; classifications and MAN-CAP acceptance remain unchanged.


### Completed parallel continuation — direct report scope and response contracts — 28 October 2026

- [x] Validate Directus `farm_activity.farm_task_id` against the location on
  create/update.
- [x] Validate Directus `expense_event.weekly_plan_id` against the location on
  create/update.
- [x] Reject invalid `crop_noi` location scope before cursor creation.
- [x] Reject invalid `resource_efficiency` location scope before cursor
  creation.
- [x] Reject invalid `holistic_wellbeing` location scope before cursor
  creation.
- [x] Reject invalid `revenue_multiplier` location scope before analyzer
  access.
- [x] Strictly validate and request-bind both farm-activity detail responses.
- [x] Strictly validate and request-bind governance-role detail.
- [x] Strictly validate the submitted-report review-queue projection while
  preserving authorization, errors, timestamp formatting, and cache headers.

The Directus `workflow_history` and `approval` audit remains an open gate:
both tables have polymorphic IDs without tenant keys, and their historical
lineage and visibility rules need populated-data review before filtering.

The integrated selection passes 411 Python tests, 27 Directus tenant-hook
tests, and the Directus TypeScript check. Ruff, compilation, report source/query
inventories, matrix validation, and diff checks pass. No migrations, databases,
providers, candidate, legacy service, or live network were used. See [evidence](builds/2026-10-28-recovery/kernel-parallel-report-and-gateway-contracts.json).

Checklist: 1,455 complete / 25 open (1,480 total); TODO: 162 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and
records 66 strict private Gateway response endpoints. MAN-CAP acceptance and
capability classifications are unchanged.


### Completed continuation — Directus, report scope, and private queue contracts — 28 October 2026

- [x] Narrow the Analyst `stakeholder_feedback` field allowlist without
  changing its existing row predicates; retain source-only evidence limits.
- [x] Audit remaining Analyst/Auditor wildcard reads; leave the all-status
  Auditor forensic permission unchanged because no approved private-field
  contract supports a safe narrower projection.
- [x] Require explicit valid location scope for direct `farm_summary` calls
  before cursor creation; keep output projections unchanged pending review.
- [x] Require explicit valid location scope for direct
  `regenerative_outcomes` calls before cursor creation.
- [x] Add an exact, request-location-bound response contract for the private
  mobile collection review queue.
- [x] Add an exact, request-location-bound response contract for the private
  farm-activity intake queue.

The integrated focused selection passes 400 tests. Ruff, compilation, report
source/query inventories, the Directus permission inventory, capability-matrix
validation, and diff hygiene pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-directus-mobile-report-scope-contracts.json).
Checklist: 1,461 complete / 25 open (1,486 total); TODO: 168 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared) and
records 68 strict private Gateway response endpoints. MAN-CAP acceptance and
capability classifications are unchanged.


### Completed parallel continuation — GNH, mobile inventory, and forecast scope — 28 October 2026

- [x] Reject invalid direct `generate_gnh_alignment` location scope before
  database access.
- [x] Enforce a strict request-location-bound response contract for the private
  mobile operations inventory.
- [x] Add fail-closed tenant reads and read-only enforcement for Directus
  `forecast_output` rows.

The integrated selection passes 422 Python tests and 138 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-gnh-mobile-inventory-forecast-output-boundary.json).
Checklist: 1,464 complete / 25 open (1,489 total); TODO: 171 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 69 strict private Gateway response endpoints. These checks do not prove
live Directus role behavior or historical forecast lineage.


### Completed parallel continuation — reports, CLI, retirement reads, and Directus scope — 28 October 2026

- [x] Reject invalid direct cultural-preservation report location scope before
  opening a cursor.
- [x] Preflight crop-rotation CLI location arguments before database setup.
- [x] Enforce the exact request-bound retirement-candidate response and page
  continuation contract.
- [x] Scope Directus `capex_breakdown` reads to operator grants and deny
  Directus mutations.

The integrated selection passes 551 Python tests and 141 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-culture-crop-solution-capex-boundaries.json).
Checklist: 1,473 complete / 25 open (1,498 total); TODO: 180 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 71 strict private Gateway response endpoints. The optional Directus hook
now covers 26 scoped collections; runtime behavior remains unverified.


### Completed parallel continuation — reports, CLI, Governance API, and Directus reads — 28 October 2026

- [x] Reject invalid direct capital-provider report location scope before
  database access.
- [x] Enforce a strict request-bound Governance roles page response contract.
- [x] Add a fail-closed read-only Directus tenant boundary for `noi_snapshot`.
- [x] Add a fail-closed read-only Directus tenant boundary for `water_access`.
- [x] Reject invalid traceability `create-batch` and `certs` location UUIDs
  before the CLI opens PostgreSQL.

The integrated selection passes 459 Python tests (3 skipped) and 140 Directus
extension tests. Build/typecheck, Ruff, compilation, report inventories,
capability-matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-report-cli-governance-directus-reads.json).
Checklist: 1,469 complete / 25 open (1,494 total); TODO: 176 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 70 strict private Gateway response endpoints. Directus runtime acceptance
and populated parity remain open.


### Completed parallel continuation — renewable report, pollinator CLI, capacity page, and attestation — 28 October 2026

- [x] Reject invalid direct renewable-energy report location scope before
  database access.
- [x] Preflight the pollinator health CLI's active location-scoped read
  commands before database setup.
- [x] Enforce the exact signed own-capacity response and pagination contract.
- [x] Add a fail-closed, read-only Directus tenant boundary for
  `attestation_plan`.

The integrated selection passes 573 Python tests and 142 Directus extension
tests; extension build/typecheck, Ruff, compilation, report inventories,
capability-matrix validation, and diff checks pass. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-renewable-pollinator-capacity-attestation.json).
Checklist: 1,477 complete / 25 open (1,502 total); TODO: 184 checked / 16 open.
The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared)
with 72 strict private Gateway response endpoints. The optional Directus hook
covers 27 location-scoped collections; live runtime parity remains open.


### Local continuation — wellbeing scope, energy CLI, Delphi response, and Directus source audit

- [x] Fail closed on invalid direct vulnerable-access and
  foundational-wellbeing report location scope before database access.
- [x] Preflight the energy-monitoring source-registration CLI location UUID
  before database setup.
- [x] Validate the private Delphi participant workspace against its exact
  session-derived projection, consent scopes, and requested page.
- [x] Complete the source-only audit of direct-required-location collections
  with managed Directus read rules; all twelve are covered by the existing
  tenant adapter. Broader runtime and relationship parity remain open.

Checklist: 1,482 complete / 25 open (1,507 total); TODO: 188 checked / 16
open. The matrix remains 67 rows (24 baseline-retained, 7 deployed, 36
prepared), with 73 strict private Gateway response endpoints.


### Completed continuation — scope preflight and private competency response — 28 October 2026

- [x] Reject malformed location UUIDs before cursor/helper access for the
  three Kokonut governance reports, scaling economics, and value-stream map;
  preserve documented network-wide modes.
- [x] Add a strict, request-bound response model for the private
  operating-pilot own competency assessment history page.
- [x] Preflight location UUIDs across Capital, Certificates, Drivers, Events,
  Finance, Forecast, Fortune500, Geostatistics, Graph Projection, Management,
  Office, Planning, RDF, Revenue Multiplier, Sandbox, Strategic Reserve, and
  Threatcasting CLIs while preserving intentional global modes.

The combined focused route/report/CLI selection passes 745 tests (2 skipped).
Ruff, Python compilation, report source/query inventories, capability-matrix
validation, and diff checks pass. The strict private Gateway response count is
77. Evidence:
[batch](builds/2026-10-28-recovery/kernel-scope-preflight-competency-response.json).

Checklist: 1,494 complete / 25 open (1,519 total); TODO: 200 checked / 16
open. Live tenant isolation and authenticated Gateway/database acceptance
remain separate gates.


### Completed parallel continuation — operating-pilot response, report scope, and CLI preflight — 28 October 2026

- [x] Add strict request-bound OpenAPI/runtime response contracts for the
  private operating-pilot capacity-period and work-claim pages, including
  migration-derived suppression, ordering, page bounds, and location binding.
- [x] Reject invalid selected location UUIDs before query/helper access in the
  business-plan adapter and State-of-Kokonut status, graph, comprehensive, and
  strategic-reserve report paths; preserve intentional network-wide modes.
- [x] Preflight and canonicalize supplied location UUIDs across Data Stream,
  Security verification, Precision Irrigation, stakeholder grievances,
  Treasury, Cooperative, and Traceability CLIs. Preserve supported unfiltered
  modes when optional scope is omitted.
- [x] Regenerate report source/helper/query inventories and record the focused
  batch evidence.

The integrated regression selection passes 961 tests; adjacent grievance,
Treasury, Cooperative, and Traceability checks pass 94 tests with 2 skips and 4
passing subtests. Ruff, Python compilation, all report inventory checks,
capability-matrix validation, and `git diff --check` pass. The capability
matrix remains 67 rows (24 baseline-retained, 7 deployed, 36 prepared); strict
private Gateway response endpoints now total 79, and 24 CLI groups have
location UUID preflight. No database, provider, candidate, legacy service, or
live network was used. Broader tenant isolation and live OIDC/database
acceptance remain open. Evidence:
[batch](builds/2026-10-28-recovery/kernel-parallel-response-report-cli-boundaries.json).

Checklist: 1,498 complete / 25 open (1,523 total); TODO: 204 checked / 16
open. Capability classifications and MAN-CAP acceptance remain unchanged.
