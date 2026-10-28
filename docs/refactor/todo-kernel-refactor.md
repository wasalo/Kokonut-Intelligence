# Kokonut Kernel refactor TODO

Updated: 27 October 2026. This is the active cross-phase work queue for the
owner-provided [architecture implementation plan](implementation-plan-alignment.md).
The detailed, historically preserved acceptance records remain in
[batches.md](batches.md); this file groups their remaining gates into work that
can proceed now and gates that need an owner, provider, populated source data,
or production environment. Check an item only when its evidence is recorded in
the batch log and the affected capability/progress records are updated.

## Completed in the current continuation

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

## Code work to continue without owner input

Work in this order. Each item is a bounded implementation batch, not a claim
that its full source-plan phase is complete.

- [ ] **C1 — Replace broad runtime database privileges with scoped contracts.**
  The initial pre-provisioning 642-migration inventory found 1,101 relations
  with unprotected runtime DML. Of these, 529 have no static write candidate
  and 334 have no SQL candidate at all; the counts are heuristic and the
  latter is a subset.
  The native full-schema acceptance through migration 662 covers the current
  runtime boundary policies, including 79 private relations, 24
  mutation-denied relations, two append-only relations, and the API-key
  read-only column allowlist: 106 declared boundaries. Focused
  migration-658–662 ACL checks pass on native and ARM64/QEMU disposable
  PostgreSQL, covering 79 private relations, 24 mutation-denied relations,
  two append-only relations, and the API-key column boundary. The complete
  653-file ARM64 replay through migration 662 passes its two-tenant scope
  probe and verifies all 106 declared boundaries (79 private, 24 mutation-
  denied, two append-only, and the API-key column boundary), with zero direct
  table or column privilege violations. It reports 1,014 public relations with
  effective table-level DML while RLS is disabled, so broad runtime access and
  universal application tenant isolation remain open. It separately reports
  zero effective runtime TRUNCATE grants across 1,511 public relations in this
  synthetic replay. This is synthetic
  software acceptance; broad runtime access
  remains beyond these selected boundaries and the probe does not establish
  universal application tenant isolation.
  The target-aware analytics inventory links 273 relations with
  effective DML and analytics write candidates to 425 write-target sites
  across 89 files, with no unmatched candidate relations; `farm` is a
  read-only source in two `INSERT … SELECT` statements, not a write target.
  `advisory_rule` and `crop_family` are protected read-only,
  `crop_nutrient_removal_factor`, `certification_type`, `cooperative_type`,
  `dfs_insurance_product_type`, `evidence_maturity_level`, `sensor_type`,
  `waste_type`, `disposal_method`, `graph_node_type`, and `graph_edge_type`
  have database-verified read-only policies through migration 661 on native
  and ARM64/QEMU focused disposable targets. `access_audit_log` is append-only
  for the runtime through migration 662 on both targets; no retention period
  or pruning authorization is included.
  Review other unresolved callers before changing grants. Classify candidates by
  capability and caller identity first. Change only
  reviewed slices with bounded functions or exact grants. Do not
  blanket-revoke from heuristic absence. Preserve rollback and distinguish
  table grants from RLS, worker, Directus and production enforcement.
  Sources: [runtime boundary](batches.md#L2826),
  [agent boundary](batches.md#L3652),
  [latest full-schema probe](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json).
- [ ] **C2 — Finish Gateway and SDK contract parity.** Audit registered routes,
  auth/action/scope policy, pagination, error models and SDK behavior; close
  source-verifiable gaps without exposing generic CRUD or weakening default
  denial. The public OpenAPI exporter now excludes private policy routes and
  allows only public GET/read operations in the generated contract; broader
  route and SDK parity remains open. Sources: [API/SDK gates](batches.md#L3226),
  [Phase 7](implementation-plan-alignment.md#L27).
- [ ] **C3 — Finish the optional Directus adapter boundary.** Close code-verifiable
  role, field, row and hook gaps for collections still retained; keep native
  farm activity in Gateway. Record surfaces that cannot be proven without a
  live runtime separately. Sources: [Directus parity](batches.md#L2117),
  [transport/Directus gates](batches.md#L3320).
- [ ] **C4 — Port repository-defined provider jobs and workflows.** Compare each
  source module against the owned scheduler/job contract, add missing adapters
  and operator controls, and keep external schedules disabled until ownership
  and active state are reconciled. Sources: [provider/job inventory](batches.md#L2288),
  [worker recovery](batches.md#L2358).
- [ ] **C5 — Close source-verifiable analytics and reporting gaps.** Port
  registered queries/cards and deterministic projections, fix correctness and
  access gaps, and preserve ClickHouse as rebuildable optional projection.
  Do not infer populated-farm parity from synthetic fixtures. Sources:
  [report/query parity](batches.md#L2334),
  [consumer scope](batches.md#L3139).
- [ ] **C6 — Complete source-only capability slices.** Continue unresolved
  route, lifecycle, lineage, provenance and review functionality for CAP-035,
  CAP-036, CAP-037 and CAP-038 where code can be completed without populated
  farm records or production identity. Sources: [CAP-035](batches.md#L3484),
  [CAP-036](batches.md#L3574), [CAP-037](batches.md#L3582),
  [CAP-038](batches.md#L3652).
- [ ] **C7 — Finish software-only ARM64 and recovery evidence.** The complete
  653-file ARM64/QEMU schema replay through migration 662 passes under the
  verified 1.5 GiB/two-CPU database budget. All 17 operator-scope assertions
  pass across two synthetic tenants and verify 106 declared runtime boundaries
  (79 private, 24 mutation-denied, two append-only, plus the API-key column
  boundary); no direct table or column privilege violations were found. The
  database was not OOM-killed, no seeds or farm data were loaded, no host ports
  were published, and temporary resources were removed. The probe still
  reports 1,014 public relations with effective table-level DML while RLS is
  disabled. This remains synthetic software evidence, not physical-device,
  populated-data, external-provider/media, R2, or production recovery
  acceptance ([full replay](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json);
  [native ACL](builds/2026-10-27-recovery/runtime-reference-catalogs-652-660-disposable.json);
  [ARM64 ACL](builds/2026-10-27-recovery/runtime-reference-catalogs-652-660-arm64-disposable.json);
  [native graph-type ACL](builds/2026-10-27-recovery/runtime-graph-types-652-661-disposable.json);
  [ARM64 graph-type ACL](builds/2026-10-27-recovery/runtime-graph-types-652-661-arm64-disposable.json);
  [native capability-audit ACL](builds/2026-10-27-recovery/runtime-access-audit-log-append-only-disposable.json);
  [ARM64 capability-audit ACL](builds/2026-10-27-recovery/runtime-access-audit-log-append-only-arm64-disposable.json)).
  The remaining optional Dockerfile targets (gRPC, MQTT, OIDC, and ML anomaly)
  now also build from pushed revision `8da25cfd` for ARM64 and pass bounded,
  network-disabled, read-only import and CLI-help checks. The OIDC image's
  missing Authlib HTTP client dependency was corrected and verified. This closes
  the image-build subgate; no database, broker, provider, or Compose service
  was started ([optional target evidence](builds/2026-10-27-recovery/arm64-optional-kernel-targets-8da25cfd.json)).
  Both base and ClickHouse-superset Kernel app images build for AMD64/ARM64
  with matching locked packages, and minimal/edge/standard/analytics Compose
  selections validate for ARM64 ([schema](builds/2026-10-27-recovery/arm64-schema-652-disposable.json);
  [app and profile evidence](builds/2026-10-27-recovery/arm64-kernel-app-build-smoke.json)).
  The full ARM64 schema replay also passes under the 1.5 GiB/two-CPU budget
  through migration 662 ([resource-limited replay](builds/2026-10-27-recovery/arm64-resource-limited-schema-662.json)).
  The repository's encrypted checkpoint command and role-prerequisite restore
  now pass against all 653 current schema migrations through 662, with a
  matching fingerprint and synthetic sentinel in a fresh database ([prior 643/652 evidence](builds/2026-10-27-recovery/kernel-checkpoint-restore-disposable.json);
  [current 653/662 evidence](builds/2026-10-27-recovery/kernel-checkpoint-restore-current-schema.json)).
  This does not represent populated farm data, external media/providers, R2,
  whole-platform recovery, or a production RPO/RTO drill. All optional
  Dockerfile image targets now have ARM64 build/import evidence. The Kernel API
  liveness smoke now passes at
  512 MiB/one CPU, but this does not establish schema readiness. No physical
  Raspberry Pi is available, so hardware power-loss and endurance remain open.
  Sources: [Phase 8](implementation-plan-alignment.md#L28),
  [portability gates](batches.md#L2012).
- [ ] **C8 — Reconcile all ledgers after each batch.** Keep the sprint TODO,
  `batches.md`, `progress.md`, capability matrix and migration/evidence links
  consistent. Preserve the 25 open composite checklist entries until their
  individual acceptance criteria close.

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
- [x] Align the Python `ExportFormat` type with the TypeScript union and use it
  for the export model and `create_export` helper. The focused SDK selection
  passes 98 tests, including a source comparison of the Python `Literal` and
  actual TypeScript union; the schema guard covers 109 models / 2,150 columns.
  Ruff, compilation, and diff checks pass. This fixes one concrete static typing
  mismatch; other create/update payloads and runtime behavior remain outside
  this subgate ([batch record](batches.md); [progress](progress.md#export-format-typing-parity--27-october-2026)).

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
