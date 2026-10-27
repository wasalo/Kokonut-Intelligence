# Next sprint: authenticated farm workflow and recovery

**Planning baseline:** `develop` at `ef29f193992717653251b325e99ae24afc62ccef`,
26 October 2026 local time. This is a plan, not an acceptance record.

## Sprint outcome

Demonstrate one repeatable, end-to-end farm workflow on an isolated Kernel:
an operator signs in through the selected self-hosted ZITADEL provider, enrolls
a location-bound Field Collector device, captures and syncs a synthetic farm
activity, and authorized people review it through the governed lifecycle.
Restart and restore the relevant services without losing, duplicating, or
silently publishing the record. Record exactly which parts also work on ARM64
under emulation.

This slice advances CAP-001, CAP-047, and CAP-053 and exercises a narrow
CAP-007 reporting path. It provides a reusable foundation for other capability
checks. It does **not** by itself accept all four capabilities, establish
whole-system tenant isolation, or complete the refactor.

**Suggested capacity:** one developer working with Codex for roughly 8–12
working days. The live identity bootstrap, image downloads, local certificate
trust, and any defects found may change that estimate. Work in the batches
below, with local commits after coherent slices and pushes grouped into a
reviewable PR targeting `develop`.

## Why this sprint

- The [capability matrix](capability-matrix.md) validates 67 rows: 24 are
  baseline-retained, seven deployed, and 36 prepared. These labels describe
  implementation or deployment, not acceptance. All 67 named MAN-CAP checks
  remain separately open.
- The [execution checklist](batches.md) contains 1,234 checked and 25 open
  checkboxes, including nested items. Many open boxes cover multiple gates;
  their count is not a measure of feature parity or release readiness.
- Gateway, session, tenant-context, mobile, and farm-lifecycle components have
  substantial source and disposable-database coverage. The selected ZITADEL
  Compose overlay exists, but its provider, browser login, and grants have not
  been accepted together. The live workflow therefore connects several
  previously separate proofs.
- Source contains ordered migrations through `651`. The most recent recorded
  full ARM64/QEMU bootstrap applied 642 schema files through 651 with no seeds;
  it is emulation evidence, not a physical Raspberry Pi result
  ([evidence](builds/2026-10-26-recovery/arm64-qemu-current-schema-refresh-after-645-fix.json)).
  A recorded candidate rollout through 598 is historical; inspect the
  candidate before assuming its present migration or credential state.
- PR #69's CI #883 and Security #607 passed on its PR head. After its squash
  merge, `develop` was at the baseline above; release readiness requires the
  required checks on the actual release PR head.

The [owner-provided original implementation plan](implementation-plan-alignment.md)
is now available and its Phase 0–8 criteria are cross-referenced against the
tracked phase ledger and current evidence. The ignored root plan file contains
progress addenda and a matrix copy, so it remains preserved as a separate
working artifact. This sprint is chiefly a Phase 7 workflow slice, supported
by Phase 2 runtime and Phase 8 recovery/ARM64 checks; it does not mark a whole
phase complete.

## Batch 1 — Baseline and a disposable acceptance target

- [x] Record the source commit, clean worktree, Docker/available-disk state,
  selected profiles, migration/checksum plan, and exact CI/Security results.
  Reconcile the current checklist snapshot and affected capability rows without
  treating historical source tests as live acceptance
  ([baseline](builds/2026-10-26-recovery/sprint-workflow-baseline.json)).
- [ ] Build an isolated Compose project with synthetic organizations, two
  locations, and the operator identities needed for independent review. Use a
  fresh PostGIS database and ordered migrations; identify any missing fixture
  or enrollment/setup work before implementing it. Never treat a transport
  receipt as consent, semantic review, or publication.
- [x] Exercise the separate runtime and operator-auth database principals in
  the fixture. Record grants, denial cases, and remaining direct-table access;
  do not label the overall database tenant-isolated on this evidence.

**Starting points:** [profile planner](../../scripts/kernel-profile.py),
[candidate Compose](../../docker-compose.kernel-candidate.yml),
[runtime-role overlay](../../docker-compose.kernel-runtime-role.yml),
[migration service](../../services/migration/),
[operator-session role check](../../scripts/check-operator-session-role-disposable.py),
and [tenant contract](mobile-tenant-isolation.md).

**Progress, 26 October:** a network-disabled native PostGIS replay applied all
642 current schema files through 651, with zero seeds and successful cleanup
([evidence](builds/2026-10-26-recovery/sprint-native-schema-replay.json)). The
replay recorded a dirty worktree because generated evidence was untracked; its
schema and migration inputs match planning commit `a0de63ef`. Separate
minimal-schema runs passed the restricted-login/session and signed operator
context checks, including wrong-location denial
([roles](builds/2026-10-26-recovery/sprint-operator-session-role-disposable.json);
[context](builds/2026-10-26-recovery/sprint-operator-tenant-context-disposable.json)).
The replay runner now refuses existing project resources before cleanup; both
labelled and unlabelled synthetic-volume collisions were preserved in a live
Docker check ([evidence](builds/2026-10-26-recovery/sprint-schema-project-collision.json)).
The full-schema replay and two-tenant probe passed on clean source `020a5279`
([evidence](builds/2026-10-26-recovery/sprint-full-schema-operator-scope.json)).
The runtime login has table-level DML on 1,101 public tables without RLS;
this is a count, not a complete privileges audit. Forced RLS in this check
applied only to the synthetic probe table. The complete disposable workflow
fixture and general tenant isolation remain open. The 97-test focused selection
and Ruff passed.

**Done when:** the target can be created and removed repeatably; migration
status and role identities are captured without secrets; a wrong-location
principal is denied; and the current candidate is identified separately from
the disposable target. If a candidate rollout is later needed, take a fresh
encrypted checkpoint and rehearse restore before applying ordered migrations.

## Batch 2 — Live local identity and operator authorization

- [ ] Start the existing optional ZITADEL, dedicated identity database, Caddy,
  and Gateway OIDC overlays in the isolated project. Generate temporary test
  secrets separately from the user's production configuration. Configure local
  issuer discovery, client, callback, and test accounts; keep credentials out
  of logs, Git, and evidence. Use a unique `--project` with the profile planner;
  its default project name targets the existing candidate.
- [ ] Use a locally trusted HTTPS test origin. Verify real discovery, PKCE,
  sign-in, callback, Gateway session, CSRF rejection, logout/revocation, and
  audit attribution. Do not bypass a browser certificate warning. If local CA
  trust or interactive provider bootstrap requires a human action, document
  the exact step and continue the independent batches.
- [ ] Provision location-qualified Kokonut grants for the synthetic operators;
  verify correct scope succeeds and missing, revoked, legacy, or other-location
  grants fail. ZITADEL authenticates identity; Kokonut remains responsible for
  sessions and authorization.

**Starting points:** [ZITADEL deployment contract](zitadel-provider.md),
[ZITADEL overlay](../../docker-compose.kernel-zitadel.yml),
[OIDC overlay](../../docker-compose.kernel-oidc.yml),
[Caddy configuration](../../config/caddy/Caddyfile.kernel.zitadel),
[operator identity](../../services/gateway/operator_auth.py), and
[operator console](../../apps/operator-console/index.html).

**Progress, 26 October:** a fresh isolated ZITADEL database, API and Login V2
started and internal discovery returned the configured issuer; the identity
database role is non-superuser and the disposable project was removed
([evidence](builds/2026-10-26-recovery/sprint-zitadel-provider-smoke.json)).
The first startup exposed a fresh-volume permission failure
([diagnostic](builds/2026-10-26-recovery/sprint-zitadel-provider-third-attempt.json));
a networkless permissions helper now preserves and restricts the Login UI
token. Tests cover its Compose contract, and a disposable volume check exercised
write/read access, rerun preservation, unrelated-user denial, invalid identity,
and symlink rejection
([evidence](builds/2026-10-26-recovery/sprint-zitadel-bootstrap-permissions.json)).
The combined profile, replay and tenant unit selection passes 98 tests;
Ruff, shell syntax and capability-matrix validation pass.
This is internal HTTP startup/discovery only: Caddy, HTTPS, client provisioning,
browser login and Gateway session acceptance remain open.

**Done when:** a reproducible browser and API run uses the real local provider
and separate operator principals, demonstrates the positive and denial paths,
and records the source commit, issuer, profile, role setup, and cleanup. A
mocked provider or a successful login alone does not satisfy this batch.

## Batch 3 — Collector-to-farm lifecycle and a reporting slice

- [ ] Through the authenticated console, issue a single-use enrollment for one
  synthetic location and register a browser device. Capture a synthetic
  `farm_activity_v1` record in the encrypted vault while that browser's access
  to the test Gateway is interrupted; restore access and sync. Keep the host
  network available. Check duplicate retry, device revocation, wrong-location
  access, and cleanup.
- [ ] Exercise the existing eligibility and content-review gates. If the
  synced record is `transport_pending` or otherwise ineligible, prove it
  cannot advance; use only an implemented, authorized path to resolve the
  prerequisite. Promote an eligible, reviewed collection to draft and run
  submit, independent verification, and publication with the distinct actors
  and grants required by the existing guards. Verify append-only lineage and
  denied self-review, invalid transitions, revoked grants, and retry behavior.
- [ ] Compare one bounded farm activity metric/report or registered dashboard
  query against a deterministic synthetic fixture before and after the relevant
  lifecycle transitions. Computation creates draft metrics; human verification
  remains separate. Include a retired-form/withdrawal denial using the
  existing synthetic required-consent fixture where applicable.

**Starting points:** [workflow map](farm-activity-workflow-map.md),
[mobile access contract](mobile-access-contract.md),
[Field Collector](../../services/mobile/field-collector.html),
[mobile API](../../services/mobile/api.py),
[farm intake](../../services/gateway/farm_activity_workflow.py),
[farm lifecycle](../../services/gateway/farm_activity_lifecycle.py),
[farm routes](../../services/gateway/farm_activity_routes.py), and
[dashboard query registry](../../services/export/).

**Done when:** the browser, live Gateway, PostgreSQL and audit evidence describe
the same synthetic record and location; retries produce one intended effect;
denials leave no unauthorized mutation; and a frozen reference comparison is
recorded for the selected report or metric. This synthetic comparison does not
replace populated farm-data parity or owner review.

## Batch 4 — Recovery, portability, and handoff

- [ ] Reuse the disposable [scheduler reconnect](../../scripts/check-scheduler-engine-reconnect-disposable.py)
  and [event-worker reconnect](../../scripts/check-event-worker-reconnect-disposable.py)
  runners for their existing scopes. Add a focused live scenario only where
  necessary for the sprint workflow: restart the app/database or worker at a
  documented point, demonstrate retry and durable audit/queue state, and
  check that no duplicate effect or automatic verification occurs.
- [ ] Create and restore an isolated encrypted checkpoint of the synthetic
  database and required local media, verifying migration fingerprints and the
  selected workflow state after restore. Document the provider's separate
  database/master-key recovery boundary; do not claim an IdP restore without
  actually exercising it.
- [ ] Repeat the relevant software checks on ARM64/QEMU where feasible, using
  the existing [schema replay runner](../../scripts/check-arm64-schema-replay.py)
  and image/profile evidence. Record resource limits, image and source
  identity, and any skipped steps. No physical Raspberry Pi claim is made.
- [ ] Update [batches](batches.md), [progress](progress.md), and the affected
  [capability rows](capability-matrix.md) with exact evidence and remaining
  gates. Keep each MAN-CAP open until its full named criteria and owner review
  are actually satisfied. Summarize rollback and the next sprint's priorities.

**Done when:** recovery checks are repeatable on disposable resources, evidence
distinguishes native, emulated, mocked, and live-provider results, and all
temporary accounts, devices, data, containers, and volumes are accounted for.
Rollback disables the optional test profile and removes its disposable project;
any applied production/candidate migrations follow their documented ordered
recovery procedure rather than editing historical migrations.

## Verification and review

Start with focused existing checks for the code touched, including
`tests/test_operator_auth.py`, `tests/test_compose_zitadel_profile.py`,
`tests/test_tenant_context.py`, `tests/test_farm_activity_workflow.py`,
`tests/test_farm_activity_lifecycle.py`, `tests/test_farm_activity_routes.py`,
`tests/test_mobile_api.py`, `tests/test_mobile_vault.py`, and the Node tests
`tests/test_mobile_offline_shell.mjs` and `tests/test_mobile_vault.mjs`.
Run the applicable disposable database and browser checks above; add tests
for observed gaps rather than duplicating existing assertions. Also run the
capability-matrix, requirement-group, provider-boundary, and relevant inventory
checks, followed by the required CI and Security checks on the PR head.

## Dependencies and later work

- Local ZITADEL can use synthetic identities and test-only secrets. Production
  issuer/client provisioning and the owner-selected `auth.kokonut.network` and
  `hub.kokonut.network` deployment remain separate.
- Farm data for Genesis, Seeds, Adelphi, and V1 has not yet been ingested.
  Populated parity, report audiences, and final capability-owner acceptance
  follow that ingestion; Terra Viva remains in design.
- Physical Pi/power-loss testing, the 24-hour recovery window, production
  failover, SMTP recipient/on-call routing, R2 recovery, and configurable
  retention/legal-hold policy activation remain open. Do not infer them from
  local synthetic tests.
- Directus, ClickHouse, Metabase, Prefect, Redis, MQTT, gRPC, and Caddy remain
  optional or replaceable according to their profiles and capability contracts.
  The temporary HTTPS identity test uses the existing optional Caddy overlay;
  it does not make that proxy a minimum Kernel dependency. Unsupported saved
  dashboard SQL remains unexecuted; port its intended behavior through reviewed
  query contracts rather than silently dropping report capabilities.
- The owner deferred the Kokonut Protocol execution bridge (CAP-067). It is
  outside this sprint. Production cutover remains conditional on the broader
  readiness gates, even though the owner approved it once ready.

After this sprint, prioritize the remaining signed tenant/worker and optional
Directus boundaries, then port and verify the remaining repository-defined
reports, dashboards, and provider jobs in scoped groups. Continue the CAP-035,
CAP-036, CAP-037, CAP-038, and other capability workflows with populated and
owner-reviewed fixtures as they become available. Schedule production recovery,
scale, provider delivery, and reviewed cutover only when their prerequisites
and operational inputs are ready.
