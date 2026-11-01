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

### C1 continuation — runtime-role reprovision guard — 31 October 2026

The runtime-role bootstrap now applies its broad legacy compatibility grant
for existing public tables and sequences only when the runtime login is first
created. Reprovisioning an existing login retains established grants and
reapplies the explicit private, mutation-denied, append-only, and bounded
function boundaries, but does not grant relations created since its previous
run. PostgreSQL 16 disposable acceptance verifies that a pre-existing login
retains its synthetic legacy grants, a newly created login receives the
one-time grant for existing relations, and neither login gains access to a
later-created relation after reprovisioning
([acceptance](builds/2026-10-31-recovery/runtime-role-reprovision-guard-disposable.json)).

This is a bootstrap-only guard, not a migration or a blanket ACL reduction.
Broad grants already present on existing relations remain; the API and worker
still share `kokonut_runtime`; and external consumers, tenant/RLS isolation,
Directus, candidate rollout, and production acceptance remain open. The
disposable checker was extended to include migrations 683–685, which the
current provisioner now expects for report-export function grants. No
persistent database or role was changed.

### Previous C1 continuation — migration 718 market-data write boundary — 1 November 2026

Migration 718 keeps global reference-price writes out of the shared
`kokonut_runtime` identity. The dedicated market-data function owner and login
from migration 430 now cover the manual-price and curated reference-seed
paths, alongside World Bank ingestion; application runtime retains its
read-only market-price access. The dispatcher retains the old persisted task
module for compatibility, while newly seeded schedules target
`services.ingestion.market_data_worker`.

The network-disabled disposable Standard recovery applied 709/709 ordered
schema files through migration 718, with zero failures or seeds, from one
captured SQL snapshot shared by the API and worker images. Role reapplication,
health/recovery, heartbeat privacy, shutdown, and cleanup passed
([Standard acceptance](builds/2026-11-01-recovery/standard-profile-recovery-718-disposable.json)).
The focused market-data migration checker and hosted confirmation are tracked
separately; current hosted CI #1037 failed earlier while applying migration
542 and did not reach migration 718.

The API and worker still share `kokonut_runtime`, and external consumers of
the legacy shared identity have not been reconciled. The aggregate C1 evidence
is now refreshed through migration 718: 709 ordered files applied on a
network-disabled, portless native PostgreSQL 16 database; all 38 synthetic
two-tenant/operator checks passed and cleanup completed. The ACL report records
1,324 of 1,522 public relations with effective runtime DML, including 937
public tables with DML while RLS is disabled; 163 migration-revoked relations
match runtime policy with zero policy mismatches, and the scoped probe found
zero direct table/column privilege violations. It also records 214 DML
relations without SQL relation candidates and 377 without candidate write
sites. These counts measure privilege reach and heuristic inventory coverage,
not confirmed leaks or complete consumer authorization. The separate SQL
review ledger contains 30 legacy-unreviewed and eight reviewed-unresolved
fingerprints; those fingerprints are a different unit from relations. See the
[successful replay and probe](builds/2026-10-31-recovery/native-resource-limited-schema-718-operator-probe-r2.json),
[refreshed source/ACL report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-718.json),
and [SQL review ledger](runtime-sql-unresolved-write-review.json).

The first attempt failed at local image inspection before schema application
because the requested platform did not match the available image tag. It
created no Compose resources and touched no persistent target
([failed preflight evidence](builds/2026-10-31-recovery/native-resource-limited-schema-718-operator-probe.json)).
No persistent candidate, legacy, or production database/role was changed.

### C1 continuation — migration 719 public aggregate views — 1 November 2026

Migration 719 removes `kokonut_runtime` table and column mutation grants from
`v_public_attestation_summary`, `v_public_ebf_scorecard_summary`, and
`v_public_ebf_pillar_summary`, while preserving SELECT. It aborts unless each
named object exists, remains an ordinary view, and is non-updatable according
to PostgreSQL's catalog. The migration does not use a name-prefix sweep and
does not alter Directus grants. Runtime provisioning and the source/ACL report
declare the same exact three-view boundary.

The network-disabled disposable PostgreSQL 16 checker applies and replays the
migration, verifies effective table and column DML removal, read/output parity,
and runtime-role provisioner reapplication. A separate trigger-backed writable
view is an explicit control: because it is not named in migration 719, runtime
INSERT/UPDATE/DELETE still work through it. Focused app tests preserve the
public location summary's attestation aggregate and align the pitch reader with
the columns actually exposed by migration 018. The source checks pass 19 tests;
Ruff, Python compilation, schema-only migration validation, and runtime SQL
inventory/ledger freshness pass ([migration](../../schemas/postgres/719_runtime_public_aggregate_views_read_only.sql),
[disposable ACL acceptance](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-disposable.json),
[source checks](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-source-checks.json)).

This removes unnecessary grants on inherently read-only projections and is not
evidence of a prior writable path, tenant isolation, or broad C1 closure. The
full aggregate source/ACL report, two-tenant probe, Standard replay, candidate
rollout, external runtime-client review, and populated-data parity remain at
their separately recorded gates. No candidate, legacy, or production database
or role was accessed or changed; rollback requires a reviewed forward
migration if 719 has been applied. Migration 719 is immutable.

### C1 continuation — thesaurus and governance reference writes — 1 November 2026

Migration 720 keeps the four supported thesaurus service operations behind
bounded `SECURITY DEFINER` functions owned by `kokonut_thesaurus_owner`. It
preserves runtime reads and the existing create/add/upsert/delete service
contracts, rejects keywords whose parent belongs to another thesaurus, and
does not grant direct table mutation. PUBLIC function execution is revoked;
the runtime-role provisioner grants the complete function set only after the
migrations install it. The migration safely handles the Standard ordering in
which schema migration runs before the runtime login is bootstrapped. Its
network-disabled disposable PostgreSQL checker covers role-absent and
role-present application/replay, runtime bootstrap/reapplication, denied
direct writes, and service behavior
([migration](../../schemas/postgres/720_runtime_thesaurus_bounded_writes.sql),
[acceptance](builds/2026-11-01-recovery/runtime-thesaurus-boundary-720-disposable.json)).

Migration 721 preserves runtime SELECT while revoking table and residual
column DML on `data_governance_category` and `data_governance_scope`; Directus
grants remain unchanged. It also supports migration-before-runtime-role
bootstrap. Disposable replay confirms denied runtime writes, retained reads,
seed/upsert behavior, unchanged Directus access, and no privilege widening
when the runtime provisioner is reapplied
([migration](../../schemas/postgres/721_runtime_governance_reference_catalogs_read_only.sql),
[acceptance](builds/2026-11-01-recovery/governance-reference-catalogs-721-disposable.json)).

Standard now has a default-off notification-delivery child mode using
migration 647's dedicated login and bounded claim/completion functions. The
supervisor filters the shared database credentials and unrelated worker DSNs
from that child while retaining only its provider configuration; Compose
passes its DSN and switch to the worker, not the API. This does not establish
separate API/general-worker identities. Focused supervisor/profile tests pass,
and the migration-647 disposable worker check is recorded at
[notification delivery acceptance](builds/2026-11-01-recovery/standard-notification-delivery-worker-isolation-647.json).

### Migration 722 and Standard placeholder-first recovery — 1 November 2026

Migration 722 preserves `kokonut_runtime` SELECT on `schema_migration`, which
the application uses for fail-closed startup readiness, and revokes table and
residual column mutation. Migration and ledger writes remain with the ordered
maintenance runner. The full Standard disposable recovery applies all 713
ordered schema files through migration 722 and passes API/worker/proxy health,
role reapplication, database outage/recovery, heartbeat privacy, graceful
shutdown, and cleanup without ports, seeds, or external network
([migration](../../schemas/postgres/722_runtime_schema_migration_read_only.sql);
[recovery](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json)).

That run also exposed a separate first-install provisioning issue. The
migration runner creates a locked `kokonut_runtime` placeholder before the
post-migration role bootstrap, so the old role-existence-only condition skipped
the one-time compatibility grants needed by existing application readers. The
bootstrap now marks only a newly created placeholder; the provisioner consumes
that marker when it applies the initial compatibility grants. Existing
unmarked roles do not receive broader grants, and later re-provisioning still
does not sweep newly created tables into the role. Migration 722 then removes
runtime mutation from the schema ledger, and readiness succeeds with SELECT
only.

The focused selection passes 279 tests; Ruff, schema-only validation of 713
migrations, runtime SQL inventory and review-ledger freshness, dependency and
provider boundaries, capability matrix, release-input validation, Python
compilation, and diff checks pass. A separate native, network-disabled C1
replay and two-tenant operator-scope probe now cover migration 722; ARM64/QEMU
full-schema acceptance through 722 remains open. Candidate rollout, external
runtime-client review, broad C1 writer retirement, API/worker identity
separation, populated-data parity, tenant/RLS, and production acceptance remain
open. The disposable checks touched no candidate, legacy, or production
database or role.

### C1 aggregate refresh — migration 722 — 1 November 2026

The native, network-disabled PostgreSQL 16 replay applied all 713 ordered
schemas through migration 722, with no seeds or farm data, then passed all 38
synthetic two-tenant/operator checks. The runtime scoped-write probe recorded
zero direct table or column privilege violations within its declared policy;
this is not a universal role, function, sequence, Directus, or external-client
audit. The disposable Compose project and volume were removed successfully
([replay and probe](builds/2026-11-01-recovery/native-resource-limited-schema-722-operator-probe.json)).

The paired source/ACL report covers 1,522 public relations, of which 1,315
have effective runtime DML and 931 tables have runtime DML while RLS is
disabled. It records 172 migration-revoked relations matching the declared
runtime policy with zero policy mismatches, 212 unprotected DML relations
without candidate SQL relations, and 374 without candidate write sites. These
categories overlap and measure privilege reach plus heuristic source coverage;
they are not confirmed leaks or a tenant-isolation result. The report used the
clean source revision `68e8b602` and the current runtime SQL inventory
([report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-722.json);
[SQL review ledger](runtime-sql-unresolved-write-review.json)).

The data-freshness writer review is now implemented in the migration-723
batch. The legacy CLI keeps its view-backed `--summary`; `--check` delegates to
the default-off isolated worker and fails closed when its dedicated identity
is not configured. Migration 723 retargets only the exact legacy schedule
entry while preserving cadence/settings, revokes direct shared-runtime writes
on six worker-owned event, freshness, and notification tables, and preserves
runtime reads plus Directus/maintenance access. The disposable test verifies
replay, residual column-grant removal, provisioner reapplication, and the
exact schedule predicate. This global/control-plane worker remains distinct
from location-tenant operations; configured-schedule and populated-source
parity still need deployment acceptance.

### C1 current continuation — migration 723 isolated worker writes — 1 November 2026

The native, network-disabled PostgreSQL 16 replay applies all 714 ordered
schemas through migration 723, passes 38 synthetic two-tenant/operator checks,
reports zero direct table/column privilege violations within the declared
scoped-write policy, and removes its disposable project. Migration 723
preserves runtime SELECT on six worker-owned relations while removing runtime
table and residual column DML; it leaves Directus and maintenance grants intact
and its policy is re-applied by runtime-role provisioning. The exact known
freshness schedule moves to `services.ingestion.freshness_worker` only when
its name, legacy module, and `--check` arguments match, preserving task cadence
and settings.

The paired source/ACL report covers 1,522 public relations: 1,309 have
effective runtime DML, 925 tables have runtime DML while RLS is disabled, and
178 migration-revoked relations match the declared policy with zero mismatches.
It records 213 unprotected DML relations without candidate SQL relations and
374 without candidate write sites. These are overlapping privilege-reach and
source-coverage counts, not confirmed leaks or a universal tenant-isolation
result. The refreshed static attribution map covers 4,958 SQL sites: 34
API-only, 367 worker-only, one shared, and 4,556 unresolved. Static candidates
are not observed executions or a safe grant list. ARM64/QEMU replay and the
two-tenant probe through 723 are still pending; physical Raspberry Pi
acceptance remains unavailable.

Evidence: [migration](../../schemas/postgres/723_isolated_worker_runtime_write_boundaries.sql),
[focused ACL acceptance](builds/2026-11-01-recovery/isolated-worker-runtime-write-boundary-723.json),
[native replay/probe](builds/2026-11-01-recovery/native-current-schema-723-operator-probe.json),
[source/ACL report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-723.json),
[runtime role attribution](runtime-role-attribution.json).

The API/general-worker identity split still needs a reviewed capability map
before a second login is introduced. Both Standard services use
`kokonut_runtime`; another login with the same compatibility DML grant would
separate credentials without providing least privilege. The source-only
[`runtime-role attribution inventory`](runtime-role-attribution.json), generated
by [`scripts/runtime_role_attribution.py`](../../scripts/runtime_role_attribution.py),
joins static Gateway route-handler reachability and the existing worker
operation graph to every direct SQL site. It keeps `api_candidate`,
`worker_candidate`, `shared_candidate`, and `unresolved` explicit, records
default-on supervisor children separately from whether a persisted schedule or
event is actually active, and documents the shared `PG_*` and worker-secret
environment paths. Its current source snapshot covers 4,958 SQL sites: 34
API-only candidates, 367 worker-only candidates, one site reached by both
graphs, and 4,556 unresolved sites. It discovers 349 API route roots and 478
statically reachable functions; four dynamic route factories remain unresolved.
The worker graph has 50 roots, 368 reachable SQL sites, and 56 registered
dynamic-dispatch edges. These are static candidates, not observed executions.
The map does not establish mounted dynamic routes, live schedule state, complete
effects, ACLs, tenant isolation, or a safe grant list; unresolved sites remain
unresolved. Review that map and its dynamic gaps before designing role-specific
provisioning, startup identity checks, or migrations. Directus effective
permission counts also remain unreconciled across the parity document, source
tests, and disposable snapshot; do not call that surface parity-certified until
the counts and runtime effects agree.

Refresh or validate the source map with
`python3 scripts/runtime_role_attribution.py --output docs/refactor/runtime-role-attribution.json`
or `python3 scripts/runtime_role_attribution.py --check docs/refactor/runtime-role-attribution.json`.
These commands inspect repository source only; they do not connect to a
database, run tests, inspect live schedules, or change runtime behavior.

### Earlier C1 continuation — migration 717 `chat_intent` runtime ACL — 1 November 2026

Source review found one application runtime reader for active `chat_intent`
rows in `services/analytics/llm_chat.py`, no application write target, and the
schema-maintenance seed/upsert in migration 140. Migration 717 denies only
`kokonut_runtime` table and residual column mutation privileges while
preserving SELECT. The runtime-role provisioner now reapplies that relation's
mutation denial after compatibility grants; the optional Directus role and
separate maintenance/seed path are unchanged.

The focused network-disabled disposable PostgreSQL 16 check applies and
replays migration 717, verifies runtime reads and table/column write denial,
and confirms Directus writes and the maintenance seed upsert remain available.
The focused source regression passes (1 test); the migration test module passes
39 tests. Ruff, Python compilation, runtime SQL inventory and unresolved-write
ledger freshness, and diff checks pass. The broader synthetic runtime-role
checker also passes its provisioner-reapplication probe across 192 relations
([migration](../../schemas/postgres/717_runtime_chat_intent_read_only.sql);
[focused checker](../../scripts/check-chat-intent-runtime-boundary-disposable.py);
[acceptance](builds/2026-11-01-recovery/chat-intent-runtime-acl-717.json)).

External SQL clients that write through `kokonut_runtime` remain unconfirmed;
verify them before persistent candidate or production rollout. No candidate,
legacy, or production database/role changed. This slice does not refresh the
aggregate ACL report (still through migration 711), close broad C1, or
establish tenant isolation/RLS.

### Previous C1 continuation — migration 716 climate function boundary — 1 November 2026

Migration 716 retains `kokonut_security.store_climate_summary` for historical
compatibility but revokes its execution from `kokonut_worker_execution`,
`kokonut_runtime`, `PUBLIC`, and the optional Directus role when present. The
current climate worker calls only the signed, audit-compatible v2 function
introduced in migration 713. Disposable PostgreSQL 16 applies/replays 405,
419, 428, 429, 713, and 716; it verifies v1 denial after selecting the worker
role, v2 operation for all five climate sources, legacy audit-hash/timing
parity, retries, failure audits, and location scope. The 44 focused climate
and worker-map tests pass; Ruff and Python compilation pass
([migration](../../schemas/postgres/716_retire_climate_summary_v1_worker_grant.sql);
[checker](../../scripts/check-climate-worker-disposable.py);
[evidence](builds/2026-11-01-recovery/climate-worker-716-disposable.json)).

This is source/disposable acceptance only. Repository search found no v1
application callsite, but external SQL callers and older deployed binaries are
not inventoried. Keep persistent rollout gated until those callers are checked.
CI #1034 is still validating pushed commit `3854d818` (the preceding inventory
repair and migration 715); migration 716 is local work not included in that
run. The C1 ACL aggregate remains through migration 711, and no candidate,
legacy, or production database/role was changed.

### Latest C1/CI continuation — migration 715 and inventory repair — 1 November 2026

Migration 715 revokes `PUBLIC`, `kokonut_runtime`, and
`kokonut_directus_runtime` table and residual column access on the exact 23
audited location-write receipt relations. It preserves the mapped bounded
function-owner column grants and does not change business operations or retry
semantics. The runtime-role provisioner now keeps the relations private. The
focused runtime-role/migration selection passes 142 tests; a network-disabled
PostgreSQL 16 checker passes migration apply/replay, owner-grant preservation,
runtime/Directus/PUBLIC denial, and compatibility regrant followed by private
policy reapplication ([migration](../../schemas/postgres/715_runtime_private_location_write_receipts.sql);
[checker](../../scripts/check-runtime-private-receipts-disposable.py);
[evidence](builds/2026-11-01-recovery/runtime-private-location-write-receipts-715-disposable.json)).

Current-head [CI #1033](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41255043315)
failed at the fast-fail inventory gate: a receipt-list insertion in
`042eebf` shifted line-based source IDs in `runtime-sql-inventory.json`. Its
kernel-image job passed, and Security #757 passed. The inventory was regenerated
after the migration-715 source edits; the inventory and unresolved-write ledger
now pass locally, along with Ruff, 706-file migration validation, and
142 runtime-role/migration tests. Hosted CI on the repair commit remains
pending. This does not establish source/ACL aggregate freshness beyond the
explicit inventory or close broad C1; the ACL report remains through migration
711. No candidate, legacy, or production database or role was changed
([CI diagnosis](builds/2026-11-01-recovery/ci-1033-runtime-sql-inventory-repair.json)).

### Earlier C1 continuation — migration 713 climate worker boundary — 31 October 2026

C1 remains open. The fresh, network-disabled native PostgreSQL 16 replay
applied 702/702 ordered schema files through migration 711 and passed all 38
synthetic two-tenant operator-scope checks. The probe confirms 88 private
relations and 71 mutation-denied relations under the current runtime role,
with zero direct table/column privilege violations. The refreshed source/ACL
join records 161 migration-owned runtime boundaries, zero policy mismatches,
1,356 relations with effective runtime DML, 968 tables with runtime DML while
RLS is disabled, and 40 unresolved write candidates. These counts measure
privilege reach and inventory coverage, not confirmed exposure or universal
isolation. The replay used no seeds, host ports, or farm data; candidate,
legacy, and production databases were not touched
([replay and probe](builds/2026-10-31-recovery/native-schema-711-operator-probe.json);
[report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-711.json)).

Migration 711 adds signed exact-location energy-reading capture, idempotent
private receipts/audit, and an isolated function owner; it preserves the
`recorded` lifecycle and revokes direct `kokonut_runtime` writes while keeping
runtime SELECT and existing Directus/maintenance writes. Its disposable
PostgreSQL 16 apply/replay and role checks pass. The legacy energy writer now
fails before database acquisition. Receipt/audit tables are also declared
private in the runtime-role provisioner, so a later bootstrap does not reopen
them ([migration](../../schemas/postgres/711_location_energy_reading_capture.sql);
[checker](../../scripts/check-energy-reading-capture-disposable.py);
[evidence](builds/2026-10-31-recovery/energy-reading-capture-711-disposable.json)).

The legacy remote-sensing due-claim path has been retired at the CLI and service
boundary. `--run-jobs`, `run_due_jobs()`, and `_claim_due_jobs()` now fail
before database/provider work and direct operators to the default-off signed
worker. Create, list, and manual-job paths remain. No broad remote-sensing ACL
revocation or candidate rollout is claimed. The runtime SQL inventory was
regenerated and its tracked freshness check now passes; the stale due-claim
fingerprint was removed from the unresolved-write review ledger.

The user-linked [CI #1014](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41172853331)
ran on `aa6a01a`. Attempt 1 failed, but its GitHub log blob has expired;
attempt 2 was cancelled during Buildx setup after a newer run superseded it.
The original attempt-1 cause is unknown. This branch later added Buildx caching
and a parallel image job. The later current-head [CI #1029](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41233060705)
failed for a separate, verified reason: the fast-fail gate found a stale runtime
SQL inventory. This batch repairs that inventory and records local passing
freshness validation. On the pushed head, CI #1032's full-ci runner later
received a shutdown signal after 704 schema migrations and 28 seeds applied;
no assertion failure was logged. Security #756 passed, while the
multi-architecture image job was still running at inspection. Hosted
validation is incomplete, not a passing CI result
([inventory repair](builds/2026-10-31-recovery/ci-1029-runtime-sql-inventory-fix.json);
[CI #1032 evidence](builds/2026-10-31-recovery/ci-1032-hosted-runner-shutdown.json)).

Migration 712 moves Standard PostgreSQL rate-limit bucket access behind bounded
consume and cleanup functions. The Standard runtime and Directus roles have no
direct bucket-table access; runtime can execute only the consume function, and
the optional dedicated maintenance login can execute only cleanup. Its
network-disabled Standard recovery replay applied 703/703 schema entries
through migration 712 and passed role provisioning, limiter behavior, API and
worker health/recovery, and cleanup
([evidence](builds/2026-10-31-recovery/standard-profile-rate-limit-712-disposable.json)).
This replay did not run the two-tenant operator-scope probe or refresh the
full source/ACL aggregate: the migration-711 report above remains the current
aggregate snapshot. The migration closes the gateway bucket boundary only; it
does not close broad runtime DML or tenant isolation. External importer
ownership, remaining runtime writers, broader Directus and tenant boundaries,
populated-data parity, and separately reviewed persistent rollout remain open.

Migration 713 routes the signed climate worker's source/audit write through a
bounded v2 function that preserves the legacy payload hash and zero-valued
success `processing_time_ms`, while recording elapsed time in a separate
`execution_duration_ms` column. It also keeps active locations readable when
coordinates are absent, so plot-only geometry remains usable by GEE and
locations with neither geometry nor coordinates return source-level skips.
The focused climate selection passes 252 tests; disposable PostgreSQL 16
applies and replays 405/419/428/429/713, verifies all five source writes,
legacy audit digest/timing parity, safe failure audit, cross-location denial,
plot-only/empty-geometry reads, and runtime DML revocation
([evidence](builds/2026-10-31-recovery/climate-worker-713-disposable.json)).
The migration has not been applied to the candidate or production, and no real
provider credentials or external calls were used. The Standard recovery
acceptance remains through migration 712; this focused climate check is not a
full-schema replay or profile acceptance.

Migration 714 closes direct access to the private
`location_solution_creation_receipt` table after compatibility provisioning.
It removes table and residual column privileges from `PUBLIC`,
`kokonut_runtime`, and `kokonut_directus_runtime`; the bounded
`kokonut_solution_creator_owner` retains only its existing request-ID column
grants. Runtime provisioning now classifies this receipt as private. The
focused runtime-role/migration regression set passes 141 tests, the ordered
source validator accepts all 705 migration files, Ruff and `git diff --check`
pass, and network-disabled PostgreSQL 16 applies/replays migrations 504 and
714 with 11 grouped checks, including simulated broad compatibility grants
followed by migration 714. This is one reviewed receipt boundary, not a
refreshed aggregate ACL report or full-schema replay; it does not close broad
runtime DML or tenant isolation. Candidate, legacy, and production databases
were not changed ([migration](../../schemas/postgres/714_runtime_location_solution_creation_receipt_private.sql);
[runner](../../scripts/check-solution-create-disposable.py);
[evidence](builds/2026-10-31-recovery/runtime-solution-creation-receipt-714-disposable.json)).

### Historical detailed notes for migrations 700–710

The detailed source/function cohort below covers migrations 700–703. Migrations
704, 705, 706, and 707 add, respectively, the runtime read-only boundary for
`living_wage_benchmark`, a migration-owned 147-relation Directus privilege
policy reapplied by the optional role provisioner, a runtime read-only
boundary for the shared `protocol` catalog, and a runtime read-only boundary
for the authorization-bearing `farmer_role` defaults. Focused native and
ARM64/QEMU PostgreSQL checks pass for migration 704; migration 705 replay and
the disposable Directus role reprovisioning check pass
([704 evidence](builds/2026-10-31-recovery/living-wage-benchmark-704-disposable.json),
[705 evidence](builds/2026-10-31-recovery/directus-relation-policy-705-disposable.json)).
Migration 706's network-isolated PostgreSQL 16 acceptance verifies apply/replay,
runtime SELECT, denial of table and residual column writes, runtime-role
reprovisioning, and unchanged Directus/maintenance grants
([evidence](builds/2026-10-31-recovery/runtime-protocol-read-only-disposable.json)).
No in-repository application writer or Directus collection rule was found;
seed upserts use the separate maintenance path. External importer use through
`kokonut_runtime` is unconfirmed, so persistent rollout remains gated on that
contract check.
The migration-707 source audit found only the application SELECT of
`default_permissions` in `services/analytics/farmer_identity.py`; role
assignments are written to the separate `role_assignment` table. No service,
extension, seed, or Directus permission/hook write path for `farmer_role` was
found beyond its migration-defined defaults. The network-isolated disposable
acceptance applies and replays migration 707, preserves runtime SELECT, denies
table and residual column writes after compatibility-role reprovisioning, and
proves synthetic Directus and maintenance roles retain actual write access
([source audit](builds/2026-10-31-recovery/farmer-role-707-source-audit.json),
[ACL evidence](builds/2026-10-31-recovery/farmer-role-runtime-read-only-707-disposable.json)).
Because `default_permissions` affects authorization, future edits remain on a
reviewed migration/maintenance path. External importer use through
`kokonut_runtime` is not confirmed; candidate and production rollout stay gated
until that identity contract is checked. Preserved SELECT does not establish
tenant isolation. The complete native migration replay through migration 707
applies all 698 ordered schema files and passes 38 synthetic two-tenant
operator-scope checks in a network-disabled, portless disposable PostgreSQL 16
project. No seeds or farm data were loaded, cleanup passed, and no candidate,
legacy, or production target was accessed. The current probe reports 976
public tables with runtime DML while RLS is disabled; this is privilege reach,
not confirmed exposure ([evidence](builds/2026-10-31-recovery/full-schema-707-native.json)).
The integrated local migration, role-boundary, profile, and worker-health
selection passes 229 tests ([evidence](builds/2026-10-31-recovery/c1-707-standard-focused-tests.json)).
The current source/ACL join generated from the native full-schema-707 probe
records 151 declared runtime boundaries, zero policy mismatches, zero direct
table/column privilege violations, 1,364 relations with some runtime DML, and
976 tables with runtime DML while RLS is disabled. It still records 41
unresolved write candidates. These are privilege-reach/audit counts, not
confirmed exposure; the source/ACL join is a review aid, not proof of
reachability, full column/sequence/ownership safety, or tenant isolation
([report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-707.json)).
Native replay through 707 and all 38 synthetic two-tenant operator checks pass.
The attempted ARM64/QEMU full replay through 705 stopped at migration 116
without a migration error; the prior complete QEMU replay through 703 and
focused ARM64 checks for later migrations remain. This is not physical
Raspberry Pi acceptance. Migrations 704, 706, and 707 remain gated from
persistent rollout until external importer use through `kokonut_runtime` is
confirmed. Migration 705 establishes role-reprovisioning resilience, not
Directus API parity or tenant isolation.

Migration 708 retires the five legacy direct writers in
`services/analytics/landscape_conservation.py` and denies only the general
runtime role's table/column DML on those records. The signed location-scoped
capture from migration 702, SELECT access, and maintenance/Directus grants
remain. A network-disabled PostgreSQL 16 check applies and replays 702/708,
checks those grants, and exercises capture/replay successfully
([checker](../../scripts/check-landscape-runtime-boundary-disposable.py)).
This targeted acceptance is not a full-schema replay or importer compatibility
decision; external importer use remains a rollout gate. The 707 source/ACL
report above is a historical schema snapshot, not a post-708 ACL measurement.
A separate fresh, no-seed PostgreSQL 16 ordered replay logged 699 migrations
through 708 applied with zero migration failures. Its subsequent ad hoc ledger
query used a nonexistent column, so the replay confirms migration application
only; it does not create a post-708 ACL inventory or ledger verification
([recovery evidence](builds/2026-10-31-recovery/ci-1024-repair-local-checks.json)).

Migration 709 preserves runtime SELECT on `public.schema_version` while
revoking runtime table and residual column DML. The ordered schema runner is
the only in-repository writer found; services, workers, extensions, and
Directus permissions have no application write path. A network-disabled
disposable PostgreSQL check applies and replays 709, confirms the runtime
read-only boundary, and proves separate Directus/maintenance writes remain
available ([source regression](../../tests/test_runtime_role_boundary.py);
[checker](../../scripts/check-schema-version-runtime-boundary-disposable.py);
[evidence](builds/2026-10-31-recovery/schema-version-runtime-read-only-709.json)).
External importer use through `kokonut_runtime` remains unconfirmed, so do not
apply the restriction to a persistent candidate or production target until
that identity contract is checked. This focused test is not a full-schema
replay or tenant-isolation acceptance.

Migration 710 makes the schema-owned `cache_invalidation_rule` table read-only
to `kokonut_runtime`, while retaining SELECT and Directus/maintenance writes.
Its isolated network-disabled PostgreSQL 16 check passed apply/replay and
table/column privilege assertions
([evidence](builds/2026-10-31-recovery/cache-invalidation-rule-710.json)).
Repository source review found no application, seed, or Directus writer, but
custom/external use through the runtime login remains unconfirmed and blocks
persistent rollout.

The refreshed Standard recovery acceptance applies all 701 schema files
through migration 710 on a network-disabled, portless disposable PostgreSQL 16
project. It explicitly bootstraps the app/worker runtime login after migration,
verifies both services use `kokonut_runtime`, rejects database-owner credentials
before child startup, preserves the migration-owned `schema_version` write
denial after bootstrap reapplication, and passes API/worker recovery after a
database restart. Heartbeat privacy/removal, graceful shutdown, and cleanup
also pass
([evidence](builds/2026-10-31-recovery/standard-profile-recovery-710-runtime-role-disposable.json)).
This does not rerun the two-tenant operator-scope probe or refresh the runtime
privilege/source aggregate. The latest aggregate therefore remains the
historical migration-707 snapshot, with 41 unresolved write candidates.

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
- [x] Reconcile the latest native C1 inventories through migration 722: the
  ACL report records 212 unprotected DML relations without candidate SQL
  relations and 374 without candidate write sites. The separate runtime SQL
  review ledger contains 30 legacy-unreviewed and eight reviewed-unresolved
  fingerprints. These are different units; source review is not ACL approval.
  Refresh both records as operations are migrated ([ACL report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-722.json);
  [SQL review ledger](runtime-sql-unresolved-write-review.json)).
- [x] Add and refresh the deterministic API/general-worker attribution map.
  The current snapshot covers 4,958 SQL sites; the original baseline covered
  4,967 before later source retirements. It includes Standard
  credential/default-child policy and explicit unresolved labels
  ([inventory](runtime-role-attribution.json);
  [generator](../../scripts/runtime_role_attribution.py)). The inventory
  checker passes; this is static source evidence only.
- [ ] Review the 4,556 unresolved SQL sites, four dynamic Gateway route
  factories, 56 worker dynamic-dispatch edges, persisted schedule activation,
  and external callers before defining any API/general-worker grants.
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
- [x] Complete native full-schema replay and refresh the aggregate ACL/source
  report plus the two-tenant operator-scope probe through migration 722: 713/713
  files, 38 checks, no seeds, zero scoped-policy table/column violations, and
  successful cleanup ([probe](builds/2026-11-01-recovery/native-resource-limited-schema-722-operator-probe.json);
  [report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-722.json)).
- [ ] Complete ARM64/QEMU full-schema replay and refresh the aggregate ACL/source
  report plus the two-tenant operator-scope probe through migration 722. This is
  emulated portability evidence, not physical Raspberry Pi acceptance.

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

- [x] Prevent runtime-role reprovisioning from applying the all-public-table
  compatibility grant again. Network-disabled PostgreSQL 16 acceptance proves
  an existing login retains old grants without gaining access to later tables,
  and a new login's initial compatibility grant is not repeated on reapply
  ([evidence](builds/2026-10-31-recovery/runtime-role-reprovision-guard-disposable.json)).
- [ ] Remove the first-creation all-public-table compatibility grant as
  reviewed writer cohorts migrate. Broad grants already present on existing
  relations remain and require per-relation retirement.
- [x] Keep `capex_breakdown`, `water_access`, `attestation_plan`,
  `event_handler`, `capital_source`, and `consent_data_type` in the
  runtime mutation-deny policy so compatibility role provisioning cannot
  restore their DML; the targeted direct table/column ACL probes pass.
- [x] Keep `farmer_role` in the runtime mutation-deny policy: application code
  reads authorization defaults but writes assignments to `role_assignment`.
  Migration 707 and its disposable acceptance preserve runtime SELECT and
  separate Directus/maintenance grants while denying runtime table and column
  writes after compatibility provisioning. External importer use through the
  runtime login remains a candidate/production rollout gate.
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

## Historical source-only checkpoint — governance-tension lifecycle — 30 October 2026

Added a location-scoped Gateway action surface for triage, start, record link,
work-item link, resolve, and defer. Requests have strict action-specific
schemas and a 32 KiB body limit; responses bind location, tension, action, and
idempotency request ID, omit actor identities, and use no-store headers. The
helper sets signed operator tenant context and calls the planned bounded
`kokonut_security.mutate_governance_tension_action` contract. Exact OIDC action
policies are registered for the six operations.

At this source-only checkpoint the database function, grants, replay receipt,
atomic event/link writes, and disposable acceptance were still deferred.
Migration 700 and its focused acceptance subsequently closed that function and
receipt gate ([evidence](builds/2026-10-30-recovery/governance-tension-location-actions-700-disposable.json)).
Legacy service/CLI writers remain enabled because the schema supports network,
organization, farm, cooperative, value-stream, initiative, and decision scopes;
the new route covers location scope only. It rejects non-location tensions
until matching authenticated scope contracts are designed. Candidate, legacy,
and production databases and roles were not touched. Other audited C1 writers
without exact Gateway equivalents remain open rather than being retired and
losing capabilities.

## Historical source-only checkpoint — extension learning and landscape capture — 30 October 2026

Added strict, location-bound Gateway write contracts for extension peer-network
creation, extension progress updates, and five record-only landscape captures
(habitat, corridor, hedgerow, buffer check, and biodiversity assessment). These
routes use exact OIDC action policies, signed tenant context, bounded request
bodies, idempotency receipts, identity-minimized no-store responses, and reject
duplicate JSON keys and NUL characters. Extension Learning adds a peer-network
creation form; progress writes remain an API operation because the source data
contains participant-linked records and no safe roster/detail UI is defined.

At this source-only checkpoint, the bounded SQL contracts, grants, database
acceptance, and console/browser checks were deferred. Migrations 701 and 702
subsequently added the bounded extension and landscape functions, preserving
legacy defaults and derivations, and their focused disposable acceptance
passed ([extension](builds/2026-10-30-recovery/extension-learning-writes-701-disposable.json),
[landscape](builds/2026-10-30-recovery/landscape-capture-702-disposable.json)).
The full native and ARM64/QEMU schema replays through 703 also apply these
contracts. Legacy services and CLIs remain enabled, and no capability was
retired. Live browser acceptance and remaining C1 writer boundaries are still
open.

## Historical source-only checkpoint — metric writes and planning preflight — 30 October 2026

The metric engine now exposes a calculator-only draft function that does not
insert or commit. New Gateway source contracts provide exact-location draft
computation, a paginated identity-minimized list, and a separate
human-verification action. The operator console can compute, inspect, and
verify using the matching location grants. The writer adapter sets signed
tenant context before source reads and the bounded write, validates calculator
output, derives reviewer identity from the operator session, rejects self-review
in the planned function contract, and maps documented SQLSTATEs. The existing
CLI adapter remains unchanged until migration and rollout.

At this source-only checkpoint those three SQL functions and their grants had
not yet been added. Migration 703 subsequently implemented the bounded draft,
list, and verification contracts, including location binding, lifecycle,
pagination, idempotent receipts, and independent-review enforcement; focused
disposable PostgreSQL acceptance passed
([evidence](builds/2026-10-30-recovery/metric-value-kernel-disposable.json)).
The planning CLI and service also reject noncanonical or reversed dates before
database acquisition. The legacy metric CLI writer remains enabled, and
populated-data parity, source-reference location validation, and broad C1
closure remain open.
