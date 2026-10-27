# Kokonut Kernel refactor TODO

Updated: 26 October 2026. This is the active cross-phase work queue for the
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
  capability records. Local commits: `020a5279`, `be1c2c2e`, `968a49fc`.
- [x] Add relation-level runtime ACL/default-ACL capture to the isolated probe
  and a source-callsite/revoke join at
  [`scripts/runtime-privilege-callsite-report.py`](../../scripts/runtime-privilege-callsite-report.py).
  The detailed replay and source join completed: 1,101 unprotected base tables
  have table-level DML, including 75 with a matching historical runtime DML
  revoke; 334 have no static candidate callsite. No database privileges were
  changed by the inventory.
- [x] Implement the source-declared C1 runtime ACL repair in role provisioning:
  after the compatibility grant, deny direct runtime access to all 64 tables
  whose ordered migrations revoke `ALL`, and deny write privileges on the 11
  tables whose migrations revoke only mutations. Existing reads remain for the
  write-only group. The provisioner verifies the resulting table and column
  ACLs. This code has not yet passed focused disposable-role acceptance and
  was not rolled out.

## Code work to continue without owner input

Work in this order. Each item is a bounded implementation batch, not a claim
that its full source-plan phase is complete.

- [ ] **C1 — Replace broad runtime database privileges with scoped contracts.**
  Inventory the 1,101 relations and actual application/worker/Directus
  callsites, group them by capability and identity, then revoke access only in
  reviewed slices with bounded functions or exact grants. Preserve a rollback
  path and keep RLS/tenant claims scoped to what is actually enforced. First
  generate the relation-level join with
  `scripts/runtime-privilege-callsite-report.py`; review explicit revokes that
  overlap effective DML and source callsites that the heuristic inventory
  cannot classify before making any ACL change. The 75 migration-declared
  runtime revokes are now restored by the bootstrap correction; focused
  acceptance is still open. The remaining broad DML grants require separate
  callsite, worker-identity and Directus review before changing them.
  Sources: [runtime boundary](batches.md#L2826),
  [agent boundary](batches.md#L3652),
  [full-schema probe](builds/2026-10-26-recovery/sprint-full-schema-operator-scope.json).
- [ ] **C2 — Finish Gateway and SDK contract parity.** Audit registered routes,
  auth/action/scope policy, pagination, error models and SDK behavior; close
  source-verifiable gaps without exposing generic CRUD or weakening default
  denial. Sources: [API/SDK gates](batches.md#L3226),
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
- [ ] **C7 — Finish software-only ARM64 and recovery evidence.** Run current
  source/profile builds and constrained-resource checks, then rehearse backup
  and restore with synthetic data. Record emulator, CPU/memory limits, source
  and image identity. This closes code gates only; no Raspberry Pi is available.
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
