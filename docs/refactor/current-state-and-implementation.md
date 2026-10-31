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
| **standard** | PostgreSQL plus distinct API and durable-worker roles, with loopback-bound Caddy ingress by default. `--no-proxy` selects a separately managed ingress. | This is the intended general-purpose starting point for an operational deployment; role provisioning, migrations, monitoring, live identity, backup/restore, and recovery acceptance still gate use. The default Caddy listener is local TLS, not public production ingress. |
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

C1 is **not closed**. The latest complete source/ACL report is through
migration 703: it found 148 declared runtime boundaries, zero policy
mismatches or direct table/column privilege violations, 1,367 public relations
with some DML, and 979 tables with runtime DML while RLS is disabled. Migration
704 adds a runtime read-only boundary, so those numbers are a dated 703
snapshot, not current post-704 totals. Migration 705 adds a separate Directus
reprovisioning policy and does not change runtime counts. These are privilege-
reach and audit counts, not counts of confirmed data exposure ([703 report](builds/2026-10-30-recovery/runtime-privilege-callsite-report-703.json)).

This local batch records migrations 700–705 and scoped operations:

| Migration | Added operation | Local acceptance recorded |
| --- | --- | --- |
| 700 | Location-scoped governance-tension lifecycle actions. The legacy network/organization scopes remain available. | Disposable PostgreSQL 16 apply/replay and synthetic authorization/lifecycle checks ([evidence](builds/2026-10-30-recovery/governance-tension-location-actions-700-disposable.json)). |
| 701 | Location-scoped extension peer-network creation and progress updates, with private receipts and isolated writer owner. | Disposable PostgreSQL 16 checks for grant/context, retry, identity-minimized result and ACL behavior ([evidence](builds/2026-10-30-recovery/extension-learning-writes-701-disposable.json)). |
| 702 | Record-only location landscape capture (habitat, corridor, hedgerow, buffer check, biodiversity assessment). | Disposable PostGIS/PostgreSQL 16 checks for location binding, geometry, defaults, lifecycle and role grants ([evidence](builds/2026-10-30-recovery/landscape-capture-702-disposable.json)). |
| 703 | Metric draft calculation/write, bounded list and separate human verification functions. | Disposable PostgreSQL 16 checks for replay, grant, location scope, draft lifecycle, idempotency, self-review denial and ACL behavior ([evidence](builds/2026-10-30-recovery/metric-value-kernel-disposable.json)). |
| 704 | Keep `living_wage_benchmark` readable to runtime while denying runtime table/column writes; preserve separate maintenance authority. | Focused native and ARM64/QEMU PostgreSQL checks for apply/replay, SELECT, DML denial, provisioner reapplication, and maintenance-role writes ([evidence](builds/2026-10-31-recovery/living-wage-benchmark-704-disposable.json)). External importer use through the runtime login is unconfirmed, so persistent rollout remains gated. |
| 705 | Record migration-owned Directus relation read-only/no-access exceptions and reapply them after the optional Directus role's compatibility grants. | Migration replay and disposable PostgreSQL role acceptance cover 147 relation policies, stale table/column/sequence grant removal, and preserved compatibility grants ([evidence](builds/2026-10-31-recovery/directus-relation-policy-705-disposable.json)). This protects reprovisioning; it does not establish API/extension parity or tenant isolation. |

The 700–703 functions use isolated owners. The runtime-role provisioner now
tracks those owners/functions, revokes public function execution, and refuses
to use the owners as application logins. The legacy metric CLI and existing
tension, extension and landscape paths remain in place; this additive slice
does not revoke legacy table DML or establish universal tenant isolation.

The focused checkers use synthetic records and disposable databases. They do
not apply these migrations to the candidate, legacy, or production database.
The grouped focused Gateway, console, source/ACL, migration, and replay-parser
selection passes 216 tests ([evidence](builds/2026-10-30-recovery/c1-700-703-focused-tests.json)).
The prior full ordered replays through 703 passed 694/694 migrations and 38
two-tenant operator checks on native and ARM64/QEMU
([native](builds/2026-10-30-recovery/kernel-c1-full-schema-703-native-r2.json),
[ARM64/QEMU](builds/2026-10-30-recovery/kernel-c1-full-schema-703-arm64-r1.json)).
The new native replay through 705 passes 696/696 migrations and all 38 checks;
its synthetic ACL probe reports 978 public tables with runtime DML while RLS
is disabled ([evidence](builds/2026-10-31-recovery/kernel-c1-full-schema-705-native.json)). This is a privilege-reach measure, not a confirmed exposure count. The source/ACL policy report remains the 703 snapshot; its 148-boundary aggregate is not regenerated after 704. A full ARM64/QEMU replay through 705 was stopped after 583.6 seconds at migration 116 (111/696 migrations); no migration error was observed and disposable cleanup passed ([interrupted attempt](builds/2026-10-31-recovery/kernel-c1-full-schema-705-arm64-qemu.json)). The prior complete QEMU replay through 703 and focused ARM64 checks for 704/705 remain evidence; no physical Raspberry Pi acceptance is claimed.
This additive source batch leaves legacy writers available, does not revoke
their direct DML, and does not establish universal tenant isolation. Broader
C1 reconciliation and separately gated candidate rollout remain required.

One SQL provenance limit remains in migration 703: the metric draft function
checks that `source_record_ids` is bounded and contains no NULLs, but it does
not prove each polymorphic ID belongs to the requested location. The current
Gateway derives this array from the location-scoped calculator; the SQL
function alone does not guarantee that relationship. Add a source-type
contract before making a stronger provenance claim or widening the caller
surface ([existing source-ID review](todo-kernel-refactor.md)).

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
