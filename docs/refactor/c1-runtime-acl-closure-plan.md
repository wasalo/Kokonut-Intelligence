# C1 Runtime ACL Closure Plan

## Goal

Replace the broad `kokonut_runtime` DML grant with reviewed, least-privilege
write boundaries while preserving supported farm, finance, credit, event,
analytics, worker, and administrative capabilities. C1 is complete when each
runtime writer has an accountable identity, a bounded operation contract, and
database-enforced scope or an explicitly approved global/system boundary; no
unreviewed direct table DML remains. The two existing append-only audit ledgers
may retain INSERT only under their declared controls.

Do not blanket-revoke the 991 relations measured at migration 689. That
snapshot showed 989 ordinary/partitioned relations with
INSERT/UPDATE/DELETE and two append-only audit relations with INSERT only.
Migrations 690–697 remove runtime DML from twelve reviewed relations; migration
699 removes unnecessary grants from the inherently non-updatable
`v_public_farm_summary` view. The native full-schema 699 probe reports 979
tables still exposed. These counts
measure ACL reach, not confirmed tenant leaks. Static SQL absence is not proof
that a table is unused: helper-mediated writes, Directus permissions, dynamic
SQL, ORM paths, external integrations, and populated production data remain
incomplete in the inventory.

## Current evidence and decisions

### Current cohort — migrations 700–705, 31 October 2026

The detailed source/function cohort below covers migrations 700–703. Migrations
704 and 705 add, respectively, the runtime read-only boundary for
`living_wage_benchmark` and a migration-owned 147-relation Directus privilege
policy reapplied by the optional role provisioner. Focused native and
ARM64/QEMU PostgreSQL checks pass for migration 704; migration 705 replay and
the disposable Directus role reprovisioning check pass
([704 evidence](builds/2026-10-31-recovery/living-wage-benchmark-704-disposable.json),
[705 evidence](builds/2026-10-31-recovery/directus-relation-policy-705-disposable.json)).
The grouped local integration selection passes 213 tests
([evidence](builds/2026-10-31-recovery/c1-704-705-standard-focused-tests.json)).
The latest complete source/ACL report remains through 703; its counts are not
current after migration 704. The full native ordered replay now passes through
705 (696/696 migrations and 38 two-tenant checks). The attempted ARM64/QEMU
replay through 705 was stopped after 583.6 seconds at migration 116 (111/696)
without a migration error; cleanup passed. The earlier complete QEMU replay
through 703 and focused ARM64 checks for 704/705 remain evidence.
Migration 704 rollout remains gated until the owner confirms external importers
do not use the runtime login. Migration 705 establishes reprovisioning
resilience, not Directus API parity or tenant isolation.

The location-scoped tension, extension-learning, landscape-capture, and metric
value source contracts now have additive SQL functions, isolated function
owners, exact runtime grants, and private receipts/audit rows. Focused disposable
PostgreSQL/PostGIS acceptance passes for each migration; the native full-schema
replay through 703 applies 694/694 files and passes all 38 two-tenant operator
checks. The full ARM64/QEMU replay through 703 passes 694/694 schemas and all 38
two-tenant operator checks ([evidence](builds/2026-10-30-recovery/kernel-c1-full-schema-703-arm64-r1.json)); it used no seeds or host ports and cleaned up its disposable project. The new native replay through 705 passes 696/696 schemas and all 38 checks, with zero seeds/host ports and disposable cleanup ([evidence](builds/2026-10-31-recovery/kernel-c1-full-schema-705-native.json)). The attempted ARM64/QEMU replay through 705 was stopped after 583.6 seconds at migration 116; it reported no migration error and cleaned up. This is software emulation, not physical Raspberry Pi acceptance. The refreshed 703 report records
148 declared policy boundaries, zero mismatches, zero direct table/column
privilege violations, 1,367 public relations with some DML, and 979 tables with
runtime DML while RLS is disabled. The 41 unresolved write candidates remain
open; these counts measure ACL reach, not confirmed tenant-data exposure.
The grouped focused Gateway/console/source/ACL/migration selection passes 216
tests ([evidence](builds/2026-10-30-recovery/c1-700-703-focused-tests.json)).

These additive routes do not retire the legacy tension/metric/extension/
landscape writers, revoke their DML, or prove universal tenant isolation. No
candidate, legacy, or production database/role was changed. Current evidence:
[native full replay](builds/2026-10-30-recovery/kernel-c1-full-schema-703-native-r2.json),
[source/ACL report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-703.json),
[migration 700](builds/2026-10-30-recovery/governance-tension-location-actions-700-disposable.json),
[migration 701](builds/2026-10-30-recovery/extension-learning-writes-701-disposable.json),
[migration 702](builds/2026-10-30-recovery/landscape-capture-702-disposable.json),
[migration 703](builds/2026-10-30-recovery/metric-value-kernel-disposable.json).

Migration 703 bounds `source_record_ids` and rejects NULL elements, but does
not verify that the polymorphic records belong to the requested location. The
Gateway currently derives them from the scoped metric calculation. Keep
provenance acceptance open until a source-type/discriminator contract makes
location validation possible at the database boundary.

The detailed entries below are dated historical checkpoints through migration
699 unless they link explicitly to the current 700–703 evidence above.

- The native full-schema migration-699 probe covers 1,513 public relations
  and reports 979 tables with runtime DML while RLS is disabled. The ARM64/QEMU
  full-schema replay through 696 applied 687/687 schema files and passed the
  38-check two-tenant operator probe; it used no seeds, farm data, or host
  ports and cleaned up its disposable project. Focused migrations 697/699 ACL
  checks and 698 relationship-scope checks pass on native and ARM64/QEMU. The
  historical 991 figure and current counts measure ACL reach, not confirmed
  tenant-data leaks.
- The current SQL inventory check passes with 41 unresolved write candidates;
  the prior migration-692 snapshot recorded 4,959 execution sites across 989
  files, 1,253 relation candidates, and 585 static write-target relations. Its analytics subset has 278 relations across
  91 files and 437 write-site candidates, with no unmatched relation in the
  analytics cohort ([current analytics inventory](builds/2026-10-30-recovery/analytics-runtime-write-candidate-inventory-692.json));
  the other reviewed service groups contain 275 unique relations across 44
  packages. These sets overlap. The inventory is a review aid, not evidence
  that each operation is reachable or authorized.
- The refreshed migration-699 report verifies 142 declared runtime controls
  with zero policy mismatches and zero direct table/column privilege
  violations; 979 tables still retain effective runtime DML while RLS is
  disabled ([report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-699.json)).
- The owner confirmed that no active gRPC clients use credit batch,
  marketplace, or bridge mutations; legacy global scopes may be replaced.
- The owner confirmed Kokonut Network operates Genesis, Seeds, Adelphi,
  Terra Viva, and V1. That does not establish wallet ownership or authority to
  mutate external credit accounts.
- `CreateBatch` and `ApplyToClass` now require exact location scopes and the
  signed Gateway tenant-context setter in the write transaction. Their focused
  regression evidence is in
  [grpc-credit-location-scope.json](builds/2026-10-30-recovery/grpc-credit-location-scope.json).
- The refreshed source/ACL join is
  [runtime-privilege-callsite-report-699.json](builds/2026-10-30-recovery/runtime-privilege-callsite-report-699.json):
  142 declared controls match, with zero migration-policy mismatches and zero
  table/column privilege violations in the native full-schema probe.
- The owner confirmed no external importer writes `process_benchmark` through
  the runtime database identity. The repository has no application read/write
  path, seed writer, or Directus collection permission. Migration 697 and the
  runtime-role provisioner preserve runtime SELECT while denying table and
  column DML; separate maintenance/import authority remains available. Native
  and ARM64/QEMU focused PostgreSQL checks pass. This does not scope the global
  benchmark SELECT by tenant.
- Migration 698 adds explicit `location_id` scope to
  `farm_task_framework_step`. It backfills only endpoints that already share a
  location, retains mismatched historical links as NULL, and adds deferred
  composite foreign keys plus a trigger that derives scope for inserts using
  the previous named-column shape. Focused native and ARM64/QEMU disposable
  checks pass, as does the native full-schema replay through 698 (689/689
  files, 38 operator checks). This is not a DML revoke or proof of caller
  authorization. Confirm external importers do not use positional
  `INSERT ... VALUES` and disposition unresolved historical edges before
  rollout.
- Migration 690 makes `capex_breakdown` read-only to `kokonut_runtime`; the
  generated inventory records two application SELECT sites and no write
  target. Native and ARM64/QEMU full-schema probes through 690 passed.
- Migration 691 makes `water_access` and `attestation_plan` read-only to
  `kokonut_runtime`. The current SQL inventory records two and one SELECT
  call sites respectively, with no write targets; the Directus Auditor policy
  and authorization hook already deny their mutations. Focused isolated
  PostgreSQL acceptance and native plus ARM64/QEMU full-schema replays through
  691 passed. Each full replay applied 682/682 files and passed the
  two-tenant operator-scope probe; the ARM64 database ran as `aarch64` under
  QEMU, not on physical Raspberry Pi hardware. Migration 692 now denies direct
  runtime, Directus, and PUBLIC writes to managed-hive tables while preserving
  the bounded function-owner grants. Migration 693 denies runtime, Directus,
  and PUBLIC writes to `pollinator_observation`, `pollinator_habitat`, and
  `pesticide_impact_log` while preserving reads and bounded capture-function
  owner grants. Focused disposable acceptance passes. The native full-schema
  replay through 693 applied 684/684 files and passed the 35-check two-tenant
  probe, reporting 983 relations with runtime DML and RLS disabled. Migration
  694 makes the `event_handler` registry read-only to `kokonut_runtime`,
  preserving Directus SQL grants and the event-dispatch owner's bounded SELECT
  columns. Its network-disabled ACL replay and native full-schema replay pass;
  the latter applied 685/685 files, passed 36 operator checks, and reports 982
  relations. ARM64/QEMU full-schema replay remains through 693, and the focused
  ACL checker passes on ARM64/QEMU through 694. None of these DML
  revocations establishes tenant-safe SELECT access or changed candidate,
  legacy, or production roles.

- Migration 695 makes `capital_source` read-only to `kokonut_runtime`. Its four
  application callsites are SELECT-only, the Directus Auditor is read-only,
  and pilot seed 008 runs through the separate maintenance `kokonut` identity.
  The migration leaves Directus grants and seed behavior unchanged. Focused
  native and ARM64/QEMU ACL checks pass, and the native full-schema replay
  through 695 applies 686/686 files with 37 operator checks. ARM64/QEMU
  full-schema replay remains through 693. The retained global SELECT still
  needs a tenant-scope contract.
- Migration 696 makes `consent_data_type` read-only to `kokonut_runtime`. The
  source inventory has no application read/write callsites, no application or
  extension DML, and no Directus collection permission entry; schema migration
  148 maintains this catalog using migration authority. Migration 401 leaves
  category retention defaults unset, while configurable retention windows and
  legal holds remain in the separate `data_retention_policy` records. The new
  boundary preserves SELECT, Directus SQL grants, and migration/maintenance
  writes. Focused native and ARM64/QEMU checks pass, as does native full replay
  through 696 (687/687 files and 38 operator checks). Full ARM64/QEMU replay
  remains through 693; `consent_data_type` SELECT remains global and is not
  made tenant-safe here.

## Next cohort findings — 30 October 2026

- The managed-hive writer cohort is closed: `add_hive()` and
  `record_hive_inspection()` in `services/analytics/pollinator_health.py`
  fail before database access, while authenticated location-scoped Gateway
  capture, lifecycle, and independent-review routes use signed context and
  bounded functions from migrations 622, 623, 625, and 627. Migration 692
  removes direct `kokonut_runtime`, Directus, and PUBLIC DML while preserving
  SELECT and bounded function-owner grants. Focused unit and disposable ACL
  acceptance pass, including stale column grants, actual denied writes, and
  provisioner reapplication. The disposable pollinator reporting fixture
  inserts its synthetic hive/inspection rows directly as test setup; the six-
  group migration-155/602 acceptance passes
  ([evidence](builds/2026-10-30-recovery/pollinator-health-reporting-disposable.json)).
  Native and ARM64/QEMU schema-692 replays and the 35-check two-tenant
  operator probe pass. These SELECTs are still not tenant-isolated by this
  DML boundary.
- The pollinator capture cohort is closed at the direct-write boundary:
  `record_observation()`, `create_habitat()`, and `record_pesticide_impact()`
  now fail before database access. Authenticated location-scoped Gateway
  operations backed by migrations 619–621 remain the supported write paths.
  Migration 693 removes runtime, Directus, and PUBLIC DML, clears stale table
  and column grants, preserves SELECT and bounded function-owner grants, and
  remains effective after provisioner reapplication. Focused source and
  disposable ACL checks pass. These read paths still need a separate tenant
  contract.
- `capital_source` is now closed at the direct runtime-write boundary. Its four
  service callsites are SELECT-only, the Directus Auditor policy is read-only,
  and pilot seed 008 executes as the maintenance `kokonut` user. Migration 695
  revokes only `kokonut_runtime` DML and preserves the distinct Directus SQL
  grants and maintenance seed path. Its global SELECT scope is still not
  tenant-isolated.
- `consent_data_type` is closed at the direct runtime-write boundary without
  fixing retention periods in the catalog: migration 401 sets the seeded
  defaults to NULL and runtime policy periods/legal holds stay configurable
  in `data_retention_policy`. The ACL migration preserves Directus and
  maintenance writes; tenant isolation for category reads remains open.
- The initial source review deferred two apparent no-callsite candidates.
  `process_benchmark` was subsequently made read-only to `kokonut_runtime` by
  migration 697 after the owner confirmed no external importer uses that role.
  `farm_task_framework_step` still has 20 unresolved historical edges among 41
  in the earlier local aggregate. Migration 698 now enforces same-location
  scope for new/edited associations and preserves mismatches for review; it
  does not revoke DML or reconcile historical rows. Verify positional external
  import behavior and dispose unresolved edges before rollout. These are
  unresolved usage/scope boundaries, not evidence of data exposure.
- The remaining credit-class mutation RPCs are not safe to enable with farm
  location context alone. Wallet-bearing requests need a verified account
  grant; baskets can span locations; class/basket definitions are global
  administration; bridge ingress/completion and buy-order settlement need
  dedicated verified worker boundaries. The likely first wallet-bound cohort
  is sell-order create/update/cancel after an account-grant contract exists.
- These audits do not justify a blanket revoke. The legacy runtime DML count
  includes real Directus hook writes, operator transitions, worker state,
  seed/import writes, and SQL sites whose reachability is still unresolved.

## Work checklist

### 1. Inventory and safe boundary set

- [x] Join migration-689 ACL evidence to the conservative SQL inventory and
  compare native with ARM64/QEMU.
- [x] Separate analytics, credit-class, and other service candidates; preserve
  unresolved and no-callsite records as unresolved.
- [ ] Resolve the 41 unresolved write candidates and refresh the inventory as
  each operation is migrated.
- [ ] Reconcile Directus field/row permissions, extension hooks, ORM/dynamic SQL,
  API keys, saved reports, and external consumers per candidate relation.
- [x] Verify migration 690 and the `capex_breakdown` boundary on network-
  disabled disposable PostgreSQL 16: replay, preserved SELECT, denied table
  and column writes, and provisioner reapplication all pass.
- [x] Verify migration 691 and the `water_access`/`attestation_plan` boundary
  on network-disabled disposable PostgreSQL 16: replay, preserved SELECT,
  denied table/column writes, unchanged Directus SQL grants, and provisioner
  reapplication all pass.
- [x] Verify migration 692 and the `hive_record`/
  `pollinator_hive_inspection` boundary on network-disabled disposable
  PostgreSQL 16: apply/replay, preserved SELECT, denied runtime/Directus/PUBLIC
  writes, stale table/column privilege cleanup, preserved bounded function
  owner grants, and provisioner reapplication all pass.
- [x] Retire both legacy service writer helpers and update the disposable
  pollinator reporting fixture; focused unit tests and the six-group
  migration-155/602 synthetic reporting acceptance pass.
- [x] Verify migration 693 and the pollinator observation, habitat, and
  pesticide capture boundary on network-disabled disposable PostgreSQL 16:
  replay, preserved SELECT/function-owner grants, runtime/Directus/PUBLIC
  write denial, stale table/column cleanup, and provisioner reapplication
  all pass ([evidence](builds/2026-10-30-recovery/runtime-pollinator-capture-693-disposable.json)).
- [x] Retire the three unscoped pollinator capture helpers and refresh the
  SQL inventory/ledger; focused source checks pass
  ([evidence](builds/2026-10-30-recovery/pollinator-capture-693-source-checks.json)).
- [x] Complete native full-schema replay through migration 691 and the
  two-tenant operator-scope probe (682/682 migrations; 988 tables with runtime
  DML and RLS disabled).
- [x] Complete ARM64/QEMU full-schema replay through migration 691 and the
  two-tenant operator-scope probe (682/682 migrations; 988 tables with runtime
  DML and RLS disabled). This is not physical Raspberry Pi acceptance.
- [x] Complete native full-schema replay through migration 692 and rerun the
  two-tenant operator-scope probe against the current runtime-role policy
  (683/683 migrations; 986 relations retain runtime DML with RLS disabled).
- [x] Complete ARM64/QEMU full-schema replay through migration 692 and the
  two-tenant operator-scope probe (683/683 migrations; 986 relations retain
  runtime DML with RLS disabled). This is software portability evidence, not
  physical Raspberry Pi acceptance ([evidence](builds/2026-10-30-recovery/arm64-resource-limited-schema-692-operator-probe-retry.json)).
- [x] Complete native full-schema replay through migration 693 and rerun the
  two-tenant operator-scope probe (684/684 migrations; 983 relations retain
  runtime DML with RLS disabled)
  ([evidence](builds/2026-10-30-recovery/native-resource-limited-schema-693-operator-probe.json)).
- [x] Complete ARM64/QEMU full-schema replay through migration 693 and the
  two-tenant operator-scope probe (684/684 migrations; 983 relations retain
  runtime DML with RLS disabled). This is not physical Raspberry Pi acceptance
  ([evidence](builds/2026-10-30-recovery/arm64-resource-limited-schema-693-operator-probe.json)).
- [x] Verify migrations 694–696 on network-disabled disposable PostgreSQL 16:
  preserve intended SELECT and separate Directus/function-owner grants, deny
  runtime table/column mutations, survive migration replay and compatibility
  provisioner reapplication; migration 696 passes on native and ARM64/QEMU.
- [x] Complete native full-schema replay through migration 696 and rerun the
  two-tenant operator-scope probe (687/687 files; 38 checks; 980 relations
  retain runtime DML while RLS is disabled)
  ([evidence](builds/2026-10-30-recovery/native-resource-limited-schema-696-operator-probe.json)).
- [x] Complete ARM64/QEMU full-schema replay through migration 696 and rerun
  the two-tenant operator-scope probe; completed 30 October 2026 with 687/687
  files and 38 checks. QEMU is not physical Raspberry Pi acceptance.

### 2. Credit-class gRPC and command surfaces

- [x] Replace global authorization on `CreateBatch` and `ApplyToClass` with
  exact location grants and same-transaction signed context.
- [ ] Add location fields to object-ID mutation requests and bind each object
  to that location inside the same transaction before changing state.
- [ ] Add a separately provisioned wallet/account grant for operations that
  name seller, buyer, depositor, holder, issuer, sender, curator, or admin
  addresses. An address in a request is not proof of wallet control.
- [ ] Keep class/basket definition mutations behind explicit global admin
  capabilities; keep bridge ingress/completion and settlement behind dedicated
  worker identities with source-chain and idempotency checks.
- [ ] Migrate direct credit-class CLI writers to an explicit operator or
  maintenance boundary before removing their table DML.
- [ ] Revoke credit-class table DML only after every affected writer is moved
  behind bounded database functions/roles and populated-state parity passes.

### 3. Analytics writers

- [ ] Group the 280 analytics write-target relations by capability and public
  caller. Replace tenant-facing writes with signed location-scoped Gateway
  operations or bounded functions; use dedicated identities for durable
  workers and distinct maintenance identities for administrative jobs.
- [ ] Separate the 439 candidate SQL sites into reachable, unused, and
  unresolved call paths using direct function/job reachability; module-level
  operation tags are not proof of worker reachability.
- [ ] Preserve current calculations and reports with synthetic/populated
  reference fixtures before changing grants.
- [ ] Revoke DML per completed relation cohort, never by broad source absence.

### 4. Other service writers

- [ ] Reconcile the 275 unique non-analytics/non-credit-class candidate
  relations across 44 packages. Preserve durable event/scheduler state,
  farm-operation workflows, finance, certificates, and protocol execution.
- [ ] Add bounded APIs/functions or dedicated writer identities per capability
  group, with authorization, idempotency, rollback, and audit coverage.
- [ ] Keep global reference and administrative writes distinct from
  tenant-owned farm data.

### 5. Runtime role migration

- [ ] Replace `services/migration/runtime_role.py`'s all-public-table DML grant
  with reviewed least-privilege grants as writer cohorts migrate. New tables
  must not inherit broad DML by default.
- [x] Keep `capex_breakdown`, `water_access`, `attestation_plan`,
  `event_handler`, `capital_source`, and `consent_data_type` in the
  runtime mutation-deny policy so compatibility role provisioning cannot
  restore their DML; the targeted direct table/column ACL probes pass.
- [ ] Keep reader, API, worker, indexer, report, Directus, and maintenance
  identities distinct where their call graphs or authority differ.
- [ ] Add a migration-backed privilege contract per cohort, including table
  and column ACLs, forced-RLS behavior where applicable, and provisioner
  reapplication after compatibility grants.

### 6. Verification and rollout

- [ ] On disposable PostgreSQL 16, replay all migrations, provision all runtime
  roles, verify every bounded function and operation, assert direct DML denial,
  verify RLS tenant isolation, and replay migrations/provisioning.
- [ ] Repeat database portability checks on ARM64/QEMU; record clearly that
  this is not physical Raspberry Pi acceptance.
- [ ] Use synthetic data for cross-tenant denial and representative populated
  fixtures for each migrated capability; keep candidate/legacy/production
  state separate.
- [ ] Before candidate or production rollout, create and restore-rehearse a
  fresh encrypted checkpoint, apply only ordered forward migrations, verify
  exact ACL/RLS deltas and protected routes, and preserve rollback evidence.
- [ ] Keep production cutover separate from code completion; retain a reversible
  route/role rollout until all hosted checks pass.

## Acceptance and rollback rules

A relation leaves the broad runtime DML set only when all in-repository writers,
workers, CLI paths, Directus paths, and declared external contracts have a
replacement or an explicit retirement; tenant-owned writes must be bound by a
database-verified identity and scope in the same transaction. A disposable
regression must prove both intended writes and cross-scope denial, and the
provisioner must not restore the revoked grant.

Use additive, ordered migrations. Never edit an applied migration or mutate a
production role before a restore rehearsal and explicit rollout gate. Rollback
uses a reviewed forward grant restoration or deployment rollback from a
verified encrypted checkpoint; it does not disable authorization checks or
silently reintroduce global scopes.

## Latest continuation — migration 697 — 30 October 2026

The owner confirmed there is no external importer using `kokonut_runtime` to
write `process_benchmark`. Source review found no app reader/writer, seed
writer, or Directus collection permission. Migration 697 and the role
provisioner preserve runtime SELECT and revoke table/column DML, leaving
separate maintenance/import authority intact. Focused network-disabled
PostgreSQL 16 replay, denied mutations, Directus privilege preservation, and
provisioner reapplication pass on native and ARM64/QEMU.

The native full-schema replay passes through 697 (688/688 files, 38 synthetic
two-tenant operator checks). The refreshed report covers 1,513 relations and
141 declared controls with zero policy mismatches and zero direct privilege
violations; 979 relations retain runtime DML while RLS is disabled. This is
privilege reach, not confirmed leaks. Full ARM64/QEMU replay remains through
696; focused 697 ARM64/QEMU ACL acceptance passes. `process_benchmark`'s
retained global SELECT is not tenant-isolated. `farm_task_framework_step`
remains unresolved because 20 of 41 historical edges lack confirmed scope.
No candidate, legacy, or production role/database was changed.

Evidence: [migration](../../schemas/postgres/697_runtime_process_benchmark_read_only.sql),
[native ACL](builds/2026-10-30-recovery/runtime-process-benchmark-697-disposable.json),
[ARM64/QEMU ACL](builds/2026-10-30-recovery/runtime-process-benchmark-697-arm64-disposable.json),
[native full-schema replay](builds/2026-10-30-recovery/native-resource-limited-schema-697-operator-probe.json),
[source/ACL report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-697.json).

## Latest continuation — migration 698 — 30 October 2026

Migration 698 adds location scope to `farm_task_framework_step`, backfilling
only same-location endpoints and preserving unmatched historical rows as NULL.
Deferred composite foreign keys bind new associations to both parent locations;
a trigger derives the scope for existing named-column inserts, rejects
cross-location links, and blocks edits/moves involving unresolved legacy links.
The migration does not change table grants or establish caller authorization.

The focused network-disabled PostgreSQL 16 replay passes on native and
ARM64/QEMU with synthetic rows. The 112-test relationship-schema/SDK selection
passes, and schema parity covers 109 models and 2,151 columns. Native full
schema replay through 698 passes: 689/689 migrations and 38 two-tenant checks.
The refreshed ACL report remains at 141 declared controls, zero policy
mismatches or direct privilege violations, and 979 relations with runtime DML
while RLS is disabled. This is privilege reach, not confirmed leaks. The 168-test
source/ACL regression selection passes against the migration-698 snapshot,
including role-boundary, source-report, SQL-inventory, and ARM64 replay-parser
checks. The full ARM64/QEMU replay remains through 696; focused migration-698 QEMU acceptance is
not physical Raspberry Pi acceptance.

The earlier data aggregate found 20 of 41 framework-step edges with unresolved
scope; only synthetic records were used in this batch. Before rollout, confirm
no external importer relies on positional `INSERT ... VALUES` and reconcile or
dispose unresolved edges. No candidate, legacy, or production database or role
changed.

Evidence: [migration](../../schemas/postgres/698_farm_task_framework_step_location_scope.sql),
[native focused check](builds/2026-10-30-recovery/farm-task-framework-step-698-disposable.json),
[ARM64/QEMU focused check](builds/2026-10-30-recovery/farm-task-framework-step-698-arm64-disposable.json),
[source/ACL regression selection](builds/2026-10-30-recovery/farm-task-framework-step-698-source-checks.json),
[native full-schema replay](builds/2026-10-30-recovery/native-resource-limited-schema-698-operator-probe.json),
[source/ACL report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-698.json).


## Latest continuation — migration 699 — 30 October 2026

Migration 699 removes `kokonut_runtime` table/column mutation grants from
`v_public_farm_summary`, preserves SELECT, and verifies the object remains a
non-updatable view. The view's grouped aggregate query was already inherently
non-updatable, so this removes unnecessary grants and protects the boundary
against a future view-definition change; it does not fix an exploitable write
path. Directus grants were preserved. The runtime-role provisioner now retains
the read-only policy.

Focused network-disabled PostgreSQL 16 apply/replay, SELECT and mutation ACL
checks, stale column-grant removal, Directus grant preservation, and
provisioner reapplication pass natively and under ARM64/QEMU. Native full-schema
replay through 699 passes all 690 migrations and the 38-check two-tenant
operator probe. The corrected source/ACL, runtime-role, SQL-inventory, and
ARM64-replay-parser selection has 169 passing tests across the full run and
single-fixture correction rerun. The latest report records 142 declared
controls, zero policy mismatches or direct privilege violations, 1,367 public
relations with any DML, and 979 tables retaining runtime DML while RLS is
disabled. These counts represent privilege reach, not confirmed data leaks;
41 write candidates remain unresolved. Focused QEMU checks are software
portability evidence, not physical Raspberry Pi acceptance; full QEMU schema
replay remains through 696. No candidate, legacy, or production database or
role changed.

Evidence: [migration](../../schemas/postgres/699_runtime_public_farm_summary_read_only.sql),
[native ACL](builds/2026-10-30-recovery/runtime-public-farm-summary-699-disposable.json),
[ARM64/QEMU ACL](builds/2026-10-30-recovery/runtime-public-farm-summary-699-arm64-disposable.json),
[native schema replay](builds/2026-10-30-recovery/native-resource-limited-schema-699-operator-probe.json),
[source/ACL report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-699.json),
[regression evidence](builds/2026-10-30-recovery/runtime-public-farm-summary-699-source-checks.json).


## Next candidate review — `living_wage_benchmark` — 30 October 2026

The service has one active benchmark SELECT scoped by the requested location;
no application write target or Directus extension permission was found. The
only repository INSERT is the Adelphi demonstration/reference seed, citing
the Global Living Wage Coalition / Anker methodology. This does not establish
whether an external importer uses the runtime identity. Preserve existing
grants until that owner boundary is confirmed; if no such importer exists, a
forward migration can retain SELECT while revoking runtime table/column writes
and preserving the separately controlled maintenance/import path.

Evidence: [source audit](builds/2026-10-30-recovery/living-wage-benchmark-c1-source-audit.json).

## Code-first continuation — governance-tension lifecycle — 30 October 2026

Added a location-scoped Gateway action surface for triage, start, record link,
work-item link, resolve, and defer. Requests have strict action-specific
schemas and a 32 KiB body limit; responses bind location, tension, action, and
idempotency request ID, omit actor identities, and use no-store headers. The
helper sets signed operator tenant context and calls the planned bounded
`kokonut_security.mutate_governance_tension_action` contract. Exact OIDC action
policies are registered for the six operations.

The database function, grants, replay receipt, atomic event/link writes, and
disposable acceptance are deferred to the final migration/test phase. Legacy
service/CLI writers remain enabled because the schema supports network,
organization, farm, cooperative, value-stream, initiative, and decision scopes;
the new route covers location scope only. It must reject non-location
tensions until matching authenticated scope contracts are designed. Candidate,
legacy, and production databases and roles were not touched. Other audited C1
writers without exact Gateway equivalents remain open rather than being
retired and losing capabilities.

## Code-first continuation — extension learning and landscape capture — 30 October 2026

Added strict, location-bound Gateway write contracts for extension peer-network
creation, extension progress updates, and five record-only landscape captures
(habitat, corridor, hedgerow, buffer check, and biodiversity assessment). These
routes use exact OIDC action policies, signed tenant context, bounded request
bodies, idempotency receipts, identity-minimized no-store responses, and reject
duplicate JSON keys and NUL characters. Extension Learning adds a peer-network
creation form; progress writes remain an API operation because the source data
contains participant-linked records and no safe roster/detail UI is defined.

The planned database functions must retain the legacy defaults and derivations:
fair corridor/hedgerow condition, current-date defaults for omitted observation
dates, width-based buffer compliance when both widths are present, and validated
location geometry. The bounded SQL contracts, role grants, database acceptance,
and console/browser checks are deferred to the final migration/test phase. The
legacy services and CLIs remain enabled until those gates pass; no capability
is retired in this source-only tranche. These routes are not deployable before
their functions exist, and no tests or migrations were added or run.

## Code-first continuation — metric writes and planning preflight — 30 October 2026

The metric engine now exposes a calculator-only draft function that does not
insert or commit. New Gateway source contracts provide exact-location draft
computation, a paginated identity-minimized list, and a separate
human-verification action. The operator console can compute, inspect, and
verify using the matching location grants. The writer adapter sets signed
tenant context before source reads and the bounded write, validates calculator
output, derives reviewer identity from the operator session, rejects self-review
in the planned function contract, and maps documented SQLSTATEs. The existing
CLI adapter remains unchanged until migration and rollout.

The future SQL functions are
`kokonut_security.create_location_metric_value_draft`,
`kokonut_security.list_location_metric_values`, and
`kokonut_security.verify_location_metric_value`. They must own grant checks,
location binding, draft/verified lifecycle, bounded pagination,
cross-operation idempotency, self-review exclusion, and identity-minimized
receipts. Separately, the planning CLI and service now reject noncanonical or
reversed plan dates before acquiring PostgreSQL. No tests or migrations were
added or run; these routes are not deployable until their functions and grants
exist.
