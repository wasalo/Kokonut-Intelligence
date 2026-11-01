# Kokonut Kernel refactor: current state and implementation guide

**Status snapshot: 1 November 2026**
**Purpose:** one readable guide to the intended architecture, current evidence,
remaining gates, and safe order of work.
**Authority:** this document summarizes the current repository; dated evidence
and the linked operational trackers remain the detailed records.

## How to read the project state

The repository contains a legacy Compose integration stack and a separate
Kernel candidate. Source code, unit tests, disposable-database acceptance,
candidate rollout, production rollout, and human acceptance are distinct
states. A passing source test or disposable PostgreSQL replay does not mean a
migration is applied to the local candidate, and a healthy candidate does not
mean production is ready.

Use these labels when discussing progress:

| Label | Meaning |
| --- | --- |
| **Implemented** | The source or migration exists in the current checkout. |
| **Focused checks pass** | The named unit, contract, lint, or static checks passed; read the evidence for exact scope. |
| **Disposable acceptance passes** | The named migration or behavior passed against synthetic data in an isolated disposable database. |
| **Candidate applied** | The migration was applied to the explicitly selected local Kernel candidate, with checkpoint and rollout evidence. |
| **Production accepted** | The production deployment, external integrations, operational ownership, and release gates passed. |
| **Human gate open** | A domain owner, provider operator, reviewer, or physical-device acceptance is still needed. |

The attached owner-provided architecture implementation plan is the design
source. Its detailed Phase 0–8 mapping is in
[implementation-plan alignment](implementation-plan-alignment.md). The current
repository behavior and migrations take precedence over historical paths,
cached web pages, or old phase snapshots. The root plan in Downloads is
ignored by Git; this guide is the tracked high-level status entry point.

## Target architecture

Kokonut owns the domain rules and governed lifecycle. PostgreSQL/PostGIS is
the canonical operational schema and durable state. The Kokonut Gateway and
Python domain services are the native application layer. Capabilities remain
available through explicit, replaceable adapters; reducing the default
deployment must not silently remove capability.

```text
Browser / Field Collector / SDK / CLI
                 |
       Kokonut Gateway + domain services
       authorization, lifecycle, audit,
       consent, evidence and adapters
                 |
    PostgreSQL + PostGIS (canonical state)
       |         |           |
   scheduler  outboxes   versioned views
       |                     |
 optional providers       ClickHouse / reports
```

Architecture invariants:

- Keep governed records in the canonical PostgreSQL schema. Analytical stores
  and cached projections are rebuildable and are not operational truth.
- Preserve `draft → submitted → verified → published`, with `rejected` for
  rework/exception. Domain state such as payment, attestation, or revocation
  belongs in its own fields.
- Keep verification, publication, sensitive execution, participant identity,
  and legal disposition behind the relevant human review boundary.
- Keep private evidence off-chain by default. Web3 provides proofs and
  coordination, not the operational source of truth.
- Keep database migrations ordered and checksummed. Never edit an applied
  migration to repair current behavior; add a forward migration.
- Retire a legacy writer or dependency only after replacement parity,
  authorization, retry/recovery, data lineage, rollback, and owner gates pass.

## Deployment profiles in the current planner

The profile planner is `scripts/kernel-profile.py`. It composes explicit
candidate manifests and prints commands; it does **not** run Docker, read
secrets, apply migrations, seed data, or perform cutover. Review `config`
output, select the intended project, then separately execute the printed
command and applicable rollout procedure.

| Profile | Current composition | Readiness meaning |
| --- | --- | --- |
| **minimal** | Private PostgreSQL/PostGIS plus the combined Kernel app/API and enabled worker processes. | Smallest candidate deployment shape. Capability parity, recovery, live identity, and operational acceptance remain open. |
| **core** | Minimal app built from the reduced, hash-locked dependency set. Optional Web3, exports, and local-media packages are selected explicitly. | Packaging profile, not a different data model. The current OIDC app overlay is incompatible with this reduced image. |
| **edge** | Minimal plus encrypted local media and edge-oriented resource settings; MQTT/HTTP sensors remain separately selectable overlays. | No physical Raspberry Pi test has been performed. QEMU and source-level ARM64 checks do not establish device performance or power-loss behavior. |
| **standard** | PostgreSQL plus separate API and durable-worker services sharing one application image, with loopback-bound Caddy ingress by default. `--no-proxy` selects a separately managed ingress. `standard --edge` composes Edge local-media and resource settings while preserving the API/worker split; the local-media key/volume apply only to the API, and Edge resource limits apply to PostgreSQL and the API, not the worker. Both services require a dedicated non-owner, non-privileged login before starting children; the worker also has a read-only PostgreSQL probe for stale leases, old eligible due backlog, and supervisor/child-process liveness. `--action release-up` prints a no-build pull/start command and requires digest-pinned application images. | The latest network-disabled Standard recovery applied all 713 schema files through migration 722 from one captured SQL snapshot; both app images matched its digest. Fresh placeholder provisioning, migration-ledger read access, runtime-role reapplication, API/worker/proxy health, database outage/recovery, heartbeat privacy, shutdown, and cleanup passed ([evidence](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json)). The aggregate runtime ACL report and two-tenant probe remain through 718. API and worker still share the `kokonut_runtime` login, so distinct identities remain an open C1 boundary. Release image publication, current-target migration/role rollout, candidate rollout, live identity, populated lease/provider recovery, external alert routing, public ingress, backup/restore, scale, prolonged recovery, and physical-device acceptance remain open. Standard+Edge is planner/Compose-source support only; it does not establish physical Raspberry Pi suitability, power-loss behavior, or production readiness. The probe reports aggregate counts and ages without IDs or payloads; it detects exited children but not an alive-but-hung child. The default Caddy listener is local TLS, not public production ingress. |
| **analytics** | Minimal plus private ClickHouse analytical projection. `--separate-workers` adds standard API/worker separation. | Requires projection parity, rebuild/outage behavior, and worker recovery acceptance. Metabase is not required. |
| **scale** | Rejected by the planner. | Multi-host/replica behavior, shared budgets, failover, measured sizing, and concurrency/recovery gates are not accepted. |

Optional overlays include external OIDC client, self-hosted ZITADEL, gRPC,
MQTT, HTTP sensor receiver, Directus compatibility, sensor anomaly ML, and core
Web3/export/local-media packages. Caddy is selected by default for Standard
and remains optional for other profiles. Each overlay has its own credentials,
permissions, runtime, and acceptance requirements. `docker-compose.yml` is
still the legacy integration stack; the candidate planner uses
`docker-compose.kernel-*` manifests and a separate Compose project. No legacy
service or data volume is implicitly adopted by the candidate.

The planner now matches the owner-provided Standard composition by adding
Caddy's loopback-bound TLS ingress by default. `standard --no-proxy` supports
an external ingress; `standard --oidc` uses the default Caddy layer, while
`standard --no-proxy --oidc` requires an externally managed HTTPS origin.
Public DNS/TLS, firewall, trusted-proxy, secure-cookie, and browser trust
acceptance remain open. See the [Standard profile guide](standard-profile.md)
for exact selection and operational constraints. The source-build `build` and
`up` actions remain for development. The new `release-up` action requires a
digest-pinned application image (and a separate digest-pinned OIDC image when
selected), pulls before starting with `--no-build`, and currently rejects
source-only optional service overlays without a published immutable-image
contract. Registry publication and target acceptance have not been performed.

ARM64 image and emulated schema/runtime checks are portability evidence. The
owner has no Raspberry Pi available, so physical-device, thermal, storage,
power-loss, and recovery behavior cannot be claimed complete. Do not publish a
host database port to work around candidate/legacy conflicts; use Compose
service names or a deliberately reviewed local override.

## Capability and phase snapshot

The tracked capability matrix currently has 67 entries classified as 24
baseline-retained, 7 deployed, and 36 prepared. These are implementation
classifications, not percentages of user-facing production readiness. Many
prepared entries have source-level or isolated contract evidence while still
awaiting live provider, populated-data, tenant/RLS, deployment, or owner
acceptance.

The source plan has Phase 0–8. Work is currently concentrated on Phase 7
(route-by-route replacement of Directus as the primary application API), with
continuing prerequisites and gates in Phases 0, 2, 3, 4, 5, 6, and 8. No whole
phase should be called complete from an individual migration or endpoint.

| Source-plan phase | Current direction | Major remaining evidence |
| --- | --- | --- |
| 0 — baseline and capability freeze | Inventory, matrix, owner/location decisions, and source audits exist. | Reconcile remaining owners, external consumers, active providers/jobs, populated data, and retention/restore responsibilities. |
| 1 — ports/adapters | Selected settings, ports, and provider boundaries exist. | Prove optional dependencies can be absent across the full runtime and all relevant imports/configuration paths. |
| 2 — minimal PostgreSQL runtime | Minimal candidate and native API/workers exist. | End-to-end governed workflows, sync, scheduled retries, accepted-work recovery, migration rollout, and backup/restore. |
| 3 — optional analytics | PostgreSQL reporting contracts and selected ClickHouse paths exist. | Port retained report/dashboard outputs and prove projection rebuild, outage recovery, and tenant-safe downstream access. |
| 4 — owned scheduler | Durable scheduler and worker state exist for selected jobs. | Reconcile all active schedules/providers and transfer jobs one at a time with output parity and recovery evidence. |
| 5 — optional Redis | Replaceable cache/rate-limit paths exist. | Prove minimal operation without Redis and durable auth/revocation/audit/retry under multi-replica failure. |
| 6 — optional edges | Compose overlays and significant transport contracts exist. | Browser HTTPS/trusted-proxy acceptance, MQTT/HTTP parity, gRPC authorization, and live external ingress. |
| 7 — native Gateway | Active route-by-route migration; selected strict read/write APIs and operator console exist. | Full field, permission, lifecycle, consent, audit, export, SDK and reviewer parity; Directus remains optional and not yet parity-certified. |
| 8 — ARM64/scale/retirement | ARM64 builds and QEMU database checks exist. | Physical Pi acceptance when hardware exists, resource/recovery measurements, scale acceptance, and reviewed retirement/cutover. |

See [the matrix](capability-matrix.md) for per-capability classification,
[the batch checklist](batches.md) for granular acceptance, and
[the TODO queue](todo-kernel-refactor.md) for current execution order. The
large [progress ledger](progress.md) is an append-only historical timeline;
older counts and deployment statements are snapshots from their dates.

## C1 runtime ACL work: current batch

C1 remains **open**. Runtime-role provisioning applies the legacy compatibility
grant only to a newly created login or a fresh migration-created placeholder
that carries an explicit first-provision marker. It records the marker as
consumed after that one-time grant. A pre-existing unmarked login is not
widened; later provisioning preserves existing grants, reapplies explicit
boundaries, and leaves relations created since the prior run inaccessible.
Network-disabled disposable PostgreSQL 16 acceptance verifies the original
role-created and re-provision cases; the Standard recovery below exercises the
placeholder-first path. Neither path removes broad grants already held on
existing relations or grants tenant isolation. The API and worker still share
`kokonut_runtime`, and C1 remains open ([acceptance](builds/2026-10-31-recovery/runtime-role-reprovision-guard-disposable.json)).

Migrations 717 and 718 add two reviewed boundaries. Migration
717 makes `chat_intent` read-only to `kokonut_runtime` while preserving runtime
SELECT, Directus access, and migration/maintenance seed upserts. Migration 718
removes direct runtime writes to `price_observation` and routes World Bank,
reference-seed, and manual marketplace-price writes through bounded functions
owned by the dedicated market-data identity. The targeted Standard recovery
for migration 718 is historical; the latest full Standard recovery passes
through migration 722. The migration-717
runtime-boundary reapplication check passed across 192 synthetic relations
([717 evidence](builds/2026-11-01-recovery/chat-intent-runtime-acl-717.json);
[Standard recovery evidence](builds/2026-11-01-recovery/standard-profile-recovery-718-disposable.json)).

Migration 719 additionally removes runtime table/column DML grants from three
catalog-guarded, non-updatable public aggregate views while preserving their
reads and the optional Directus grants. Its focused network-disabled
PostgreSQL 16 acceptance passes apply/replay, output parity, provisioner
reapplication, and a trigger-backed writable-view control; 19 focused app and
policy tests pass. This is a narrow view-ACL cleanup, not tenant isolation or
the full C1 aggregate refresh. See the [migration](../../schemas/postgres/719_runtime_public_aggregate_views_read_only.sql),
[disposable check](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-disposable.json),
and [source checks](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-source-checks.json).

Migration 720 moves the supported thesaurus mutations behind four bounded
functions, preserves the service contract and runtime reads, and prevents
cross-thesaurus keyword parenting. Migration 721 preserves runtime reads while
removing direct runtime writes to the governance category and scope reference
catalogs; Directus grants are unchanged. Both migrations handle Standard's
migration-before-role-bootstrap ordering and pass isolated PostgreSQL
apply/replay, privilege, provisioner, and behavior checks. Standard also has a
default-off notification-delivery child using migration 647's bounded API and
dedicated login. That child receives its DSN and provider credentials without
inheriting shared runtime or unrelated worker database credentials; this does
not separate the API and general worker identities. See the
[thesaurus check](builds/2026-11-01-recovery/runtime-thesaurus-boundary-720-disposable.json),
[governance-catalog check](builds/2026-11-01-recovery/governance-reference-catalogs-721-disposable.json),
[notification-worker check](builds/2026-11-01-recovery/standard-notification-delivery-worker-isolation-647.json),
and [Standard profile guide](standard-profile.md).

Migration 722 preserves runtime SELECT on `schema_migration` while revoking
table and residual column writes; the ordered migration runner remains its
writer. The migration bootstrap marks only a newly created locked runtime
placeholder for its first provisioning, allowing the one-time compatibility
grant to run in Standard's migration-before-role order. Provisioning consumes
that marker so later reapplication cannot widen access. The latest portless,
network-disabled Standard recovery applies all 713 schemas through 722,
provisions and reapplies the role, and passes the ledger-dependent API/worker
health and outage-recovery checks ([migration](../../schemas/postgres/722_runtime_schema_migration_read_only.sql);
[recovery](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json)).
The aggregate source/ACL report and two-tenant probe are still at migration
718; C1 remains open for the remaining runtime writers, shared API/worker login,
external callers, and tenant/RLS review.

External `kokonut_runtime` SQL clients remain unconfirmed and must be reviewed
before persistent rollout. Migration 714 keeps the location-solution creation
retry receipt private from `PUBLIC`, the runtime role, and Directus while
preserving its bounded function-owner column grants. Its focused role/migration
tests and 11-group disposable PostgreSQL 16 apply/replay pass
([evidence](builds/2026-10-31-recovery/runtime-solution-creation-receipt-714-disposable.json)).
Migration 713's climate worker compatibility and plot-only geometry behavior
also pass focused unit and disposable acceptance
([climate evidence](builds/2026-10-31-recovery/climate-worker-713-disposable.json)).
The aggregate C1 report and two-tenant operator-scope probe are now refreshed
through migration 718. A network-disabled, portless native PostgreSQL 16 replay
applied all 709 ordered schema files, loaded no seeds or farm data, passed all
38 synthetic tenant/operator checks, and cleaned up its disposable resources.
The paired source/ACL report records 1,522 public relations, 1,324 with some
effective runtime DML, 937 public tables with runtime DML while RLS is
disabled, 163 migration-revoked relations with matching runtime policy and
zero policy mismatches, zero direct table/column violations within the tested
scoped policy, 214 unprotected DML relations without SQL relation candidates,
and 377 without candidate write sites. These inventory categories overlap and
are not confirmed leaks. A separate SQL review ledger has 38 unresolved
fingerprints (30 legacy-unreviewed and eight reviewed-unresolved); its units
are not directly comparable to relation counts. This is not a full sequence,
function, ownership, column, Directus, worker, or external-consumer audit, and
it does not establish populated-data isolation or persistent deployment
([replay and two-tenant probe](builds/2026-10-31-recovery/native-resource-limited-schema-718-operator-probe-r2.json);
[source/ACL report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-718.json);
[SQL review ledger](runtime-sql-unresolved-write-review.json)).

The first native replay attempt stopped at image inspection before applying
any schema because its requested platform did not match the available local
image tag. It created no Compose resources and touched no candidate or legacy
database; the corrected image reference is recorded in the successful `r2`
evidence above ([failed preflight](builds/2026-10-31-recovery/native-resource-limited-schema-718-operator-probe.json)).
No persistent candidate, legacy, or production database/role was changed.

The latest code-first cohort includes:

| Change | Result and boundary | Evidence |
| --- | --- | --- |
| Migration 721 — governance reference-catalog ACL | Preserves runtime reads on `data_governance_category` and `data_governance_scope`, revokes table/column DML, leaves Directus unchanged, and stays closed after runtime provisioning. | [Disposable apply/replay and ACL acceptance](builds/2026-11-01-recovery/governance-reference-catalogs-721-disposable.json) |
| Migration 720 — bounded thesaurus writers | Preserves the thesaurus service operations through four bounded functions; runtime and PUBLIC receive no direct table DML or PUBLIC function execution. Provisioning grants the full function set only after it exists. | [Disposable apply/replay and behavior acceptance](builds/2026-11-01-recovery/runtime-thesaurus-boundary-720-disposable.json) |
| Standard notification-delivery child identity | Default-off worker child uses migration 647's dedicated login/functions; shared runtime DB credentials and unrelated worker DSNs are filtered from the child. API and general worker still share `kokonut_runtime`. | [Disposable worker acceptance](builds/2026-11-01-recovery/standard-notification-delivery-worker-isolation-647.json); [focused supervisor/profile checks](../../tests/test_kernel_runtime_supervisor.py) |
| Migration 719 — public aggregate-view ACL | Preserves runtime SELECT and optional Directus grants while revoking runtime table/column DML from the three catalog-confirmed non-updatable public attestation/EBF summary views. A separate INSTEAD OF-trigger writable view remains writable as a scope control. This removes unused privileges only; no tenant boundary is established. The aggregate ACL report remains through 718; the Standard replay now passes through 722. | [Disposable ACL acceptance](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-disposable.json); [source checks](builds/2026-11-01-recovery/runtime-public-aggregate-views-719-source-checks.json); [Standard replay](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json) |
| Migration 722 — schema migration ledger | Preserves runtime SELECT needed for fail-closed schema readiness while removing runtime table/column mutation privileges. | [Standard ordered recovery and role reapplication](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json) |
| Runtime-role one-time compatibility grant | The compatibility grant runs for a newly created login or an explicitly marked fresh migration placeholder, then marks the one-time step complete. An existing unmarked role is not widened; reprovisioning preserves grants and reapplies explicit denials. This does not remove broad grants already held or establish tenant isolation. | [Prior role-reprovision acceptance](builds/2026-10-31-recovery/runtime-role-reprovision-guard-disposable.json); [Standard placeholder-first recovery](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json) |
| Migration 718 — isolated global market-data writes | Retires direct runtime mutation of `price_observation`; the dedicated market-data worker uses bounded reference-seed, manual-price, and World Bank functions. Runtime SELECT remains. External runtime callers remain a persistent-rollout review gate. | [Full Standard replay](builds/2026-11-01-recovery/standard-profile-recovery-718-disposable.json); [fresh C1 replay and two-tenant probe](builds/2026-10-31-recovery/native-resource-limited-schema-718-operator-probe-r2.json); [refreshed source/ACL report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-718.json) |
| Migration 717 — read-only chat-intent runtime access | Preserves runtime reads and migration/maintenance upserts while revoking table and column mutation from `kokonut_runtime`; Directus is intentionally unchanged. Runtime provisioner reapplication does not restore DML. External runtime-login clients remain unconfirmed. | [Disposable apply/replay and runtime-boundary checks](builds/2026-11-01-recovery/chat-intent-runtime-acl-717.json) |
| Migration 716 — retire climate v1 worker grant | Keeps the legacy `store_climate_summary` definition for compatibility but removes execution from the worker, runtime, optional Directus, and `PUBLIC`; the active climate worker continues using signed `store_climate_summary_v2`. Disposable PostgreSQL acceptance applies/replays both migrations and exercises all five source writes, retries, failure audit, and location scope. External callers remain a persistent-rollout gate. | [Disposable apply/replay and climate worker checks](builds/2026-11-01-recovery/climate-worker-716-disposable.json) |
| Migration 715 — private location-write receipts | Revokes `PUBLIC`, `kokonut_runtime`, and `kokonut_directus_runtime` table and residual column privileges on 23 audited idempotency receipts while preserving mapped function-owner column grants. Runtime provisioning keeps the relations private. The migration changes no business function or retry behavior; external receipt consumers still require review before persistent rollout. | [Disposable apply/replay and ACL checks](builds/2026-11-01-recovery/runtime-private-location-write-receipts-715-disposable.json) |
| CI #1033 runtime inventory repair | Regenerated the source inventory after a receipt-list insertion shifted line-based SQL call-site IDs. The inventory and unresolved-write ledger now pass locally; this does not establish ACL coverage or close C1. | [CI diagnosis and repair evidence](builds/2026-11-01-recovery/ci-1033-runtime-sql-inventory-repair.json) |
| CI workflow hardening | CI #1037 passed preflight, source checks, and the multi-architecture image gate. Integration failed in the Directus startup/data-seed phase while `seed.sh` applied `542_agent_deterministic_summary_source_reader.sql`; the runner exposed only `psql` exit status 3, so the underlying PostgreSQL diagnostic and root cause remain unconfirmed. CI #1036's workflow-expression error was corrected by moving `runner.temp` to step scope. The current workflow splits preflight, source checks, database integration, and image validation; its aggregate reports failure if any required gate fails. Hosted confirmation of this split workflow remains required on the current branch head. | [Workflow](../../.github/workflows/ci.yml); [preflight](../../scripts/ci-preflight.sh); [runner](../../scripts/run-github-ci.sh); [fast-fail gate](../../scripts/ci-check.sh); [contract tests](../../tests/test_github_ci_workflow.py); [CI #1037](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41264042173) |
| Migration 711 — energy-reading capture | Adds a signed, exact-location Gateway capture with idempotent receipts and private audit reason; retains `recorded` lifecycle; revokes runtime table/column DML while preserving SELECT and the existing Directus/maintenance write boundary. The legacy direct writer now fails closed before DB access. | [Disposable apply/replay and authorization checks](builds/2026-10-31-recovery/energy-reading-capture-711-disposable.json) |
| Remote-sensing due-runner retirement | Legacy `--run-jobs`, `run_due_jobs()`, and `_claim_due_jobs()` paths fail before DB/provider access and direct operators to the default-off signed worker. Create/list/manual-job paths remain; this is not a blanket `remote_sensing_job` ACL revocation. | Focused remote-sensing/scheduler tests recorded in the current batch below. |
| Runtime SQL inventory reconciliation | Regenerated the tracked inventory and review ledger after the due-claim query was retired. The freshness check passes locally; the stale fingerprint was removed from the unresolved candidate set. | `python3 scripts/runtime_sql_inventory.py --check docs/refactor/runtime-sql-inventory.json` |

The user-linked [CI #1014](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41172853331)
was on older head `aa6a01a`: attempt 1 failed after 1h 13m. Its Actions
annotation says “The hosted runner lost communication with the server”; that
message does not identify whether network loss, resource pressure, or another
runner-side condition caused it.
The job-log endpoint does return logs for the later attempt: attempt 2 reached
the BuildKit dependency download, then logged “The operation was canceled” as a
newer PR revision superseded it. This is expected concurrency cancellation,
not GitHub failing to finalize the job.
Later commits on this branch isolate the multi-architecture image gate from
full CI. This separation reduces shared runner contention but does not prove
the cause of #1014. The later current-head [CI #1029](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41233060705)
failed at the fast-fail gate because `runtime-sql-inventory.json` was stale;
that occurrence was repaired locally. The next [CI #1033](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41255043315)
again found a stale inventory after commit `042eebf` inserted a receipt name in
`runtime_role.py`, shifting the inventory's line-based call-site IDs. This batch
regenerates the inventory after the 715 source changes; both the inventory and
unresolved-write ledger pass locally. The #1033 kernel-image job passed and
Security #757 passed, but its full-ci job failed at that inventory gate. Hosted
confirmation on the repair commit is pending. The preceding pushed-head CI
#1032 full-ci runner received a shutdown signal after 704 schema migrations
and 28 seeds applied; no assertion failure was logged. These outcomes are
incomplete hosted validation, not a complete passing run. Current-head
[CI #1035](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41257476642)
on commit `f7864c7` has passed its multi-architecture image gate and Security
#759 passed. Its `full-ci` job remained active in the monolithic `Run the
complete CI gate` step; the live Actions page showed 67 minutes in that step,
with the last visible output at “Installing Python and system build
dependencies.” The old script ran apt index/package commands without useful
progress output for the duration. The Actions page provides step logs; the
workflow-job log download endpoint returned 404 while this job was still
running, whereas completed-run archives were available. The database image
pull had completed before this point. The workflow changes under review here split
source/security/static/contracts, database integration, and multi-architecture
image verification into parallel jobs, skip the hosted-runner apt bootstrap,
require Python wheels, move the release-input lock into preflight, and bound
remaining installs and Compose cleanup. They remain local and have not been
exercised on a hosted run. Run #1033's concrete stale
inventory failure and run #1034's expected superseding-commit cancellation are
separate from #1035's long dependency bootstrap. Another push would cancel
#1035 under the configured PR concurrency group; the workflow changes therefore
await a deliberate push after local validation.
The GitHub workflow-job endpoint returned the logs for earlier completed
attempts: CI #1012 failed its release-input lock check because
`profile-selection.md` changed without a matching lock refresh; CI #1013
failed two fast-fail checks because the report-generator source and helper
scope inventories were stale. Those failures are distinct from #1014's runner
communication annotation and the current #1035's long dependency bootstrap.
The earlier outcomes are recorded here:
([#1029 evidence](builds/2026-10-31-recovery/ci-1029-runtime-sql-inventory-fix.json);
[#1032 evidence](builds/2026-10-31-recovery/ci-1032-hosted-runner-shutdown.json);
[#1033 diagnosis](builds/2026-11-01-recovery/ci-1033-runtime-sql-inventory-repair.json)).

Standard-profile disposable recovery is accepted through migration 722 for
the controls recorded above. The latest full replay used one captured SQL
snapshot for both API and worker image builds and applied 713/713 schema files.
This does not establish candidate or production rollout, provider recovery,
scale, 24-hour endurance, or physical-device acceptance. No candidate, legacy,
or production database or role was changed. Broader caller reconciliation,
external importer ownership, Directus API parity, tenant/RLS, populated-data
parity, and reviewed persistent rollout remain open. The two-tenant
operator-scope probe and C1 source/ACL aggregate remain at migration 718.

## Human and operational gates

The owner selected self-hosted ZITADEL and `auth.kokonut.network`; this is a
provider decision, not live OIDC acceptance. The owner identified SMTP at
`smtp.maileroo.com` (TLS 465 or STARTTLS 587/2525), the sender/service account,
and R2 buckets `kokonut-production` and `kokonut-backups`. Credentials must
remain in SOPS, and live delivery, R2 inventory/restore, and on-call ownership
acceptance are still separate gates.

Other open gates recorded in the operational trackers include:

- live authenticated browser login/session/logout and operator provisioning;
- populated-data/report/dashboard parity and downstream access boundaries;
- Directus effective-role/extension parity while Directus remains optional;
- remaining runtime write and read/RLS boundaries plus caller/worker context;
- external provider, scheduler, alert, backup/restore, and long-duration recovery;
- policy owners for configurable retention and legal holds across USA and the
  Dominican Republic;
- physical Raspberry Pi/power behavior when a device is available;
- scale/replica failover, public ingress and trusted-proxy acceptance;
- reviewed seed/data migration and eventual cutover with rollback evidence.

The owner has approved a 24-hour recovery objective. It remains a target until
measured recovery and restore rehearsal pass for the selected deployment.

Retention caveat: the source DDL historically assigned fixed one- and two-year
ClickHouse TTLs. Current DDL has none; the `011_retention_policy_no_prune.sql`
manifest is applied by `scripts/apply-clickhouse-retention.py`, which removes a
table TTL only when metadata says one is present. The pinned-image disposable
acceptance passes fresh-bootstrap skip, removal of eight simulated TTLs, repeat
application, and old-row survival after a merge
([evidence](builds/2026-10-30-recovery/clickhouse-retention-no-prune-disposable.json)). Existing analytics targets must still run and verify this helper before ingestion. Field Collector migration 358
still has a fixed 30-day expiry for unattached media; that is a known
implementation gap, not an approved retention rule, and must be made
configurable before production acceptance.
Retention and legal-hold periods are to be configurable; no hardcoded schedule
should be used as a substitute for the missing policy configuration and owner
approval.

## Recommended execution sequence

1. **Source/code cohort:** audit a capability and its consumers; implement the
   Gateway/service/console contract and maintain the legacy path until parity
   is accepted. Keep domain behavior, consent, human review, and existing
   scopes intact.
2. **Migration design:** add ordered, checksummed migrations only after the
   source contract is reviewed. Prefer additive functions/receipts/roles and
   precise grants. Do not apply to the candidate as part of source work.
3. **Grouped local verification:** run focused unit/route/SDK/console checks,
   Ruff and compilation, migration validation, then network-disabled
   disposable PostgreSQL/PostGIS checks. Exercise exact scopes, replay,
   rollback, ACLs, and realistic synthetic fixtures.
4. **Integration verification:** run the full ordered native schema replay,
   ARM64/QEMU replay where supported, operator-scope probe, runtime/source/SQL
   inventory checks, capability/matrix checks, and CI-equivalent selections.
   Refresh evidence with the exact HEAD and test count.
5. **Candidate rollout:** take and restore-rehearse an encrypted checkpoint,
   apply the ordered migration to only the named local candidate, rebuild the
   candidate app, and verify routes/health. Keep rollback and candidate state
   evidence adjacent to the change.
6. **External and human acceptance:** configure real identity/providers,
   select retained reports and owners, test ingress/transport, retention,
   restore and operational recovery. Keep secrets out of chat and repository.
7. **Release/cutover:** merge through the protected `develop` flow; promote to
   `main` through a reviewed release PR. Retire legacy services or writers only
   after capability parity, rollback, and accountable-owner acceptance.

## Supporting records

- [Implementation-plan phase alignment](implementation-plan-alignment.md)
- [Capability matrix](capability-matrix.md)
- [Batched acceptance checklist](batches.md)
- [Code-first execution queue](todo-kernel-refactor.md)
- [Historical progress ledger](progress.md)
- [C1 runtime ACL closure plan](c1-runtime-acl-closure-plan.md)
- [Architecture decisions](decisions.md)
- [Current profile command planner](profile-selection.md)
- [Candidate deployment procedure](kernel-candidate.md)
- [Migration and rollout procedure](../migrations.md)
- [Evidence archive](builds/)
