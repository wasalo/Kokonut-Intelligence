# Kokonut Kernel refactor: current state and implementation guide

**Status snapshot:** 3 November 2026
**Purpose:** canonical overview of the target architecture, current implementation evidence, deployment profiles, open gates, and execution order.
**Design source:** the owner-provided [Architecture implementation plan](implementation-plan-alignment.md).

This guide is the single current-status entry point for the refactor. It
consolidates the decisions and readiness summary; the linked matrix, checklist,
plans, and evidence remain detailed supporting records. The [refactor README](README.md)
explains which record to use for each question. This guide supersedes older
"latest" statements in dated logs. The progress ledger is historical and
append-only.

## How to interpret status

The repository contains both a legacy Compose integration stack and an
isolated Kernel candidate. Source implementation, focused checks, disposable
acceptance, candidate rollout, production acceptance, and human approval are
separate states.

| Evidence label | Meaning |
| --- | --- |
| **Implemented** | Source code or an ordered migration exists in this checkout. |
| **Focused checks pass** | The named unit, contract, lint, or static checks passed; the evidence defines their scope. |
| **Disposable acceptance passes** | The named behavior passed against synthetic state in an isolated disposable service/database. |
| **Candidate applied** | A migration was applied only to the explicitly selected local Kernel candidate, with checkpoint and rollout evidence. |
| **Production accepted** | The production deployment, external integrations, operating ownership, and release gates passed. |
| **Human gate open** | A product owner, provider operator, reviewer, or physical-device acceptance is still required. |

Never infer a later label from an earlier one. In particular, a disposable
replay is not a candidate migration, and candidate health is not production
readiness.

## Target architecture

Kokonut owns its domain policy, governed lifecycle, and capability contracts.
PostgreSQL/PostGIS is the canonical operational schema and durable state. The
Kokonut Gateway and Python domain services are the native application layer.
Optional infrastructure must stay replaceable without silently removing
capability.

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

- PostgreSQL holds governed operational records. Analytics and cached
  projections are rebuildable and are not operational truth.
- Preserve `draft → submitted → verified → published`; use `rejected` for
  rework/exception. Payment, attestation, execution, and revocation use their
  own domain fields.
- Human review remains in control of verification, publication, sensitive
  execution, participant identity, and legal disposition.
- Keep private evidence off-chain by default. Web3 is a proof and coordination
  layer, not the operational source of truth.
- Migrations are ordered and checksummed. Fix deployed behavior with a forward
  migration; never rewrite an applied migration.
- Retire an old writer or dependency only after replacement parity,
  authorization, retry/recovery, lineage, rollback, and owner gates pass.

## Deployment profiles

The profile planner is [`scripts/kernel-profile.py`](../../scripts/kernel-profile.py).
It composes candidate manifests and prints proposed commands. It does not
start Docker, read secrets, apply migrations, seed data, or perform cutover.
Use an explicit Compose project and inspect `config` before executing a
printed command. The default `docker-compose.yml` remains the legacy stack.

| Profile | Composition | Current readiness |
| --- | --- | --- |
| **minimal** | Private PostgreSQL/PostGIS and combined Kernel app/API with enabled worker processes. | Smallest candidate shape. End-to-end capability parity, live identity, recovery, and operational acceptance remain open. |
| **core** | Minimal app built from the reduced, hash-locked dependency set; optional Web3, export, and local-media packages are selected explicitly. | Packaging choice, not a different data model. The OIDC app overlay is incompatible with this reduced image. |
| **edge** | Minimal plus encrypted local media and edge resource settings; MQTT and HTTP sensors are separate overlays. | No physical Raspberry Pi acceptance. ARM64/QEMU is portability evidence only. |
| **standard** | PostgreSQL, separate API and durable-worker services using the same `kokonut_runtime` login, and loopback-bound Caddy ingress by default. `--no-proxy` selects external ingress; `--edge` composes Edge settings. `release-up` prints a digest-pinned, no-build start command. | Portless, network-disabled disposable first-install/recovery passed through migration 746. Native/ARM64 operator probes remain through 745; see the current acceptance below. This is not candidate or production deployment. |
| **analytics** | Minimal plus private ClickHouse projection; `--separate-workers` composes Standard API/worker services with the runtime-role overlay and explicit migration/bootstrap actions. | Report parity, projection rebuild/outage recovery, and downstream tenant-safe access remain open. Metabase is not required. |
| **scale** | Not accepted; the planner rejects this profile. | Replica/failover, shared budgets, sizing, concurrency, and recovery acceptance remain open. |

Caddy is the Standard default but remains optional for other profiles. Other
selectable overlays include ZITADEL/OIDC, gRPC, MQTT, HTTP sensor intake,
Directus compatibility, sensor-anomaly ML, and Web3/export/local media. Optional
services have separate configuration and acceptance requirements. No legacy
service or data volume is implicitly adopted by a Kernel candidate.

Standard's API and general worker are separate services but **still share the
`kokonut_runtime` database login**. Dedicated identities exist for selected
isolated workers; they do not close the API/general-worker C1 boundary. The
candidate database is private and the app defaults to loopback. Do not publish
the PostgreSQL host port to work around legacy-stack conflicts; use Compose
service names or a deliberately reviewed local override.

The owner plans `hub.kokonut.network` for the application and
`auth.kokonut.network` for self-hosted ZITADEL. Public DNS/TLS, firewall,
trusted-proxy, secure-cookie, and authenticated-browser acceptance are open.
`standard --no-proxy --oidc` requires a separately managed HTTPS origin.
`release-up` requires reviewed digest-pinned images and rejects optional
overlays without an immutable-image contract. Registry publication has not
been performed.

## Current implementation and evidence

### Database image build policy follow-up

The finalization branch replaces Debian's dated snapshot download dependency
with maintained signed bookworm repositories. The PostgreSQL base digest and
exact PostGIS selections remain pinned; Debian transitive versions may change
between base-image builds. Installed inventories and architecture differences
remain checked. Runtime release reproducibility requires the tested immutable
image digest, rather than rebuilding old Debian package URLs. This source change
does not constitute a published image, candidate migration, or release acceptance.
See the [finalization work queue](finalization-plan.md) for scope and remaining gates.
The local AMD64 and ARM64/QEMU build and OCI inventory acceptance passed
(229/228 packages, only the existing documented `libquadmath0` difference),
along with 134 profile/release tests. See the
[5 November build evidence](builds/2026-11-05-recovery/maintained-debian-postgis-multiarch.json).
Hosted CI, publication, database runtime/restore, and candidate acceptance remain open.

### Capability and phase snapshot

The tracked matrix has **67 capabilities**: 24 baseline-retained, 7 deployed,
and 36 prepared. These are implementation classifications, not a completion
percentage or production-readiness measure. Prepared capabilities may still
await live providers, populated-data parity, tenant/RLS boundaries, rollout,
or owner acceptance.

Work is concentrated on Phase 7, replacing Directus as the primary application
API route by route, with continuing prerequisites in Phases 0, 1, 2, 3, 4, 5,
6, and 8. No whole phase is complete because one migration, route, or profile
check passed.

| Source-plan phase | Current direction | Main open evidence |
| --- | --- | --- |
| **0 — Baseline and capability freeze** | Inventory, capability matrix, owner/location decisions, and source audits exist. | Reconcile remaining data owners, external clients, live providers/jobs, populated-data lineage, and recovery/retention ownership. |
| **1 — Ports and adapters** | Typed settings and provider boundaries exist in selected paths. | Prove optional dependencies can be absent across runtime imports, configuration, and workflows. |
| **2 — Minimal PostgreSQL runtime** | Minimal profile, Gateway, and native workers exist. | End-to-end governed workflows, mobile sync, scheduled retries, accepted-work recovery, rollout, and backup restore. |
| **3 — Optional analytics** | PostgreSQL report contracts and selected ClickHouse projections exist. | Retained report/dashboard parity, rebuild/outage recovery, and safe downstream access. |
| **4 — Owned scheduler** | Durable scheduler and worker state exist for selected jobs. | Reconcile all active schedules/providers; transfer one at a time with output parity and recovery proof. |
| **5 — Optional Redis** | Replaceable cache/rate-limit paths exist. | Demonstrate minimal operation without Redis and durable behavior under multi-replica failure. |
| **6 — Optional edges** | Compose overlays and significant transport contracts exist. | HTTPS/trusted proxy, MQTT/HTTP parity, gRPC authorization, and external ingress acceptance. |
| **7 — Native Gateway** | Active route-by-route migration; selected strict APIs and operator console exist. | Field, permission, lifecycle, consent, audit, export, SDK, reviewer, and Directus compatibility parity. |
| **8 — ARM64, scale, and retirement** | ARM64 builds and emulated database/runtime checks exist. | Physical Pi acceptance when hardware is available, resource/recovery measurements, scale, and reviewed cutover. |

### Current Standard and C1 snapshot — migrations 742–746

Native PostgreSQL 16 and ARM64/QEMU replays applied all **736 ordered schema
migrations through 745**, with zero failures or pending entries, no seeds, and a
passing 47-check synthetic operator/two-tenant probe. The 3 November portless,
network-disabled Standard recovery applied **737 schemas through migration 746**
from one captured snapshot shared by the API and worker images. Runtime-role
bootstrap/reapplication, optional Directus checks, API/worker/proxy health,
database-outage and stalled-child recovery, and clean shutdown with zero active
leases passed. The 745 native/ARM64 operator probes remain the latest full
47-check probes; they have not been rerun through 746. Evidence:

- [Native replay and operator probe through 745](builds/2026-11-01-recovery/native-current-schema-745-operator-probe.json)
- [ARM64/QEMU replay and operator probe through 745](builds/2026-11-01-recovery/arm64-qemu-current-schema-745-operator-probe.json)
- [Standard first-install/recovery through 745](builds/2026-11-01-recovery/standard-profile-recovery-745-disposable.json)
- [2 November Standard recovery rerun through 745](builds/2026-11-02-recovery/standard-profile-recovery-745-disposable.json)
- [3 November Standard recovery through 746](builds/2026-11-03-recovery/standard-profile-recovery-746-disposable.json)
- [Migration-746 ClickHouse outbox operator acceptance](builds/2026-11-03-recovery/clickhouse-outbox-operator-746-disposable.json)
- [Farm-activity operations acceptance: migrations 359/404, synthetic PostgreSQL 16](builds/2026-11-02-recovery/gateway-farm-activity-operations-disposable.json)
- [Retention/legal-hold acceptance: migrations 401/402, synthetic PostgreSQL 16](builds/2026-11-02-recovery/data-retention-policy-disposable.json)
- [Local ZITADEL startup/discovery smoke (no browser login)](builds/2026-11-02-recovery/zitadel-local-startup-smoke.json)
- [Standard profile runbook](standard-profile.md)

The 3 November Standard run used a dirty checkout at source revision
`9c1bd501f8c7e2928b777926d55c78c6c9b559b4`; its schema snapshot SHA-256 is
`3757f48b2184cd83bdd33ea71720a0733a5422c6e8abd9040b1e7830bad6c0f0`. The
migration-746 checker separately verifies the dedicated operator login,
DBA-only capability grant/revoke audit, bounded replay/resolve/discard functions,
and removal of direct runtime transitions. No live operator capability was
granted, and no candidate, legacy, or production database/role was changed.

The farm-activity fixture verifies bounded create/edit/submit/review/publish,
wrong-location/task denial, and append-only audit behavior. It does not exercise
live OIDC, browser Collector sync, or populated farm-data parity. The retention
fixture validates migrations 401/402 and legal-hold/scope behavior; separate
unit coverage pins the dynamic soft-delete query; fingerprint
`4aca5b9e9e98337e9c9ba48c612a1b5e5d3bc5b39dec2c69a8f07e7feb0a2b3d` is
`reviewed_unresolved` for source semantics only, with owner/ACL review still
open. No grants are approved by this evidence.

Migrations 742–745 establish narrowly scoped boundaries: `readiness_dimension`
is a global curated catalog (owner-confirmed read-only for runtime and
optional Directus; location weights remain in `readiness_location_weight`),
and `v_public_ebf_scorecard`, `v_public_metric_summary`, and
`v_public_wellbeing_metric_summary` retain reads while unnecessary mutation
privileges are removed. Migration/maintenance paths remain as documented;
these changes do not alter base-table writers or RLS. `quality_grade` remains a
global curated catalog, with no known external writers reported by the owner;
that report is not an exhaustive client audit.

Migration 746 adds capability-gated ClickHouse outbox dead-letter routes for
read, replay, resolve, and discard. The Gateway checks distinct global
capabilities through the operator-auth identity; an optional dedicated action
login invokes bounded security-definer functions and has no direct table access.
The shared runtime retains enqueue/read access and `updated_at` only, while the
legacy CLI mutation flags fail closed before database access. The action
password is routed to the API child and bootstrap, not the general worker. The
disposable checks did not grant any live operator capability and do not establish
tenant scope for these explicitly global actions. The pending PR #73 follow-up
reapplies the outbox write boundary after runtime compatibility grants, forwards
the optional operator password, and scopes its database CONNECT grant. Its
clean-bootstrap check uses and removes a separate network-disabled Compose
project; GitHub integration validation remains pending.

The **906 public-schema table** count below comes from the migration-745 native
source/ACL report; it was not regenerated through migration 746. It measures
effective runtime table-level `INSERT`, `UPDATE`, or `DELETE` while RLS is
disabled; it is privilege reach, not confirmed writes, data leaks, or Internet
exposure. C1 remains open for the rest of the writer/caller set,
shared API/worker identity, external consumers and Directus API permissions,
tenant/RLS boundaries, populated-data parity, and persistent-target rollout.
The BMC CLI persistence commands are retired and its health score is now
calculated read-only; direct Python write helpers and shared-runtime BMC
privileges remain unchanged for separate caller/ACL review.
See the [current C1 closure plan](c1-runtime-acl-closure-plan.md) and
[migration-745 source/ACL report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-745.json).

Here **DML** means data modification (`INSERT`, `UPDATE`, or `DELETE`),
**ACL** means PostgreSQL `GRANT`/`REVOKE` privileges, and **RLS** means
row-level security policies that filter which rows a role can see or modify.
“Public schema” names a PostgreSQL schema; it does not mean the records are
publicly available on the Internet. The earlier 915 figure was a historical
privilege-reach count and did not mean 915 confirmed data leaks.

These are short disposable checks using synthetic state. They do not establish
candidate or production rollout, live identity/provider delivery, public
ingress, backup restoration, 24-hour recovery, scale, populated-data parity,
or physical Raspberry Pi behavior. QEMU is software-portability evidence only.
No candidate, legacy, or production database/role was changed by these replay
checks.

The latest tracker totals are **2,264 complete / 43 open** in
[`batches.md`](batches.md) and **836 checked / 39 open** in the active
[`todo-kernel-refactor.md`](todo-kernel-refactor.md). The matrix remains at the
67 classifications above.

## Decisions and remaining human/operational gates

Recorded owner decisions:

- The application is planned for `hub.kokonut.network`; self-hosted ZITADEL
  for `auth.kokonut.network`. The owner identified `hello@kokonut.network` as
  the operator account. Do not put credentials in chat; use SOPS.
- Standard retained reporting should initially port the legacy report set.
  Intended audiences include liquidity providers, DAO and guild members, and
  the wider community across the farm lifecycle. Final report selection,
  audience/scope per report, measures, and reference fixtures still need
  review.
- Provider capability should remain comparable to the legacy platform, but
  current activation, cadence, inputs, idempotency, overlap, recovery, and
  accountable operators still need reconciliation.
- The owner selected SMTP at `smtp.maileroo.com` (TLS 465 or STARTTLS 587/2525)
  and identified Cloudflare R2 buckets `kokonut-production` and
  `kokonut-backups`. Credentials belong in SOPS. Live delivery, bucket-scoped
  access, object inventory, restore rehearsal, routing, and on-call ownership
  remain open.
- Retention and legal-hold periods must be configurable and dynamic; no fixed
  durations are approved. Jurisdictions identified are the USA and Dominican
  Republic. Policy ownership and legal review remain open.
- The recovery objective is 24 hours. It is a target, not measured acceptance.
- The owner has no Raspberry Pi available; only code and ARM64/QEMU checks can
  be performed for now. Do not claim physical device, thermal, storage,
  power-loss, or recovery acceptance.
- Kokonut Network is the exclusive owner of Kokonut Genesis, Kokonut Seeds,
  Kokonut Adelphi, Kokonut Terra Viva, and Kokonut V1. Owner mapping for other
  populated/legacy locations and operator affiliations still requires
  reconciliation.

Other remaining operational gates include live authenticated browser
login/session/logout and grant provisioning; mobile live sync and downstream
disposition; effective Directus role/field/row and extension parity while it
remains optional; external-client ownership; populated report/provider parity;
external ingress and trusted-proxy acceptance; dependency retirement; reviewed
seed/data migration; and cutover with checkpoint, rollback, and release
evidence. The exact open list is maintained in [`batches.md`](batches.md).

## Recommended execution order

1. **Code/source cohort:** audit one capability and its callers; implement the
   native Gateway/service/console contract while preserving behavior and
   review boundaries.
2. **Migration design:** add ordered migrations only after the source contract
   is understood. Use bounded roles/functions and precise grants; preserve
   rollback and replay behavior.
3. **Grouped local verification:** focused unit/route/SDK/console checks, Ruff
   and compilation, migration validation, then network-disabled disposable
   PostgreSQL/PostGIS acceptance with synthetic data.
4. **Integration verification:** native and ARM64/QEMU migration replay,
   operator-scope checks, runtime/source/SQL inventory, capability validation,
   and CI-equivalent checks. Record exact revisions and evidence scope.
5. **Candidate rollout:** create and restore-rehearse an encrypted checkpoint,
   apply migrations only to the named candidate, rebuild it, and verify
   health/routes. Keep rollback evidence adjacent to the rollout.
6. **External/human acceptance:** configure identity and providers, agree
   report owners and retention policy, test transports/ingress, backup restore,
   and sustained recovery.
7. **Release/cutover:** merge through protected `develop`; promote with a
   reviewed release PR to `main`. Retire legacy services only after parity,
   rollback, and owner acceptance.

## Refactor document map

| Question | Current supporting record |
| --- | --- |
| Which source plan phases map to the repository? | [Implementation-plan alignment](implementation-plan-alignment.md) |
| What profile should I select and what does its planner print? | [Profile selection](profile-selection.md), [candidate procedure](kernel-candidate.md) |
| What is the Standard release/recovery procedure? | [Standard profile guide](standard-profile.md) |
| What is the detailed C1 access-control status? | [C1 closure plan](c1-runtime-acl-closure-plan.md) |
| Which capability is implemented or prepared? | [Capability matrix](capability-matrix.md) |
| What acceptance work remains and what is next? | [Batches checklist](batches.md), [TODO queue](todo-kernel-refactor.md) |
| What changed over time? | [Append-only progress ledger](progress.md) |
| Where are run results? | The linked dated JSON artifacts in [`builds/`](builds/) |
| Which architecture choices were recorded? | [Architecture decisions](decisions.md) |

Update the current guide, matrix, checklist, and TODO when implementation
status changes. Append dated facts to the progress ledger. Preserve old
evidence and label it historical when newer runs supersede it.
