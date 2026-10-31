# Kokonut Kernel refactor: current state and implementation guide

**Status snapshot: 31 October 2026**
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
| **standard** | PostgreSQL plus distinct API and durable-worker roles, with loopback-bound Caddy ingress by default. `--no-proxy` selects a separately managed ingress. Both processes require a dedicated non-owner, non-privileged login before starting children; the worker also has a read-only PostgreSQL probe for stale leases, old eligible due backlog, and supervisor/child-process liveness. | A network-disabled disposable acceptance applies all 703 schema files through migration 712, provisions the runtime role, verifies bounded gateway rate-limit ACLs and consume/cleanup behavior, confirms API/worker identities, and passes outage recovery and cleanup ([evidence](builds/2026-10-31-recovery/standard-profile-rate-limit-712-disposable.json)). Candidate rollout, live identity, populated lease/provider recovery, external alert routing, public ingress, backup/restore, scale, prolonged recovery, and physical-device acceptance remain open. The probe reports aggregate counts and ages without IDs or payloads; it detects exited children but not an alive-but-hung child. The default Caddy listener is local TLS, not public production ingress. |
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
for exact selection and operational constraints.

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

C1 remains **open**. A network-disabled, portless native PostgreSQL 16 replay
through migration 711 applied all 702 ordered schema files and passed the
synthetic two-tenant operator-scope probe. The refreshed source/ACL report
records 161 migration-owned runtime boundaries, zero policy mismatches, zero
direct table/column privilege violations, 1,356 relations with effective
runtime DML, and 968 tables with runtime DML while RLS is disabled. It lists
40 unresolved write candidates. These are privilege-reach and source-review
counts, not confirmed leaks, tenant isolation, or universal sequence/function,
ownership, column, Directus, or external-consumer safety
([native replay and probe](builds/2026-10-31-recovery/native-schema-711-operator-probe.json);
[source/ACL report](builds/2026-10-31-recovery/runtime-privilege-callsite-report-711.json)).

The latest code-first cohort includes:

| Change | Result and boundary | Evidence |
| --- | --- | --- |
| Migration 711 — energy-reading capture | Adds a signed, exact-location Gateway capture with idempotent receipts and private audit reason; retains `recorded` lifecycle; revokes runtime table/column DML while preserving SELECT and the existing Directus/maintenance write boundary. The legacy direct writer now fails closed before DB access. | [Disposable apply/replay and authorization checks](builds/2026-10-31-recovery/energy-reading-capture-711-disposable.json) |
| Remote-sensing due-runner retirement | Legacy `--run-jobs`, `run_due_jobs()`, and `_claim_due_jobs()` paths fail before DB/provider access and direct operators to the default-off signed worker. Create/list/manual-job paths remain; this is not a blanket `remote_sensing_job` ACL revocation. | Focused remote-sensing/scheduler tests recorded in the current batch below. |
| Runtime SQL inventory reconciliation | Regenerated the tracked inventory and review ledger after the due-claim query was retired. The freshness check passes locally; the stale fingerprint was removed from the unresolved candidate set. | `python3 scripts/runtime_sql_inventory.py --check docs/refactor/runtime-sql-inventory.json` |

The user-linked [CI #1014](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41172853331)
was on older head `aa6a01a`: attempt 1 failed, but GitHub has expired its job
log; attempt 2 was cancelled during Buildx dependency installation when a newer
run superseded it. Its original failure cause cannot be established. Later
commits on this branch add an isolated multi-architecture Buildx cache and run
the image gate in parallel with full CI, but those changes do not prove the
cause of #1014. The later current-head [CI #1029](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41233060705)
failed at the fast-fail gate because `runtime-sql-inventory.json` was stale.
That specific failure is repaired in this worktree and the inventory check now
passes; hosted verification on the next pushed head remains open
([diagnosis](builds/2026-10-31-recovery/ci-1029-runtime-sql-inventory-fix.json)).

Standard-profile disposable recovery is accepted through migration 712 for the
specific controls recorded above. This does not establish candidate or
production rollout, provider recovery, scale, 24-hour endurance, or physical
device acceptance. No candidate, legacy, or production database or role was
changed. Broader caller reconciliation, external importer ownership, Directus
API parity, tenant/RLS, populated-data parity, and reviewed persistent rollout
remain open.

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
