# Kokonut Kernel implementation progress

**Updated:** 14 October 2026. **Current candidate runtime: migrations 387–391 are applied (382 schemas, zero pending); one curated seed (`seed:140_mobile_forms.sql`) is recorded and 120 seed files remain pending. The five existing mobile forms and ten revisions now have reconciled seed-ledger history. Migration 391’s encrypted checkpoint and app-only rollout passed health and anonymous protected-route checks; a read-only follow-up confirms the migration checksum and 382-schema ledger, health 200, and protected review route 401. RLS remains disabled.** **Current implementation focus: the candidate serves Field Collector `1.2.0` schemas; Phase 7 source includes OIDC enrollment controls, a separate-grant Field Collector review queue, and append-only reviewer notes; the full clean replay passed and migrations 382–386 are now applied to the candidate; its app health and protected anonymous-access gates pass, while real OIDC remains unconfigured; browser checks cover mock-origin offline capture/reconnect plus candidate-Gateway sync and pending-badge refresh. A locked-browser local vault reset control is now implemented and visible in the candidate.** The vault reset confirmation was not invoked. The repository owner has since unlocked the existing browser vault; its home shows zero pending records and requests a new enrollment code because the synthetic server device was removed. The latest Batch 3 slice also adds a published-only farm-activity aggregate to the governed farm summary and extends `rework_rate_pct` with bounded source/rework provenance; actual report/snapshot/metric integration after all 375 ordered schema migrations replayed into disposable PostGIS 16 passes; the expanded Batch 3 suite passes 91 tests and Ruff, including location-scope and injected-event-failure unit checks. A real PostgreSQL workflow-event trigger failure now confirms transaction rollback after all 375 schema migrations; two simultaneous PostgreSQL duplicate-promotion calls passed; candidate migrations 383–385 and the app-only rollout from `f854d47` now pass local schema, health, and protected-route checks; higher-contention stress, real OIDC, and MAN-CAP-001 remain open. A rollback-only live PostgreSQL check confirms the consent eligibility view preserves post-collection withdrawal after regrant, and real Gateway HTTP checks reject both active and synthetic retired required-consent records after withdrawal/regrant without writes; browser consent handling, OS airplane mode, real OIDC/provider acceptance, and the remaining media, governance and retention gates remain open. The seeded retired `1.1.0` forms are `not_required`, so a reviewed synthetic retired revision was used for the latter policy branch. Preparatory Phase 8 image work has also occurred. This is not a sequential completion claim: earlier phases have implementation evidence but unresolved acceptance criteria. Current source adds OIDC-scoped canonical farm-activity queue/detail reads, console promotion/lifecycle controls, and migration-385 immutable-form-validated draft correction. The focused source suite passes 95 tests plus Ruff; all 376 ordered schema migrations and a synthetic edit/event-digest/append-only/rollback acceptance pass in disposable PostGIS 16. At the migration-385 rollout checkpoint, the candidate had 376 applied schemas and zero pending. A fresh age-encrypted checkpoint restored with matching migration fingerprints, extension versions, and workflow counts; only the app was rebuilt from `f854d47`. A retention-safety slice now blocks generic soft-delete policies for consent, Field Collector, private-media, and governed farm-activity tables; withdrawal still restricts use pending human disposition, and end-to-end erasure remains unimplemented. Health returned 200 and protected review, activity, and draft-edit routes returned 401; PostgreSQL, Metabase, and proxy stayed up. Configured OIDC, populated workflow acceptance, and MAN-CAP-001 remain open ([rollout](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json)).

Implementation began on `feat/kernel-architecture-refactor`; current Field
Collector acceptance continues on `feat/mobile-offline-acceptance` in open PR #68,
based on the updated main branch. No merge or passing release CI is recorded. The
root implementation plan remains intentionally
ignored; this ledger and the [capability matrix](capability-matrix.md) provide
repository-visible progress alongside it. Owner-only decisions and external
acceptance inputs are collected in [Open Follow Ups](open-follow-ups.md).

The prescribed platform-integrity suite was rerun on local commit `1c00845`
after the owner authorized ongoing verification: 288 tests passed across
migration discovery/transactions, Gateway authorization, durable scheduler and
event delivery, credits, threatcasting, backcasting, and Delphi. This confirms
the focused source contracts; real-provider outage recovery, physical hardware,
and the remaining manual acceptance gates are still open ([run evidence](builds/2026-10-14-recovery/platform-integrity-288-tests.json)).

GitHub CI #304 on PR #68 completed with 4,632 passed tests, 75 passed subtests,
and five failures. The local fix batch updates tenant-aware test contracts,
makes operator enrollment denials explicitly non-cacheable, and corrects seed
ordering and OIDC Compose assertions. The five CI regressions pass locally; the
full operator-auth and Compose suites pass 72 tests, and Ruff/Python syntax
checks are clean. Security run #28 passed. The fix batch is pushed in
`7b155cb705cb03895bba9a16b3ab07937502bb68`; CI #305 is in progress and Security #29 passed, so the local results still
need remote CI confirmation
([verification record](builds/2026-10-14-recovery/ci-304-regression-fix-checks.json)).

## Phase ledger

| Phase | Implementation status | Delivered evidence / likely owners | Remaining completion gates |
| --- | --- | --- | --- |
| 0 — Baseline | Inventory delivered; closure partial | 66 capability owners/checks, frozen source/dependency inventory and local container/volume counts; [baseline](README.md), [storage](local-data-inventory.md) | Collection/consumer refinement, logical Redis/BI/broker/private-media state, selected legacy logical records restored; complete provider/media/role recovery and broader ownership pending |
| 1 — Ports/providers | Implemented in selected paths; acceptance open | Typed provider settings/health; analytics/cache/events/scheduler ports; lazy vendor adapters; static check passes at 17 vendor sites; services/core/, services/common/, services/analytics/ | Contract/import/config and legacy behavior acceptance; storage/remaining domain construction audit; reviewed dependency lock |
| 2 — Minimal runtime | Fresh AMD64 runtime exercised; workflow acceptance open | Dockerfile.kernel, standalone candidate/portability manifests, supervisor and split roles; portability DB/API/worker had run, then returned to stopped/exited state after recovery probes; latest portability app image includes audit CLI; separately, the active candidate app and database are healthy with a current-source image, five active candidate 1.2.0 forms plus five retained retired 1.1.0 snapshots, 382 applied schema migrations through 391 and zero pending; one curated seed is ledgered and 120 seed files remain pending; five mobile_form rows and ten revisions have reconciled seed history; strict JSON Schema payload validation is deployed; a fresh encrypted checkpoint restored into an isolated template0 target with matching migration fingerprints, extensions, and schema inventory; isolated live sync rejected an undeclared field (422) and accepted a valid 1.2.0 payload (200) [rollout](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json); farm-activity migrations 383–385 and the app image from `f854d47` are deployed with checkpoint restore parity, zero pending, and protected-route checks passing [evidence](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json); separate recovery fixture has 365 checksummed schema files through 374; sensor anomaly alert/claim/outbox/actuation approval effects now share a transaction and one actual EventBus worker crash/retry completed on attempt two without duplicate effects; [runtime](portability-runtime.md), [sensor entrypoint](sensor-entrypoint-recovery.md), [sensor delivery](sensor-anomaly-delivery.md) | Governed farm write/submit/independent review/publish, PostgreSQL metric/report acceptance, mobile sync and accepted-work recovery; no seeded pilot fixture yet; external provider acceptance and broader event/runtime recovery remain open |
| 3 — Optional analytics/BI | Partial | PG metric catalog/public roll-up; optional ClickHouse driver/overlay; sensor source/event/outbox paths exercised against raw ClickHouse and v3 daily summary; Directus, Metabase metadata, and analytics-source roles verified on isolated copies; pinned Directus bootstrap/runtime and Metabase populated-metadata startup healthy; sample board classified as generic e-commerce demo; source-aligned scratch applied all 369 migrations through 378, zero pending, and passed actual-view grants and rollback-only reporting probes; transactional replay validated all 369 current schema checksums and rollback of injected DDL plus ledger state (`0|0`); a separate clone accepted the 25 pending archived migrations with zero pending and unchanged original-column fingerprints across 16 populated tables; migration-354 SAFE addresses, owners, thresholds, versions, and nonces matched read-only Gnosis Chain calls; independent NOI recomputation matched the view on six cycles, exposing six stale snapshots and a missing upsert key; migration 379 plus native reconciliation SQL and Directus-hook alignment brought six snapshots into parity on a separate network-disabled clone; [NOI reconciliation](noi-snapshot-reconciliation.md), [evidence](builds/2026-10-11-recovery/noi-snapshot-parity.json), [consumer role policy](optional-database-roles.md), [report contract](metabase-reporting-contract.md), [populated parity](builds/2026-10-11-recovery/populated-report-view-parity.json), [candidate preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json), [compatibility review](pending-migration-compatibility-review.md), [reporting migration](../../schemas/postgres/377_kokonut_reporting_contract.sql), [NOI index migration](../../schemas/postgres/379_noi_snapshot_crop_cycle_key.sql), [reporting evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json), [transaction evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json), [populated clone evidence](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json), [checksum triage](migration-checksum-drift.md), [startup evidence](builds/2026-10-11-recovery/metabase-populated-startup.json) | Archived application clone remains unchanged with 25 pending migrations. The candidate's exact historical checksum was repaired through the audited path; migrations 371–379 applied transactionally and the exact-target plan reports zero pending across 372 applied schema files. Its checkpoint restored successfully in isolation. The reporting views and NOI unique index exist. The candidate analytics login is provisioned and verified with no unreviewed application relation access; the optional Metabase profile is healthy with its separate H2 demo and Kokonut source/cards; populated saved-card SQL matches independent farm, attestation and synthetic metric references, including publication and date-window filters. Populated farm-summary and Celo-attestation view parity passed; synthetic nonempty metric period/method probe passed while the populated source has zero published policies; ClickHouse dataset/report parity and rebuild lineage; replay/outage acceptance; DuckDB/Parquet path and owned dashboard UI |
| 4 — Owned orchestration | Partial; source-level schedule ownership inventory delivered; local candidate reports zero scheduled tasks | 15 JobSpecs, legacy flow delegation, scheduler planning/graph audit/guarded activation and same-window migration 371; per-job Prefect/cron/seed/event-worker mapping and cutover/replay policy; the new daily `noi_snapshots` job is prepared but disabled; services/core/jobs.py, services/scheduler/, services/flows/ | Reconcile active provider state and accountable owners; resolve source/input/cadence gaps and per-job idempotency; transfer one job at a time with output parity, retries, and rollback; no task activation or shadow comparison performed |
| 5 — Optional Redis | Partial; local runtime/restart and isolated PostgreSQL shared-consumption, lock-timeout, and direct and ASGI multi-process plus two-container network HTTP checks passed; provider selection remains open | Existing PG computation cache retained; local limiter concurrency/LRU/process reset and candidate app restart verified; in the migration-373 portability DB, two backend instances admitted 121/140 concurrent checks within the refill-aware bound, denied an over-capacity request, returned retry 10, and isolated a distinct caller; a held synthetic row lock raised SQLSTATE 55P03 after 2.124 seconds and its bucket was removed; network-disabled source ASGI checks selected PostgresRateLimiter and returned 503/Retry-After 30 on an unreachable DB; GatewayAudit now has a bounded SQLite queue, idempotent startup replay, a status/checkpoint/restore CLI, and process-exit/checkpoint/restore recovery evidence; four OS processes shared one bucket across 160 direct calls (114 allowed, 46 denied in 1.653 seconds), then four gateway processes handled 160 ASGI requests (121 returned 200, 39 returned 429 with Retry-After) within the refill-aware bound; two private-network API containers then handled 160 HTTP requests through the shared database (119 returned 200, 41 returned 429 with Retry-After); PostgreSQL adapter remains opt-in and candidate stays local; [local runtime](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json), [local contract](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json), [process reset](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json), [app restart](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json), [PG shared check](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json), [lock timeout](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json), [multi-process check](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json), [ASGI multi-process](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json), [two-container HTTP](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json), [audit outage/replay](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json), [checkpoint recovery](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json), [audit write guard](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json) | Volume/host/device loss, external alert delivery and production retention owner; auth/revocation/cache/TTL and identity-abuse acceptance; production/public ingress, multi-host failover, replica restart and scale acceptance; scale remains unavailable |
| 6 — Optional edges | Prepared/built in selected targets; acceptance open | MQTT/gRPC/HTTP sensor/Caddy overlays; CSV/HTTP exercised in-process and over TCP inside the private recovery network; selected handler receipt recovery; bounded Caddy TLS/redirect/header smoke, one-hop forwarded-header audit identity check, loopback-published redirect/follow check at default and alternate HTTPS ports, configured/untrusted CORS preflight, CORS decoration on an auth denial, isolated current-source and deployed local limiter checks with 429/Retry-After, preflight bypass and durable audit, plus promoted-image local concurrency/LRU, process reset, candidate app restart, source-level PostgreSQL-outage 503, real audit outage journaling and startup replay across app-container replacement, checkpoint/restore and process-exit recovery, held-row lock-timeout handling, direct four-process shared-bucket consumption, four-process gateway ASGI 200/429 behavior, and two-container network HTTP sharing; [sensor evidence](sensor-entrypoint-recovery.md), [proxy evidence](kernel-proxy.md), [source limiter](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json), [runtime limiter](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json), [local contract](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json), [process reset](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json), [app restart](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json), [outage boundary](builds/2026-10-11-recovery/postgres-rate-limit-outage.json), [audit outage](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json), [lock timeout](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json), [multi-process check](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json), [ASGI multi-process](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json), [two-container HTTP](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json), [audit journal](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json), [audit checkpoint](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json), [audit write guard](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json) | Volume/host/device loss, external alert delivery and production retention owner; production/public ingress, replica failover/scale; non-loopback/public ingress, multi-hop trusted-proxy policy, mobile/upload consent/form baseline and candidate migration 380/381 plus 1.2.0 strict-schema rollout complete; 60 mobile/schema and four CORS checks passed; live device acceptance remains open, CORS on successful authenticated/credentialed responses, HTTP/CSV/MQTT parity, optional service parity, broader handler recovery, delayed sink visibility/reconciliation, RPC streaming/auth and external Traefik acceptance |
| 7 — Native API | **Active, partial read slice deployed; v1 public read aliases, typed SDK sources, local operator overview, and source-level OIDC report reads, mobile review queue and append-only review-event source; mobile consent/form enforcement and exact-revision JSON Schema validation deployed on the candidate** | Native public locations/metrics, published CRISP and location roll-up, strict response models, bounded read execution and readiness gates; additive `/api/v1` routes with explicit public policies; generated Python/TypeScript models and paths; local read-only Kernel overview; optional OIDC identity/session adapter; location-scoped submitted `report_snapshot` list/detail routes and same-origin read-only queue; services/gateway/router.py, services/gateway/operator_auth.py, services/gateway/operator_review.py, services/gateway/app.py, apps/operator-console/index.html, services/mobile/api.py, services/mobile/form_validation.py, schemas/postgres/381_mobile_consent_form_revisions.sql | Live v1 payload/role/grant/auth and Directus parity; JavaScript SDK runtime import and offline Python/JavaScript SDK contract parity passed with fake adapters, while live route parity remains open; shared lifecycle hooks and tenant/RLS scope; farm-activity lifecycle writes and human actor guards have source/disposable checks; canonical queue/detail and console controls are source-tested; migration-385 draft editing passes focused service/route/console checks and full disposable PostGIS replay/trigger acceptance; migration 385 and the operator routes/editor are deployed to the candidate with zero pending schemas and protected-route checks passing; OIDC-scoped same-origin Field Collector enrollment and revocation routes plus the one-time code console are implemented and source-tested; provider configuration, login/session/audit, and live enrollment-created workflow remain open; isolated authenticated 1.2.0 sync accepted valid data and rejected an undeclared field; report queue scope/detail and review-event source checks pass; migration 382 is applied to the candidate; the current-source app was rebuilt and returned health 200, while OIDC login remains disabled and anonymous review-queue access returns 401 ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json)); migrations 380/381 and the candidate 1.2.0 form rollout remain applied |
| 8 — ARM64/scale/retirement | Build preparation; default and ClickHouse app build gate configured; CI run 284 built both PostGIS architectures after CA bootstrap, then exposed one package inventory difference now explicitly locked | Earlier matched AMD64/ARM64 artifacts; [build record](arm64-image-pair-refresh.md); [release input contract](kernel-release-inputs.md); [GitHub Actions setup](../github-actions.md) | Fresh multi-architecture rerun against the exact architecture-specific package contract, ARM64 runtime/bootstrap/restore, actual 4 GB Pi/SSD measurement, 24-hour recovery, GitHub runner/environment setup, scale concurrency, production cutover and dependency retirement remain open |

## Phase 4 schedule ownership inventory — 12 October 2026

Added a source-level inventory for all 15 shared JobSpecs, the four scheduled
Prefect deployments and manual full-pipeline entry point, the active and
deprecated worker crontab entries, the historical scheduled-task seed, and the
long-running event worker. It assigns the PostgreSQL scheduler as the minimal
profile target while keeping Prefect as an optional adapter, with a one-active-
dispatcher rule and per-job replay cautions. The inventory identifies
conflicting sensor and metrics contracts, climate fan-out versus per-location
scheduling, unscheduled projection and cleanup work, remote-sensing's internal durable job
ownership, and the weekly ML retraining docstring/body mismatch. For climate,
`--all` means all datasets at a required location; Prefect currently fans out
over active locations, while native planning represents one location per task.
See
[schedule ownership inventory](schedule-ownership-inventory.md) and the
[Batch 4 checklist](batches.md).

The only runtime action was a read-only `services.scheduler.cli --status`
inside the healthy local candidate app: it reported zero enabled, disabled,
running, or failing tasks. No job ran and no task/seed/schedule was written or
activated. The candidate project has no Prefect container, and a read-only
global Docker name filter found no running container matching `prefect`; no
external Prefect API or host process was queried. The restored legacy database
also had no scheduled task rows. Historical seed 050 contains enabled
definitions, but `scripts/seed.sh` uses `--schemas-only` and its curated seed
list excludes it. Its inaccurate comment about applying numbered seed
migrations is corrected. See
the [candidate status evidence](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json).
Batch 4 remains open until live provider state, operational ownership,
idempotency, and per-job cutover/recovery evidence are established.

**No phase is marked fully accepted under the plan's complete criteria.** Builds,
source implementation and idle startup are useful milestones, but do not satisfy
domain or recovery acceptance. Work advanced across phases while preserving old
data/providers; provider retirement and production cutover have not occurred.

## Capability accounting

All 66 original IDs/checks remain in the matrix. Current integration progress:

- **7 deployed partial/adjacent integrations:** CAP-001, 007, 014, 031, 039, 047, 053.
- **3 prepared partial integrations:** CAP-040, 064, 066. CAP-040 now includes one bounded handler-effect and durable-receipt recovery rehearsal; it remains partial.
- **56 baseline-retained domains:** Kernel access paths and parity still unassessed.
- **0 fully accepted Kernel capabilities.** All MAN-CAP gates remain open.

CAP-031's public location roll-up is adjacent API work, not completion of planning
or internal portfolio analyses. CAP-014's published read does not certify the
five-dimension scoring engine. Shared infrastructure/image/schema work supports
many rows without migrating or certifying their full workflows. Source retention
does not guarantee an unchanged capability can run with minimal dependencies.

## Current deployment evidence

The isolated project `kokonut-kernel-portability` previously ran a private AMD64
database, API and native scheduler/event worker. Its recorded API and worker
image is
`sha256:78389fb6cf1f05291e89b35ce4f0271e533bbe5403be97a8d77a29cdfc5825f5`;
the database image is
`sha256:b573e82124b3530c454ea6d5ae8aefce1fb7ee137467f66f75a5079f8569ee6b`.
The portability app image was rebuilt with the audit maintenance CLI at
`sha256:13602e4470f02855320d458c3b229cf6d341a337ea3f7ccb04e4a353f42234f3`.
A one-off network-disabled container returned an empty status for an absent
journal without mounting a database or persistent volume; checkpoint, verify,
restore and overwrite refusal also passed against a private temporary bind
fixture. The candidate app and database remain up and healthy; portability API/worker containers remain
exited on the previous image and the portability database remains cleanly
stopped. No service recreation or provider change occurred. Ports remain private
per the manifest/runtime record; no legacy storage was migrated into this fresh
database. [CLI image evidence](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).

364 ordered schema migrations completed with zero failures, including 371–373.
That applies only to portability; candidate/legacy backlog is independent.
Numbered seeds and pilot data have not been loaded. Last worker workload
inspection was empty. Readiness checks cover bundled checksums, required extension
presence and four public relations/column sets; they do not certify view semantics,
grants, populated API responses, or recovery. See [exact runtime chronology and
rollback identities](portability-runtime.md).

No broad Python/Solidity/extension acceptance suites, multi-domain parity
fixtures, live summary request comparisons or full restore rehearsals are recorded.
The scoped single-reading sensor parity check is documented separately.
Lint/static gates and Docker health/startup are reported separately from tests.
The latest paired batch artifacts include public read models and the structural
relation gate; no ARM64 service has been started. Scale is still rejected by
the planner. Directus hooks/metadata, old dashboards and legacy volumes remain.

## Next work and tracking rule

Prioritize closing baseline/recovery and minimal workflow acceptance alongside
Phase 7, before adding governed writes or retiring a provider. Prepare a scoped
pilot/reference fixture and backup/restore path; establish public response,
authorization/lifecycle, mobile and worker recovery evidence. Continue Phase 7
through explicit domain contracts and reviewer policy, then SDK/console work.
ARM64/Pi/scale certification follows the relevant parity gates.

Every subsequent Kernel slice updates this ledger, the ignored root plan's phase
notes, directly affected matrix rows and the linked execution record. Record
source/image/profile identity, what changed, what was exercised, remaining gates,
and rollback. Mark an acceptance gate closed only with its retained evidence;
never infer parity from unchanged source, a build or a healthcheck. Avoid a single
completion percentage until work items and acceptance weights are agreed.

## Phase 7 v1 public location contract — 11 October 2026

Added strict response envelopes and additive `GET /api/v1/locations` and
`GET /api/v1/locations/{location_id}` routes. They use the native governed
`v_public_farm_summary` read path, document schemas through FastAPI OpenAPI, and
leave the existing unversioned Directus/native response wrappers unchanged.
Malformed UUIDs return 400; missing and ineligible locations share a 404.
Added typed location methods to separate Python and JavaScript public API
clients; the existing Directus clients remain unchanged. Updated the contract
and capability checklist. This is source implementation only: no runtime
payload comparison, grant review or Directus parity check was performed; the
SDK source has not been generated from OpenAPI or released; the TypeScript package build could not run because `tsc` is unavailable in the local checkout. No test suite was
added or run. Roll back by reverting the additive routes/models/SDK clients or
deploying the preceding gateway image; existing clients continue using
`/api/locations`.

The scoped native v1 OpenAPI snapshot is now retained at
[`native-public-api-v1.openapi.json`](native-public-api-v1.openapi.json); see
the additive-read entry below.

## Phase 7 additive public read aliases — 11 October 2026

Added `/api/v1/metrics/{location_id}`, `/api/v1/crisp/{location_id}`, and
`/api/v1/analytics/{location_id}/summary` as additive wrappers over the existing
strict-model read handlers. Successful v1 responses use `{ "data": ... }`, while
the legacy unversioned paths retain their raw response shape. Added explicit
public `read` route policies, envelope response models, and unique OpenAPI
operation IDs. Extended Python and JavaScript public clients with typed metric
summary, published CRISP, and governed location-summary results. Updated the
contract docs, capability rows, and Batch 5 checklist. This is source-level
implementation only. Exported the scoped native OpenAPI from the existing
Gateway dependency image with the current source mounted read-only and network
disabled; the generated document includes `x-kokonut-policy` derived from the
route-policy function. No service was started. The local host cannot import
FastAPI. The JavaScript build remains unavailable because `tsc` is not installed.
Python syntax compilation, JSON parsing and diff whitespace checks passed; no
test suite or HTTP route request was executed. SDK release packaging, HTTP
authorization/payload/Directus parity, and the operations-console slice remain
open. Rollback reverts the additive decorators and policy entries plus SDK
methods; the original routes remain.

## Phase 7 OpenAPI-derived SDK types and paths — 11 October 2026

Added a standard-library generator that reads the retained native v1 OpenAPI
snapshot and emits public response payload types for Python and TypeScript plus
operation-to-path tables. Both SDK clients now import those generated types and
use the generated path templates, while convenience method wrappers remain
handwritten. Regenerated artifacts from the snapshot; Python syntax compilation
and `python3 -m scripts.generate_public_api_sdk --check` passed. The local `tsc`
executable is still unavailable, so the TypeScript build was not run; no test
suite or HTTP route request ran. Refresh the OpenAPI snapshot before rerunning
the generator. SDK build/publication, runtime
parity, and the operations-console slice remain open.

## Directus parity source inventory — 13 October 2026

Mapped the legacy permission seed, DML-only Directus runtime identity, Directus
hook registrations and side effects, native Gateway/operator route surface,
tenant scoping model, and the limited coverage of the existing metadata and
permission source checks. The inventory distinguishes database privileges from
Directus API authorization and identifies the scheduled NOI and weekly snapshot
callbacks that need a single-owner decision. The staff permission seed
references `$CURRENT_USER.location_id`, but the restored archive has no
corresponding `directus_users.location_id` column; the native operator console
uses explicit grants, so these identity models are not assumed to be
equivalent. Many read permissions request every field, and Auditor has
unfiltered access to additional report/governance collections; confirm the
intended forensic scope before changing it. The weekly callback only groups
eligible activity and logs a count, so it does not establish persisted snapshot
parity. See the [Directus parity inventory](directus-parity-inventory.md).

## Phase 3 Directus isolated API probe — 13 October 2026

Restored the populated application archive into a fresh internal-only copy,
applied its ordered migrations with zero pending and no checksum drift, and
started the pinned Directus 12.1.1 bootstrap/runtime using the DML-only
identity. Bootstrap and health passed; admin login returned 200, anonymous
`farm_activity` access was denied, and the optional consumer-role fixture
passed. The archived `directus_users` table has no `location_id` even though
the Field Worker permission seed filters on `$CURRENT_USER.location_id`.
Synthetic Field Worker requests returned 403 for both own- and other-location
rows, with zero rows exposed. This is fail-closed behavior and does not prove
location-scoped authorization or field privacy. Identity-creation retries hit
Directus `LIMIT_EXCEEDED`, and hooks/scheduled jobs were not started. API
cleanup for the first synthetic identities did not finish; removing the entire
isolated database volume, runtime and private network removed the test rows and
identities. Candidate services stayed healthy and the legacy stack stayed
stopped. See [sanitized runtime evidence](builds/2026-10-13-recovery/directus-api-parity.json).

The next parity run needs an explicit identity-location model (or a deliberate
switch to grants), followed by own-location, cross-location, field, write,
extension-hook and schedule checks. Directus remains optional; this result does
not authorize ownership backfill or tenant RLS.

The broader reporting gate is now mapped at source level: three first-party
cards have copied-fixture evidence, the report generator registers 94 draft
snapshot types, the typed analytics query port has one public query, and the
legacy dashboard dataset runner executes stored SQL but discards result rows
after counting them. The inventory distinguishes these from bounded evidence
graph reads and optional ClickHouse rollups. Accountable owner selection,
reference fixtures, and retained dashboard/report acceptance remain open
([source inventory](metabase-source-inventory.md); [reporting contract](metabase-reporting-contract.md);
[parity inventory](reporting-parity-inventory.md)). No test suite or live
dashboard SQL execution was performed for this source review.

## Phase 4 reporting and projection source inventory — 13 October 2026

Mapped the native analytics query port, versioned public Gateway reads, graph
lineage projection, 94 registered draft report types, optional Metabase card
slice, legacy `dashboard_dataset.query_sql` refresh path, and ClickHouse rollup
contracts. The inventory found that the dashboard refresh worker executes the
stored SQL through the application database connection, fetches all returned
rows, discards them after counting, and stores only refresh metadata. The five
repository-seeded dataset examples are `published` while the `--all` command
selects `active` rows. This worker is not a durable result store or a safe
general reporting interface; review its DB role, writers, and retained
consumers before enabling it. The source inventory does not approve or execute
stored SQL, select which reports remain product requirements, or establish
parity. See the [reporting parity inventory](reporting-parity-inventory.md) and
[Batch 4 checklist](batches.md).

The legacy stored-SQL refresher is now an explicitly gated compatibility path:
`KOKONUT_FEATURE_LEGACY_DATASET_SQL` defaults to `false`, and the execution
function enforces that gate while read-only dataset listing stays available.
This keeps unreviewed stored SQL out of the default Kernel runtime. It does not
make opt-in queries safe or close the outstanding owner, role, location-scope,
materialization, and report-parity gates. The focused core-feature suite passes
12 tests, Ruff passes on the changed Python files, and Python compilation passes;
no live dashboard query ran. The switch now reaches candidate, portability,
and standard API/worker Compose environments while defaulting to false. Compose
profile checks confirmed the explicit override. Those checks also exposed and
fixed a strict-shell health-check false negative: container-name detection now
consumes the full Docker output instead of allowing `grep -q` to close its pipe
early. The combined focused core and Compose-profile suites pass 23 tests; Ruff,
shell syntax, and whitespace checks pass. No stored dashboard query ran.

A read-only aggregate pass over the isolated legacy archive found 43 stored
dashboard dataset definitions, all with owner metadata but only 12 distinct
owner labels; the labels were not retained. None had refresh metadata, none
would be selected by `--all`, and only five were location-scoped. The stored
query fields include 11 `SELECT` prefixes and 32 `dashboards` prefixes; this
was a leading-token count, not SQL validation, and none was executed. Three
unlocated, unfrozen draft report snapshots remain in the archive. See the
[sanitized archive inventory](builds/2026-10-13-recovery/reporting-archive-inventory.json).

## Phase 7 JavaScript SDK compiler compatibility — 11 October 2026

Installed the SDK's declared TypeScript 5.8.3 development dependency locally and
ran `npm run build` successfully. This exposed stale Directus SDK usage in
`sdk/javascript/src/client.ts`: item commands are now imported from
`@directus/sdk` and passed to `request()`, login reads the SDK's documented
`access_token` field, and requests await the asynchronous token setup/update.
The build compiles package sources and declarations; no
test suite or API request ran. This establishes compile-time compatibility, not
live Directus behavior, public-route parity, or SDK release readiness. Local
`node_modules/` and generated `dist/` remain ignored. Rollback by reverting the
client adapter change; the prior source failed this same compile. See the
[Batch 5 checklist](batches.md).

## Phase 7 JavaScript SDK package preflight — 11 October 2026

The npm package is configured as ESM to match `@directus/sdk` 17, its repository
metadata points to this checkout's `sdk/javascript` directory, the Apache
license is included at the package root, and `src/__tests__` is excluded from
published output. The lockfile pins TypeScript 5.8.3, `@directus/sdk` 17.0.2,
and Vitest 5.0.3. After cleaning only the generated, ignored `dist/`, the
TypeScript build passed and `npm pack --dry-run --json` listed 27 files with no
test output. The initial five development-tool audit findings were addressed by
upgrading Vitest; npm now reports zero vulnerabilities. No tarball was created
or published. No test suite or package runtime import was run; runtime parity
and versioned release remain open. See the [Batch 5 checklist](batches.md).

## Phase 7 Python SDK package preflight — 11 October 2026

Added the repository README, Apache license, and `py.typed` marker to the
`kokonut-intelligence` 0.1.0 distribution metadata. The repository URL now
matches this checkout's GitHub origin. Built a wheel and source distribution
with the installed setuptools backend, then inspected their archive contents and
metadata without installing or importing them. The wheel contains the typed
HTTP/Directus and native public API client modules, license, and package
metadata; the source distribution also contains the README and project source.
Artifacts were retained outside the repository in
`/private/tmp/kokonut-python-sdk-artifacts/`:

- `kokonut_intelligence-0.1.0-py3-none-any.whl` — 16,976 bytes;
  SHA-256 `3b99e5e9358794a804ef32283508839f460ccfcc1b13565e9342fff7b8e3a2fd`.
- `kokonut_intelligence-0.1.0.tar.gz` — 16,787 bytes;
  SHA-256 `208380cba97d05cc418b8d68b77bc805e44909f2a4b875158c51d4ebe9762ab5`.

The initial distribution contained only the `kokonut` HTTP SDK package;
generated protobuf/gRPC modules were excluded. That boundary is resolved in the
following entry. No SDK import, API request, test suite, or publish ran. Runtime
import/API parity and explicit release authorization remain open. See the
[Batch 5 checklist](batches.md).

## Phase 7 Python SDK optional gRPC distribution — 11 October 2026

Resolved the generated-protobuf packaging boundary without adding gRPC to the
base SDK. Added a pinned `grpc-codegen` extra and a `grpc` runtime extra, plus a
reproducible generator that puts source-generated modules under `kokonut.grpc`
and rewrites Python imports and generated class module metadata; protobuf
package/service names and descriptors remain derived from the unchanged
`proto/` files. The generated
code requires `grpcio>=1.68.1` and `protobuf>=5.28.1`; the SDK extra declares
compatible runtime bounds. Ruff passes, and regeneration reports all 10
generated Python modules up to date. The 0.1.0 wheel and sdist build and each
contain the 16 package `.py` files (10 generated modules plus six package
initializers); artifacts are under
`/private/tmp/kokonut-sdk-proto-artifacts/`. The standard isolated build first
could not reach PyPI, so the archive build used the already-installed setuptools
in the isolated code-generator environment. No SDK install/import, gRPC call,
test suite, publish, or release occurred. Runtime import/API parity remains
open. Roll back the generator, generated package and SDK extras together; the
legacy repository-level generated stubs and gRPC server are unchanged. See the
[Batch 5 checklist](batches.md).

## Phase 7 Python SDK isolated wheel import check — 11 October 2026

Installed the built `kokonut-intelligence` 0.1.0 wheel and the declared `grpc`
runtime dependencies into a clean temporary environment at
`/private/tmp/kokonut-sdk-import-env/`. The base REST clients and all 10
generated gRPC/Protobuf modules imported successfully with grpcio 1.84.0 and
protobuf 5.29.6. The check confirmed namespaced `PageRequest` class metadata and
the unchanged `data.v1.DataService` and `ecocredit.v1.EcocreditService` names
from their original descriptor paths. No API/RPC request, test suite, or
publish ran. Python SDK import acceptance is closed for this wheel/runtime
combination; JavaScript runtime import, live route/API parity, gRPC transport
authorization and release approval remain open. The wheel used is retained
under `/private/tmp/kokonut-sdk-proto-artifacts/`. See the [Batch 5
checklist](batches.md).

## Phase 7 TypeScript gRPC package proto boundary — 11 October 2026

Source inspection found that the TypeScript gRPC clients searched for proto
files relative to a repository checkout, while the npm package published only
`dist/`; an installed package therefore could not load either service
definition. The package now copies the Data/Ecocredit proto files and their
pagination/type imports into `dist/proto` during build, and both clients resolve
definitions relative to that package-owned directory. `prepack` performs a
clean build so npm archives include those assets. Removed the unused
`@bufbuild/protobuf` runtime dependency and Buf generation step; this client
uses `@grpc/proto-loader` directly. The first npm archive listing included
Vitest output under `dist/__tests__`, so the TypeScript build now excludes test
sources. `npm pack --dry-run --json` then completed its clean build and listed
23 files, including all five proto files and no test output. The default npm
cache is root-owned on this machine, so the archive preflight used a temporary
cache under `/private/tmp/kokonut-typescript-npm-cache/`. No test suite,
installed-package import, API/RPC call, or publish ran. Runtime acceptance and
Python/TypeScript API parity remain open. Roll back the package copy script,
client paths, build exclusions, lifecycle/dependency edits, and this
documentation together. See the [Batch 5 checklist](batches.md).

## Phase 7 TypeScript gRPC isolated npm package import check — 11 October 2026

Created the 1.0.0 npm tarball with its clean `prepack` build, extracted it into
`/private/tmp/kokonut-typescript-sdk-import-check-20261011/`, and resolved
`@grpc/grpc-js` and `@grpc/proto-loader` from the existing local dependency
installation. Constructing both `DataServiceClient` and
`EcocreditServiceClient` loaded their package-bundled proto definitions and
exposed the expected `generateIRI` and `classes` methods; both clients closed
successfully. No RPC/API call or test suite ran. This validates package import
and proto loading for this local artifact/dependency combination, not
server/client API parity or a published registry install. The tarball and
extracted package remain under the temporary path above. See the [Batch 5
checklist](batches.md).

## Phase 7 Python/JavaScript SDK pagination parity — 11 October 2026

Static comparison of the generated native v1 path maps found the same five
OpenAPI operation IDs and route templates in both REST SDKs. The legacy Directus
SDKs differed in pagination: JavaScript treated `0` as absent, defaulted an
offset without a limit to 100 rows, and let `page` override offset; Python
preserves explicit zero values, converts offset only when a limit is supplied,
and gives offset precedence. JavaScript now follows those rules and rejects a
zero limit paired with offset before it can emit an infinite page value. The
TypeScript build passed. No suite, runtime import, HTTP request, or live API
parity check ran; these remain separate acceptance gates. See the [Batch 5
checklist](batches.md).

## Phase 7 JavaScript REST SDK isolated package import check — 11 October 2026

Packed the `@kokonut-intelligence/sdk` 0.1.0 artifact (27 files) and extracted
it to `/private/tmp/kokonut-javascript-sdk-import-check-20261011/consumer/`.
The isolated consumer resolved `@directus/sdk` from the existing local
dependency install, imported the package's ESM entry point, and instantiated
both `KokonutClient` and `KokonutPublicApiClient`. Expected method groups and
the exported `PublicApiError` were present. A guarded fetch implementation
recorded zero HTTP calls. No test suite, live request, or API response parity
check ran. This closes local package import acceptance for this artifact and
dependency combination; full Python/JavaScript API behavior parity and release
approval remain open. See the [Batch 5 checklist](batches.md).


## Phase 7 Python/JavaScript offline API parity — 11 October 2026

Ran both SDKs against injected fake HTTP adapters, with no network or live API
calls. The probe covered all five generated v1 reads (location list/detail,
metrics, published CRISP, and location summary), including special-character
path IDs, `Accept` and API-key headers, response field values, and error cases
for malformed envelopes, error payloads, and invalid JSON. Python returns date
and datetime objects while JavaScript preserves the equivalent ISO wire strings.
The probe also captured Directus list queries for missing limits, offset/page
precedence, and zero-limit offset handling.

The comparison exposed and fixed inconsistent URL-component escaping, permissive
JavaScript handling of `data: null`, different malformed/error fallback
messages, Python's uncaught successful-response JSON error, and Python's divide
by zero for offset pagination with a zero limit. JavaScript now matches Python's
strict path escaping and response-envelope rules; both SDKs now report consistent
public API errors and reject zero-limit offset pagination before a request.
`npm run build` passed, and the rebuilt 27-file JavaScript npm artifact passed
the same consumer-side probes. The 6 D / 4 P / 56 B / 0 accepted capability
counts do not change: live Gateway route/auth behavior, tenant scope, and wider
SDK parity remain open. See the [Batch 5 checklist](batches.md).

## Phase 7 operations-console identity boundary — 11 October 2026

Initial repository inspection found no first-party operator web app. The Cloudflare
edge preview is synthetic-only and disconnected from KI APIs; the mobile
Field Collector is not an operator surface. The Gateway currently authenticates
protected routes with API keys or capability tokens, and treats the configured
Directus admin token as full access. It has no human browser session or
federated identity adapter. Those credentials must not be embedded in a browser
bundle. Documented a replaceable operator identity/session port, tenant and
location scope rules, stable audit actor requirements, same-origin/CSRF
boundary, a read-only first console slice, likely files, acceptance, and
rollback in [the console contract](kernel-operations-console.md). Split the
Batch 5 checklist into completed boundary documentation and pending provider
selection/implementation. No code, credentials, CORS settings, or runtime state
changed; no tests or runtime probes ran. The identity source is a product choice
before implementation; the contract recommends provider-neutral OIDC so
Directus remains optional.

## Batch 5 mobile access boundary review — 11 October 2026

Read `services/mobile/api.py`, migrations 139/215/320/322/357/358, and the
Field Collector vault. The current mobile path derives device/user/location from
the consumed enrollment and active hashed device token; it binds media uploads
and references to device, location, client ID, status, and expiry. Anonymous
forms are active public global forms; enrolled devices can read active global
and their assigned-location forms. `offline_collection` has no `party_id`,
consent event, or tenant ID, and mobile `user_id` has no enforced mapping to the
canonical party-based consent ledger. Sync also does not validate provided
form ID/version/type against an active form. Documented the boundary and these
gaps in [mobile access contract](mobile-access-contract.md), and corrected the
mobile README's migration status: schemas 357/358 are in the local candidate's
applied migration set, without enabling local media or changing legacy,
staging, or production. No runtime probe or test suite ran. No consent/form
policy or schema behavior changed. Rollback only the candidate mobile profile or
revert any future implementation; preserve encrypted media and key custody.

## Batch 5 mobile consent and form enforcement — 11 October 2026

The owner approved collector/participant separation, reviewer-managed location
links, canonical append-only consent checks, immutable form revisions, and
private review handling for known retired revisions. Added migration 381 source
with immutable snapshots, explicit `unclassified`/`required`/`not_required`
policy state, reviewed policy provenance, hashed participant references,
collection validation fields, and a dynamic eligibility view that blocks later
use after withdrawal. The mobile API now lists revision snapshots, rejects
unknown/mismatched revisions, checks exact consent at collection and sync for
classified required forms, and routes retired revisions only to review. The
browser stores participant references in its encrypted queue and does not
create consent from a checkbox. Gateway link creation/revocation is
location-scoped and uses OIDC session/CSRF/grants when OIDC is enabled.

All five current form revisions remain `unclassified`, so records stay private
and none receives inferred consent. The source migration was not applied; no
containers, databases, or test suites were run. Per-form classification, human
retention/erasure disposition, tenant/RLS policy, and mobile acceptance remain
open. CAP-053 remains partial; see the [contract](mobile-access-contract.md)
and [batch checklist](batches.md).

## Batch 5 HTTP sensor deployment contract — 11 October 2026

Reconciled `http-sensor-overlay.md` against the Compose service,
`http_sensor_receiver.py`, and `http_sensor_limits.py`. Documented private-only
port exposure, HMAC/device checks, 10 KiB single and 256 KiB batch limits,
ten-second body deadline, per-reading transaction/duplicate semantics, and
single versus batch retry behavior. Linked the earlier isolated receiver
listener/CSV/outbox evidence and clarified it did not enable the optional Compose
overlay. The overlay itself has not been built or started; runtime identity,
health, grant, timestamp, shutdown, and public-ingress gates remain open. No
source/runtime behavior changed and no test suite ran. Rollback remains removing
only the `http-sensors` overlay service; preserve database/outbox/device state.

## Batch execution — 10 October 2026

[Six-batch checklist](batches.md). **Batch 1 complete:** matching AMD64/ARM64
minimal artifacts now bundle source inventories and the public relation readiness
gate. [Build evidence](builds/2026-10-10-batch1/README.md). Running images are unchanged.
No new capability acceptance gates closed; counts remain 6 D / 4 P / 56 B / 0 accepted.
**Current batch: 2 — scoped PostgreSQL restore complete; legacy storage preservation
and populated/provider recovery gates remain in progress.**

### Batch 2 preparation update — 10 October 2026

Read-only aggregates recorded for five legacy stores; anonymous Redis and broker
log volumes now have explicit owners. Added a scoped age-encrypted PostgreSQL
checkpoint script, standalone recovery Compose destination, retention/restore
procedure and Adelphi fixture outline. [Evidence and gaps](recovery-preparation.md).
Shell syntax and Compose parsing passed; no checkpoint/restore or test suites ran.
Batch 2 remains in progress; full provider ownership and recovery acceptance open.
Running deployments unchanged; capability acceptance counts unchanged.

### Batch 2 scoped recovery performed — 10 October 2026

Portability PostgreSQL encrypted checkpoint restored successfully into a fresh,
isolated database. All 364 migration fingerprints, extension versions and eight
selected aggregate counts match. Selected workload/media tables are empty; active
work and media recovery remain unproven. Stopped legacy Redis/broker files archived
with age encryption; logical session/message inventory and archive restore pending.
Recovery container stopped with volume retained; source deployments unchanged.
[Retained evidence](builds/2026-10-10-recovery/README.md). No acceptance suites run. Batch 2 stays open
for complete provider ownership, independent backup copy and populated recovery.

### Batch 2 legacy preservation — 10 October 2026

All ten locally attached legacy volumes and selected configuration captured in
a finalized age-encrypted archive; source containers remained stopped. Sizes and
image/volume mappings retained. External-setting presence inspected without values;
no configured Prefect/mobile storage settings found in the inspected local scope.
[Preservation scope and restore procedure](legacy-storage-preservation.md). Logical provider
state and populated job/media recovery remain open; no capability acceptance closed.
User deferred independent R2 production backups and authorized a local development
mirror under backups/development-mirror/. Same-disk copies are not independent
production protection. Running Kernel services unchanged; no test suites ran.

Local development mirror completed with matching ciphertext/metadata SHA256;
independent production backup remains deferred to the release batch.

### Batch 2 provider clone inventory — 10 October 2026

Isolated copied Redis/PostgreSQL engines loaded successfully: Redis has four string
keys without expiry; Metabase contains 39 cards and one dashboard. Four PostgreSQL
databases and globals captured into age-encrypted logical archives, with matching
development mirror checksums. Broker clone counters are ambiguous/anomalous and
do not certify application backlog. [Evidence and limits](provider-clone-inventory.md).
All clones stopped; original legacy services/storage unchanged. No test suites ran.
Batch 2 remains open for populated recovery, provider semantics and logical archive
restore. No capability acceptance counts changed.

### Batch 2 populated legacy database restore — 10 October 2026

All four legacy logical archives restored into fresh isolated databases on the
compatible recorded image. Counts and whole-row comparison fingerprints match for
13 selected tables, including populated events, sensors, weather, wallets,
attestations and Metabase cards/dashboard. [Restore evidence](legacy-logical-restore.md).
Both recovery engines stopped and volumes retained. Original legacy and running
Kernel deployments unchanged. Globals/grants were not applied; no active workload
or uploaded media exists in the selected source. Batch 2 remains open for those
recovery gates, broker/ClickHouse and external ownership. No acceptance suites ran
and no complete capability acceptance counts changed.

### Batch 2 analytics and broker inventory — 10 October 2026

Compatible isolated ClickHouse copy loaded: 34 analytics objects in default, zero
active non-system rows/parts, expected kokonut_analytics empty. Schema definitions
encrypted and mirrored; complete object metadata retained. Original broker file
scanned offline: version 6, one configuration chunk, zero message/client/subscription
chunks. [Evidence and limits](analytics-broker-recovery.md). Original services remain stopped;
ClickHouse clone stopped with volume retained. No acceptance suites ran. Full
analytics output/restore and transport recovery remain open; capability counts
unchanged. Redis semantics, active work/private media and permissions still pending.

### Batch 2 work/media recovery preparation — 10 October 2026

Added quiesced local-media checkpoint and exclusive staged restore commands, with
ciphertext/object hashes, database checkpoint binding and secret custody labels.
Defined exact isolated lease/window/event/delivery/dead-letter/device/media fixture.
[Commands, fixture and gates](work-media-recovery.md). Both scripts passed Ruff; no media
commands, fixture records or acceptance suites executed. AES/key/DB-reference
authentication and active-work recovery remain open. Running deployments unchanged.

### Batch 2 guarded fixture preparation — 10 October 2026

Added standalone private fixture deployment and guarded transactional disabled
durable-work seed loader. Checks dedicated project/image/volume/network/roles and
all bundled migration checksums before insertion. [Setup and limits](recovery-fixture-setup.md).
Ruff and Compose parsing passed. Deployment not started, SQL not applied, no
acceptance suites run. Device/media loader and exercised recovery gates remain
open; no phase/capability acceptance counts changed.

### Batch 2 device/media loader preparation — 10 October 2026

Added authenticated two-object synthetic media loader and transactional device/
collection/reference seed. Shared full target/schema guard extracted for both
loaders. AES-GCM associated-data, JPEG size/hash and exact scope validated before
insertion; no device/enrollment authority minted. [Inputs and limits](recovery-media-fixture.md).
Ruff passed. No fixture provisioned or SQL applied; acceptance suites not run.
Paired recovery, stale ownership, replay/disposal and enrollment/consent remain open.

### Batch 2 exercised synthetic recovery — 10 October 2026

With explicit user authorization, provisioned the private fixture and restored
364 checksummed schema records. Applied disabled work and two authenticated
synthetic media records. Captured a quiesced paired encrypted DB/media checkpoint;
restored DB into fresh `recovery_roundtrip` and media into an unused private directory.
All 12 selected whole-row count/fingerprints match. Both restored objects authenticate
with the separately age-encrypted development AES key. Wrong key, changed associated
data, duplicate work/media seeds, reused restore destination and capture without
quiescence were rejected. Actual scheduler code recovered the expired lease,
retained its original window, advanced retry to 2 and rejected stale completion;
no job dispatched. Fixture stopped after checks; volumes and checkpoints retained.

[Sanitized results](builds/2026-10-10-recovery/fixture-roundtrip.json).
Backups/key custody: ignored `backups/recovery-fixture-20261010/`; the key itself
is only persisted as `media-key.age`. This is a local development recovery exercise.
Live enrollment/consent, handler effects/replay/disposal, role/grant policy,
external provider ownership, production/Pi certification and full recovery acceptance
remain open. Batch 2 stays active; no capability is fully accepted.

### Batch 2 event recovery exercised — 10 October 2026

After the host restart, started only the retained private recovery fixture for
this slice. Host project/image/volume/network/schema guard passed. Eight synthetic
event checks passed against real PostgreSQL: expired lease reclaim/stale owner
rejection; successful delivery skipped on retry; bounded retries to dead letter;
audited replay with duplicate rejection and successful-delivery preservation;
orphan replay rejection; operator identity/reason requirements; audited disposal
with duplicate rejection. Handler invocation used controlled outcomes; no domain
handler or external effect ran. Synthetic handlers disabled again on exit.

[Evidence](builds/2026-10-10-recovery/fixture-events.json).
Reproducible guarded launcher: `bash scripts/kernel-recovery-event-checks.sh`
after loading encrypted secrets and starting the fixture. This mutates the exact
seeded event fixture and is intentionally not repeatable against completed state:
restore the retained pre-exercise checkpoint into a separately reviewed fresh
fixture before another run. Never rerun its seed into existing work tables.
The first attempt stopped before claiming work because a check assumed no standard
handler registrations; corrected to inspect the synthetic event type only.

Fixture stopped afterward; volumes/backups retained. Legacy stack remains stopped.
Candidate services restarted automatically; portability services remain stopped
following the host restart. No deployment promotion occurred.
Actual handler side effects/idempotency, child-process timeouts, concurrent workers,
roles/grants and provider ownership still require evidence. Batch 2 remains active;
no capability becomes fully accepted.

### Batch 2 legacy authorization recovery — 10 October 2026

Read-only metadata from all four isolated source databases excludes password hashes.
One custom role (`kokonut`) is superuser with create-role/create-database,
replication and bypass-RLS privileges. No custom memberships, default ACLs or
row-security tables were found. Ownership and explicit object ACLs matched all
four logical restores. Main database schema ACLs initially differed because
no-privileges dumps omit grants. Rehearsed two explicit schema grants only on
the isolated logical restore; all selected main-database catalog fields then matched.
Both recovery clones stopped; original databases and encrypted globals unchanged.

[Inventory](builds/2026-10-10-recovery/legacy-authorization.json),
[before comparison](builds/2026-10-10-recovery/legacy-authorization-comparison.json),
[grant rehearsal](builds/2026-10-10-recovery/legacy-authorization-grants-rehearsal.json).
Recovery compatibility policy: create the recorded database owner under private
operator custody, restore no-owner/no-privileges archives, review source catalog
metadata, then apply only explicitly reviewed grants. Never replay encrypted
globals blindly or print their credentials. The isolated SQL fixture is not a
production migration and must not be added to ordered schema files.

Production policy remains open: separate migration/operator and runtime roles,
restrict privileges to actual service needs, and verify runtime denial of DDL,
role creation and unrelated databases alongside required domain workflows.
Legacy superuser parity does not satisfy that gate. Batch 2 remains active.

### Batch 2 Redis ownership assessment — 10 October 2026

Inspected the retained no-network Redis clone without printing key identities or
values. Four db0 string keys have no Redis expiry. Three are source-mapped against
the exact retained Directus image: two API request telemetry counters and one
collaboration instance registry. These are not evidence of governed domain state
or queued jobs. One opaque key remains unclassified; retain the encrypted RDB and
original volume, and leave Redis retirement blocked pending its ownership review.

[Sanitized evidence](builds/2026-10-10-recovery/redis-ownership.json).
Pinned source paths: `middleware/request-counter.js`,
`telemetry/counter/use-counters.js`, `websocket/collab/messenger.js`,
`websocket/collab/store.js`, `utils/store.js` in the retained Directus image.
Telemetry counters stay archived; they must not become native rate-limit state.
Collaboration presence is runtime state: archive it, reconnect clients and recreate
instance identity when restoring the optional adapter. Do not import stale
presence into Kernel domain tables. No Redis keys deleted or rewritten; clone stopped.

Kernel computation cache remains PostgreSQL-backed (`services/cache/cache.py`),
and native gateway rate-limit state has its own provider boundary and PostgreSQL
schema. Directus Redis settings remain optional-adapter concerns; clustered Directus
cache/collaboration/limit behavior still needs adapter acceptance before changing
its deployment. Source mapping is not live Redis-free Directus certification.
Batch 2 remains active; no capability promoted to fully accepted.

### Batch 2 final Redis key mapped — 10 October 2026

All four retained db0 keys now have source-backed owners. The remaining `rlflx`
namespace is the pinned rate-limiter-flexible default. Directus authentication
constructs a limiter with `duration: 0` and consumes by `user.id`; privately matched
the retained UUID to `directus_users` in the isolated legacy PostgreSQL clone.
Only a boolean match is retained, with hashed key identity; no UUID or counter
value is published. This is a persistent failed-login counter, not disposable
cache or native gateway rate-limit state. No source keys/grants/data modified.
Both recovery clones stopped after inspection.

[Updated evidence](builds/2026-10-10-recovery/redis-ownership.json).
Redis ownership inventory is complete for the retained local snapshot. Retirement
remains open: optional Directus must preserve this security counter in compatible
Redis state, or use an explicitly reviewed transfer/reset policy with login lockout
acceptance checks. Native gateway token buckets do not replace failed-login policy.
Do not clear Redis wholesale or promote a Redis-free Directus deployment based
on the telemetry/presence classifications. Original volume and encrypted archives
remain the rollback source. Live lockout behavior and provider parity remain open.
Batch 2 stays active; no capability fully accepted.

### Batch 2 ClickHouse database reconciliation — 10 October 2026

Found the bootstrap selecting no database while repository SQL uses unqualified
object names. Legacy objects therefore reside in `default`, whereas service
clients/analytics profiles select `kokonut_analytics`. Corrected `scripts/seed.sh`
to validate a simple `CH_DB` identifier and explicitly select it for readiness
and schema application; no historical SQL files edited. Shell syntax passed.
In the isolated retained clone, the configured database was empty. Applied all
six repository schema files twice successfully, creating 34 objects; default
name/engine/row inventory unchanged. This is a rehearsal, not deployment promotion.

[Bootstrap evidence](builds/2026-10-10-recovery/clickhouse-target-bootstrap.json).
A synthetic sensor projection inserted values 10,20 and then 30 in separate blocks.
Raw and summary counts equal 3, but sum of per-block summary averages is 45 versus
raw average 20. `mv_daily_sensor_summary` uses SummingMergeTree with ordinary
average/min/max/uniq outputs; those statistics cannot safely be summed across
blocks. This is a failed analytics parity gate, not an accepted projection.
[Projection evidence](builds/2026-10-10-recovery/clickhouse-sensor-projection.json).

Batch 4 must introduce versioned corrected rollups using aggregate states or
sum/count plus proper min/max/distinct aggregates, audit all analogous views,
rebuild from retained raw data with explicit backfill, update consumers, and
exercise multi-block/merged output against PostgreSQL queries. Preserve old
views/data until parity passes; never silently replace their definitions.
Legacy physical application tables had zero rows, so no populated historical
transfer was inferred. New synthetic rows exist only in the recovery clone;
clone stopped afterward. Original legacy storage and running deployments unchanged.
Batch 2 remains active for external ownership and remaining recovery gates.

### Versioned sensor rollups exercised — 10 October 2026

Added schema 007 with aggregate-state materialized views and finalized v2 daily/
rate read interfaces; historical schemas/views unchanged. Isolated quiesced
backfill, subsequent separate blocks and FINAL merge outputs match raw aggregates
for all fields, including exact distinct sensors/locations and suspect readings.
No deployment promotion or consumer switch. [Migration, rollback and evidence](sensor-rollups-v2.md).
Batch 2 stays active; PostgreSQL/outbox/dashboard parity and other rollups remain open.

### Remaining analytics rollups corrected — 10 October 2026

Audited all 11 materialized definitions in schemas 002/003/006. Added versioned
raw read interfaces in schema 008 for monthly distinct wallets, both Digital Lego
rollups with missing merge-key dimensions, and remote-sensing non-additive
statistics. Historical definitions retained. Reapplication, separate-block fixtures,
nullable statistics, dimension preservation and before/after FINAL merge checks
passed in the isolated clone; clone stopped. [Interfaces, audit and evidence](analytics-read-views-v2.md).
No saved dashboard switch, running deployment promotion or full analytics acceptance.
PostgreSQL/outbox parity and raw-view resource measurements remain open.

### Durable outbox recovery exercised — 10 October 2026

Hardened enqueue: a reused event key requires identical hash, source/target,
columns and rows; conflicting projection raises for caller rollback. Completion
now requires an unexpired lease as well as owner/token. No SQL migration changed.
Seven PostgreSQL-backed isolated checks passed: caller rollback, matching-key
idempotency/conflict rejection, paused-provider retry preservation, expired lease
reclaim/stale completion rejection, eight-attempt dead letter, replay/duplicate
rejection and successful delivery not reclaimed. Ruff passed.
[Evidence](builds/2026-10-10-recovery/fixture-outbox.json).

Execution used pinned fixture operator plus a read-only mount of changed outbox
source; this does not certify the unchanged deployed image. Fixture retains one
synthetic succeeded outbox record; check intentionally refuses nonempty outbox
on rerun. Recovery checkpoint and volumes retained; fixture stopped afterward.
Transport results were controlled: no live ClickHouse driver delivery or
PostgreSQL-v2 output parity claimed. Cross-store crash after insert/before ack can
still duplicate analytics rows; requires explicit delivery identity and proven
sink deduplication/reconciliation. Outbox replay currently lacks actor/reason audit
and needs alignment with event dead-letter governance before acceptance.
Batch 2 stays active; these are preparatory Batch 4 durability checks.

### Outbox operator auditing exercised — 10 October 2026

Added ordered schema 374 and atomic audited replay/disposal with required actor/
reason, retained attempts/hash and duplicate rejection. Explicit host migration
runner applied one migration to fixture only (365 schemas); four isolated checks
passed, including forced audit insert failure rolling back state. Ruff passed.
[Interfaces, deployment and rollback](outbox-operator-audit.md).
Initial attempt to invoke the Compose-based migration CLI inside the operator
failed because Docker is absent there; no migration applied in that attempt.
Host invocation with explicit fixture selection succeeded. Running images unchanged.
Recovery fixture stopped and records retained; full operator role/identity policy,
concurrent actions and live sink crash deduplication remain open. Batch 2 active.

### Live outbox recovery exercised — 10 October 2026

Fixed ingestion CH_DB selection and JSON-persisted payload transport; added stable
insertion tokens/bounded raw-table block windows and NULL sensor plot handling.
Real driver crash-before-ack replay passed against new raw sensor v3 read views;
three outbox payloads yield three raw rows, average 20. V2 materialized summaries
failed replay parity even with dependent-view setting; failure slices retained.
[Exact limits, failure evidence and deployment](live-outbox-recovery.md).
Fixture roles stopped afterward; production/legacy unchanged. Canonical domain
source ingestion, restarts/concurrency/window eviction and full parity remain open.
Batch 2 stays active. Earlier sensor-v2 arithmetic checks did not cover this crash
case; v3 now supersedes v2 as the recommended sensor read interface.

### Canonical sensor ingestion recovery — 10 October 2026

Transactional producer now projects stored PostgreSQL precision/unit and actual
reading UUID through the shared outbox helper; enqueue failures propagate. Same
sensor/timestamp conflicting value/quality is rejected. Five real PostgreSQL/live
ClickHouse checks passed, including source rollback, retry identity and v3 parity.
Ruff passed. [Evidence, migration/rollback and limits](canonical-sensor-recovery.md).
Fixture roles stopped; running deployment unchanged. Legacy hash-keyed projections
require reconciliation before producer promotion; full CSV/HTTP, concurrent source
writes and field device authority remain open. Batch 2 still active.

### Batch 2 single-reading sensor path — 10 October 2026

Ran the normal `run_single` producer in the isolated recovery fixture. Two source
rows, platform events, distinct succeeded outbox records, raw ClickHouse rows and
the v3 daily summary match. The first post-delivery read did not see the rows in a
five-second window; a later read-only verification confirmed parity. No latency
guarantee is inferred. [Scope and evidence](sensor-entrypoint-recovery.md).
Ruff passed; no Python acceptance suite ran. Both fixture services stopped with
volumes retained. Legacy lineage, CSV/HTTP, handler effects, concurrency/restart,
operator authorization and dashboard parity remain open; Batch 2 stays active.

### ClickHouse first-read visibility trace — 10 October 2026

Sanitized query-log evidence confirms both inserts and 44 immediate reads used
`kokonut_analytics`; inserts and reads reported no exceptions. The reads found no
rows within five seconds, while a later query found both sensor-date rows. Effective
settings had async inserts and query cache disabled, so those factors do not explain
the delay. Root cause and delivery-visibility contract remain open; no latency
guarantee or capability acceptance is inferred. [Evidence](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json).
The isolated analytics service is stopped with volumes retained; no application
deployment changed.

### Batch 2 CSV and authenticated HTTP sensor entrypoints — 10 October 2026

Fixed FastAPI route annotation resolution and added HTTP `sensor_reading` event
publication through the shared event-store adapter in the source/outbox
transaction. Isolated rehearsal accepted two CSV rows and three authenticated
HTTP rows; rejected one malformed timestamp and an invalid HMAC with 401. Five
source rows produced five pending platform events and five succeeded outbox rows.
Raw ClickHouse rows and the v3 location/day/type summary match. The first read was
immediate; the earlier delay remains unexplained. [Evidence and limits](sensor-entrypoint-recovery.md).
Ruff and diff checks passed; no Python test suite ran. At that point, event handlers
remained unprocessed, and HTTP used in-process ASGI rather than a network listener.
Batch 2 remains active; CAP-040 stays P.

### Batch 2 selected sensor handler and receipt recovery — 10 October 2026

Processed only the synthetic low-moisture `sensor_reading` event in the isolated
fixture. Runtime execution exposed and fixed three handler defects in
`services/ingestion/anomaly_detector.py`: UUID/text comparison in the device lookup,
a missing current-value argument for rate-of-change evaluation, and a UUID-valued
alert-event JSON field. The bounded retry completed with one warning alert at
reading 10; three earlier failed attempts remain in the durable delivery/log history.
After a controlled return to processing with a new lease owner, the successful
handler receipt skipped re-execution: attempt/log/alert counts did not change. Four
sibling sensor events remain pending and the generated `sensor_alert` event remains
pending. SMTP, Directus and actuator outputs were disabled. [Sanitized evidence](builds/2026-10-10-recovery/sensor-handler-recovery.json).

This is a controlled receipt-recovery simulation, not a process-kill, concurrent
worker, or queue-wide run. No schema migration or pytest suite ran. After evidence
capture, only the fixture database was stopped; analytics stayed stopped and the
volumes/checkpoint were retained. The HTTP listener/proxy, broader handler behavior,
legacy lineage, runtime-role policy, restart/concurrency, dashboards and full
provider recovery remain open. Batch 2 continues; CAP-040 stays P.

### Batch 2 HTTP listener over the isolated network — 10 October 2026

Before writes, created encrypted PostgreSQL checkpoint
`backups/recovery-fixture-pre-http-listener-20261011T024804Z` (restore not
rehearsed). Ran the actual receiver in a temporary operator container and sent
requests from a second container on the fixture's internal Docker network; no host
port was published. Health returned 200, invalid HMAC returned 401, authenticated
single and two-item batch requests succeeded, a repeated reading returned duplicate,
and a signed URL/payload device mismatch returned 400. PostgreSQL shows three
distinct source readings, three pending `sensor_reading` platform events and three
pending ClickHouse outbox rows. No ClickHouse worker or event handler ran. The
temporary credential was removed and the synthetic device restored to inactive.
[Sanitized evidence](builds/2026-10-10-recovery/sensor-http-listener.json).

The request assertions completed; the probe's final report-file write failed because
its host temp path was not mounted into the client container. Uvicorn access logs
and a separate read-only SQL query confirmed the HTTP status codes and persisted
counts. Pydantic v2 emitted deprecation warnings for `.dict()` calls, without
affecting the requests. TLS, proxy, host-published ingress, concurrent requests,
ClickHouse delivery and handler execution remain open. The encrypted checkpoint
and fixture volumes are retained; the fixture database and legacy stack are stopped.
Batch 2 remains active; CAP-040 stays P.

### Batch 2 retained local sensor lineage reconciliation — 10 October 2026

Read-only inspection of the isolated, no-network legacy PostgreSQL recovery clone
found 15 sensor source rows with 15 distinct reading IDs and zero ClickHouse
outbox rows. The retained ClickHouse inventory has zero physical rows in
`default.sensor_readings`. No historical local projection needs re-keying or
replay beside the canonical UUID-keyed producer. This does not establish remote
or unarchived sink state; any populated external target still requires independent
source/sink reconciliation before promotion. The clone was stopped after
inspection; no sensor values or original source/archive data were changed.
[Sanitized evidence](builds/2026-10-10-recovery/legacy-sensor-lineage.json).

This closes only the retained local snapshot lineage item. Batch 2 remains active;
CAP-040 remains partial while TLS/proxy, concurrency/restart, broader handlers,
external target ownership, dashboard parity and full transport acceptance remain
open.

### Batch 2 HTTP listener ClickHouse follow-up — 10 October 2026

Created an encrypted PostgreSQL checkpoint before changing fixture delivery state
and verified it by decrypting to `/dev/null`; restore remains unrehearsed. A
read-only query confirmed the three target sources were created after the exact
pre-listener checkpoint timestamp. In the isolated recovery deployment, the
existing outbox function claimed only the three canonical HTTP listener projections; all
three succeeded on attempt one. ClickHouse has one exact-value row at each source
timestamp. Three unrelated ready outbox rows were held only for batch scoping and
their original availability times were restored.

A broad per-device pending-event count initially included older fixture events. A
read-only follow-up keyed by the three source UUIDs confirmed all three listener
events remain pending with no handler deliveries or logs. No event processor ran.
The database and analytics containers were stopped with volumes retained. [Sanitized
evidence](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json).

This completes only the synthetic listener-to-ClickHouse projection slice. Batch 2
remains active; CAP-040 remains partial while TLS/proxy, restart/concurrency,
broader handler behavior, external target ownership, dashboard parity and full
transport acceptance remain open.

### Optional Kernel Caddy localhost TLS check — 10 October 2026

Validated the pinned Caddy configuration and exercised HTTPS against the existing
healthy candidate app from a private Docker network. The explicit local CA and
`localhost` hostname validated; `/health` returned 200, HTTP redirected with
308, the three configured security headers were present, and an unauthenticated
unknown route remained 401. The local certificate remained usable after
container recreation with its dedicated volume retained. The final proxy had no
host port bindings; the existing candidate app retained its prior loopback
8098 binding and was not rebuilt or restarted. The legacy stack remained
stopped. Normal gateway access auditing ran for the HTTPS requests; no domain
records or migrations were written. [Scope and evidence](kernel-proxy.md),
[sanitized result](builds/2026-10-10-recovery/kernel-proxy-runtime.json).

An initial disposable Compose attempt retained the default loopback mappings
because `ports: []` merged instead of resetting; it was stopped before probe
traffic. The corrected resolved model used `!reset []` and was verified to have
no host bindings. This check does not cover public ingress, mobile/upload parity,
header spoofing/audit identity, CORS, rate limits, or production certificate
recovery. CAP-040 and Phase 6 remain partial.

### Optional Caddy forwarded-header audit identity check — 10 October 2026

Through the private Caddy proxy, sent one request to a unique unknown route with
forged `X-Forwarded-For`, `X-Real-IP`, and `Forwarded` values. The gateway
returned 401. A read-only query restricted to that exact request path found one
denied audit row whose IP matched the Caddy container's upstream peer address
and none of the supplied addresses. This confirms the selected single-hop
Caddy path honors the gateway's `proxy_headers=False` behavior. The synthetic
denied access-audit record intentionally remains in the candidate database; no
farm/sensor domain data or schema changed. [Evidence](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json).

This does not define trusted client IP handling for other ingress layers or
multiple proxy hops, and does not validate rate limiting or public exposure.
Phase 6 and CAP-040 remain partial.

### Optional Kernel Caddy loopback-published ingress check — 10 October 2026

The first host-level HTTP probe found that Caddy's default HTTPS redirect
omitted the nonstandard published TLS port. Updated the Kernel Caddy config to
redirect through `KOKONUT_KERNEL_HTTPS_PORT` (default `8448`) and passed that
setting into the proxy container. After recreating the proxy, the host-published
HTTP endpoint at `127.0.0.1:8088` returned 308 to
`https://localhost:8448/health`; following it with the local CA explicitly
trusted and hostname verification enabled returned 200. The container bound
both ports only to `127.0.0.1`. [Evidence](builds/2026-10-10-recovery/proxy-loopback-ingress.json).

The existing candidate app and database were not rebuilt or restarted; the
legacy stack remained stopped. The health request traversed gateway middleware,
but audit persistence was not queried. No domain writes or migrations were
issued. The temporary proxy project and volumes were removed. Non-loopback or
public ingress, mobile/upload parity, CORS, rate limits, multi-hop trusted
proxies, and production origin/cookie behavior remain open. Phase 6 and CAP-040
remain partial; no pytest suite ran.

### Optional Kernel Caddy configurable HTTPS port check — 10 October 2026

Used a separate temporary Compose project with HTTP `18088` and HTTPS `18448`.
Compose published both ports only on loopback and passed `18448` into Caddy.
HTTP redirected to `https://localhost:18448/health`; the CA-verified,
hostname-verified follow-up returned 200 after one redirect. This checks that
the environment override stays aligned between Docker port publication and
the redirect. The candidate app/database were reused without restart; the
temporary proxy and its volumes were removed, and the legacy stack remained
stopped. [Evidence](builds/2026-10-10-recovery/proxy-custom-port.json). No
domain writes, migrations or pytest suites ran. Public ingress and the remaining
Phase 6/CAP-040 acceptance work remain open.

### Kernel gateway CORS preflight check — 10 October 2026

Read the active gateway's explicit localhost origin list and sent two direct
loopback `OPTIONS` preflights to `/health`. `http://localhost:3000` was allowed
for `GET` with `x-api-key`; `https://untrusted.invalid` received 400 without an
allow-origin header. The preflight path does not enter gateway audit/rate-limit
middleware. A separate reachability `GET /health` traversed normal middleware;
audit persistence was not queried. No farm/sensor domain writes or migrations
were issued. [Evidence](builds/2026-10-10-recovery/proxy-cors-preflight.json).
Authenticated response CORS, credentials, mobile/media paths, public origins
and rate limits remain open; Phase 6 and CAP-040 remain partial.

The follow-up CORS response probe sent two unauthenticated GETs to a unique
unknown path. Both returned 401; the configured origin received the matching
allow-origin header and the untrusted origin did not. A read-only exact-path
query found the two expected denied `credentials_required` audit rows, retained
in the candidate database. No domain data or schema changed. [Evidence](builds/2026-10-10-recovery/proxy-cors-auth-response.json).
At the time of the CORS probe, the running candidate image predates the new
rate-limit provider module, so no runtime result was claimed from that container.

### Kernel gateway rate-limit source-path check — 10 October 2026

At the time of this source-path check, the deployed candidate image predates
`services/gateway/rate_limit_backend.py`.
A disposable network-isolated container used the current workspace `services/`
as a read-only mount and injected a one-token in-memory limiter. A health GET
returned 200; configured-origin preflight still returned 200 after that token
was spent; the next GET returned 429 with `Retry-After: 100` and the configured
CORS allow-origin header. The audit method was monkeypatched to capture one
allowed 200 and one denied `rate_limited` 429 in memory. No candidate service,
database, persistent audit, domain data or schema was touched. [Evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json).

This proves only the current-source ASGI middleware path with injected test
settings. It does not certify deployed defaults, persistent audit, the
PostgreSQL shared adapter, concurrency, eviction/restart or multi-replica
behavior. Rebuild before runtime acceptance; Phase 6 and CAP-040 remain partial.
No pytest suite ran.


### Kernel gateway local limiter runtime and promotion — 10 October 2026

Rebuilt the candidate app image and ran an API-only canary on loopback port
18098 against the existing private candidate database. The configured provider
was `local`; current source defaults are 100 tokens with a 10-token/second
refill. A 2.766-second sequential burst allowed 127 `GET /health` responses,
then returned 429 with `Retry-After: 1` and the configured CORS origin. OPTIONS
preflight from that origin returned 200 after exhaustion; the next GET returned
429. A read-only query confirmed 127 allowed and two denied `rate_limited` audit
rows for the accepted probe, intentionally retained.

The rebuilt image was promoted to the active candidate app. It is healthy and
serves `/health` with the configured CORS header; the PostgreSQL container and
volume were not recreated. A credential-free filesystem rollback image was saved
before replacement. Exploratory probe rows are separately listed in the
[evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json).

This accepts only the single-process local limiter runtime. PostgreSQL shared
limits, concurrency, restart/eviction policy, multiple replicas, public ingress,
and broader authenticated/mutation CORS remain open. No migrations, domain
writes or pytest suites ran. Phase 5/6 and CAP-040 remain partial.

### Batch 2 GatewayAudit outage and recovery boundary — 11 October 2026

The initial isolated stop/restart probe characterized the pre-journal behavior:
the event attempted during downtime was absent after PostgreSQL returned, while
a new control event persisted. This is retained as historical baseline evidence
and is superseded by the implementation and recovery check below.
[Historical evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).

### Batch 2 bounded GatewayAudit journal and replay — 11 October 2026

Added a standard-library SQLite journal for failed audit writes, stable event
UUIDs and occurrence timestamps, idempotent PostgreSQL inserts, a 10,000-event
default queue cap, a 16 KiB event cap, private file checks, Compose named-volume
mounts, and a FastAPI startup/15-second replay worker. The real ASGI outage
request returned 503 with `Retry-After: 30` and queued one row. After replacing
the app container while retaining its volume, the startup worker replayed the
event once without another request, preserved `created_at`, and drained the
journal. The duplicate event ID remained one database row; a one-event
configured cap rejected a second enqueue; file mode was 0600.
[Implementation details](gateway-audit-spool.md), [sanitized recovery evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).

No migration or domain write occurred. The exact synthetic audit row, temporary
app containers and temporary spool volume were removed; the portability
database returned to its previous stopped state, and the active candidate was
not touched. No pytest suite ran. CAP-040 remains partial: saturation,
volume/host loss, encrypted retention and live-volume restore, candidate
activation, replica failover/scale and production ingress need separate
acceptance. The PostgreSQL rate-limit
provider remains opt-in; the active candidate continues to use local limits.

### Batch 2 audit journal checkpoint and crash recovery — 11 October 2026

Added `services.gateway.audit_spool_cli`, mounted as `services.cli audit-spool`,
for status, integrity verification, SQLite online checkpoint and restore to a
new path. The status command leaves an absent journal absent. In a private
synthetic fixture, a committed enqueue
survived abrupt writer-process exit; an uncommitted insert rolled back. A
checkpoint remained a consistent one-event snapshot after a second event was
added to the live source. Restore preserved the event ID, wrote mode 0600, and
refused to overwrite an existing destination. The source held two events after
the checkpoint; all temporary fixture data was removed.
[Runbook and limitations](gateway-audit-spool.md), [sanitized evidence](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).

This accepts only the CLI and local SQLite process-exit/checkpoint recovery
boundary. Encrypted retention/transfer, actual installation into a stopped
Compose volume, physical-device/power failure, external alert routing and
production retention ownership remain open. A separate temporary container from
the rebuilt portability image ran unified-CLI status with no database or spool
volume mounted. Checkpoint/verify/restore also ran in the temporary image
container with a private bind fixture; candidate containers stayed healthy and untouched.
[Image check](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json).
No migration, domain write or pytest suite ran.

### Batch 2 concurrent audit journal writers and online checkpoint — 11 October 2026

The first cold-start contention probe exposed a reproducible SQLite lock race:
3 of 8 processes failed during simultaneous WAL/schema initialization. Added
bounded retry with capped exponential backoff for transient `busy`/`locked`
initialization errors in `services/gateway/audit_spool.py`. After the change,
three cold-start runs each committed all 144 events from 12 writer processes
with clean integrity checks. Ten warm writers committed 201 events including a
seed event. A separate online checkpoint ran during active writes: all 8 writers
were still active when it returned, the checkpoint contained a valid 166-event
snapshot, and the source completed with 481 events. No writer errors occurred.
[Sanitized evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json).

Temporary fixtures were removed. No Compose stack, migration, domain write or
pytest suite was touched. This closes local SQLite process-contention coverage;
device/power loss, volume/host loss, external alert delivery, approved retention
and live-volume restore remain open. CAP-040 stays partial.

### Batch 2 audit journal saturation alert and write guard — 11 October 2026

Added an absolute queue alert threshold, defaulting to 80% of the configured
cap, and passed its override through the candidate and portability Compose
profiles. `services.cli audit-spool status` now reports count, cap, threshold,
alert and write-restriction state without printing records. `/health` reports
`audit_capture` as `ok`, `degraded` or `unavailable`. Before a non-read handler,
the middleware replays pending records, checks capacity and commits/removes a
small SQLite write probe. At/above threshold or on detected storage failure it
returns 503 with `Retry-After: 30` before handler execution. The guard logs a
state transition once per process; reads remain available.

In the private ASGI fixture, four of five queued records crossed a configured
threshold of four and the synthetic mutating handler was not called. Removing
one event allowed the handler to run. Removing a journal file after the process
had observed it, or pointing at a path whose parent was a regular file, blocked
the handler and reported unavailable. An injected `ENOSPC` probe error also
returned 503 before handler execution; no real disk was filled. The CLI kept an absent journal absent,
reported a 4/5 queue as alerting/restricted, and exposed no event payload. The
transactional capacity probe left no retained probe record. All fixtures were
removed; no Compose service, migration or domain row was changed. No pytest
suite ran. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json).

CAP-040 remains partial: physical-device/power failure, lost-volume detection
after process restart, external alert delivery, approved retention ownership,
cross-process/multi-worker admission races, live-volume restore and multi-replica
recovery remain open.

### Batch 2 audit mutation admission reservations — 11 October 2026

Added an in-process reservation around mutating gateway requests. Admission now
counts outstanding mutations against the journal threshold and holds each slot
through handler completion and audit capture; `finally` releases the slot after
both successful and exceptional handler paths. This prevents concurrent
requests in one gateway process from each claiming the same remaining headroom.

A private synthetic spool at 3/4 threshold admitted one of 32 concurrent thread
callers, released the reservation, and admitted a later call without changing
the three queued records. An ASGI fixture confirmed reservation → handler →
audit → release order on success and error. Ruff, compileall and diff checks
passed. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).

This is single-process admission evidence only. Cross-process/multi-worker
coordination was still open at that checkpoint. Queue pressure from concurrent
read/denial audits, power/device failure, external alert delivery and approved
retention remain open. No Docker service, database, migration or domain row was
changed; no pytest suite ran. CAP-040 remains partial.

### Batch 2 cross-worker audit reservations and stale-owner recovery — 11 October 2026

Moved admission reservations into SQLite transactions and tied them to private
POSIX advisory owner locks. Sixteen local worker processes sharing one journal
at 3/4 threshold admitted exactly one mutation. After a worker was terminated
with `os._exit` while holding a reservation, the next write preflight detected
the released OS lock, removed the stale reservation and admitted a new request.
ASGI fixtures confirmed successful and error audit events are queued before the
reservation is released; a synthetic outage also confirmed a later write is
blocked before its handler. A forked worker retained the parent's active
reservation under a distinct owner lock. An injected release-storage failure
was logged and its orphan slot was reclaimed on the next preflight. A health
read's own queued audit event demonstrated that read traffic can consume
remaining spool capacity.

Ruff, compileall and whitespace checks passed. [Evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json).
This covers local processes on one POSIX filesystem only. Multi-host filesystems,
independent replicas/failover, power/device failure, external alert delivery and
approved retention remain open. No Compose service, database, migration or
domain row was changed; no pytest suite ran. CAP-040 remains partial.

### Batch 2 concurrent event-handler effect — 11 October 2026

Restored the retained encrypted recovery checkpoint into a new private Compose
project on its recorded PostgreSQL image. Four separate operator containers
concurrently processed 16 synthetic `metric_computed` events in batches of four.
An in-flight query observed six completed and ten processing events across four
worker IDs. All workers finished four events each with zero failures. The real
allowlisted cache handler invalidated 16 marked analytics entries for one
synthetic location while preserving three sentinel entries for another. All 16
delivery receipts and logs succeeded on attempt one, and every event lease was
released. [Details](event-handler-concurrency.md), [machine evidence](builds/2026-10-11-recovery/event-handler-concurrency.json).

The Compose network was internal and published no host ports; the recovery
database is stopped with its volume retained. Candidate API/database containers
remain healthy and unchanged; legacy services remain stopped. One unrelated
expired synthetic event from the checkpoint was briefly deferred from the global
worker and its original lease timestamp restored exactly afterward. No migration,
domain record or external integration changed. The scoped probe helper passes
Python syntax and whitespace checks; no pytest suite ran. This adds one
concurrent cache-handler effect, not same-event retry/crash or exactly-once
external-effect evidence. Additional handlers, runtime-role policy, provider
ownership/recovery and CAP-040 parity remain open; Batch 2 stays active.

### Batch 2 CRISP cache-handler effect — 11 October 2026

Reused the isolated restored checkpoint and guarded probe to insert 16 synthetic
`crisp_scored` events, 16 target CRISP cache rows, and three sentinel rows. Four
operator containers were launched concurrently; final PostgreSQL ownership
shows four events completed by each of four worker IDs. The allowlisted
`handle_crisp_scored` handler invalidated the 16 target entries with the expected
reason and preserved all three sentinels. Receipts and logs all succeeded on
attempt one, and all event leases were released. The generalized helper also
reverified the earlier metric run. [Report](event-handler-concurrency.md),
[evidence](builds/2026-10-11-recovery/crisp-handler-concurrency.json).

The CRISP in-flight observer query failed on an ambiguous `status` column; the
helper now qualifies it, but this run retains only the final worker distribution,
not an in-flight snapshot. The earlier metric probe retains its in-flight
observation. No migration, domain row or external integration changed. The
recovery DB is stopped with its volume retained, and the unrelated checkpoint
event lease is restored exactly. Same-event retry/crash, remaining handler types,
production runtime-role policy, provider recovery and broader CAP-040 parity stay
open. No pytest suite ran; CAP-040 and Batch 2 remain partial.

### Batch 2 same-event active lease exclusion — 11 October 2026

Held a synthetic CRISP handler at its cache write while worker A owned the
event. Worker B attempted the real event CLI claim; it processed no event, and
PostgreSQL still showed worker A as lease owner with one processing delivery
attempt. After releasing the temporary table lock, worker A completed once,
recorded one successful receipt/log, invalidated its target cache row and
preserved the sentinel. [Details](event-handler-concurrency.md),
[evidence](builds/2026-10-11-recovery/same-event-claim-exclusion.json).

The isolated recovery DB is stopped with its volume retained, and the unrelated
checkpoint event lease was restored to its exact original timestamp. This closes
only exclusion while an event's lease is active; stale-lease takeover during a
still-running handler, crash after side effect, remaining handler types,
production runtime-role policy and provider recovery remain open. No service
behavior, migration or domain record changed, and no pytest suite ran. CAP-040
and Batch 2 remain partial.

### Batch 2 same-event handler timeout and retry — 11 October 2026

A synthetic CRISP handler was held at its cache write until its 30-second
deadline. The first delivery timed out and returned the event to pending with
one retry recorded. A later operator process completed that same event on
attempt two: PostgreSQL retained one timeout and one success log, the event
completed with its lease released, the target cache row was invalidated and the
sentinel row remained valid. The forced lock exceeded the handler deadline, so
the planned concurrent claimant did not run and this does not establish
expired-lease takeover. The unrelated checkpoint fixture lease was restored to
its exact original timestamp. The recovery database is stopped with its volume
retained. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json).

No migration, service behavior or domain record changed; no pytest suite ran.
Crash-after-side-effect recovery, other handler types, production runtime-role
policy, provider recovery and broader CAP-040 parity remain open. CAP-040 and
Batch 2 remain partial; acceptance counts do not change.

### Batch 2 same-event expired-lease takeover — 11 October 2026

Worker A claimed one synthetic CRISP event and blocked in its cache update under
a temporary PostgreSQL table lock. A guarded helper expired only that event's
lease. Worker B reclaimed it while A's handler was still blocked: the database
snapshot showed B as owner on delivery attempt two and two blocked cache-update
sessions. After releasing the lock, both handlers succeeded. A invalidated zero
rows and lost the event completion race; B invalidated the target row and
completed the event. The final delivery is successful, with two success logs,
one target invalidation and the sentinel preserved. A's CLI reported one failed
event because its lease was no longer current.

The default 30-second handler timeout was too short for the first attempt to
capture a second claim; that isolated probe dead-lettered with cache rows
unchanged. For the successful rehearsal, the isolated handler timeout was
temporarily set to 120 seconds and restored to 30. The unrelated checkpoint
fixture lease was restored exactly. The recovery database is stopped with its
volume retained. [Report](event-handler-concurrency.md),
[machine evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json).

No source service behavior, ordered migration, domain record or external effect
changed; no pytest suite ran. Crash-after-side-effect recovery, other handlers,
runtime-role policy, stale-worker lease-loss reporting semantics, provider
recovery and broader CAP-040 parity remain open. The stale worker's CLI counted
one failure even though worker B completed the event; review whether this should
be exposed separately from handler failure. CAP-040 and Batch 2 remain partial;
acceptance counts do not change.

### Batch 2 stale-worker reporting correction — 11 October 2026

`EventBus.process_pending()` now reports `lease_lost` independently from
`failed`, and does not retry an event when the current worker no longer owns its
lease. One-shot event processing exits successfully when lease loss is the only
outcome, while the persistent worker sleeps for its poll interval if it has no
processed or failed work. Handler errors and timeouts remain failures. A focused
regression function passed by direct invocation, along with Python compilation
and `git diff --check`; the standard pytest command could not start because
`pytest` is not installed in the host Python environment. No migration or
database state changed. The concurrent takeover evidence above predates this
reporting correction; rerunning it with the updated CLI remains optional
confirmation. Batch 2 and CAP-040 remain partial.

### Batch 2 crash-after-effect recovery — 11 October 2026

In the private recovery fixture, a guarded worker ran the real CRISP cache
handler, confirmed the target row was invalidated and the sentinel remained
valid, then exited with status 86 immediately before the delivery receipt could
be updated. PostgreSQL retained a processing event and processing delivery at
attempt one, with no handler log. After a guarded expiry of only that synthetic
event's lease, the real event CLI reclaimed it and reported one processed, zero
failed, zero skipped and zero lease losses. The handler ran again, invalidated
zero additional cache rows, and completed attempt two. Final state: completed
event, released lease, one successful handler log, target invalidated once and
sentinel preserved. [Evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json).

The known seeded fixture event was temporarily deferred so a global worker
could not claim it, then its exact original lease timestamp and other fields
were restored. Only the dedicated recovery database was started; it is now
stopped with both fixture volumes retained and no ports published. This covers
one idempotent local cache effect. It does not prove safe retries for non-idempotent
handlers or external effects; remaining handlers, runtime-role policy, provider
recovery and broader CAP-040 acceptance remain open. No migration changed.

### Batch 2 registered event-handler inventory — 11 October 2026

Source-audited the five effective event registrations and execution allowlist.
The metric/CRISP cache invalidators have isolated concurrency and crash/retry
evidence. The anomaly handler can create alert and optional draft-claim records,
publish a downstream event, and use email/Directus/actuator integrations; its
cooldown is not a per-event idempotency receipt. The stale-data and threshold
handlers call best-effort webhook/Directus transports without durable delivery
receipts, leaving duplicate-send and lost-send windows around event completion.
No external endpoint or actuator was contacted. Updated the batch checklist,
capability matrix and handler report to require notification idempotency before
replay probes. No code, migration or database state changed, no Compose project
was started, and no test suite ran. Batch 2 and CAP-040 remain partial.

### Batch 2 event notification outbox implementation — 11 October 2026

Added checksummed migration source `375_notification_outbox.sql` for durable
webhook/Directus notification queue rows, per-attempt receipts and operator
audit. Event handlers now enqueue with stable event/channel/destination identity
before their event receipt can succeed. The event worker dispatches enabled
channels using leases, bounded exponential retry, a stable `Idempotency-Key`,
dead-letter handling and audited replay/disposal. Provider-disabled channels
remain unclaimed; destination URLs and credentials are read from worker env and
are not stored in PostgreSQL. Exposed status/process/dead-letter CLI commands
and configured the standard/portability workers for optional notification
providers. Source compilation and whitespace checks passed. Migration was not
applied to either application database. A fresh, internal-only scratch database
accepted the migration twice. A fake transport verified enqueue idempotency,
changed-payload rejection, disabled-provider pause, retry/backoff, crash after a
fake send followed by lease reclaim using the same idempotency key, CLI help and
operator replay/disposal audit, including replay after a full retry budget with
monotonic attempt history. The allowlisted handler also received the stable source
event id and duplicate handler execution enqueued only one row. All nine checks
passed, with six fake sends and no external network. The scratch database is stopped
and its volume retained.
`py_compile`, CLI help in the operator image, and whitespace checks passed; no
pytest suite ran. Real provider acceptance and sensor anomaly idempotency remain
open. Notification table retention/capacity policy remains open; no automatic
pruning was added. Batch 2 and CAP-040 remain partial. [Evidence](builds/2026-10-11-recovery/notification-outbox-check.json).

### Batch 2 notification outbox capacity visibility — 11 October 2026

`--notification-stats` now reports queue status counts, oldest open age, and
combined storage for the outbox, attempts, and operator audit. Compose profiles
expose configurable 256 MiB warning / 512 MiB critical advisory thresholds.
No writes are blocked and no rows are deleted at either threshold. The
operations note sets a no-prune interim rule to protect identity and audit
evidence; the product/jurisdiction retention and archive period still requires
an owner decision. Ten isolated checks passed against a fresh internal-only
scratch database, including the deterministic critical threshold path; application
databases remain unchanged. [Evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json).
Batch 2 and CAP-047 remain partial.

### Batch 2 sensor anomaly crash/replay — 11 October 2026

Added additive migration `376_sensor_anomaly_delivery.sql` for a durable
per-reading/rule effect receipt, email outbox channel and the existing critical
actuation approval status. The event handler now resolves the exact source
reading and keeps its alert, optional draft claim, ingestion log, notification
intents, approval record and follow-up event in one PostgreSQL transaction.
Auto-created claims use the reading date. The actual EventBus worker subprocess
exited with code 86 after handler commit and before receipt acknowledgement. A
replacement worker reclaimed the expired source event lease and completed
delivery on attempt two; the event receipt moved from `processing` to `success`
with one success log. Alert, claim, effect receipt, ingestion log, downstream
event, actuation record and three notification intents each remained
single-copy. Critical work remained unapproved with
`human_approval_required=true`. A fake SMTP object verified stable `Message-ID`
and idempotency header; internal-only networking prevented egress and no real
provider or actuator was contacted. The focused fixture used only the relevant
schema set, not all repository migrations. Migration 376 re-applied twice;
Python compilation, migration-source validation, Compose parsing and
`git diff --check` passed. The scratch database is stopped with its volume
retained; candidate stayed healthy and legacy services stayed stopped. No
application database migration or pytest suite ran. [Design](sensor-anomaly-delivery.md);
[machine evidence](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json).
This closes one scoped sensor anomaly event-worker crash/retry check. Real
provider acceptance, notification retention, production operator policy,
additional handler/runtime recovery and broader CAP-040/Batch 2 acceptance
remain open.

## Phase 7 local operator overview CLI — 11 October 2026

Added `python3 -m services.cli kernel overview`, a local read-only view of build
metadata and environment-selected provider flags. It performs no database or
network checks and prints no credential values; its output labels health and DB
checks as false. The existing `kernel schema-readiness` remains the separate
read-only database gate. Documented why public `/api/health/services` is not an
operator-console dependency: it probes configured services and is not an
authenticated console. No service was started and no database was queried. A
browser console remains gated on operator identity/scope, audit, CORS, and write
approval policy. Python syntax compilation, generated SDK drift check, and diff
whitespace checks passed. The new CLI command was not invoked and no test suite
was run.

### Batch 2 PostgreSQL runtime-role boundary — 11 October 2026

Added `services/migration/runtime_role.py` and an opt-in Compose overlay that
provisions a distinct application role while leaving migration/operator
credentials separate. The app reads `PG_PASSWORD` first and preserves the
`POSTGRES_PASSWORD` fallback for existing deployments. A synthetic isolated
PostgreSQL fixture provisioned the role twice, checked table DML and default
grants for a table created afterward, and confirmed denial of persistent DDL,
role/database creation, admin-role switching, and access to `postgres`,
`template1`, and a second database. The role has no elevated attributes,
memberships, public-schema CREATE privilege, or owned probe relations. The
fixture had no published ports or network egress.

Candidate and legacy application databases were not migrated or reconfigured.
The candidate remains healthy with its current owner-backed credential; legacy
services remain stopped. The scratch role-check database is stopped and its
named volume retained. Python compilation, Compose parsing and whitespace checks
passed; no pytest suite ran. This completes the opt-in role primitive and its
isolated denial check. A fresh, internal-only populated restore then accepted
repeat provisioning; the native `public_locations()` read returned two rows, a
PostGIS function returned SRID 4326, and a synthetic admin-owned table supported
DML/sequence use. Persistent DDL, role/database creation, admin-role switching
and connections to the other two databases were denied. The test changed no
restored domain rows. [Populated restore evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json).

The candidate remains on its owner-backed credential. Source Compose shows
legacy Directus and Metabase still using the `kokonut` superuser; they are not
included in the Kernel runtime-role overlay and need distinct role/grant plans
before optional adoption. Full domain workflow acceptance, provider recovery
and broader platform-integrity acceptance remain open. Batch 2 remains partial.
[Policy](runtime-role-policy.md); [isolated evidence](builds/2026-10-11-recovery/runtime-role-isolation.json).

### Metabase source inventory — 11 October 2026

A fresh internal-only restore of both encrypted database archives found one
registered Metabase source: the sample H2 source, with no host or database name
and no nonempty password value configured. All 39 saved cards and all 22 dashboard card
placements reference H2. The restored metadata has one dashboard and one user;
there is no PostgreSQL or ClickHouse source configured. The inventory did not
read saved-query definitions/SQL, print connection values, start the populated
Metabase runtime, or execute cards. Therefore the legacy dashboard is not
evidence of Kokonut analytics parity. The temporary containers/network were
removed, the isolated named volume was retained, and the candidate remains
healthy while legacy services remain stopped. [Report](metabase-source-inventory.md) ·
[machine evidence](builds/2026-10-11-recovery/metabase-source-inventory.json).

The populated metadata startup is complete: pinned Metabase is healthy on the
non-superuser metadata role and retained the saved-content aggregate counts.
The initial curated-view source contract and migration are now documented and
authored. The next open work is applying migration 377 and running the expanded
role fixture in a fresh isolated populated restore, then validating
Kokonut-specific measures and output parity before optional-profile promotion.

### Populated Metabase startup — 11 October 2026

Restored the encrypted application and Metabase archives into a new
internal-only project. The optional consumer-role fixture passed again: the
Metabase login owned the `metabase` database and 290 application relations;
the analytics login read only its synthetic curated view, and cross-database
denials held. The pinned Metabase 0.62.4 image started against the populated
metadata DB and reached healthy; the health endpoint returned 200. Post-startup
counts matched the earlier inventory of the same encrypted metadata archive:
39 cards, one dashboard, 22 dashboard placements, and one user. The sole source
remains sample H2. No card definitions or SQL
were read or executed. The recovery containers and network were removed; the
volume was retained. Candidate services stayed healthy; legacy services stayed
stopped. [Evidence](builds/2026-10-11-recovery/metabase-populated-startup.json).

This closes the populated metadata startup checklist item only. Source
connectivity, card rendering, semantic/output parity, Kokonut-specific cards,
and optional-profile promotion remain open.

### Metabase saved-content review — 11 October 2026

A fresh internal-only Metabase metadata restore revealed one **E-commerce
Insights** dashboard with 22 placements from 39 cards. The card titles and
source categories cover orders, products, subscriptions, checkout, revenue,
and survey examples; every card points to the sample H2 source. The cards span
19 visualization types. The read-only structural inventory emitted no SQL,
filter values, connection values, user records, or domain rows and did not
execute saved cards. This is generic demo content, not Kokonut analytics
capability or output-parity evidence.

Disposition: preserve the archive and use the sample board only as an
explicitly labeled demo/compatibility fixture. Build Kokonut-specific reports
against reviewed published views and compare agreed reference outputs before
enabling Metabase in an analytics profile. [Report](metabase-source-inventory.md) ·
[evidence](builds/2026-10-11-recovery/metabase-content-inventory.json).

This content-only fixture restored only the Metabase archive. An exploratory
application-database restore in the same temporary project hit a PostGIS
duplicate-extension catalog error; the unused app database was reset empty.
The Metabase restore and inventory succeeded, the isolated volume is retained,
and candidate/legacy services remain unchanged. CAP-007 and Batch 2 remain
partial; no source query or test suite ran.

### Metabase reporting contract — 11 October 2026

Documented the initial PostgreSQL-only reporting boundary and proposed stable
`kokonut_reporting` views. The contract uses the existing public views as
behavioral evidence, not as an approved source to grant unchanged: the farm
summary's `SUM(DISTINCT area)` can undercount equal-area farms, while the metric
summary omits period/method, may tie on computed time, and has no explicit
public metric allowlist. The attestation summary remains explicitly Celo-only.
The document defines role scope, an additive implementation sequence,
acceptance and rollback gates. No schema, grant, Metabase connection, or card
changed in this documentation batch. [Contract](metabase-reporting-contract.md)
· [Checklist](batches.md) · [CAP-007](capability-matrix.md).

### Metabase reporting views verified — 11 October 2026

Applied all 368 current schema migrations, including migration 377, to a clean
`kokonut_reporting_scratch` database in a copied isolated recovery volume. The
checksum-tracked plan then reported zero pending schema migrations. The expanded
consumer-role fixture passed exact access to the three reviewed views and denied
base-table/policy-table reads, DDL, writes, and cross-database connections. Its
rolled-back synthetic probes confirmed equal-area farm/plot totals, farm-specific
registry scope, unsupported-unit fail-closed behavior, an empty-by-default metric
allowlist with published-value visibility, and Celo-only verified/published
attestation counts. Metabase metadata remained populated in the clone; its
ownership setup was confined there. The archived application DB restore still
reports historical checksum drift at `schema:000_extensions.sql`; this was not
repaired or bypassed, and no candidate/legacy database was changed. No Metabase
source or Kokonut cards were configured. [Evidence](builds/2026-10-11-recovery/kokonut-reporting-contract.json) ·
[checklist](batches.md) · [contract](metabase-reporting-contract.md).

### Archived migration checksum drift triage — 11 October 2026

Read the migration ledger and extension catalog from the retained isolated
application restore. Of 344 applied schema rows, only
`schema:000_extensions.sql` mismatches the current source checksum; 24 newer
current schema files are absent from that archive ledger. The six extensions
listed in the current source are installed, but that does not prove the
historical SQL matched. The local Git parent has no prior copy of this migration,
and the ledger's 24-byte `sql_up` value does not hash to the recorded checksum.
No exact repair is approved by the migration runner. I left the ledger and
database unchanged and stopped the inspection container with its volume kept.
[Triage](migration-checksum-drift.md) ·
[sanitized evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json).


### Historical migration source recovered — 11 October 2026

Extracted `schemas/postgres/000_extensions.sql` from the stopped local legacy
worker image. Its SHA256 exactly matches the archived ledger's stored checksum
`cf493b…a245`. The current source adds a synchronization note and three
idempotent extension declarations; all six current extensions are already
installed in the archived clone. Preserved the old SQL under recovery provenance
evidence. No database ledger repair or migration was performed: the runner has
no allowlist entry for this migration, and its policy directs new drift to a new
migration. The archived clone remains gated until the migration/recovery
disposition is documented. The temporary inspection container was removed; the
legacy stack remains stopped and the candidate remains healthy.

[Drift record](migration-checksum-drift.md) ·
[Historical source](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql) ·
[Sanitized evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Historical migration checksum reconciled in source — 11 October 2026

Git history shows the expanded `000_extensions.sql` was reintroduced on 9
October, after checksum enforcement landed on 15 July. I restored the active
migration file to the exact deployed bytes recovered from the stopped worker
image (`cf493b…a245`) and moved the later `postgis_topology`, `pg_trgm`, and
`pg_stat_statements` declarations into new migration 378. The archived clone
and ledger were not changed. Source validation covered 369 migrations and the
focused migration suite passed (15 tests). A read-only plan on the retained
clone and a fresh 369-migration reporting scratch run are still required; the
previous 368-source reporting scratch used the interim checksum and is not a
current-source target.

[Source correction](migration-checksum-drift.md) ·
[Migration 378](../../schemas/postgres/378_optional_extensions.sql) ·
[Historical source](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql) ·
[Evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Source-aligned reporting replay and archived clone plan — 11 October 2026

The post-alignment read-only plan on the retained archived clone passed checksum
validation and reported 25 pending migrations (353–378); none were applied. I
copied the stopped reporting clone into a second-generation volume, created a
fresh scratch database, applied all 369 current schema migrations through 378,
and confirmed zero pending. The expanded actual-view role fixture passed its
aggregation, publication/lifecycle, Celo attestation, scope, and denial probes.
Synthetic fixture rows rolled back. The first fixture connection used a rotated
credential and failed before changes; I set a synthetic password only in the
second-generation clone and reran successfully. Temporary containers and
networks were removed; the copied volume remains retained, while the source
clone, original recovery volume, candidate, and legacy stack were unchanged.

[Source-aligned evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json) ·
[Archived plan](builds/2026-10-11-recovery/application-migration-checksum-drift.json) ·
[Drift/source record](migration-checksum-drift.md) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Transactional migration replay and rollback — 11 October 2026

The migration runner now wraps each SQL body and its `schema_migration` ledger
write in one transaction under the existing advisory lock. Existing balanced
top-level transaction markers are folded into the runner transaction; nested or
unmatched markers are rejected. The focused migration suite passed with 17 tests,
and the wrapper preflight accepted all 488 schema and seed files.

On a third-generation disposable copy, all 369 current schema migrations were
applied and checksum-validated with zero pending. An injected migration created
a table and row, then failed on a duplicate table creation. The runner returned
the expected SQL error; independent post-failure queries confirmed zero probe
tables and zero ledger rows (`0|0`). The reporting-view role fixture remains
covered by its separate source-aligned replay. The archived application clone,
original recovery volume, candidate, and stopped legacy stack were unchanged.
The temporary container and network were removed; the disposable clone volume
was retained.

In a separate compatibility replay, all 25 migrations pending on the archived
clone were applied through the same runner to a copied populated database. The
plan returned zero pending, and pre-migration column fingerprints matched for
all 16 selected populated tables. The retained archived clone still has all 25
pending and was not changed. Two SAFE rows and six migration-version markers
were the expected additions; all other new optional workflow/reporting tables
remained empty. SAFE seed values and the NOI view formula were subsequently
verified onchain and against a populated clone; migration 379 and the native
snapshot reconciler were exercised on a separate network-disabled copy. Active-
target application still requires duplicate-key preflight, exact-target checksum
review, and a verified backup. The daily job remains disabled. Populated
report-output parity and Metabase source/cards remain open.

[Runner documentation](../../services/migration/README.md) ·
[Transactional evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json) ·
[Populated-clone review](pending-migration-compatibility-review.md) ·
[Drift record](migration-checksum-drift.md) ·
[Checklist](batches.md) · [CAP-007](capability-matrix.md).


### Populated reporting-view parity — 11 October 2026

On a network-disabled disposable copy of the populated recovery database, bidirectional EXCEPT comparisons matched the independent farm-summary query (2 rows) and Celo-attestation query (1 row), with zero differences. The verified-metrics view also matched its independent query, both returning zero because no metric publication policy was published in this dataset. The analytics role received only named SELECT grants on the three reporting views in the disposable copy; as that role it could read those views and was denied on metric values, the migration ledger, the private policy table, and DDL. Five pre-existing public extension metadata relations remained readable through their own grants. The copied source, candidate, and legacy deployment were unchanged; the temporary database and volume were removed. No Metabase source or cards were configured.

Evidence: [sanitized parity and role results](builds/2026-10-11-recovery/populated-report-view-parity.json), [report contract](metabase-reporting-contract.md), and [Batch 4b](batches.md). The copied PostgreSQL cluster emitted a collation-version warning, but all read-only queries completed successfully.


### Candidate migration preflight and fresh schema replay — 11 October 2026

The active candidate has 361 applied schema rows through migration 370 and nine current migrations pending (371–379). The exact-target read-only plan found a single checksum mismatch at schema:000_extensions.sql: the stored checksum is 6e5850e5…5723ff, matching the source used by the candidate, while the current source checksum is cf493b73…1a245. The candidate has zero NOI snapshots, duplicate keys, or null crop-cycle keys. No migration or checksum repair was applied.

A fresh encrypted checkpoint was created for this exact candidate and its archive authenticated and restored successfully into an internal-only database. The ledger, relation count, and selected table counts matched. The checkpoint is mirrored under the same disk. Separately, all 370 current schema sources applied with zero failures to a network-disabled fresh database; its final plan had zero pending. Both scratch projects were removed. The checksum mismatch still blocks applying migrations to the existing candidate under the repository migration-integrity rules.

Evidence: [candidate preflight, backup and fresh replay](builds/2026-10-11-recovery/candidate-migration-preflight.json), [checksum history](migration-checksum-drift.md), [Batch 4a](batches.md), and the ignored root plan.


### Candidate reporting-source ACL review — 11 October 2026

Before the candidate migration update below, read the active candidate's roles and database/schema ACLs inside a
`BEGIN READ ONLY` transaction. `kokonut` is the only login/superuser role; the
runtime, analytics-source, and Metabase metadata roles and migration-377
reporting objects are absent. `PUBLIC` retains `CONNECT` and `TEMPORARY` on
the application database (and `CONNECT` on `postgres` and `template1`). No
grant, schema, role, application row, or Metabase source was changed. This
closes the exact-target ACL inventory item. The source was not ready at review
time. The checksum policy and schema migrations are now resolved on the
candidate; dedicated role/ACL setup remains open.

Evidence: [candidate reporting ACL inventory](builds/2026-10-11-recovery/candidate-reporting-acl-review.json), [active candidate migration result](builds/2026-10-11-recovery/candidate-migration-apply.json), [reporting contract](metabase-reporting-contract.md), [optional database roles](optional-database-roles.md), and [Batch 4b](batches.md). No test suites were run for the ACL inventory; capability counts and deployment selection are unchanged.


### Candidate migration compatibility review — 11 October 2026

The candidate's stored `schema:000_extensions.sql` checksum matches the exact
repository-base bytes. The source change only relocates three idempotent
extension declarations to migration 378; a read-only candidate query confirms
all six expected extensions are installed. The runner now recognizes the exact
historical/current source pair through its audited repair allowlist and refuses
repair unless all six extension effects are present. The focused migration suite
passes 22 tests, including exact-checksum approval, audit insertion,
current-source pinning, and missing-extension rejection. The candidate ledger
had not yet been repaired at this checkpoint, and no pending migration had been applied.

The exact repair and planner then passed on an internal-only fixture seeded from
the candidate's read-only schema ledger. Its post-repair plan reported zero
checksum mismatches and the expected nine pending migrations; the audit row
recorded the exact old/current checksum pair. No candidate application schema
was restored or changed by this check.

Evidence: [preflight](builds/2026-10-11-recovery/candidate-migration-preflight.json), [ACL and extension inventory](builds/2026-10-11-recovery/candidate-reporting-acl-review.json), [isolated repair policy evidence](builds/2026-10-11-recovery/candidate-checksum-repair-policy.json), [migration drift record](migration-checksum-drift.md), [runner policy](../../services/migration/README.md). This is an implementation preparation step; capability counts remain unchanged.


### Active candidate migrations 371–379 — 11 October 2026

The exact candidate repair was recorded through the audited runner path after
the full six-extension precondition passed. The post-repair plan returned the
nine expected migrations; the transactional runner applied all nine with zero
failures. A final source/target plan reports zero pending from 370 applied
schema files. The reporting schema and its three views now exist, with no PUBLIC
table grants. The NOI table remains empty; the unique crop-cycle index exists,
and null/duplicate keys remain zero. Candidate app and database are healthy.
The app supervisor runs scheduler and event-worker processes; scheduler status
reports zero enabled, disabled, or running tasks, so the NOI daily job is not
registered. A separate analytics login is now provisioned and verified; no Kokonut Metabase source/cards are configured, and the built-in H2 demo is recorded in the optional-profile section below.
Legacy remains stopped.

Evidence: [active candidate migration record](builds/2026-10-11-recovery/candidate-migration-apply.json), [preflight backup and restore](builds/2026-10-11-recovery/candidate-migration-preflight.json), and [checksum policy](migration-checksum-drift.md). The recorded checkpoint restores the pre-repair schema; reapplication requires the audited repair. No capability acceptance count changes.

### Active candidate app rebuild — 11 October 2026

Rebuilt the AMD64 Kernel image after adding the optional Metabase-role bootstrap
module. The final image matches every embedded checkout hash: 1,294 of 1,294;
the 11 omitted paths are optional transport/orchestration or development inputs.
The previous app image is preserved as
`kokonut-kernel-candidate-app:pre-metabase-role-20261011`; earlier rollback tags
remain available. Only the app container was recreated. The database container
and PostgreSQL volume remained unchanged and healthy, and Metabase remained
healthy. The app liveness endpoint returned 200,
the explicit candidate migration plan reports zero pending schema migrations,
and the scheduler reports zero enabled/disabled/running tasks. Compose created
the previously absent empty gateway-audit spool volume. No migration, grant,
role or Metabase change occurred. This does not establish API or domain parity,
ARM64/Raspberry Pi readiness, or phase acceptance.

Evidence: [candidate app rebuild](builds/2026-10-11-recovery/candidate-app-rebuild.json),
[migration state](builds/2026-10-11-recovery/candidate-migration-apply.json), and
[batch checklist](batches.md). Capability counts remain unchanged.

### Candidate analytics-source login — 11 October 2026

Added the opt-in `analytics-admin` Compose profile and repeatable
`services.migration.analytics_role` bootstrap. It is guarded for a dedicated
PostgreSQL instance, revokes inherited PUBLIC database CONNECT on all four
existing candidate databases, removes PUBLIC TEMPORARY on the application DB,
and grants the non-admin `kokonut_analytics_ro` login access only to that DB and
the three reviewed reporting views. Its random credential is stored encrypted
in `.env.sops`; the running application keeps its existing identity.

The real analytics login read all three candidate views (each currently has
zero rows) and was denied on the migration ledger, private publication policy,
DDL, temporary tables, and all other candidate databases. No unreviewed
application relation is readable. Existing extension privileges remain
inherited: eight extension metadata relations are accessible and 1,165
extension functions are executable; none of the public-executable extension
functions is SECURITY DEFINER. The one-shot bootstrap container was removed;
the app and database remained healthy, and the migration plan still reports
zero pending. No Kokonut Metabase source/cards were created; the built-in H2
demo was inventoried separately below.

Evidence: [candidate analytics-role record](builds/2026-10-11-recovery/candidate-analytics-role.json),
[role policy](optional-database-roles.md), [migration/bootstrap instructions](../../services/migration/README.md),
and [Batch 4b](batches.md). MAN-CAP counts do not change.

### Candidate Metabase analytics profile — 11 October 2026

Added an opt-in candidate-only `analytics` overlay with pinned Metabase 0.62.4,
a loopback-only UI port, private PostgreSQL networking, sharing disabled, a
bounded JVM heap, and a distinct SOPS-managed encryption key. The one-shot
`metabase_role` bootstrap created `kokonut_metabase` and its
`kokonut_metabase_app` owner. Database ACLs give that role CONNECT and CREATE
only on the metadata database; a real login created a temporary table that was
rolled back and was denied on `kokonut_intelligence`.

Metabase startup exposed the database-level CREATE requirement for installing
`citext`; the bootstrap was tightened to grant CREATE only on its metadata DB,
then re-run successfully. Metabase is healthy; its loopback endpoint returned
HTTP 200 and Docker reports healthy. The default candidate manifest contains
only `database` and `app`, and PostgreSQL has no host port. A sanitized
inventory found one built-in H2 sample source, 39 generic demo cards, one
dashboard with 22 placements, and one user record; no Kokonut PostgreSQL source
or Kokonut cards exist. The startup log confirms credential encryption is
enabled. The legacy stack remains stopped.

The secrets loader also now resolves its own path when sourced from zsh, the
repository's interactive shell. It loaded the needed keys without displaying
values, and the combined opt-in Compose configuration validated.

Evidence: [profile contract](metabase-kernel-profile.md), [profile runtime record](builds/2026-10-11-recovery/candidate-metabase-profile.json), [source inventory](metabase-source-inventory.md), [role policy](optional-database-roles.md), [Batch 4d/4e checklist](batches.md), and [Metabase credential-encryption docs](https://www.metabase.com/docs/latest/databases/encrypting-details-at-rest).
Capability counts remain unchanged.

### Kokonut Metabase source, cards, and local metadata backup — 11 October 2026

Completed local first-run setup with the generated administrator credential
stored encrypted in `.env.sops`. Registered `Kokonut Reporting Views` through
`kokonut_analytics_ro`, using a string inclusion pattern for `kokonut_reporting`.
The first attempt encoded the pattern as a list; that prevented schema
discovery. After correcting it to the comma-separated string expected by
Metabase, schema sync completed and listed only the three approved reporting
views. The source connection validates, and saved credential encryption was
enabled before registration.

Created the `Kokonut Reporting` collection, three SQL cards (farm summary,
verified metric values, and Celo attestation summary), and the
`Kokonut Intelligence | Reporting Overview` dashboard. All card queries
completed and exposed the expected columns. Each returned zero rows, matching
direct PostgreSQL counts; the active candidate has no pilot rows. The generic
H2 sample remains separately labeled demo content. A credential-free card
export and sanitized source/card inventory are retained.

Streamed a fresh custom-format dump of `kokonut_metabase` directly through age
encryption to the ignored local `backups/kernel-metabase-20261011/` directory;
no plaintext dump was written. Decryption with the supplied age identity and
`pg_restore --list` both succeeded with 2,177 archive entries. The
`KOKONUT_METABASE_ENCRYPTION_KEY`, source password, and admin password remain in
SOPS. The archive restored successfully with `--exit-on-error` into a
network-disabled, disposable container using the matching PostGIS 16 image.
Counts matched the live metadata exactly: two sources, 42 saved cards, two
dashboards, 25 saved-card placements, 14 virtual tiles, and two users. The
E-commerce board's virtual tiles are populated heading/text/link/iframe content,
not empty cards. The disposable target was removed and the live metadata was
unchanged. Populated card-output parity was then completed separately on a
copied fixture; the database-view parity evidence from Batch 4b alone does not
certify the Metabase card layer.

Evidence: [candidate runtime and card results](builds/2026-10-11-recovery/candidate-metabase-profile.json),
[sanitized source inventory](metabase-source-inventory.md),
[credential-free card export](metabase/kokonut-reporting-cards.json),
[encrypted backup manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json),
[profile contract](metabase-kernel-profile.md), and [Batch 4e checklist](batches.md).
Capability counts remain unchanged.

### Kokonut card SQL output parity — 11 October 2026

Copied the retained populated reporting volume read-only into a fresh scratch
volume. A temporary source used `kokonut_analytics_ro` and the
`kokonut_reporting` schema filter on a private internal Docker network; there
were no host ports. Metabase executed the exact SQL from the three
credential-free card definitions. Farm summary returned two rows and Celo
attestation summary returned one; both matched independently written
base-table queries with zero differences.

For the metric card, a synthetic verified value and reviewed policy were added
only to the disposable copy. The value stayed hidden while the policy was
`verified`; after publishing the policy, one verified value appeared and an
unverified value remained excluded. In-window and outside-window queries
returned one and zero rows respectively. Both outputs matched independent SQL.
The temporary source, network, container, and scratch volume were removed. The
retained source volume, candidate metadata, candidate application database, and
legacy stack were unchanged. No query rows or credential values were printed.

The active candidate still has no pilot rows, so its saved cards return zero
rows. The populated comparison used the same exported card SQL through the
Metabase dataset API and did not modify saved card objects. See
[sanitized parity evidence](builds/2026-10-11-recovery/metabase-card-output-parity.json),
[card export](metabase/kokonut-reporting-cards.json), and
[Batch 4e checklist](batches.md). Capability counts remain unchanged.


## Batch 5 MQTT deployment contract — 11 October 2026

Reviewed the optional Mosquitto/subscriber Compose overlay and the related QoS,
transaction, recovery, and readiness records. Confirmed the broker/subscriber
are on the private Kernel network with no host ports, separate read-only broker
and subscriber credential mounts, a dedicated persistent broker volume, stable
QoS 1 client identity, manual ACK after durable source/outbox commit, and local
connection/subscription health state. Corrected stale statements: migrations
371/372 are applied to the active local candidate through 379, while the
MQTT-specific image is a historical build and neither MQTT service has been
started. No secrets, broker state, or services were changed; no test suite or
Compose deployment was run for this review. ARM64, mTLS/ACL, ingestion, retry,
reconnect, readiness, and storage recovery acceptance remain open. See
[mqtt profile contract](mqtt-overlay.md), [delivery](mqtt-delivery.md),
[recovery](mqtt-recovery.md), [readiness](mqtt-readiness.md), and [checklist](batches.md).


## Batch 5 gRPC deployment contract — 11 October 2026

Reconciled the private gRPC overlay with the server, auth interceptor, pooled
database adapter, and shutdown code. The contract now states that the service
has no host port, the Caddy profile does not proxy it, Compose omits TLS settings
so the transport is insecure within the private `kernel` network, and API keys
with exact method scopes authorize business RPCs. It also records the `kokonut`
DB-user fallback, unmeasured 4-worker/1–5 pool sizing, 30-second server grace,
40-second container grace, and liveness-only health. Historical image digests
need a rebuild from current checkout. The service was not started and no RPC was
issued; no schema, secrets, or runtime state changed. ARM64, TLS, role, auth/scope,
streaming, data parity, concurrency and shutdown acceptance remain open. No test
suite ran. See [gRPC contract](grpc-overlay.md), [auth](grpc-authentication.md),
[database](grpc-database.md), [shutdown](grpc-shutdown.md), and [checklist](batches.md).

## Batch 5 Caddy proxy deployment contract — 11 October 2026

Reconciled the pinned Caddy Compose overlay, Caddyfile, and retained runtime
checks. Documented loopback defaults (8088/8448), alternate HTTPS port behavior,
all-path forwarding only to the Gateway, local-CA trust, three response headers,
no Caddy healthcheck, no gRPC/sensor routes, ignored forwarded headers, and the
public-ingress gates. Existing private internal TLS, host loopback, alternate
port, and one-hop forwarded-header probes are retained; they do not certify
public bind/DNS/ACME, client trust installation, multi-hop proxies, or
authenticated CORS. No service or config was changed and no suite ran. Rollback
removes only the proxy profile and keeps certificate volumes. See
[proxy contract](kernel-proxy.md), [proxy evidence](builds/2026-10-10-recovery/kernel-proxy-runtime.json),
and [Batch 5 checklist](batches.md).

## Phase 7 OIDC operator identity and report review slice — 11 October 2026

Added an opt-in OIDC adapter using the separate `oidc` image target and
`docker-compose.kernel-oidc.yml` overlay, with secure HTTPS-only cookies,
state/nonce handling, S256 PKCE, database-backed opaque sessions, CSRF checks,
and locally provisioned identity/location grants. Added additive migration
380, a CLI for identity/grant lifecycle, and a same-origin page that displays
the authenticated principal without persisting credentials in browser storage.
The minimal `kernel` target remains free of OIDC dependencies. OIDC is still
disabled because no provider credentials/settings are configured. Migration
380 was not applied and no live login/session request or acceptance suite was
run. Selected `report_snapshot` because the schema and workflow define the
submitted review state. Added exact OIDC route policies, active scope listing
for the signed-in principal, per-location `report_snapshot_review:read`
authorization, read-only list/detail SQL limited to submitted rows, and a
same-origin browser queue that renders report data with `textContent`; SQL
rechecks the active grant, and report details are capped at 512 KiB. Network
snapshots without a location remain outside this scope; the console has no
verification/rejection/publication controls. Python AST parsing, provider-boundary
and requirement-group checks, inline JavaScript syntax, and `git diff --check`
passed. Ruff is not installed, and no tests ran. Runtime authorization, audit,
login, queue and detail acceptance remain open.
Capability counts do not change. See
[`kernel-operations-console.md`](kernel-operations-console.md)
and [Batch 5](batches.md).

## Batch 5 retired-form consent parity and collection-reader audit — 11 October 2026

A source review found that a known retired revision with `required` consent
could enter private media storage and sync without repeating participant-link
and consent checks. The mobile API now applies the immutable required policy to
active and retired revisions before reading media bytes and again at sync.
Retired rows remain `retired_review` and unassessed for eligibility; valid
consent does not promote them into normal use. The review also traced every
`offline_collection` reference: the legacy analytics CLI is a transport/admin
producer and sync marker, not a consent-aware admission path; its rows default
to unassessed and fail the migration 381 eligibility view. No business,
reporting, or publication consumer was found in the source tree.

Updated the access contract, operator-facing mobile and field-collection guides,
repository CLI guidance, Batch 5 checklist, and CAP-053 status. Python syntax
compilation and `git diff --check` passed. No test suite, migration, database,
or container was run or changed. Per-form classification, tenant/RLS policy,
retention/erasure disposition, and the migration/mobile acceptance gates remain
open.

## Batch 5 Field Collector CORS header parity — 11 October 2026

Compared the browser's private-media request headers with the Gateway's
explicit-origin CORS allowlist. The allowlist omitted collection type, form ID,
form version, collection timestamp, and participant reference, so a separately
hosted Field Collector would fail browser preflight before the consent-aware
upload route ran. Added those headers and both API-key/capability header aliases.
Same-origin deployment is unchanged; wildcard origins remain rejected, and
credentialed cookies remain conditional on OIDC.

Updated the mobile deployment README and Batch 5 checklist. Python syntax
compilation and `git diff --check` passed; no test suite, live preflight, API
request, migration, or container change was run. Successful authenticated and
credentialed CORS runtime acceptance remains open, along with mobile migration
and owner-policy gates.

## Batch 5 Field Collector mobile and CORS source acceptance — 11 October 2026

Ran the mocked Field Collector API, private-media adapter, and legacy offline
transport modules: **51 passed**. The run exposed fixtures that still used the
pre-revision request shape and 12-column collection rows; aligned those fixtures
with the immutable form-revision contract and added regression coverage for a
retired `required` revision. The upload test confirms a missing participant
reference is rejected before private storage; the sync test confirms a matching
grant remains `retired_review`/`unassessed` rather than becoming eligible.

Ran the four focused Gateway CORS cases: **4 passed**. Expanded the CORS test to
request all 14 current browser headers (including form metadata, participant
reference, and auth aliases), and separately confirmed a configured-origin
preflight accepts the full list. No migration, database, container, authenticated
browser request, or credentialed-cookie flow was exercised. Existing Starlette,
httpx, and FastAPI lifecycle deprecation warnings remain. Mobile migration
acceptance, five per-form consent decisions, tenant/RLS, retention/erasure, and
successful authenticated/credentialed CORS remain open. CAP-053 stays partial.
See [Batch 5 checklist](batches.md), [mobile access contract](mobile-access-contract.md),
and [capability matrix](capability-matrix.md).

## Batch 5 Field Collector form classification worksheet — 11 October 2026

Added a reviewer worksheet grounded in `schemas/seeds/140_mobile_forms.sql` for
the five active version 1.0.0 forms. It records each source schema's required
and optional fields and provides one decision record per exact form revision
for consent classification, category, purpose, recipient, scope, consent
version, participant-reference need, retention/disposition, reviewer, and
evidence. Every policy decision remains pending; the worksheet is not approval
and does not change seeds, migration 381, form policy, or database state. It
also keeps tenant/RLS and retention/erasure system design as separate gates.
No test suite or runtime probe was needed or run for this documentation-only
slice. The next policy gate requires authorized reviewer decisions; until then
the five forms remain unclassified and CAP-053 remains partial. See the
[classification worksheet](mobile-form-classification-review.md), [access
contract](mobile-access-contract.md), [capability matrix](capability-matrix.md),
and [Batch 5 checklist](batches.md).

## Phase 8 ARM64 application and PostGIS image refresh — 11 October 2026

Built the current-checkout Kernel app (`kernel` target) and PostgreSQL/PostGIS
16 (`kernel-postgis` target) for `linux/arm64` through Buildx. The images were
loaded under new local tags with their identities, source commit, pinned base,
package versions, and sizes recorded in the [build record](arm64-image-pair-refresh.md).
The app dependency-installation and PostGIS package-installation layers were
reused from prior builds of the same manifests/recipe; this did not resolve or
lock dependencies again. No container was created or started, and the active
candidate app, Metabase, database, and their volumes were unchanged. No tests,
schema application, or runtime checks ran. Actual ARM64 bootstrap/restore,
PostGIS behavior, 4 GB Raspberry Pi budgets, release locking, and architecture
CI gates remain open. No capability matrix count changes from an image build.

## Batch 5 Field Collector form policy decisions and source revisions — 12 October 2026

The repository owner delegated the five built-in Field Collector form-policy
decisions. Based on their location-scoped operational purpose and the existing
party-linked consent model, all five `1.1.0` source revisions are classified
`not_required` for participant-linked consent. Each has category, purpose,
dynamic location scope, intended operator recipient, review evidence, and
collection guidance. Person-centered/sensitive content is directed to a
separate consent-required workflow. The policy record clarifies that these are
product-purpose classifications, not legal determinations, and that the API
does not enforce free-text/photo content boundaries.

Added the five reviewed policies and immutable revision updates to
`schemas/seeds/140_mobile_forms.sql`, included that seed after migrations in
`scripts/seed.sh`, and aligned the browser fallback forms. Updated the mobile
access contract, field-data guide, mobile README, and Batch 5 checklist. No
tests, migrations, seed execution, candidate database changes, or container
changes were run. The candidate still has migration 381 pending; existing
`1.0.0` forms remain unclassified until the migration and curated seed run in
order. Retention/erasure disposition, tenant/RLS policy, content validation,
and live mobile acceptance remain open. CAP-053 remains partial. See the
[decision record](mobile-form-classification-review.md), [access contract](mobile-access-contract.md),
[capability matrix](capability-matrix.md), and [Batch 5 checklist](batches.md).


## Batch 5 candidate Field Collector policy rollout — 12 October 2026

Created and successfully rehearsed an encrypted pre-migration checkpoint in a
separate, network-isolated recovery project. Applied migrations 380 and 381
through the checksummed runner, then seeded five reviewed `1.1.0`
`not_required` location-scoped forms on the local candidate. The migration plan
now reports 372 applied schema files and zero pending. Rebuilt and recreated
only the candidate app; the app, database, and optional Metabase are healthy,
and the served browser fallback contains all five current form definitions.
The anonymous forms endpoint returned HTTP 200 with an empty list, as expected
for the location-scoped forms. Location query without a token and invalid token
each returned HTTP 401.
The legacy `kokonut-intelligence` project remains stopped and unchanged.

Focused mobile API, offline transport, media, and CORS checks passed: **55
passed**, with 121 deprecation warnings. The candidate had no pre-existing
mobile form or collection rows when migrated. This rollout does not establish
policy for populated deployments; their legacy rows remain unassessed until
reviewed. Live device enrollment through sync/eligibility, configured OIDC and
operator-scope acceptance, tenant/RLS, retention/erasure, server-side content
validation, and media expiry cleanup remain open. See [rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json),
[access contract](mobile-access-contract.md), [Batch 5](batches.md), and
[CAP-053](capability-matrix.md#cap-053).


## Batch 5 Field Collector payload-schema validation — 12 October 2026

Added `services/mobile/form_validation.py` using the small, declared
`jsonschema` core dependency. New sync payloads are validated against the exact
immutable form revision; built-in source revision `1.2.0` schemas close the
field allowlist with `additionalProperties: false`. Required fields, primitive
types, enums, numeric bounds, and date formats are checked. Remote `$ref`
retrieval is rejected, malformed stored schemas fail closed, and client errors
do not echo submitted values. The browser fallback mirrors version `1.2.0`.
This structural validation cannot identify sensitive text meaning or inspect
photo contents, which remain governed review gates.

Focused mobile/schema suites passed: **60 passed**, with 109 deprecation
warnings. Ruff, dependency-group alignment, and the browser fallback syntax check passed. At that source-only checkpoint the candidate remained on `1.1.0`; the subsequent candidate rollout is recorded below. See the
[policy record](mobile-form-classification-review.md), [access contract](mobile-access-contract.md),
[Batch 5 checklist](batches.md), and [CAP-053](capability-matrix.md#cap-053).
## Batch 5 Field Collector schema-validation candidate rollout — 12 October 2026

Created the fresh encrypted PostgreSQL checkpoint at
`backups/kernel-candidate-pre-form-schema-20261012` and restored it into a
network-isolated database created from `template0`. The migration ledger matched
all 372 applied fingerprints; extension versions and schema inventory matched,
and the pre-rollout clone had five active `1.1.0` revisions and zero collection
rows. The curated `1.2.0` seed first passed against that clone, retaining the
old immutable revisions and activating five schemas with
`additionalProperties: false`.

The current-source image was rebuilt with `jsonschema` 4.26.0, and only the
candidate app container was recreated. The app, candidate database, and Metabase
are healthy. The served app returned HTTP 200 and contained all five `1.2.0`
fallbacks; anonymous forms returned 200 with an empty list, and unauthenticated
location query plus invalid token returned 401. The previous app image remains
tagged, but must not serve mobile sync against the 1.2.0 database because it
lacks payload validation.

The first restore attempt correctly failed transactionally because PostGIS had
initialized the default database with schemas also present in the dump. That
volume is retained stopped; the successful retry used a separate project and a
clean `template0` target. No legacy container or volume was changed. Focused
mobile/schema checks remain **60 passed** (109 deprecation warnings). An isolated
live HTTP sync probe rejected an undeclared field with 422/no echo/no row and
accepted a valid 1.2.0 payload with 200; its synthetic fixture was removed. The
trusted enrollment-created device path, OIDC workflows, semantic free-text and
photo review, tenant/RLS, retention/erasure, and media cleanup remain open.
See [rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json),
[recovery procedure](recovery-preparation.md), [access contract](mobile-access-contract.md),
[Batch 5 checklist](batches.md), and [CAP-053](capability-matrix.md#cap-053).

## Phase 7 OIDC Field Collector enrollment console — 12 October 2026

Added same-origin `/operator/api/mobile/...` wrappers for issuing and revoking
location-scoped Field Collector enrollments and revoking active devices. The
Gateway applies the operator session, explicit `mobile_device:enroll` or
`mobile_device:revoke` grant, and CSRF checks before the handlers run. Code
issuance reuses the existing mobile enrollment handler, records the stable
operator UUID as creator, and returns the one-time plaintext code with
`Cache-Control: no-store` and `Pragma: no-cache`. The console lists only
locations with the exact enrollment grant, requests a collector attribution ID
and bounded code lifetime, then renders the code for handoff without storing
it. The OIDC session cookie stays scoped to `/operator`.

The first route test exposed unresolved local FastAPI annotations in the
operator router; moving the request and enrollment model types into resolvable
module scope restored FastAPI request/body injection. Five new route/auth tests
pass. The combined mobile API, Gateway auth, and OIDC route focused checks pass
**56 tests**. Verification ran in the repository virtual environment with the
declared `itsdangerous` OIDC dependency installed; the Gateway audit spool was
pointed at a private temporary directory because the default user-state path is
outside the workspace sandbox. Existing deprecation warnings remain.

No candidate container was rebuilt or restarted, and no OIDC provider is
configured. The real identity-provider login, PostgreSQL-backed grant
provisioning/denials, browser interaction, and enrollment-to-offline-capture,
media, sync, and eligibility workflow remain open. CAP-053 and Phase 7 remain
partial. See the [operator console contract](kernel-operations-console.md),
[mobile access contract](mobile-access-contract.md), [Batch 5 checklist](batches.md),
and [CAP-053](capability-matrix.md#cap-053).


## Batch 5 Field Collector enrollment-to-sync HTTP acceptance — 12 October 2026

Ran the actual Gateway over HTTP using a temporary Uvicorn process bound to
loopback inside the candidate app container. The process used a synthetic API
key scoped to `mobile_device:enroll` for one location; setup and cleanup each
asserted the database name was `kokonut_restore`, the restored recovery clone.
Enrollment returned 201 and one one-time code; registration returned 200 and
derived the collector identity and location from that claim. The device then
retrieved all five active `1.2.0` forms and submitted one valid `field_note_v1`
record; sync returned 200 with one accepted record.

The stored row was `active` for form validation, `not_required` for consent,
and not marked for form review. It remained `pending`, so the governed
eligibility view correctly returned `eligible_for_use = false` with
`transport_pending`. This confirms transport acceptance without treating it as
publication or downstream approval. Synthetic location, device, collection,
and sync-log rows were removed. The temporary Gateway and its private spool
were removed; the recovery database was detached from the candidate network
and stopped with its volume retained. Candidate app, database, and Metabase
remained healthy; the legacy project remains stopped.

One failed harness attempt briefly created and then removed a synthetic
location in the candidate database because the setup script inherited the
container's default `PG_DB`. Cleanup verified zero synthetic location, device,
and collection rows there. The successful run explicitly asserted
`current_database() = kokonut_restore` for setup and cleanup.

Configured OIDC provider/login/session and browser acceptance, private media,
offline browser capture, retired-form and consent-required/withdrawal cases,
semantic review, tenant/RLS, and retention/erasure remain open. See [rollout
evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json),
[Batch 5 checklist](batches.md), [mobile access contract](mobile-access-contract.md),
and [CAP-053](capability-matrix.md#cap-053).


## Batch 5 Field Collector encrypted media upload/sync HTTP acceptance — 12 October 2026

Using the restored `kokonut_restore` clone and a temporary Gateway bound to
container loopback, repeated scoped enrollment and registration, then uploaded a
67-byte synthetic JPEG through the Field Collector API with the encrypted local
provider enabled only in that temporary process. Upload returned 201. The object
was stored in a private `0700` directory as a `KKM1` AES-256-GCM envelope with
file mode `0600`; the original byte sequence was absent at rest, the matching key
and authenticated `head_private` returned the expected JPEG type and length, and
an incorrect key failed authentication.

Sync verified the uploaded object metadata and attached its `media_id` to one
valid `field_note_v1` 1.2.0 collection (HTTP 200). The upload metadata transitioned
to `attached`; form validation was active and consent was not required, but the
collection stayed pending and the eligibility view returned `transport_pending`.
No public download route exists under the access contract, so this slice tested
private object verification/attachment rather than exposing image retrieval.

Cleanup removed the synthetic location, device, enrollment, media metadata,
collection, sync log, encrypted object, ephemeral key, and spool/log directory.
The temporary Gateway stopped, its loopback port closed, and the recovery
container was detached/stopped with its volume retained. Candidate app/database/
Metabase stayed healthy, and the legacy Compose project remained stopped. Offline
browser capture/reconnection, key-matched backup/restore, expiry/orphan cleanup,
OIDC browser acceptance, retired/consent-required withdrawal, semantic review,
tenant/RLS, and retention/erasure remain open. See [media contract](local-private-media.md),
[rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json),
[Batch 5 checklist](batches.md), and [CAP-053](capability-matrix.md#cap-053).


## Batch 5 Field Collector offline app shell — 12 October 2026

Added a service worker for the Field Collector's supported `/mobile`,
`/api/mobile/app`, and Caddy `/field/` entry points. The page registers the
worker on secure origins and asks it to cache the exact static HTML and vault
helper pair, so a previously opened URL can launch offline. Worker updates use
network-first requests for these shell assets and fall back to their cached
copies when offline. API forms, enrollment, media, sync responses, and all
write requests remain network-only; the encrypted IndexedDB vault remains the
only local store for forms, device credentials, records, and photos.

Added explicit public Gateway policies and served worker aliases for each
Gateway entry route. The Caddy `/field/` static route already serves files from
`services/mobile/`, so it needs no route change. Direct `file://` use can still
capture while its page is open but cannot register a service worker or reopen
the app from the offline shell.

The dependency-free Node worker harness passed 2 checks: paired same-origin
shell caching and offline navigation fallback; it rejected a cross-origin
helper and confirmed `/api/mobile/forms` and sync POSTs are not intercepted.
The focused mobile API and Gateway authorization suites passed 51 tests with a
private temporary audit spool. Ruff passed on the changed Python files. An
initial test attempt used the world-writable temp root directly, which the
audit journal correctly rejected; rerunning with a private spool directory
passed. No candidate service was rebuilt or restarted.

Actual browser airplane-mode capture and reconnect/sync remains open, along
with live OIDC provider acceptance, retired and consent-required withdrawal
flows, durable media backup/restore and cleanup, semantic review, tenant/RLS,
and retention/erasure. See the [mobile access contract](mobile-access-contract.md),
[Field Collector guide](../../services/mobile/README.md), [Batch 5 checklist](batches.md),
and [CAP-053](capability-matrix.md#cap-053).

## Batch 5 Field Collector browser offline and reconnect acceptance — 12 October 2026

Exercised the real Field Collector page in an isolated Codex in-app browser
against a temporary same-origin loopback mock. The secure-origin service worker
cached exactly `/mobile` and `/field-collector-vault.js`. After stopping the
mock server, the browser reopened the app shell from cache, unlocked the
encrypted IndexedDB vault, and saved one synthetic field note. The pending count
remained one after a second reload and vault unlock while the origin was still
unavailable. Restarting the mock returned one accepted client ID; the app showed
one record uploaded and cleared the queue. This exercised the browser UI, service
worker, encrypted queue persistence and reconnect client together.

This was an origin outage rather than OS airplane mode: the browser network
interface remained up and `navigator.onLine` continued to say Online. The API
was a temporary mock, not the candidate Gateway/PostgreSQL path. No Docker
container or database was touched. The temporary test service stopped, its
browser tabs closed, and its service-worker registration, cache and encrypted
IndexedDB vault were removed. Machine summary: [browser recovery evidence](builds/2026-10-12-recovery/field-collector-browser-offline-reconnect.json).

CAP-053 stays partial. Actual airplane-mode/device behavior, live Gateway
reconnect in the browser, real OIDC login, media upload while disconnected,
retired/consent-withdrawal paths, durable media backup/cleanup, semantic review,
tenant/RLS and retention/erasure remain open. See the [mobile access contract](mobile-access-contract.md),
[Batch 5 checklist](batches.md), and [CAP-053](capability-matrix.md#cap-053).

## Batch 5 Field Collector candidate-Gateway browser sync and badge refresh — 12 October 2026

Rebuilt only the candidate `app` service after adding an in-place pending-queue
summary refresh in `services/mobile/field-collector.html`. Using the unlocked
encrypted test vault in the Codex in-app browser, saved a second clearly
synthetic Field Note and let the app's normal online sync run. Without pressing
Sync or navigating away, the home screen updated to “Everything is up to date”
with a zero badge. The two browser notes generated two successful candidate
Gateway upload receipts. Aggregate database inspection confirmed both rows
used active Field Note revision `1.2.0`, had no form-review requirement, and
remained `sync_status=pending`, `eligible_for_use=false`,
`eligibility_reason=transport_pending`; transport acceptance did not verify or
publish them.

The candidate had no configured OIDC provider/API-key enrollment credentials,
so this run used a one-time synthetic enrollment fixture in the isolated
candidate database. After the browser check, a guarded transaction removed the
synthetic location, device, enrollment, two offline collections, and two sync
logs; final counts for all fixture relations were zero. The browser vault was
locked. Its encrypted IndexedDB record remains on the local browser because the
Field Collector currently has no supported vault-destroy/reset action; deleting
the candidate device makes the stored test credential unusable. No secrets,
passphrase, token, note payload, or enrollment code are recorded in evidence.

Static verification: inline JavaScript syntax check with `node --check -` and
`git diff --check` passed. Real-browser candidate acceptance verified online
sync and the UI refresh only; it did not simulate airplane mode or Gateway
outage/reconnect, use real OIDC, or cover retired forms, consent withdrawal,
media, retention, erasure, tenant/RLS, or downstream human disposition. No
schema, migration, seed, or canonical provider configuration changed. Rollback
is to revert the `field-collector.html` summary-refresh change and rebuild the
candidate app; the database fixture is already removed. Evidence:
[candidate Gateway browser check](builds/2026-10-12-recovery/field-collector-browser-candidate-gateway.json).

CAP-053 and Batch 5 remain partial. See the [checklist](batches.md),
[capability matrix](capability-matrix.md#cap-053), and [mobile access contract](mobile-access-contract.md).

## Batch 5 Field Collector local vault reset control — 12 October 2026

Added a **Delete local vault** action to the locked Field Collector gate. The
action requires a browser confirmation, closes the app's own IndexedDB handle,
deletes the encrypted local database, and clears known legacy localStorage keys
after database deletion succeeds. If another Field Collector tab blocks the
delete request, open app tabs close their handles and lock their in-memory state
on IndexedDB's version-change event; the deleting tab asks the user to close a
stale tab if the block persists. The warning says this action does not revoke
server-side device enrollment or erase records already synced to the server.

Nine focused Node vault checks passed, covering database deletion/reopen,
blocked-delete notification, and cross-tab version-change behavior. Two offline
shell checks also passed. Inline Field Collector JavaScript syntax and
`git diff --check` passed. The Python pytest wrapper could not run because
pytest is not installed; its underlying Node test command passed directly.
Rebuilt only the `app` service in
`kokonut-kernel-candidate`; Docker reports it healthy. The existing browser
showed the locked vault, deletion warning, and button. The delete action was not
invoked, so the encrypted browser vault remains locked and intact. No schema,
database, provider configuration, or synthetic rows changed.

Rollback: revert the Field Collector source/tests/docs and rebuild only the
candidate app; no database rollback is needed. This does not close real OIDC,
OS airplane-mode/Gateway recovery, retired/withdrawal, downstream disposition,
media recovery/cleanup, tenant/RLS, retention/erasure, or semantic review.
Evidence: [vault reset browser and test record](builds/2026-10-12-recovery/field-collector-vault-reset-control.json).

CAP-053 and Batch 5 remain partial. See the [checklist](batches.md),
[capability matrix](capability-matrix.md#cap-053), [mobile access contract](mobile-access-contract.md),
and [Field Collector guide](../../services/mobile/README.md).

## Batch 5 Field Collector retired-consent withdrawal source checks — 12 October 2026

Added two API regressions for known retired `required` form revisions. A photo
upload is denied before private object storage when a grant was active at
collection but consent has been withdrawn by upload time. Sync is also denied
when an offline retired-form record was captured under a grant, consent was
withdrawn, and a later grant is now the newest decision; the intervening
withdrawal remains disqualifying. Both cases assert rollback and no collection
or media-object write. The existing valid-retired revision check still confirms
that an accepted row enters private review as `retired_review` and
`unassessed`.

The repository `.venv` already contains pytest 9.1.1. All four focused mobile
suites passed: 62 tests. The first run without an explicit audit spool failed
closed because the default journal directory was not private; rerunning with a
mode-0700 temporary spool under `/private/tmp` passed, and that spool was
removed. The API tests mock database decisions and do not cover browser consent
handling; the separate live PostgreSQL view acceptance is recorded below. No
committed database, container, browser vault, migration, or provider configuration
changed. Evidence:
[withdrawal source tests](builds/2026-10-12-recovery/field-collector-withdrawal-source-tests.json).

Rollback: revert the focused test and documentation changes; no runtime or
database rollback is required. CAP-053 remains partial pending browser/API
consent acceptance, OS airplane mode/Gateway recovery, OIDC, and the remaining
human disposition, media, tenant/RLS, and retention gates. See the
[Batch 5 checklist](batches.md), [capability matrix](capability-matrix.md#cap-053),
and [mobile access contract](mobile-access-contract.md).

## Batch 5 Field Collector PostgreSQL consent eligibility — 12 October 2026

Ran the real `v_mobile_collection_use_eligibility` view against the active
candidate PostgreSQL database with synthetic location, participant, form,
consent, and collection rows inside one explicit transaction. The view first
returned `eligible=true` / `eligible` for a synchronized collection covered by
an active grant. After a withdrawal effective after collection and a later
grant, it returned `eligible=false` / `withdrawn_after_collection`, preserving
the intervening withdrawal. Both assertions passed; the transaction ended in
`ROLLBACK`. A follow-up aggregate query found zero locations, parties,
participant links, consent events, or collections, confirming no fixture rows
remain. No migration, provider configuration, or browser vault changed.

This closes the live database-view portion of the consent eligibility check.
It does not exercise the API or browser consent flow, or establish human
retention/erasure disposition, tenant/RLS, OIDC, or OS airplane-mode behavior.
CAP-053 and Batch 5 remain partial. Evidence:
[PostgreSQL acceptance record](builds/2026-10-12-recovery/field-collector-postgres-consent-eligibility.json).

Rollback: the acceptance transaction was rolled back and left no fixture rows;
no runtime rollback is needed. See the [Batch 5 checklist](batches.md),
[capability matrix](capability-matrix.md#cap-053), and
[mobile access contract](mobile-access-contract.md).

## Batch 5 Field Collector PostgreSQL-backed sync handler — 12 October 2026

Exercised `services.mobile.api.sync_collections` against a disposable restored
clone of the candidate database. The synthetic record had an active grant at
collection, then a withdrawal, then a later grant that was current when the
handler ran. The handler rejected it with status 403 and the expected
withdrawal detail. The request left zero `offline_collection` rows for the
client ID and zero upload success logs for the synthetic device.

The source candidate remained unchanged: zero locations, parties, devices,
participant links, consent events, and collections; its ten seeded form
revisions remained. The disposable database and its dump were removed. This was
a direct handler invocation with real PostgreSQL; the Gateway ASGI/HTTP check
is recorded in the following section, and browser consent flow remains open. Evidence:
[PostgreSQL-backed sync acceptance](builds/2026-10-12-recovery/field-collector-postgres-sync-withdrawal.json).

Rollback: the complete synthetic dataset lived in the disposable database,
which was dropped after the check. No candidate migration or service change is
needed. CAP-053 and Batch 5 remain partial pending live retired-form and browser
consent acceptance, OIDC, airplane-mode recovery, and the remaining human
disposition, tenant/RLS, media, retention, and semantic-review gates.

## Batch 5 Field Collector Gateway ASGI/HTTP consent withdrawal — 12 October 2026

Sent a real HTTP request through the Gateway ASGI app and `/api/mobile/sync`
using a temporary Uvicorn server bound only to an ephemeral loopback port in the
candidate app container. The request used an active required-consent form with
a collection-time grant, a later withdrawal, and a still-later current grant.
The API returned HTTP 403 with the expected withdrawal detail and persisted no
collection or upload success log. Gateway audit logging was stubbed in the
temporary process so the shared audit spool stayed untouched.

The PostgreSQL clone and dump were removed, the temporary server exited, and
the candidate app/database stayed healthy. Source candidate counts remain zero
for locations, parties, devices, links, consent events, and collections. This
closes the active required-consent sync path through Gateway HTTP. The
retired-form HTTP case is recorded in the following section. Browser consent
flow remains open, as do OS airplane mode, real OIDC, human disposition, media
recovery, tenant/RLS, and retention/erasure.
Evidence: [Gateway HTTP acceptance](builds/2026-10-12-recovery/field-collector-gateway-http-consent-withdrawal.json).

Rollback: the clone, dump, and loopback server were removed; no candidate
rollback is needed.


## Batch 5 Field Collector retired-form Gateway ASGI/HTTP consent withdrawal — 12 October 2026

Sent a real loopback HTTP request through the Gateway ASGI middleware and
`/api/mobile/sync` using a disposable clone of the candidate PostgreSQL database.
The fixture was a synthetic, reviewed `retired` form revision with a required
consent policy, because all five seeded retired `1.1.0` revisions are
`not_required`. The synthetic participant had a grant effective at collection,
a later withdrawal, and a still-later grant current at sync.

The route returned HTTP 403 with `Consent was withdrawn or denied after
collection`; it wrote neither an `offline_collection` row nor an upload-success
`sync_log` row. The Gateway audit method was stubbed in the temporary process.
The temporary server stopped, the clone was dropped, and its dump was removed.
The candidate remained healthy and its source counts remained zero for locations,
parties, devices, links, consent events, collections, and sync logs; its ten
seeded form revisions remained. This closes the retired required-consent sync
policy path through Gateway HTTP for a synthetic reviewed revision. Browser
consent, OS airplane mode and reconnect, real OIDC, and human disposition,
media, tenant/RLS, retention, and semantic-review gates remain open.

Evidence: [retired-form Gateway HTTP acceptance](builds/2026-10-12-recovery/field-collector-retired-form-gateway-http-consent-withdrawal.json).

Rollback: the synthetic fixture was confined to the disposable clone, which was
dropped after the request; the dump and temporary loopback server were removed.
No candidate data or migration changed.

## Batch 5 Field Collector focused source rerun and synthetic browser consent acceptance — 12 October 2026

Reran the focused Field Collector Python suites for schema validation, offline
transport, encrypted vault behavior, private media, mobile API policy, and
Gateway authentication/CORS: **83 passed**. The Node offline-shell and vault
suites also passed: **11 passed**. The host interpreter lacked pytest, so the
authorized isolated `uv` environment supplied it. The first Python run could
not create the default audit spool in this sandbox and returned 503 on 25 write
paths; rerunning with a private mode-0700 spool passed all checks. No source,
candidate database, or candidate Gateway state changed.

The retired required-consent browser fixture at `http://localhost:8103/mobile`
served the checked-in collector UI and a synthetic local API. Native browser
validation blocked a 19-character participant reference when entered through
real keyboard input (the field requires 32 characters); that value was not
queued. A valid synthetic reviewer-issued reference was then saved in the
encrypted local queue. The mock returned HTTP 403 on sync, and the UI retained
one pending record after retry. An earlier automation-driven short-reference
fill bypassed browser validation and was removed from the queue before the
keyboard check. The fixture observed one form fetch, one device registration,
and five in-memory sync attempts, all rejected with 403.

This passes only the client fixture check. The browser did not use the candidate
Gateway or exercise consent withdrawal. One synthetic encrypted record and its
device credential remain in the isolated local test vault; the mock server is
stopped. No candidate database or Gateway data was written. Actual OS airplane
mode, live Gateway recovery, real OIDC, consent withdrawal in the browser, and
the existing human disposition, media, tenant, and retention gates remain open.

Evidence: [focused source checks and browser acceptance](builds/2026-10-12-recovery/field-collector-consent-source-regressions.json).

Rollback: the Python audit spool, test environment, and mock server are isolated
under `/private/tmp`. The encrypted browser test vault remains available for
inspection; deleting it requires the application’s explicit confirmation
action. No application rollback is needed.


## Batch 5 Field Collector form operations decision — 12 October 2026

Decided that form customization must remain available when Directus is absent.
The initial authoring surface will be a reviewed JSON-manifest CLI that
validates and previews offline, then explicitly publishes through the existing
`mobile_form` row and migration 381 immutable-snapshot trigger. Direct writes to
`mobile_form_version` and edits to applied migrations remain prohibited.

A private location-scoped review queue is also required before retired or
review-required records are used operationally. It must derive location scope
from OIDC grants, minimize payload visibility, keep consent eligibility as a
hard prerequisite, and append review/disposition events without changing
consent or publishing records. Legal retention periods, erasure authority, and
organization-wide tenant/RLS policy remain open human/governance gates.

The decision and interface requirements are recorded in the
[form operations contract](mobile-form-operations.md). Offline validation and
preview remain available without database credentials. The new `publish`
command also defaults to an offline preview; applying requires `--apply`, a
publisher distinct from the manifest reviewer, and an explicit expected current
version or an assertion that the form is absent. It locks the mutable
`mobile_form` row, rejects historical version reuse and location reassignment,
sets transaction-local `kokonut.actor`, and leaves immutable snapshot creation
and retirement to the migration 381 trigger. It writes no `mobile_form_version`
rows directly. Twenty-nine focused form/schema checks passed using an isolated
fake transaction adapter; Ruff and `git diff --check` passed. A separate
no-volume PostGIS fixture then verified trigger-created snapshots, actor
attribution, active-to-retired transition, duplicate/stale/location guards,
database-error rollback, and immutable historical content. The fixture applied
the migration 381 publication-trigger prefix with minimal prerequisites, not the
full migration or active candidate. [Acceptance evidence](builds/2026-10-12-recovery/mobile-form-publication-transaction.json).
The temporary container and files were removed; candidate services and database
were not changed.


## Batch 5 OIDC Field Collector review queue source slice — 12 October 2026

Added `services/gateway/operator_mobile_review.py` with read-only list/detail
queries for synced collection rows that are form-review-required or fail the
consent/form eligibility view. Both queries bind the requested location and
repeat the active-grant check. List access requires
`mobile_collection_review:read`; payload detail requires the separate
`mobile_collection_review:read_detail` grant, returns payloads only up to
512 KiB, and exposes only a photo count. The query omits participant linkage,
collector identity, and device ID.

The operator console now lists these rows and displays payload detail as text.
The OIDC middleware scopes and audits both routes by operator and canonical
location; there are no review decision controls or media-download routes.
Thirteen focused route/query tests passed, Ruff is clean, and the console's
inline JavaScript passes `node --check`. The OIDC provider is not configured,
and this source-only change was not deployed or tested against the candidate
database. Append-only review/disposition events, real-provider grant checks,
and browser payload/privacy acceptance remain open.


## Batch 5 OIDC Field Collector append-only review events — 12 October 2026

Added `schemas/postgres/382_mobile_collection_review_events.sql` and the
append-only write path in `services/gateway/operator_mobile_review.py`. The
OIDC route requires the location-scoped `mobile_collection_review:review` grant
and separately requires `read_detail`; CSRF is enforced by the existing
operator middleware, and the authenticated OIDC operator supplies the event
actor. The browser form captures one of three review-note decisions, a bounded
reason, and one to twenty evidence references.

Migration 382 binds each event to a synced collection in the same location that
is currently review-required or ineligible. It validates reason/evidence
bounds and exact evidence keys, and rejects event updates and deletes. The write
path inserts only into the event table; it does not alter collection payload,
consent eligibility, or governed lifecycle state. The console renders the event
history with text-only DOM APIs and shows the form only when both grants exist.

The focused queue/event/auth suites passed **22 tests**; Ruff, console
JavaScript syntax, and `git diff --check` passed. Migration 382 was applied to a
separate no-volume PostGIS fixture with minimal prerequisite tables and an
eligibility-view stub. Actual service list/detail and append/history calls passed; collection eligibility
fields remained unchanged. Cross-location, ungranted-operator, and revoked-grant
list/detail/write attempts were denied and persisted no unauthorized events.
Migration 382 rejected malformed/missing evidence keys, unsynced collections,
updates, and deletes. This did not replay
migration 381 or connect to the active candidate; the candidate remains at its
previous schema level. [Isolated migration evidence](builds/2026-10-12-recovery/mobile-review-event-migration-isolated.json).

Configured OIDC, real operator grants, browser acceptance, full migration-chain
acceptance, human content disposition, tenant/RLS, retention/erasure, and media
recovery remain open. Rollback is to disable the review-event route and form;
append-only events remain preserved for audit.


## Phase 7 clean ordered migration replay through 382 — 12 October 2026

The repository migration runner applied all 373 ordered PostgreSQL schema
migrations through 382 to a clean, disposable PostGIS 16 database. The run
reported zero failures; the subsequent schema-only plan reported zero pending.
Direct inspection confirmed 373 applied ledger rows, the
mobile_collection_review_event table, both non-internal triggers, and the
expected pgcrypto, PostGIS, and uuid-ossp extensions.

The database had no persistent volume and published no host port. Its temporary
container and network were removed after verification. The candidate app,
Metabase, and database containers remained healthy and were not targeted.
Encrypted settings were decrypted only to list OIDC variable names; none were
present, so configured-provider acceptance remains open.

This closes the clean full-source replay gate for migration 382. That replay
did not target the candidate; the separate candidate rollout and its encrypted
checkpoint/restore rehearsal are recorded below. Real OIDC login/grants,
authorized browser review, human content disposition, retention/erasure, and
tenant/RLS remain open.
[Evidence](builds/2026-10-12-recovery/mobile-review-event-ordered-migration-run.json).


## Phase 7 candidate migration 382 rollout — 12 October 2026

The candidate migration plan showed exactly one pending schema and no checksum
drift. Before rollout, an age-encrypted PostgreSQL checkpoint was created and
restored into a separate internal-only template0 database. All 372 applied
schema migration IDs/checksums, installed extensions, and selected mobile and
operator row counts matched. The encrypted checkpoint remains under the ignored
local backups directory; the temporary restore container, network, and volume
were removed.

The checksummed runner applied only migration 382 to the candidate. The follow-up
plan reports zero pending across 373 applied schema migrations. The review-event
table and both triggers are present, with zero events. Only the candidate app
was rebuilt from source commit 7c69510 and recreated; its database container,
PostgreSQL volume, and Metabase were not recreated. All three services are
healthy. From inside the app container, /health returned 200, the OIDC login
route returned 404 because the optional provider is disabled, and the anonymous
review queue returned 401.

The exact prior app image had been pruned locally; a retained pre-form-schema
image is tagged as the fallback and is not an exact image snapshot. The encrypted
database checkpoint is the exact pre-migration rollback point. Real OIDC login,
authorized browser review, reviewer disposition, semantic review, retention/
erasure, and tenant/RLS remain open.
[Evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json).


### Batch 5 local Docker candidate recovery — 12 October 2026

The Docker daemon responds normally. The earlier app-image commit failed because
the exact prior image content digest had already been pruned locally. The
candidate app was rebuilt from source commit `7c69510`; the running image is
`sha256:4a238b97dd2d6fa68ac68068948857b2cd93c2dbce17267f379991180fc886f8` and
is now also retained under the dated local tag
`kokonut-kernel-candidate-app:mobile-review-382-20261012`.

The candidate app, Postgres, and Metabase are all healthy with zero restarts.
`http://127.0.0.1:8098/health` returns 200. The configured Compose host port is
8098; 8103 was used by an earlier browser fixture and is not published now. The
legacy stack remains stopped. No database, Metabase, legacy, or recovery volume
was modified. Nineteen stopped, successful recovery-helper container records
were removed without `-v`; all volumes remain. Docker reports 12.68 GB of
reclaimable local volumes and 20.61 GB of build cache, which were retained; no
global prune was run. The older
`pre-form-schema` image is only a fallback, not an exact image snapshot; the
encrypted database checkpoint remains the exact pre-migration data rollback
point.

[Docker recovery evidence](builds/2026-10-12-recovery/docker-candidate-runtime-recovery.json).


### Batch 5 live Field Collector Gateway outage recovery — 12 October 2026

With user approval, a temporary synthetic device was enrolled against a
synthetic location in the local candidate. One non-sensitive `field_note_v1`
1.2.0 record was prepared in the browser. The candidate app container alone was
stopped while Postgres and Metabase remained up. The browser saved the note to
its encrypted queue and showed one pending record; the database had no
collection or sync log for the fixture at that point.

The candidate app restarted and `/health` returned 200. No manual sync was
triggered. The Field Collector's background retry cleared the pending badge
after its next interval. The database recorded one accepted transport and one
collection; the governed eligibility view kept it ineligible with
`transport_pending`. A guarded cleanup revoked the temporary device and removed
the synthetic location, enrollment, collection, and sync log; all five
post-cleanup counts were zero. The browser vault was locked afterward. Its
encrypted test credential remains locally stored but its server device was
deleted, so the credential is unusable.

This confirms encrypted queue retention and automatic sync after a local
Gateway outage. The host stayed online and the browser displayed “Online”; this
does not satisfy OS airplane-mode or `navigator.onLine=false` acceptance. Real
OIDC, browser consent withdrawal, tenant/RLS, retention/erasure, media recovery,
and human disposition remain open.

[Gateway outage recovery evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json).


### Batch 5 macOS Wi-Fi-off Field Collector probe — 12 October 2026

With the user's approval, Wi-Fi interface en1 was briefly switched off and then
restored; its final reported power state was On. The existing browser remained
on `http://127.0.0.1:8098/mobile`, continued to display Online, and showed an
empty queue with no enrolled device. No test note or credential was created.

This is inconclusive rather than offline acceptance: the candidate app and
Gateway are on localhost, which stays reachable when Wi-Fi is off, and the
browser did not report Offline. The capability matrix and OS-offline checklist
remain open for capture/reconnect against a path that is actually severed; no
LAN binding or other network exposure was added.

[Probe evidence](builds/2026-10-12-recovery/field-collector-wifi-off-probe.json).


### Batch 5 isolated private-media checkpoint/restore rehearsal — 12 October 2026

The repository media checkpoint/restore scripts passed with one synthetic local
`KKM1` object. The age-encrypted archive did not contain the separate media key;
the manifest bound the SHA-256 of a synthetic DB-checkpoint fixture. Restore to a
new 0700 directory verified the object inventory. `head_private` authenticated
the restored envelope with the temporary media key; direct test-only decryption
matched the synthetic plaintext SHA-256, and a wrong media key failed.

The database fixture only exercised manifest binding; no database was restored
and no upload-row hash/size parity was checked. The temporary media key remained
in process memory and no SOPS secret was read. All synthetic files, keys and
archives were removed. The candidate database and provider configuration were
not touched. Production SOPS custody, database/object parity, persistent-volume
recovery, expiry/orphan cleanup and retention remain open.

[Evidence](builds/2026-10-12-recovery/field-collector-media-backup-restore.json).


### Batch 5 media archive restore with supplied SOPS age identity — 12 October 2026

The age recipient was derived from the user-provided identity file. The local
media checkpoint script encrypted one synthetic `KKM1` object; after deleting
the source, the restore script used that identity to restore into a new private
directory. Inventory and ciphertext SHA-256 matched, `head_private` authenticated
the envelope with a separate temporary media key, and the wrong media key was
rejected.

This validates access to the supplied age identity for archive encryption and
restore. It did not decrypt `.env.sops` or recover the production media key. The
DB checkpoint fixture was synthetic; there was no real DB restore, upload-row
parity check, or persistent-volume/container replacement. Temporary data and keys
were removed, and candidate database/provider configuration stayed untouched.

[Evidence](builds/2026-10-12-recovery/field-collector-media-sops-age-restore.json).


### Batch 5 local media key configuration check — 12 October 2026

At the time of this check, a targeted SOPS lookup found no
`MOBILE_MEDIA_LOCAL_KEY` or explicit `MOBILE_MEDIA_PROVIDER` entry in the tracked
`.env.sops`. The source defaults to S3 when no provider is set, and
`docker-compose.kernel-edge.yml` requires the local media key. The result was
historical; the next batch provisions the key with owner approval. See
[availability evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-availability.json).


### Batch 5 SOPS media-key provisioning and recovery — 12 October 2026

With the repository owner's approval, generated a random 32-byte
`MOBILE_MEDIA_LOCAL_KEY` in process memory and added it to the tracked encrypted
`.env.sops` through `sops set --value-stdin`. A targeted SOPS extraction using
the supplied age identity matched the generated value; the key was not printed
or stored in plaintext. `MOBILE_MEDIA_PROVIDER` remains unset, so the source and
base profile still default to S3; the candidate runtime was not reconfigured.

Then used that exact SOPS-managed key in an isolated one-object KKM1 checkpoint
and restore. The archive was encrypted and restored using the supplied age
identity. The restored AES-GCM object authenticated, its plaintext digest
matched the synthetic fixture, and a wrong media key was rejected. The
database-checkpoint binding was a synthetic fixture only; no database, upload
row, Compose volume, or candidate container was touched. All temporary media,
archives, and dependency files were removed.

This closes the SOPS key availability and one-object key-matched recovery check.
Database/upload-row parity, persistent-volume/container replacement,
expiry/orphan cleanup, and retention remain open. See
[provisioning and recovery evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-provisioning.json),
[media contract](local-private-media.md), and [CAP-053](capability-matrix.md#cap-053).


### Batch 5 isolated edge media-volume recovery — 12 October 2026

Ran the candidate and edge Compose overlays under a unique temporary project,
with only the targeted SOPS media key and database password read into process
memory. Using `docker compose run --rm --no-deps`, the first disposable app
container wrote one synthetic KKM1 object to the edge `kernel-private-media`
named volume. A second disposable app container found the same object, verified
its AES-GCM tag and plaintext digest, rejected a wrong media key, and deleted the
object. The private directory and object modes were 0700 and 0600, and the
plaintext was absent from the stored envelope.

The isolated Compose network and synthetic volumes were removed. The database
service and candidate project were not started or changed. A first verifier
invocation had a Python syntax error before checking recovery; its temporary
project was also torn down, and the corrected full run passed. This validates
named-volume persistence across disposable app containers, but it did not create
or compare a `mobile_media_upload` row, recreate the candidate service, or test
expiry/orphan cleanup and production retention. See [edge volume
evidence](builds/2026-10-12-recovery/field-collector-edge-media-volume-recovery.json)
and [CAP-053](capability-matrix.md#cap-053).

### Batch 5 isolated PostgreSQL/private-media parity — 12 October 2026

Applied the real migration 358_mobile_private_media.sql in a disposable
PostGIS project with minimal synthetic prerequisite tables. A synthetic upload
row matched the encrypted object written through the edge Compose provider on
object key, content type, byte size, and SHA-256. A second disposable app
container queried the row, authenticated/decrypted the AES-GCM object, matched
the plaintext digest to the row, and rejected an altered key. Synthetic rows,
object, network, and project volumes were removed. The running candidate app,
database, and provider selection were untouched.

The first database setup saw an early socket close; after full Compose health
wait, a diagnostic run passed the setup and migration. One full-check attempt
then stopped before fixture creation because its command used a Compose flag
unsupported by the installed version; the corrected run passed. The acceptance
was not an HTTP upload-route test, full ordered migration replay, or candidate
service recreation. Expiry/orphan cleanup, retention, and candidate recreation
remain open. See [parity evidence](builds/2026-10-12-recovery/field-collector-media-db-object-parity.json),
[media contract](local-private-media.md), and [CAP-053](capability-matrix.md#cap-053).

### Batch 5 bounded Field Collector media expiry cleanup — 12 October 2026

Implemented the dry-run-default operator CLI at services/mobile/media_cleanup.py
and mounted it as mobile-media-cleanup in the unified CLI. Apply mode is
explicit, limits a run to 1–500 rows (default 100), and selects only uploads
whose 30-day expires_at has passed, which remain in uploaded status, and which
have no attached collection. It locks rows with FOR UPDATE SKIP LOCKED, deletes
the object before marking the row expired, and keeps attached media for governed
retention/erasure review. Provider exceptions are sanitized. No object-listing
interface exists, so unregistered crash-orphans are not automatically removed.

Eight cleanup unit tests passed. The broader cleanup/media/API/CLI regression
set passed all 44 tests using a private temporary audit spool; standard and
security Ruff passed. The run emitted 117 existing Starlette/FastAPI
deprecation warnings. An isolated PostGIS acceptance applied migration 358,
created two expired unattached objects, one expired
attached object, and one unexpired object, and verified dry-run count, a
one-row apply limit, the next bounded apply, and an idempotent repeat no-op.
Both eligible objects were removed and marked expired; attached and live rows
and objects remained. All synthetic rows, objects, temporary directory, Compose
network, and project volumes were removed. The candidate project was untouched.
The first integration harness stopped before fixture creation due to an invalid
Compose port argument; the corrected run passed. Candidate service recreation,
orphan reconciliation, and production retention remain open. See [cleanup
evidence](builds/2026-10-12-recovery/field-collector-media-expiry-cleanup.json),
[media contract](local-private-media.md), and [CAP-053](capability-matrix.md#cap-053).

### Batch 5 full edge runtime media-volume replacement check — 12 October 2026

Started two disposable full Kernel runtime containers from the existing
candidate app image on the candidate Docker network. Both reached the health
endpoint while using the existing database for health connectivity only. A
synthetic encrypted object in a unique named volume authenticated and matched
its plaintext digest after each runtime start. The object, both containers, and
volume were removed. The primary candidate app, database, Metabase, and their
configuration were not stopped or changed; background workers and upload/sync
were not exercised.

This verifies a full runtime start/replacement with the edge media volume on the
candidate network, but does not certify replacing or reconfiguring the primary
candidate app service. See [runtime volume evidence](builds/2026-10-12-recovery/field-collector-media-runtime-volume-recreation.json),
[media contract](local-private-media.md), and [CAP-053](capability-matrix.md#cap-053).

### Batch 5 Gateway lifespan deprecation cleanup — 12 October 2026

The prior focused run reported 117 Starlette/FastAPI deprecation warnings. All
application lifecycle warnings traced to the Gateway's deprecated
`@app.on_event("startup")` and `@app.on_event("shutdown")` registrations,
repeated as test apps were created. Replaced those hooks with FastAPI's lifespan
context manager while preserving the 15-second audit replay loop and cancelling
and awaiting its task on shutdown. Added a lifecycle test that verifies the
worker is created and cancelled. The service tree now has no application
`on_event` registrations.

The updated Starlette TestClient also warned when falling back to legacy
`httpx`; declared `httpx2` in the development dependency group and legacy full
requirements, then installed version 2.13.1 in the local environment. Updated
the stale public-metrics tests to use valid UUID paths and mock the current
analytics backend contract. The Gateway lifecycle, public metrics, Gateway auth,
mobile API, media cleanup/storage, and CLI suites passed: 68 tests, zero
warnings. Ruff, `git diff --check`, and dependency-group alignment passed. See
[the Batch 5 checklist](batches.md).

### Batch 5 candidate edge-media provider activation — 12 October 2026

The current candidate had no `mobile_media_upload` rows. After validating the
edge Compose configuration against SOPS, the app image was rebuilt and the
candidate app alone was recreated with the edge overlay; the old image was
retained under `kokonut-kernel-candidate-app:pre-edge-media-6ce3c3f`. The
running app selected the local provider and mounted the named private-media
volume with directory mode 0700 and ownership 10001:10001.

A synthetic encrypted KKM1 JPEG passed write/head/delete with plaintext absent
and file mode 0600. A second object remained on the volume across an app
restart, authenticated with the configured key, and matched its expected
plaintext SHA-256; it was then removed. Upload-row counts remained zero, the
database and Metabase containers were not recreated, and all three candidate
services remained healthy. The source and base Compose profile still default
to S3; the running candidate now uses the edge overlay. Full edge resource
limits on PostgreSQL, authenticated HTTP upload/sync, ARM64, production backup
retention, and orphan reconciliation remain open. See [candidate activation
evidence](builds/2026-10-12-recovery/field-collector-candidate-edge-media-activation.json)
and the [media contract](local-private-media.md).


### Batch 5 candidate Gateway browser outage/reconnect and form payload correction — 12 October 2026

Repeated the approved live browser outage check against the candidate. The first
retry returned HTTP 422 because the form serialized empty optional fields as
JSON `null`, while immutable schemas accept the field only when omitted or a
string. The failed item stayed encrypted locally and created no server row; it
was removed through the queue UI. Updated `saveRecord` to omit empty fields.

Rebuilt with the explicit Compose project `kokonut-kernel-candidate` and
recreated only the app. Pausing the candidate app left PostgreSQL and Metabase
healthy. While paused, one synthetic note remained in the encrypted browser
queue and database collection/sync-log counts stayed zero. After app recovery,
the browser's background retry returned HTTP 200 and the home badge cleared
without manual sync or navigation. One active `field_note_v1@1.2.0` row and one
sync receipt were observed; the row remained `eligible_for_use=false` with
`transport_pending`. A guarded transaction revoked and removed the synthetic
location, enrollment, device, collection and sync log. All guarded counts were
zero afterward, the browser vault was locked, and its stored token is invalid.

An initial rebuild attempt omitted the candidate Compose project selector and
created a stopped app container plus empty resources under the legacy project
name; it failed to bind the candidate's already-used port. Only those exact
newly-created resources were removed. Pre-existing legacy containers/volumes
were left untouched and remain stopped; the three candidate services are
healthy. This outage test keeps host Wi-Fi online and the browser reports
“Online”; per-browser offline indication/OS airplane mode remains open. Real
OIDC, browser consent-withdrawal, retention/erasure, tenant/RLS, and human
disposition remain open. See [browser outage evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json),
[Batch 5 checklist](batches.md), and [CAP-053](capability-matrix.md#cap-053).

### Batch 5 Field Collector proxy route correction — 12 October 2026

Addressed the PR #68 review finding that `/mobile` resolves its relative
service-worker URL at the origin root, outside Caddy's `/mobile*` proxy route.
The Gateway now redirects `/mobile` to canonical `/mobile/`; relative vault and
service-worker URLs therefore remain under `/mobile/`, which the existing
Caddy and Traefik Gateway routes forward. The `/mobile/` route remains an
explicitly public Field Collector route. Updated operator/deployment docs to
use the slash URL.

The complete mobile API suite passed (33 tests), as did both dependency-free
offline-shell Node checks; Ruff and `git diff --check` passed. The suite used a
private mode-0700 temporary audit-spool directory and that journal was removed.
Rebuilt and recreated only the candidate app; PostgreSQL and Metabase remained
healthy. Direct loopback HTTP confirmed `/mobile` returns 308 to `/mobile/`,
`/mobile/` returns 200, the worker asset returns 200 JavaScript, and Gateway
health is `ok`. No browser reload or vault change occurred. Caddy/Traefik was
not running for this probe, so live proxy ingress is still not certified. See
[route evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json)
and the [Batch 5 checklist](batches.md).


### Batch 5 candidate Caddy Field Collector proxy acceptance — 12 October 2026

Started only the optional `proxy` service in `kokonut-kernel-candidate` with
`--no-deps`; the existing app, database, and Metabase stayed healthy. Using the
loopback-only Caddy ports, HTTP `/mobile` redirected to HTTPS, HTTPS `/mobile`
redirected to canonical `/mobile/`, the shell returned 200, and the service-worker
asset returned 200 JavaScript. `/health` returned 200 with `status=ok` and
`audit_capture=ok`; Caddy's `Via`, `nosniff`, frame-denial, and referrer-policy
headers were present. The HTTPS request used curl's local-CA bypass because Caddy
issued a local development certificate. No browser tab or vault changed, no
database or schema was written, and the legacy Compose project was untouched.
This closes the candidate Caddy route smoke only; external Traefik, public ingress,
trusted-proxy chains, and browser acceptance through Caddy remain open. A fresh
isolated browser tab then stopped before page load with `ERR_CERT_AUTHORITY_INVALID`
for the local Caddy certificate. The security interstitial was not bypassed and the
existing user vault tab was not touched. Browser-through-proxy acceptance needs a
locally trusted development certificate, completed by the repository owner. See
[proxy route evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json).


### Batch 5 private-media orphan reconciliation — 12 October 2026

Added a provider-neutral inventory and operator command in
`services/mobile/media_storage.py`, `services/mobile/local_media.py`, and
`services/mobile/media_reconcile.py`, mounted as `mobile-media-reconcile` in the
unified CLI. It is dry-run by default, requires objects to be at least 24 hours
old, and caps each apply run at 500 objects (default 100). Apply rechecks both
registered upload keys and current provider inventory before deletion, sanitizes
provider/database errors, and never modifies upload rows. Local inventory fails
closed on symlinks, unknown entries, and non-regular files. S3-compatible
inventory uses pagination and needs prefix-scoped ListBucket permission; apply
also needs DeleteObject permission.

The focused storage, reconciliation, and expiry-cleanup suites passed: 31 tests.
Standard Ruff and security Ruff passed, and the standalone command help rendered.
A dry-run against the local edge provider in `kokonut-kernel-candidate` found
zero provider objects and zero registered upload keys; it deleted nothing and
made no database changes. The one-off app container used read-only mounts of the
current `services/` tree and `VERSION`; candidate services were not rebuilt or
recreated. Live S3/R2 listing/deletion, populated-bucket lineage, and production
retention ownership remain open. See [run evidence](builds/2026-10-12-recovery/field-collector-media-orphan-reconcile.json),
[media contract](local-private-media.md), and [CAP-053](capability-matrix.md#cap-053).


### Batch 5 isolated private-media orphan apply acceptance — 12 October 2026

Exercised the actual local encryption adapter and reconciliation function in an
isolated temporary directory. Two synthetic objects were written; one object's
modification time was set to 26 hours old while the other remained current.
Dry-run reported two unregistered objects, one eligible object, one too-young
object, and zero deletions. Explicit apply deleted only the aged object. The
younger object's `head_private` check still authenticated successfully.

The injected database adapter recorded two SELECT statements during apply and
no mutations. The temporary directory and remaining synthetic object were
removed. This validates the local apply path and age gate without touching the
candidate media volume, a live database, S3/R2, or production data. See
[isolated apply evidence](builds/2026-10-12-recovery/field-collector-media-orphan-apply-isolated.json)
and the [media contract](local-private-media.md).


### Batch 3 farm activity workflow source map — 12 October 2026

Mapped `farm_activity_v1` 1.2.0 across the offline Field Collector, exact-form
validation and consent eligibility, the location-scoped mobile review queue,
canonical `farm_activity`, lifecycle ledger/specification, metrics, and farm
summary report. The source map confirms mobile sync creates a private
`offline_collection`; there is no Field Collector promotion route. For this
`not_required` form, the eligibility view can report consent eligibility, but
that is separate from semantic review, independent verification, and
publication. The existing workflow spec also has terminal rejection and system
publication; that conflict is corrected in the workflow-spec slice below.

Checked the source-map and workflow-spec items in Batch 3. The declarative spec
now requires an independent human verifier by contract, keeps rejected records
available for an explicit correction loop or terminal exception disposition,
and makes publication a separate human-approved step. Added focused contract
coverage. These are workflow declarations only: runtime authorization,
submitter/verifier identity enforcement, database lifecycle guards, canonical
promotion, and report/metric integration remain open. The [workflow map](farm-activity-workflow-map.md)
contains the source trace, field contract, acceptance sequence, and rollback
strategy. CAP-001 remains partial; no end-to-end capability acceptance is
claimed.


### Batch 3 private intake and canonical draft promotion — 12 October 2026

Implemented the first native Field Collector-to-farm-activity write slice on
the feature branch. `services/gateway/farm_activity_workflow.py` now lists
eligible, unpromoted `farm_activity_v1` 1.2.0 captures without free text,
returns bounded private detail behind two location-scoped read grants, and
promotes an explicitly reviewed capture to one canonical `draft`. Promotion
rechecks the exact active form revision, stored payload schema, consent/use
eligibility, location, sync state, and database grants in the write transaction.
It holds locks on the active form revision, any participant link, and both
grants through commit so concurrent retirement or revocation is ordered against
the promotion. Location comes from the collection; only declared activity fields are copied;
source lineage retains a payload digest rather than another copy of private
text. The operator identity is recorded separately from participant/device
identity. Identical retries return the existing source row; mismatched source
identity fails closed.

OIDC policies and routes in `services/gateway/operator_auth.py` use CSRF for
promotion and require `farm_activity:create_draft` plus
`mobile_collection_review:read_detail`; private reads are no-store. Migration
383 preflights duplicate Field Collector source identities, adds a partial
unique source index, and adds an append-only event ledger with transition-shape
checks and a trigger tying event location/status/source to the canonical row.
The `draft_created` event requires a review acknowledgement and matching
payload digest. It does not yet implement governed transition routes or
independent verifier/publisher enforcement.

Validation: `tests/test_migration.py`, `tests/test_workflow_specs.py`,
`tests/test_farm_activity_workflow.py`, and `tests/test_operator_auth.py`
passed (55 tests); Ruff passed. Migration 383
compiled transactionally in a disposable database, and synthetic trigger
checks accepted a valid draft event while rejecting canonical status mismatch
and event updates. A read-only `EXPLAIN` verified the exact promotion lock
query against the existing eligibility view. The temporary database and
migration file were removed. No candidate migration, app rebuild, or data
write occurred. The migration/API are not yet deployed.

Batch 3 now has the native intake/draft slice checked off. Submit/reject/rework/
verify/publish enforcement, reviewer independence, published-only reporting,
draft metric parity, and complete disposable database failure coverage remain
open. CAP-001 remains partial; this does not satisfy MAN-CAP-001. The
[workflow map](farm-activity-workflow-map.md) and [Batch 3 checklist](batches.md)
track the interface, evidence, and rollback boundary.


### Batch 3 native farm activity lifecycle enforcement — 12 October 2026

Added `services/gateway/farm_activity_lifecycle.py` and six OIDC-protected,
location-scoped transitions at
`POST /operator/api/farm-activities/{id}/{action}`: submit, verify, reject,
request-rework, publish, and close-exception. Every action requires its own
grant, CSRF, a canonical row lock, and an active grant lock. Rejection, rework,
and exception closure require a nonblank reason. One transaction changes
status and writes the append-only operator event; identity, action, source,
location, current status, and event-to-scope mapping are checked by PostgreSQL.
The verifier differs from the latest submitter. Rejection from either submitted
or verified state requires a reviewer distinct from the latest submitter and
verifier. Publication requires a third actor distinct from both. Rework returns
the row to draft while preserving prior events; content is immutable after
submission and editable only after an explicit rework transition. Exception
closure records a reasoned event without changing the rejected lifecycle state.

Migration 384 scopes write/status guards to `farm_activity_v1` version 1.2.0,
preflights matching draft and current-status evidence, requires an enabled
operator with a current location grant, locks both promotion grants and
transition grants, and appends status-change events synchronously. Historical
Field Collector rows from other form versions remain outside this guard. The
deferred constraint trigger protects draft creation evidence; status-transition
evidence is inserted and validated in the same statement transaction.

Validation: 77 focused migration, workflow-spec, draft-promotion, lifecycle,
and OIDC tests passed; Ruff passed. Migrations 383–384 compiled transactionally
in a disposable PostgreSQL database. Synthetic rows completed draft creation,
submit, independent verification, rework, resubmission, publication, rejection,
and same-status exception closure. Database guards rejected missing draft
evidence, self-verification, rejection by either submitter or verifier,
missing reason, revoked scope, illegal transitions, post-submit content edits,
and event update/delete. A legacy Field Collector row remained outside the
new 1.2.0 guard. The scratch database was removed; no candidate migration,
rebuild, or write occurred. The candidate does not have
these routes yet.

Sanitized scratch evidence: [lifecycle acceptance](builds/2026-10-12-recovery/farm-activity-lifecycle-isolated.json).

At this lifecycle checkpoint, runtime transition enforcement was implemented in source only. OIDC against a
configured provider, wrong-location/error-injection acceptance, duplicate and
stale-source promotion checks, published-only metric/report handoffs and MAN-CAP-001 remained open. CAP-001 remains partial. Rollback after deployment
must keep a compatible transition endpoint for 1.2.0 rows or pause native
intake; the additive database guards must not be bypassed through Directus.
See the [workflow map](farm-activity-workflow-map.md),
[checklist](batches.md), and [capability matrix](capability-matrix.md).


### Batch 3 published farm-activity report and rework metric — 12 October 2026

`services/export/reports/core.py::generate_farm_summary` now includes a
location- and activity-date-filtered summary of published farm activities:
counts and reported labor hours by activity type. It omits description, notes,
raw source payload, device or participant identity, media references, and
canonical activity IDs. The existing `store_snapshot` path hashes and stores
this report as an unfrozen `draft`, with no automatic submission or publication.

`services/metrics/calculators/rework_rate.py` includes farm activities in its
published lifecycle cohort, uses an inclusive calendar end date, and returns
published source IDs plus the reworked subset with 100-ID caps and truncation
metadata. The existing metric engine stores the result unverified and still
requires separate human review. Cursor cleanup in the calculator was also
made explicit.

Validation: 11 focused report, metric, report-governance, and draft-metric
tests passed; Ruff passed. The synthetic report fixture yielded three published
activities and 5.25 reported hours; snapshot hashing and draft/frozen fields
were checked. The metric fixture yielded 50%, with exact published and
reworked source IDs; the metric-engine test confirmed `verified = FALSE`.
An additional disposable PostGIS 16 run used a minimal synthetic schema (not
the migration chain) and verified two published activities, 5.25 hours,
exclusion of a draft activity and private fields, a hashed unfrozen report
draft, a 50% rework metric with both source IDs, and `verified = FALSE`. The
container was removed. Full-schema parity remains open. No candidate migration,
rebuild, or data write occurred.
Evidence: [sanitized report/metric contract](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json).

Batch 3's report/metric source item and synthetic PostgreSQL check are complete;
full-schema parity, route and grant acceptance, candidate rollout, and
MAN-CAP-001 remain open. CAP-001 is still partial. See the [workflow map](farm-activity-workflow-map.md),
[checklist](batches.md), and [capability matrix](capability-matrix.md).


### Batch 3 full-schema report/metric parity — 12 October 2026

Replayed all 375 ordered PostgreSQL schema migrations (excluding seeds) through
the repository migration runner into an isolated PostGIS 16 database. The actual
farm-summary, snapshot, and metric service functions passed against the migrated
schema: two published activities produced 5.25 reported hours; a draft activity
and private source marker were excluded; snapshot hash matched with
`status=draft` and `frozen=false`; and `rework_rate_pct` persisted 50% with two
source IDs and `verified=false`. The scratch volume and network were removed; candidate state remained unchanged. This closes full-schema parity for the selected report/metric slice. The expanded Batch 3 suite passes 91 tests and Ruff, including wrong-location query guards and an injected event-write failure that rolls back draft promotion using a unit database double. A disposable full-schema PostGIS check then made a real trigger reject the submitted workflow event during the transition service call: status remained `draft`, with no submitted workflow event or lifecycle transition committed. Two barrier-synchronized promotion calls for one synthetic capture produced one draft and one `draft_created` event; the second result used the same activity ID with `created=false`. Higher-contention stress, configured-provider OIDC, candidate rollout, and MAN-CAP-001 remain open.
Evidence: [report/metric acceptance](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json);
[Batch 3 checklist](batches.md); [workflow map](farm-activity-workflow-map.md).


## Batch 3 farm-activity candidate rollout — 12 October 2026

Applied migrations 383–384 to the local candidate after checking that its
`farm_activity`, native 1.2.0 activity, and `offline_collection` tables were
empty and had no duplicate source identities. Created an age-encrypted
PostgreSQL checkpoint; restored it into a fresh internal-only template0 target;
and matched all 373 pre-rollout schema fingerprints, installed extensions, and
selected mobile/operator/farm counts across 388 comparison rows. The temporary
recovery project was removed after parity passed.

The migration runner applied both migrations with zero failures. The candidate
now has 375 applied schema migrations, zero pending, the native lifecycle
guards, and zero farm-activity, collection, or workflow-event rows. Rebuilt the
current app from commit `c87aa33f1cbaf03ef4fae991077c2198be14e1fa`, preserved the
prior app image under a rollback tag, and recreated only the candidate app. App,
database, and Metabase are healthy. Loopback checks returned 200 for `/health`,
401 for anonymous review-queue access, and 404 for OIDC login; the provider is
not configured. See [rollout evidence](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json).

The checkpoint covers only the candidate PostgreSQL database; roles/grants,
media, and other Docker state are outside its scope. No suite was run during this
rollout. Provider-backed reviewer acceptance, populated domain workflow,
higher-contention stress, and MAN-CAP-001 remain open.


### Batch 3 canonical lifecycle queue and operator workflow console — 13 October 2026

Added source-level `GET /operator/api/farm-activities` and
`GET /operator/api/farm-activities/{id}` with location binding, active-grant
checks, no-store responses, a 100-row cap, exact native `farm_activity_v1`
1.2.0 lineage filtering, queue free-text omission, separate detail grants, and
workflow-event history capped at the latest 100 entries with a truncation marker. The console now has intake payload review, explicit
content-review acknowledgement before idempotent draft promotion, a canonical
lifecycle queue, and submit/verify/reject/rework/publish/exception controls
filtered by current operator scopes. Rejection, rework, and exception closure
require reasons; publication requires a confirmation step. The transition
service now refuses historical Field Collector rows outside the native form
lineage. Promotion also requires and locks `farm_activity:read_detail` in
addition to `create_draft` and `mobile_collection_review:read_detail`.

At this prior queue/console checkpoint, no test suite was added or run and the
candidate app was not rebuilt. Draft editing had not yet been implemented;
focused route/query/console checks, guarded candidate rollout, OIDC provider
acceptance, and MAN-CAP-001 remained open.

### Batch 3 native farm-activity draft correction — 13 October 2026

Added migration 385, `edit_farm_activity_draft`, and the OIDC-protected
`PATCH /operator/api/farm-activities/{id}/draft` route. The route requires the
location-scoped `farm_activity:edit_draft` action plus both farm-activity and
mobile-review detail grants, a CSRF token, and a nonblank correction reason.
The service locks the canonical draft and its exact immutable
`farm_activity_v1` 1.2.0 form revision, merges only the revision's five declared
fields, and validates the complete content before updating the canonical row.
Optional `null` values clear fields; unknown keys, invalid schema values,
no-op edits, non-draft rows, and unavailable source revisions are rejected.

Migration 385 adds a same-state `draft_edited` action to the append-only event
ledger. PostgreSQL enforces native lineage, enabled operator identity, current
edit and detail grants, a required reason, the allowlisted changed-field list,
and a SHA-256 matching canonical content digest. The event does not copy free
text, and neither `source_raw` nor the original offline collection is changed.
The operator console now exposes the editor only for drafts and locations with
the edit and private-detail grants.

This paragraph records the initial source-only checkpoint before focused
verification and the separately authorized candidate rollout. The additive
migration should remain applied during an application rollback; use a reviewed
forward fix if needed and preserve edit-event history.

### Batch 3 native draft-edit verification — 13 October 2026

Focused verification now passes 95 tests across migration, immutable form
validation, intake promotion, farm-activity lifecycle editing, OIDC route policy,
CSRF, and operator-console source contracts. Ruff passes on the changed Python
files. Updating the promotion test doubles to include the required
`farm_activity:read_detail` grant restored the existing promotion, retry, and
event-write failure cases; no production service changes were needed for that
test correction.

The repository migration runner applied all 376 ordered PostgreSQL schema
migrations (schema-only, no seeds) to a pinned PostGIS 16 disposable database.
A synthetic location, operator, grants, collection, immutable form revision,
and native draft then exercised migration 385: the edit produced an append-only
same-state event with the expected changed-field list and content digest;
an event update was rejected; and an injected event-insert failure rolled the
canonical content update back with no extra event. The database used tmpfs, no
network, and no published ports; its container and scratch fixture were
removed. The existing candidate was not changed. Reproducible evidence is in
[the acceptance record](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json).

This closes source and isolated database verification for draft editing, not
the full Batch 3 gate. The separately authorized candidate rollout is recorded
next. Configured-provider OIDC, real browser workflow, populated candidate
acceptance, higher-contention stress, and MAN-CAP-001 remain open.

### Batch 3 migration 385 candidate rollout — 13 October 2026

A fresh age-encrypted PostgreSQL checkpoint was created from the candidate and
restored into a unique internal-only PostGIS 16 project. Migration fingerprints,
extension versions, and farm-activity/workflow/mobile-collection counts matched;
the temporary recovery container, network, and volume were removed. The ordered
migration plan had exactly one pending schema, migration 385, with no checksum
drift. The runner applied it successfully; the candidate now has 376 applied
schemas and zero pending.

The app was rebuilt from commit `f854d47`, with its previous image retained as
`kokonut-kernel-candidate-app:rollback-pre-draft-edit-20261013T122602Z`. Only
the candidate app was recreated. Health returned 200, and unauthenticated
Field Collector review, farm-activity list, and draft-edit routes returned 401.
PostgreSQL, Metabase, and proxy stayed up. The candidate currently has zero farm
activities, workflow events, and offline collections; OIDC remains disabled,
so no live edit or human review was exercised. See the
[rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json).

This completes the migration-385 checkpointed candidate rollout, not Batch 3
acceptance. Configured-provider OIDC, browser workflow, populated candidate
acceptance, higher-contention stress, and MAN-CAP-001 remain open.


## Field Collector retention disposition safety — 13 October 2026

Set the interim policy for collections affected by consent withdrawal or an
erasure request: immediately restrict use, preserve the private record for a
human dependency/legal-basis review, and do not automatically delete or claim
erasure. Generic retention sweeps now reject new policies and skip pre-existing
policies for the protected consent, collection, participant-link, media, form,
review-event, device, and governed farm-activity tables. Added the detailed
[retention and disposition contract](mobile-retention-disposition.md) and linked
it from the mobile access contract and checklist.

This change performs no data mutation. The current schema's restrictive foreign
keys, immutable evidence, media objects, canonical source lineage, and backups
mean complete erasure still needs a dedicated two-person reviewed executor and
reconciliation flow. No jurisdiction-specific period is assumed; CAP-053 remains
partial pending an accountable retention owner and end-to-end acceptance. Tests
were not run for this slice.

## Field Collector read-only disposition inventory — 13 October 2026

Added a separate-grant OIDC route and console action for a content-free known
database lineage inventory. `mobile_collection_retention:inventory` and
`mobile_collection_review:read` are both required; payload detail access is not.
The query binds collection and location, repeats the inventory grant in SQL,
and returns only aggregate payload/attachment metadata, private-media
counts/bytes/statuses, canonical farm-activity counts/statuses, and review and
workflow event counts. The query repeats both required grants in SQL and binds
every count to the requested location. It omits collection contents,
participant identity, media keys/hashes, and cross-location lineage. The console uses text rendering,
`no-store`, and makes clear that reports, external exports, and backup copies
are not covered.

This is a source-only slice. Focused service/query, dual-grant route authorization,
and console acceptance passed: all 49 tests in the focused operator auth/review/
console files passed, and Ruff is clean. The query contract verifies location
binding and both active grants,
read-only transaction mode, and absence of payload/object-key output; route tests
verify either missing grant denies access. It does not create a case, approve a
retention basis, or execute erasure. Reports, external exports, on-chain
references, backups, and full cross-location lineage remain uncovered.

## Field Collector tenant isolation target — 13 October 2026

Inspected the location and organization schema before choosing the tenant
boundary. `location.organization_id` is nullable, while `organization_member`
is an organization-to-location/farm relationship and does not authorize an
operator. The mobile API continues to use the enrolled device's location and
explicit operator location grants. Documented organization as the future
security tenant, location as operational scope, explicit sharing grants,
fail-closed handling for unmapped records, transaction-local database context,
and the required RLS rollout/rollback acceptance in the
[tenant isolation contract](mobile-tenant-isolation.md).

This is a policy and sequencing decision only. No RLS migration, ownership
backfill, provider configuration, or live data mutation was made. The current
mobile location boundary remains in force; tenant-aware identity/grants, owner
reconciliation, RLS, worker isolation, and downstream eligibility checks remain
implementation gates.

## Field Collector tenant ownership preflight CLI — 13 October 2026

Added `python3 -m services.cli mobile-tenant-preflight` with an optional
`--location-id` filter. The command runs an explicitly read-only,
repeatable-read transaction with a 15-second statement timeout. It compares
nullable direct organization assignments with active `owned`/`primary`
relationships, inventories known device, enrollment, collection, private-media,
canonical activity, workflow/review event, report snapshot, and dashboard
dataset counts, and reports rows lacking a location separately. It emits
stable opaque location/organization references rather than raw UUIDs. The
filtered mode labels unlocated counts as database-wide.

At the time this source slice was added, the candidate database was not queried
and no tests were run. The command does not infer or write ownership.
Tenant-aware grants, RLS, worker isolation, complete downstream lineage, and
ownership reconciliation remain open. See the [CLI guide](../../services/mobile/README.md)
and [tenant contract](mobile-tenant-isolation.md).

### Candidate execution — 13 October 2026

Ran the unified CLI in a disposable container on the private
`kokonut-kernel-candidate` network. The current CLI and preflight module were
bind-mounted read-only; the database transaction used repeatable-read, read-only
mode with a 15-second statement timeout. The candidate contained zero location
rows, zero ownership relationships, and zero known mobile/downstream records,
including zero records without a location. The legacy stack was not queried,
and no long-lived service was recreated. The sanitized result is retained in
the [preflight evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight.json).

This closes the local-candidate inventory run only. It does not resolve
ownership for a populated or production database; accountable owner review,
tenant-aware grants, RLS, and downstream lineage remain open. No tests were
run, and no database records were changed.

## Field Collector tenant preflight schema gate — 13 October 2026

Updated the read-only preflight to inspect the required public relation/column
set before running ownership or lineage counts. If a restored or deployed
database is behind the current Field Collector schema, the command returns
`inventory_status: schema_incomplete`, the missing `relation.column` names, and
the latest applied migration when migration history exists. It does not issue
the inventory queries in that case. Complete schemas retain the existing
repeatable-read, read-only behavior and include the schema-coverage summary.

At the source-only checkpoint, no older populated snapshot had been queried;
the subsequent populated-restore check is recorded below. No test suite ran.
The CLI does not infer or write ownership, and no backfill or RLS migration is
authorized by this preflight.

### Populated archived restore check — 13 October 2026

Restored the checksum-verified encrypted `kokonut_intelligence` archive into a
new template0-derived database using the pinned PostGIS image. The isolated
internal network had no published ports or application services; synthetic
credentials were used. A separate read-only aggregate confirmed two locations
and 376 migration-history rows. The unified CLI returned
`inventory_status: schema_incomplete`, found 16 of 27 required columns, listed
the 11 missing columns, and did not query or emit ownership/lineage counts.
Migration history was correctly ordered by `migration_id`, reporting
`schema:352_attestation_request_anchor_fields.sql`. The disposable container
and network were removed; the recovery volume was retained. The candidate and
legacy services were not connected to or changed.

Evidence: [schema gate restore](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-gate.json).
The restore and read-only query are not a test suite; no test suite was run.
Ownership reconciliation remains open. A fully migrated populated copy and
accountable owner review are still required before any tenant backfill or RLS.

The complete-schema path was also run against the current candidate. It returned
27/27 required columns and migration 385, with zero locations and zero known
lineage rows. This confirms only the empty-candidate path; see the separate
[complete-schema evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-complete.json).

## Populated Field Collector migration replay and ownership inventory — 13 October 2026

Restored the checksum-verified archived database into a new internal-only,
template0-derived copy. The migration planner found 32 pending schemas, from
353 through 385 with existing numbering gaps, and no checksum drift. The
transactional runner applied all 32 with zero failures; the follow-up plan
reported zero pending schemas. The restored copy now records 376 applied
schema migrations and the original 32 seed migrations. No seed migration,
owner assignment, tenant grant, or RLS policy was applied.

The complete read-only preflight found 27/27 required columns and migration
385. Across two locations, it found no active organization-member rows: one
location has a direct organization assignment without a confirming active
owned-primary relationship, and the other has no direct assignment. The
inventory counted four mobile devices and five location-scoped dashboard
datasets; it also found three report snapshots and 38 dashboard datasets with
no location. These counts identify review work, not an ownership decision.

The first complete-schema execution exposed a driver-boundary bug: an empty
PostgreSQL `uuid[]` arrived as the string `{}`, which the preflight iterated as
two characters and turned into false opaque owner references. The result was
discarded. The query now aggregates IDs as `text[]`, and the collector fails
closed on any unsupported array representation. The corrected read-only run
reported zero relationship candidates, one `assigned_owner_not_confirmed_by_relationship`
location, and one `unassigned` location. Python syntax compilation and
`git diff --check` passed; no test suite ran.

The one-shot runner and recovery container/network were removed after capture;
the isolated volume was retained. An earlier incomplete first-boot volume was
also retained separately without archive restore or migrations. The candidate,
legacy stack, and their databases were not accessed. Accountable owner review,
unlocated report/dashboard lineage, tenant-aware grants, RLS, and downstream
eligibility parity remain open. See the [sanitized replay evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json),
[tenant contract](mobile-tenant-isolation.md), and [Batch 5 checklist](batches.md).

## Field Collector current-use gate — 13 October 2026

Added ordered migration 386 with a fail-closed canonical farm-activity
eligibility predicate. It matches the Field Collector source ID, payload
lineage, location, collection type, immutable form revision, and current
eligibility view; it also checks that the revision remains active. Form
retirement/inactivation moves linked collections into the existing private
review queue. A database trigger blocks ineligible content edits and forward
workflow changes; existing rejection/exception actions remain available only
where governed lifecycle state permits, and do not replace formal retention
disposition.

Applied the predicate to farm summaries, ecological/value-added analytics,
Fortune 500 governance counts, process traces and value-stream calculations,
three lifecycle metrics, data-quality sampling, repository-owned Metabase and
saved-dashboard queries, the optional Directus weekly snapshot hook, and both
farm-activity export paths. The migration rewrites only the exact known seeded
dashboard SQL; custom/operator-edited SQL still needs inventory and review.
Authorized canonical lifecycle reads retain ineligible rows and return
eligibility/reason fields for disposition; the editor and transition service
return a conflict before writes when the source is no longer eligible. The
source change is documented in the mobile access and retention contracts, the
workflow map, Batch 5 checklist, and CAP-001/CAP-053 progress.

Focused source tests pass: 56 passed, 18 skipped across eligibility,
lifecycle, workflow, farm metrics/report, process/value-stream, and operator
console checks. Targeted Ruff, Python compilation, the operator-console inline
JavaScript syntax check, and `git diff --check` also pass. Migration 386 was applied to a network-isolated PostgreSQL 16
disposable database populated with synthetic schema and rows. Assertions
covered active eligibility, legacy-source compatibility, wrong-location and
malformed lineage, withdrawal followed by a later grant, content/workflow
blocking, allowed rejection disposition, immutable provenance, retired-form
review queuing, Directus permission-scope preservation, seeded dashboard
filters, and the migration marker. The Directus seed repair was then applied
twice against nested location scopes and a NULL permission row; the recursive
gate check found exactly one gate per row, and a row-for-row comparison showed
the second pass changed no permission state. A Kernel-only run of the final
SQL removed
`directus_permissions` before applying migration 386 and passed, confirming the
optional Directus branch. Temporary containers were removed.

The checksummed runner then applied the final migration 386 checksum to a fresh
copy of the retained populated archive's `kokonut_restore` database after its
plan found one pending schema and no checksum drift. The post-run schema plan returned zero pending; the migration
ledger and marker were present, all 8/8 existing farm-activity Directus read
permissions carried the source gate, and the present seeded farm-activity
dashboard query was eligibility-gated. The clone retained two locations, four
devices, and 43 dashboard datasets, plus 30 total `farm_activity` rows and
zero Field Collector-sourced canonical activities; the second seeded VSM
dataset ID was absent. The retained recovery volume was unchanged. The
temporary clone volume, container, and network were removed; the candidate
app, proxy, Metabase, and database remained healthy on migration 385 at this
source-verification checkpoint. The separately approved candidate rollout is
recorded below. See [synthetic acceptance evidence](builds/2026-10-13-recovery/farm-activity-use-gate-disposable-acceptance.json),
[populated replay evidence](builds/2026-10-13-recovery/farm-activity-use-gate-populated-replay.json),
[Batch 5 checklist](batches.md), and [capability matrix](capability-matrix.md).

## Field Collector current-use gate candidate rollout — 13 October 2026

Created a fresh age-encrypted PostgreSQL checkpoint before changing the
candidate. Restored it directly into a template0 database in an internal-only
temporary project without writing a plaintext archive; all 376 ordered schema
fingerprints, 10 extension versions, and six selected row-count comparisons
matched the candidate. The temporary restore container, network, and volume
were removed; the encrypted checkpoint remains at
`backups/kernel-candidate-pre-farm-activity-use-gate-d22fa49`.

The exact-target ordered migration plan found only
`schema:386_farm_activity_consent_use_gate.sql` with no checksum drift. The
runner applied one migration with zero failures; the follow-up plan found zero
pending across 377 applied schema files. The eligibility function and single
version marker are present. Directus is absent in the Kernel candidate as
expected for this optional provider.

Built the app from source commit `d22fa49`, tagged the previous image for
rollback, and recreated only the candidate app container. The app, database,
Metabase, and proxy are healthy/running. Loopback checks returned 200 for
`/health` and 401 for anonymous farm-activity and mobile-review queue requests.
The candidate remained empty for farm activities, workflow events, mobile
collections, and devices. Its prior encrypted checkpoint and rollback image
remain available; the legacy stack was not accessed. See the [rollout
evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json).

This deploys the use gate but does not provide populated workflow acceptance,
configured OIDC login/session validation, or MAN-CAP-001/MAN-CAP-053
certification. Candidate and populated-clone checks remain distinct.


## Phase 8 release-input lock and architecture CI gate — 13 October 2026

Added a SHA-256 manifest for the minimal app and PostGIS Dockerfiles, their
pinned base image references, direct Python requirement files, and verified
PostGIS package catalog. The GitHub Actions CI workflow invokes a Buildx script
that creates fresh temporary AMD64/ARM64 OCI archives for both targets, checks
the platform entries, compares resolved Python package versions, and verifies
the selected PostGIS versions. The script does not publish, load, or start those
images.

A current-source AMD64 Kernel app build completed locally as
`kokonut-kernel-release-app-amd64:c2a5354`. The matching ARM64 build began
resolving ARM64 wheels but failed after DNS lookup for `files.pythonhosted.org`
failed; no ARM64 result is recorded as passing. The GitHub Actions gate has not
run yet ([attempt record](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).
Python transitive requirements and apt repository snapshots remain unlocked;
hardware runtime, restore, and Raspberry Pi resource acceptance remain separate
gates ([contract](kernel-release-inputs.md)). No test suite was added or run for
this slice.


## GitHub Actions workflow migration — 13 October 2026

Replaced the repository's OneDev buildspec with GitHub Actions workflows for
the full CI gate, Gitleaks security scanning, disabled staging deployment
on a dedicated self-hosted runner, and manual production promotion. Extracted the
CI steps into `scripts/run-github-ci.sh`; it uses `ki-ci`, isolated loopback
ports, placeholder secrets, full migration/test/static-analysis/Solidity/Directus
checks, and the existing non-publishing multi-architecture build script. The
script preserves and restores any existing `.env` and `.env.sops` files during
its run. Production retains the explicit confirmation, pre-deploy backup, and
health check. Deployment runbooks, contribution guidance, compliance evidence,
and capability progress now refer to GitHub. The OneDev buildspec was removed.

The first GitHub Actions run exposed 544 Gitleaks findings. Review traced the
matches to public OpenZeppelin test fixtures, public EVM addresses, SHA-256
recovery/build inventories, domain migration labels, deterministic test keys,
and literal credential placeholders in examples. Added `.gitleaks.toml` with
rule-scoped exact path/line/value exceptions and made the workflow select that
config explicitly; full-history scanning and the other secret rules remain
enabled. The full-history Security workflow passed on 13 October 2026. Two CI
runs built both architecture images and failed release validation because
Buildx wrapped platform manifests in nested OCI indexes. The PR fix recursively
inspects nested indexes, then derives platform labels from image configs when
image descriptors omit them. [CI run 283](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38443881835)
included the Python dependency locks and apt snapshot inputs but failed during
PostGIS package-source setup because the
pinned PostgreSQL base had no system CA bundle. A signed Debian snapshot
bootstrap now installs `ca-certificates` before the build switches to HTTPS
sources; a fresh multi-architecture run must pass before the release gate is
accepted. GitHub runner registration,
`staging`/`production` environments, branch rules, and production SSH secrets
remain pending remote configuration; see [setup requirements](../github-actions.md).
Staging also requires a reviewed source change to clear its disabled flag. No
deployment was performed.

### Kernel Python lock follow-up — 13 October 2026

Generated hash-locked Python dependency closures for the default Kernel runtime
and optional ClickHouse-enabled profile with pip-tools 7.6.2. The Kernel
Dockerfile now selects one full lock at build time and pip enforces hashes.
`config/kernel/release-input-lock.json` covers the source manifests, both lock
files, and Dockerfile bytes. The multi-architecture release script now builds
and inspects both app profiles plus PostGIS for linux/amd64 and linux/arm64.
GitHub [CI run 283](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38443881835)
included the Python locks and app profiles and reached the
PostGIS build, where the missing CA bundle prevented apt from reaching the
locked HTTPS sources. This run does not accept the multi-architecture release
gate. No local test suite or Docker build was run for this slice.

### Kernel apt source lock follow-up — 13 October 2026

Added a UTC-dated Debian Bookworm snapshot source and switched the selected
PostGIS packages to the PGDG released-package archive with exact versions.
The apt source and preference files plus the package catalog are covered by
`config/kernel/release-input-lock.json`; the release checker requires the
timestamp, suites, archive, and low default PGDG priority to agree. Earlier
local amd64/arm64 PostGIS artifacts were built before this source lock and are
retained as historical identities, not acceptance evidence for the new input.
CI run 283 showed that the pinned PostgreSQL base has no CA bundle, so apt could
not authenticate the locked HTTPS sources and could not install
`ca-certificates` from those same sources. A first build stage now installs the
bundle from the same timestamped Debian snapshot over HTTP, with APT signature
checks and the Debian archive keyring enabled; later stages use the locked
HTTPS sources. CI run 284 confirmed that bootstrap and built both PostGIS
architectures, then the full inventory comparison found only the amd64
`libquadmath0` package. The package record now allows that exact version and
absence on arm64, with a Debian package rationale; any additional or stale
difference remains a failure. The next clean multi-architecture run must pass.
Extension and restore acceptance and hardware certification remain open.

### PostGIS CA bootstrap repair — 13 October 2026

CI run 283 failed in the PostGIS stage because the digest-pinned PostgreSQL base
has no trusted CA bundle. The build tried to install `ca-certificates` only
after enabling HTTPS Debian and PGDG sources, producing a bootstrap cycle. Added
a separate first stage that installs the CA bundle from the same dated Debian
snapshot over HTTP while retaining APT signature verification with Debian's
archive keyring. The next stage then switches to the locked HTTPS Debian and
PGDG sources. The bootstrap source is included in the input lock and the
release checker verifies both the source and stage ordering. No local Docker
build or test suite was run; fresh GitHub multi-architecture CI remains the
acceptance gate.

### PostGIS architecture-specific inventory follow-up — 13 October 2026

CI run 284 passed the CA bootstrap and built the selected PostGIS packages for
both linux/amd64 and linux/arm64. The package inventory checker then identified
one difference: `libquadmath0` version `12.2.0-14+deb12u1` on amd64 and no such
package on arm64. Debian publishes this package for amd64/i386, and
`libgfortran5` only depends on it on those architectures ([package details](https://packages.debian.org/bookworm/libquadmath0), [dependency details](https://packages.debian.org/bookworm/libgfortran5)). The reviewed difference is now recorded in the SHA-256-locked package catalog. The checker still requires the observed complete difference map to equal that contract exactly, so any extra package/version delta or a stale expectation fails. Static release-input validation is the next local check; a fresh GitHub CI run remains required for acceptance.

### GitHub CI run 285 test-suite repair — 13 October 2026

CI run 285 passed the default and ClickHouse-enabled app builds for AMD64 and
ARM64, passed the PostGIS builds for both architectures, and passed the locked
installed-package inventory comparison. The full suite then reported 23
failures with 4,532 passing tests. The failures traced to a missing CI
ClickHouse database selection in the end-to-end helper, the mobile-form seed
rewriting immutable revisions on rerun, a hard-coded developer scratch path,
and stale tests for current gRPC scopes/handlers, sensor projection adapters,
strict sensor ranges, CORS `Vary` headers, rate-limiter constraints, and
provider-independent workflow jobs. These were corrected in the active PR.
The focused local run passed 155 tests with one database-backed seed check
skipped because the local database service was unavailable. A clean GitHub CI
run is still required to confirm the complete database-backed path.

### GitHub CI run 286 seed-idempotency follow-up — 13 October 2026

[CI run 286](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38458613711)
passed 4,556 tests and failed only the database-backed seed-idempotency check.
The initial fix changed the mobile-form seed to `ON CONFLICT DO NOTHING`, but
PostgreSQL still evaluates the immutable-revision `BEFORE INSERT` trigger before
discarding a conflicting row. The seed now selects only form IDs absent from
`mobile_form` before inserting and retains `DO NOTHING` as the uniqueness
fallback. The regression check asserts that exclusion predicate. The focused
pytest invocation could not run locally because pytest is absent from the
system interpreter; source assertions and `git diff --check` pass. [CI run 287](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38466475973)
then passed on fix commit `6549043`, including the database-backed idempotency
check; see the acceptance record below.

### GitHub CI run 287 release-gate acceptance — 13 October 2026

[CI run 287](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38466475973)
completed successfully on commit `6549043` in PR #68. It built and verified the
default and ClickHouse-enabled Kernel apps for AMD64/ARM64, plus the snapshot-
pinned PostGIS images for both architectures. The full package comparison found
229 AMD64 and 228 ARM64 packages with only the documented architecture-specific
`libquadmath0` difference. The complete Python/database suite passed 4,557 tests
and 75 subtests; `tests/test_seed_idempotency.py::test_seed_idempotency` passed.
The Solidity suite passed 62 tests and the Directus hooks suite passed 52 tests;
the workflow reported all CI checks successful. Full-history Security run 11
also passed. These results close the build, inventory, and seed-regression gates
for commit `6549043`. Later changes on the current PR branch are not covered yet;
a fresh run is required before the release-CI gate closes for its current head.

### Batch 4 Redis and shared-limiter profile decision — 13 October 2026

The Kernel candidate has no Redis service or Python Redis dependency. Operator
sessions and computation results are PostgreSQL-backed; Redis remains limited
to the optional legacy Directus cache/rate-limit adapters. Minimal and edge
profiles keep the bounded process-local limiter for one API instance. The
standard profile now defaults to the PostgreSQL-backed limiter so horizontally
scaled API replicas can share budgets after migration 373 is applied. Existing direct-call, ASGI
multi-process, and two-container HTTP acceptance covers shared consumption;
production multi-host failover, public ingress, and migration/retirement of
legacy Directus Redis state remain open. The two focused Compose profile tests
pass, and the mobile-form seed source regression check also passes (3 total).
Provider-boundary and dependency-group checks pass (17 vendor import sites;
12 groups/32 requirements aligned). No services or database state were changed.
This slice is not pushed until CI run 287 completes.


## Batch checklist reconciliation — 13 October 2026

Reconciled the parent Batch 2 Metabase checkbox with the already-retained Batch
4e evidence. The optional profile is scoped to the three reviewed
`kokonut_reporting` views; three first-party cards were executed against the
empty candidate and their exact exported SQL matched independent base-table
references on a copied populated fixture. The metadata backup restore also
matched the live source/card/dashboard inventory. Linked the card-output record
from CAP-007 and the parent checklist. This closes only that implementation and
reporting-slice item; the candidate remains empty, broader analytics parity and
MAN-CAP-007 are not accepted, and the Batch 2 provider/recovery gates remain
open. No runtime state or services changed.


## Optional Metabase documentation state reconciliation — 13 October 2026

Aligned the optional consumer-role and reporting-contract documents with the
completed Batch 4e candidate setup. The candidate profile uses the distinct
`kokonut_analytics_ro` identity and exposes only the reviewed reporting views;
its three Kokonut cards passed copied-populated-fixture SQL parity, and encrypted
metadata restore counts matched. Removed stale statements that source/card setup
was still pending, corrected the profile-default wording, and marked the source
and parity steps complete in the reporting contract. Production credentials,
live populated candidate results, broader report/dashboard parity, and
MAN-CAP-007 remain open. This reconciles existing evidence; no runtime state
or services changed.


## Batch 5 authenticated CORS success response — 13 October 2026

Extended the cookie-backed mobile review queue test with an explicit allowed
browser origin. The authenticated 200 response now asserts the exact
`Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials: true`,
`Cache-Control: no-store`, and `Vary` behavior using the existing fake OIDC
provider; no identity-provider call or live service was involved. The new
focused test passed, and the four Gateway CORS preflight tests passed. This
closes the in-process source regression gap only; browser/certificate, real
OIDC, and deployed credentialed-CORS acceptance remain open.


## Batch 5 OIDC deployment-input contract — 13 October 2026

Added the optional OIDC provider settings to `.env.example`, including a
localhost HTTPS callback example and a reminder to keep client/state secrets in
SOPS. Compose checks confirm the default candidate omits OIDC, the OIDC overlay
fails configuration when the issuer is missing, and explicit test settings
reach the app environment. The profile planner now supports `--oidc` and rejects
that option without `--proxy`, ensuring the secure-cookie path uses HTTPS.
Config-only checks cover minimal, edge, standard, analytics, portability, and
OIDC selections, including private ClickHouse, edge media/resource settings,
and the explicit ARM64 guard. Eighteen Compose/planner checks pass; Ruff, Python
compilation, and whitespace checks are clean. No real provider, credential,
browser, or service was used; OIDC login/session and console acceptance remain
open.


## Batch 2 focused platform-integrity source run — 13 October 2026

Ran the repository's eight focused platform-integrity suites: **279 passed**.
The first host run exposed five Gateway mutation tests failing closed because
the container-default audit-spool path was not writable by the host process.
Added an autouse test fixture that gives each Gateway test a private journal in
pytest's temporary directory; the complete suite then passed. Ruff is clean.
No candidate or Docker service changed. This is source test evidence only;
external delivery, provider state, physical failure, and broader runtime
recovery remain open.


## Current local architecture checks — 13 October 2026

After the latest local commits, dependency groups align (12 groups, 32
requirements), provider boundaries pass across 17 vendor import sites, and the
Kernel release-input lock matches its sources. The release checker received no
OCI archives, so this confirms source/config consistency only; it does not
replace a CI run for the current branch head or ARM64 runtime acceptance.


## Tenant ownership mapping — 13 October 2026

The repository owner confirmed Kokonut Network as the exclusive owner of the
two repository seed locations, Kokonut Adelphi and Kokonut Genesis. Source now
adds ordered migration 387, a final idempotent pilot ownership seed after
Genesis creation, and consistent assignments in the legacy organization seeds.
The migration is limited to the two exact seed identities, accepts only the
observed legacy Adelphi owner or an already-canonical assignment, and refuses
other owners. It preserves the legacy Adelphi organization and non-owner
relationship types, and it does not enable RLS or assign the unlocated report
and dashboard rows. A network-disabled PostgreSQL 16 compatibility fixture
passed archive-like and clean-bootstrap scenarios, migration/seed idempotency,
legacy owner-link deactivation, and wrong-owner refusal with transaction
rollback ([evidence](builds/2026-10-13-recovery/tenant-ownership-disposable-acceptance.json)). All 16 test functions in `tests/test_impact_network.py` were invoked directly and passed; pytest
could not be installed because PyPI DNS/network access is unavailable. No local
candidate or legacy database was changed, and the disposable container was
removed. Unlocated lineage review, tenant-aware grants, transfer/sharing
semantics, full ordered-migration replay, and RLS remained open at that
checkpoint. GitHub confirmed CI run #291 and Security run #15 passed on remote
PR #68 head `56a0105f700ad1137d3b5ee6accce59552ebee7e`; the local branch was 12
commits ahead at that point, so those changes were not covered.


## Archived report/dashboard tenant-lineage review — 13 October 2026

Reviewed the unlocated dashboard definitions and report snapshots on the
retained network-isolated archive clone in explicit read-only transactions.
None of the 38 dashboard rows contains a known location ID/name reference in
its stored query or metadata, and none of its owner fields equals the
confirmed Kokonut Network tenant. The three draft reports are two DAO proposal
history snapshots and one State of Kokonut snapshot; embedded location
fields/lists do not match either known location, and narrative mentions do not
prove a single-location owner. Stored
queries and report payloads were not returned, and no data was changed. All 41
records therefore remain unassigned; their lineage review is complete for this
archive snapshot, while broader downstream lineage and report/dashboard
capability selection remain open ([evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).
The temporary network-disabled inspection container was stopped and removed;
the review volume remains retained. CI run #291 is green on the earlier remote
PR head; this local evidence and the current branch changes await the next
batch push and CI run.


## Tenant-aware operator grant source foundation — 13 October 2026

Added ordered migration 388 with an explicit tenant-owner verification ledger
for the two confirmed seed locations, OIDC operator organization memberships,
revocable location shares, and an optional organization key on
`operator_scope_grant`. The local operator CLI can provision tenant membership,
create/revoke owner-authorized shares, issue tenant-qualified resource/action
grants, and revoke dependent grants when membership or a share is withdrawn.
Gateway scope checks and report, mobile-review, and farm-activity SQL queries
now call one shared predicate that validates identity, membership, owner/share,
location, resource, and action. Browser responses continue to receive only
resource/action/location scopes.

No operator tenant affiliations were inferred from legacy location grants;
NULL-tenant grants remain compatible and prevent this slice from claiming full
tenant isolation. Transfer controls, worker/database-role boundaries,
transaction-local RLS context, CLI membership/share lifecycle, legacy-grant
conversion, full migration replay, and candidate rollout remain open. Source
syntax compilation, pilot seed shell syntax, Ruff 0.17.0 on the modified
Gateway modules, and whitespace checks passed. No test suite, migration
replay, database change, candidate rollout, or external push had occurred at
the time of this source update; CI run #291 still covers only the earlier
remote PR head. See [tenant boundary](mobile-tenant-isolation.md), [console
contract](kernel-operations-console.md), [batch checklist](batches.md), and
[`388_tenant_aware_operator_grants.sql`](../../schemas/postgres/388_tenant_aware_operator_grants.sql).

### Downstream Field Collector source audit — 13 October 2026

A source audit of repository-owned farm-activity consumers found that report,
export, metric, analytics, trace, Gateway, hook, and seeded dashboard paths use
the migration-386 eligibility predicate directly or through the shared
`farm_activity_source_eligible_for_use` function. The audit found one exception:
`services/analytics/process_interfaces.py` fetched a farm-activity timestamp by
ID without checking current eligibility. That lookup now applies the shared
predicate for farm activity. The source inventory is in
[field-collector-downstream-source-audit.md](field-collector-downstream-source-audit.md).

This closes only the repository-source audit. External or operator-edited
dashboard SQL, populated output parity, and direct-database isolation remain
open. At that point focused checks and migration 388–389 replay awaited
verification authorization; the owner has since approved them. CI run 291 is
green on the earlier PR head and does not cover this local batch.

Migration 389 adds database-trigger checks for tenant-aware grants on Field
Collector draft creation, content edits, and lifecycle events, using the
shared predicate from migration 388. The checks retain NULL-tenant grant
compatibility.

### Migration 388–389 disposable acceptance — 13 October 2026

Ran the actual migrations 387–389 in order against a network-disabled
disposable PostgreSQL 16 container, then replayed 388–389 to check idempotency.
The owner verification rows for Adelphi and Genesis were created as expected.
Positive and negative grant cases covered owner access, partner access with
and without a share, expiry/revocation, operator membership and identity state,
organization status, grant revocation, unverified/stale ownership, and legacy
NULL-tenant compatibility. Migration 389 accepted an authorized draft insert,
edit, submit event, and draft-edited event, and denied each tested path when a
required grant was missing. A legacy grant passed the trigger boundary, while
non-target manual records were unaffected. The sanitized run record is
[`tenant-grants-migrations-disposable.json`](builds/2026-10-13-recovery/tenant-grants-migrations-disposable.json).

This is a minimum compatible schema check, not a full repository migration
replay; it does not exercise the existing 384–385 triggers in combination with
389. Operator-CLI membership/share lifecycle, legacy-grant conversion, full
ordered replay, candidate rollout, transfer controls, worker/direct-database
boundaries, transaction-local context, and RLS remain open. No candidate or
legacy database was touched. CI run #291 covers the earlier remote PR head,
not these local changes.

### Migration 388–389 operator CLI acceptance — 13 October 2026

Ran the migration and trigger acceptance plus the real
`services.gateway.operator_cli` commands against a disposable PostgreSQL 16
database. The CLI checks covered listing identities and grants, idempotent
membership and share grants, refusing a role change until the old membership
is revoked, requiring an owner tenant administrator to share a location,
denying partner grants without a share, allowing them with a share, and
revoking dependent grants when either the share or membership is revoked. A
legacy NULL-tenant owner grant converted in place to the verified owner tenant
and remained authorized. This run exposed and fixed positional row access in
the CLI; its database adapter returns named mappings. Ruff 0.15.22 and Python
syntax checks pass. Sanitized evidence is in
[`tenant-grants-cli-disposable.json`](builds/2026-10-13-recovery/tenant-grants-cli-disposable.json).

The CLI run used a minimum compatible schema on a disposable Docker bridge;
the candidate and legacy databases were untouched, and its temporary database
and network were removed. It did not itself exercise the full migration chain
or migrations 384–385. A separate clean full-schema replay subsequently passed
and is recorded below. Migration 388 has not been rolled out to the candidate.
Transfer controls, operator affiliation reconciliation, transaction-local
tenant context, direct-database isolation, and RLS remain open.

### Tenant grants full ordered schema replay — 13 October 2026

Closed the clean-bootstrap replay gate for the tenant-aware grant slice. All
380 migration source files validated and applied in order to disposable
PostGIS 16 with zero pending or failed. The catalog confirmed 11 registered
activity/workflow triggers across migrations 384, 385, and 389. Candidate app
and database health remained good; the candidate and legacy databases were not
modified. The disposable database, internal network, and volume were removed.
This did not include archived data or curated/pilot seeds, so populated replay
and candidate rollout remain separate gates. Evidence:
[`tenant-grants-full-schema-replay.json`](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json).

Ruff 0.15.22 is available in `.venv`; `pip check` reports no broken
requirements and the repository dependency-group alignment check passes.


### Audited location tenant transfer source — 13 October 2026

Added migration 390 and `services.gateway.operator_cli tenant-transfer` request,
accept, and cancel commands. A current owner tenant administrator opens a
referenced request; a separate enabled target-owner tenant administrator
accepts it, while the original source administrator must remain active.
Acceptance atomically changes the verified tenant and owned-primary
relationships, retires the previous owner evidence, and revokes all location
shares and grants (including legacy NULL-tenant grants); regranting requires a
separate review. Pending transfers change no access and source admins may
cancel them with a reason. Conflicted/unassigned ownership is rejected. The
[transfer contract](tenant-owner-transfer-contract.md) records that this is a
platform tenant assignment, not legal land-title evidence.

Ruff and Python syntax checks pass for the changed CLI. At this source-only
checkpoint, focused disposable PostgreSQL acceptance and candidate rollout were
still pending; acceptance results are recorded in the following entry.

### Migration 390 disposable transfer acceptance — 13 October 2026

Ran the approved acceptance against PostgreSQL 16 using synthetic organizations,
operators, grants, shares, locations, and a farm relationship. The actual
ordered migrations 387–390 applied successfully. All ten checks passed:
operator history listing; pending-request access preservation; self-approval
and non-admin rejection; stale ownership snapshot rejection and cancellation;
conflicting and unverified owner rejection; transaction rollback after an
injected failure; transfer of the tenant and owned-primary farm relationship;
revocation of owner, partner, and legacy NULL-tenant grants/shares; post-transfer
access only after a separate tenant-qualified grant; immutable request history;
and idempotent migration-390 replay.

The PostgreSQL port was bound to loopback. Docker bridge egress was available,
but the check made no external requests. The repository's encrypted secrets
were not read; CLI source ran from a temporary copy with synthetic database
credentials. The database container, named network, and temporary copy were
removed. Neither the local candidate nor legacy database was accessed. This
does not validate archive/pilot ownership mappings, legal title, RLS, worker
isolation, or candidate rollout. Migration 390 remains source-only pending the
separately gated candidate rollout. Evidence:
[`tenant-owner-transfer-disposable.json`](builds/2026-10-13-recovery/tenant-owner-transfer-disposable.json).

### Tenant transfer candidate rollout and context groundwork — 14 October 2026

Ran the focused context unit suite (8 passed) and the expanded disposable
PostgreSQL acceptance (14 checks passed). In addition to transfer request,
approval, rollback, cancellation, revocation, and replay, the database run
confirmed owner and explicitly shared tenant context, the unique-grant guard
against ambiguous scope, denial and clearing for legacy NULL-tenant grants,
and transaction-local reset after commit. The disposable container, network,
and source copy were removed; the candidate and legacy database were not used
by these acceptance checks. Evidence:
[`tenant-owner-transfer-context-disposable.json`](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json).

The separately approved candidate rollout took a fresh age-encrypted
single-database checkpoint; age authentication, checksum, and PostgreSQL
archive listing passed, but restore was not rehearsed. The ordered runner
applied migrations 387–390 with zero failures. Candidate schema status is
381/381 applied with zero pending; the full plan has 120 pending seed files and no recorded applied seeds, while
five mobile-form rows and ten revisions already exist. Candidate `location`
and transfer tables are empty, and the
canonical Kokonut Network organization row exists. Only the app was rebuilt
and recreated. It is healthy; `/health` returns 200 and anonymous farm
activity/mobile review routes return 401. Database, Metabase, and proxy
container IDs were preserved; rollback app tags and the encrypted checkpoint
remain local. See
[`candidate-tenant-transfer-rollout.json`](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json).

Added `services/common/tenant_context.py` as transaction-local groundwork. It
clears prior transaction settings, derives tenant/location/actor from a single
active tenant-qualified grant validated by the shared database predicate, and
rejects missing or ambiguous scopes. Focused tests pass. The helper is not yet
integrated into every Gateway or worker transaction; operator-affiliation
reconciliation, direct-database isolation, worker scoping, downstream lineage,
and RLS remain open. No seed data, populated archive, production data, or RLS
policy was changed by the candidate rollout.

### First Gateway tenant-context integration — 14 October 2026

The report review queue and report detail reads now call
`set_operator_tenant_context` inside the same read-only PostgreSQL transaction
as their protected query. The context is derived from a tenant-qualified
operator grant, current membership, and verified owner/share relationship;
the query retains its existing location and grant predicates as defense in
depth. A location-only legacy grant receives HTTP 403 on these two routes until
its operator affiliation and tenant grant are explicitly provisioned. The
expanded disposable PostgreSQL acceptance passed 17 checks; both focused HTTP
denial tests passed. It confirmed actual owner and shared-partner queries,
context-before-query on the same connection, legacy denial, and cleanup after
success and denial. The full existing operator-auth file also reported three
`Vary` header assertion failures in older cases (33 passed); these assertions
are outside the report-review changes and remain to be reconciled. Evidence:
[`tenant-owner-transfer-context-disposable.json`](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json).

This integrates one bounded read surface only: other Gateway handlers and
workers remain unintegrated, no RLS policy is enabled, and worker/direct-
database isolation remains a gate.

The Field Collector review queue and detail service functions now use the same
helper in their read-only transactions; missing tenant-qualified scope maps to
HTTP 403. The content-free disposition inventory validates its retention and
review grants together and sets context only when both resolve to one tenant.
Twenty-two synthetic disposable PostgreSQL checks and 31 focused context,
mobile service, and route checks passed. Owner queue/shared detail queries set
context on the same connection before protected reads, rollback clears context,
legacy location-only grants are denied before collection data is queried, and
individually valid grants from different tenants are rejected. Ruff and syntax
checks pass. Candidate and legacy databases were untouched. Human
retention/erasure disposition, other Gateway routes, workers, direct-database
boundaries, and RLS remain open.

The append-only reviewer-note write now applies the same pattern before its
INSERT: `mobile_collection_review:review` and `mobile_collection_review:read_detail`
must resolve to one verified tenant, and context is set on the connection that
performs the write. A denied context returns HTTP 403 with no-store headers.
Thirteen mobile-review service tests, eleven tenant-context tests, and three
focused auth-route tests pass; Ruff is clean. The service check confirms
context precedes the INSERT, while helper tests cover same-tenant acceptance,
cross-tenant rejection, and transaction-local cleanup. Candidate and legacy
databases were not accessed. Broader Gateway/worker integration, affiliation
reconciliation, direct-database boundaries, and RLS remain open.

Next, the Field Collector farm-activity intake and canonical activity
list/detail reads, draft promotion, draft correction, and lifecycle transitions
were updated to establish tenant context before protected queries and writes
on the same connection. Multi-grant operations require all grants to resolve
to one tenant, and the OIDC draft-promotion policy now lists both detail grants
that its service already requires. Denial maps to HTTP 403. Ten workflow
service tests, 31 lifecycle tests, and 26 focused auth-route tests pass,
including all seven farm-activity route denial mappings. Two older CORS header
assertions were corrected to issue the requests with the configured `Origin`;
the focused route slice now passes. Ruff, Python syntax compilation, and diff
checks pass, and no database was accessed.

The OIDC operator paths for creating enrollments, revoking unused enrollment
codes, and revoking active devices now set tenant context before their SQL
write using `mobile_device:enroll` or `mobile_device:revoke`. The public
API-key enrollment endpoint still uses its existing Gateway capability check
and does not attempt OIDC tenant context. Ten focused operator-route checks
and one public enrollment authorization check pass; Ruff and syntax checks
pass. No database was accessed.

The OIDC participant-link routes now live under `/operator/api/mobile/...`,
inside the session cookie path. Creation and revocation validate the
`mobile_participant:create` or `mobile_participant:revoke` grant, require CSRF,
and set tenant context before the party lookup or link write on the same
transaction. A context denial returns HTTP 403 before either query; both
responses are no-store. The existing `/api/mobile/.../participants` endpoints
remain on Gateway API-key/capability authorization. Five focused operator
authorization and transaction tests pass, along with one API-key regression
check confirming the original route still uses Gateway scope and skips OIDC
context. The wider mobile review/API/operator-auth/context run passed 116 tests
after isolating the mobile API test audit journal under pytest's private
temporary directory. Ruff and Python syntax checks passed. Candidate and legacy
databases were not accessed. Real OIDC/browser acceptance, other Gateway and
worker routes, direct-database boundaries, and RLS remain open.

### Field Collector owner-bound device access — 13 October 2026

Following the repository owner's transfer policy decision, new device
enrollments and registrations now store the location's verified organization
owner in additive migration 391. No legacy owner is inferred or backfilled.
Device-token form reads, upload policy and metadata writes, sync, and sync
status use `set_mobile_device_tenant_context` in their protected database
transaction. It validates the pinned owner against the active verified owner
and holds row locks until transaction end, so a transfer cannot race past
authorization. Stale enrollment codes and old-owner devices fail closed.

The Field Collector detects the dedicated owner-change response, clears only
the obsolete device token and cached forms, and marks existing encrypted queue
items for owner review. Those payloads and photos remain in the local vault
and are excluded from sync after a replacement device enrolls; newly captured
records use the new device identity. Already-synced records are not rewritten.
The ownership preflight requires the migration's two new tenant columns and
reports unbound, active-token, pending-enrollment, and stale-owner counts.

After the repository owner approved focused checks, 67 Python checks passed
across tenant-context setup, mobile API authorization, registration, media
cleanup, vault persistence, and preflight inventory. The two offline-shell Node
checks passed. Ruff, Python syntax compilation, requirement-group alignment,
provider-boundary checks, and `git diff --check` passed. A disposable PostgreSQL
16 database applied migration 391 twice; legacy rows remained NULL, wrong-owner
device and enrollment inserts were rejected, owner bindings were immutable,
and the former owner's device stopped matching the protected-access predicate
after transfer. A fresh owner-bound device insert succeeded. The disposable
container was removed. No candidate or legacy database was accessed.

At the time of this source-only acceptance, migration 391 had not yet been
applied to the candidate. The separately approved rollout completed on 14
October after an encrypted checkpoint; the additive columns remain, and any
rollback to an owner-unaware app must keep mobile ingress disabled until a
compatible owner-aware image is restored. Live-browser acceptance remains open
([rollout evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)).

### Pushed commit 258e46f platform-integrity verification — 13 October 2026

Before the local owner-bound device slice, commit
`258e46fa84e66e610f4d1f124a036e1443b7a2cf` was pushed to PR #68. The
approved focused platform-integrity suite passed all 279 tests across
migrations, Gateway auth, durable scheduler/event workers, credit custody, and
advisory workflows. The reviewer-note slice passed 14 mobile-review service
tests and three route authorization tests; tenant-scope denial rolls back and
closes the write transaction before any INSERT. Ruff and `git diff --check`
passed for that slice. No candidate or legacy database was used.

The latest observed GitHub Actions state on pushed commit
`79757675b2b562019e57209ef17138ab80f45fcd` is CI run #296 in progress and
Security run #20 passed. This is a point-in-time check; the local preflight
batch described below is not part of that run.
At that pushed revision, OIDC operator APIs set tenant context in their
service transactions, while device-token APIs lacked owner binding. The
repository owner has since approved the re-enrollment rule, and its local
implementation is documented above. The Directus runtime parity gate remains
partial: the archived schema lacks the legacy `directus_users.location_id`
field referenced by its policies.

### Aggregate operator grant preflight — 13 October 2026

Extended the read-only tenant preflight with database-wide operator identity
and active organization-membership totals, plus per-location counts for active
legacy and tenant-qualified grants. Tenant-qualified grant counts are split by
the same `operator_scope_grant_allows` predicate used by authorization, so the
preflight distinguishes currently accepted grants from stale or mismatched
ones. It returns aggregate counts only, with no operator identity claims,
contact fields, or raw operator, organization, and location IDs.

Five focused Python checks passed, along with Ruff, syntax compilation, and
`git diff --check`. A schema-targeted disposable PostgreSQL 16 database applied
the actual migrations 388 and 391. Synthetic owner and shared-partner grants,
an unaffiliated operator, a disabled operator, and a legacy grant produced the
expected per-location and global counts. Identifier-leak checks passed, and
post-run cleanup queries found zero synthetic rows across grants, shares,
memberships, owner records, locations, organizations, and identities. The
disposable database was removed. Candidate and legacy databases were not
accessed.

This preflight sizes remaining operator-mapping work but does not identify the
real organization for any operator, convert legacy grants, backfill tenant
data, or enable RLS. Worker coverage, direct-database isolation, populated
archive acceptance against the expanded schema, and RLS remain open. See the
[sanitized acceptance record](builds/2026-10-13-recovery/tenant-preflight-operator-access-disposable.json).

### Phase 8 current-head security and required-check audit — 14 October 2026

On pushed commit `cf3acab7e9a6ee011f28694e755fe1ca1b671a3d`, Security run #21
failed because full-history Gitleaks 8.30.1 classified two 64-character
SHA-256 source digests in the sanitized disposable preflight evidence as
generic API keys. Review found only source fingerprints, not deployment
credentials. The existing rule-specific allowlist now includes only that exact
evidence path and SHA-256 line shape. The official Darwin x64 archive checksum
matched, and the pinned local full-history command scanned 869 commits (about
74.31 MB) with no leaks.

The allowlist repair and exact context audit were pushed as
`cfe65140b17dc66314fb6875fa8439a12220da88`. Security run [#22](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38504514023)
passed; CI [#298](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38504514028)
is in progress. CI #297 was cancelled when the newer commit was pushed. Active
ruleset `18234835` now requires `CI / ci` and `Security / gitleaks`; GitHub API
verification confirms its review, CODEOWNERS, strict up-to-date, linear-history,
deletion, force-push, and bypass settings remain. The active version-tag
ruleset `18234836` is unchanged. The older 279-test platform-integrity run and
the current in-progress CI run do not yet certify the current source head.


### Candidate migration 391 rollout — 14 October 2026

After explicit approval, I created a fresh age-encrypted checkpoint for the
local candidate database. Age authentication and `pg_restore --list` passed.
The checkpoint was then restored into a fresh isolated `template0` database;
all 381 pre-391 migration fingerprints, extension versions, and selected
aggregate counts matched the candidate. The ordered runner applied only
`schema:391_mobile_device_tenant_binding.sql` with zero failures. The candidate
now has 382 applied schema migrations and no pending schemas; all 121 seed files
remain pending. No seeds were applied.

Only the candidate app was rebuilt and recreated. Its source manifest contains
1,315 files with digest
`ccc9b2c264601986b7478f78510a1490b12aa472d5caa86431335dd7b5711932`; app,
database, and Metabase are healthy, and the proxy remains running. `/health`
returned 200; anonymous farm-activity and mobile-review routes returned 401.
Post-rollout queries found no location, tenant-transfer, device, or enrollment
rows. The two tenant columns are present and RLS remains disabled. The legacy
stack and seed state were untouched. The previous app image and encrypted
checkpoint remain available; an owner-unaware app rollback requires mobile
ingress to stay disabled. Evidence:
[`candidate-mobile-tenant-binding-rollout.json`](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json).

The local candidate rollout and isolated PostgreSQL restore rehearsal are
complete for schema and anonymous-route checks. Live-browser re-enrollment,
populated ownership/transfer behavior, human retention/erasure disposition,
RLS, the remaining curated-seed candidate rollout, and media/role/external-provider recovery
remain open. The approved eight-suite platform-integrity suite passed all 279
tests locally on pushed commit `33dcc55ca5e5a2079f8fa6bd554a3ac85fe80118`.
The seed replay/bootstrap evidence is pushed at
`8aa33e24f169f15afb249a53ae3d281ed8d843a2`. CI run [#304](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38511715581)
is queued behind still-running run [#303](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38510013935); Security run [#28](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38511715446)
passed. The current local documentation update is not part of those checks.

### Isolated Field Collector browser offline acceptance — 14 October 2026

Ran the current candidate Field Collector shell in Google Chrome 155 using a
fresh temporary browser context. After the service worker cached the shell, the
browser switched to Playwright network-offline mode (`navigator.onLine=false`),
reopened the page from cache, unlocked a synthetic encrypted vault, and saved a
non-sensitive synthetic field note. The IndexedDB envelope retained ciphertext
and did not contain the note text. On reconnect, a mocked first sync returned
503 and the queue remained; a mocked retry returned 200 and removed the accepted
item. Every `/api/mobile/*` request was intercepted, so this is client/offline
queue acceptance, not live Gateway, enrollment, consent, or database
acceptance. The existing user vault, candidate database, and legacy stack were
not touched. See
[browser evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json).

### Candidate seed discovery and ledger preflight — 14 October 2026

Migration discovery previously skipped `schemas/seeds/064-068_impact_network.sql`
because its range prefix was not all digits. The runner now accepts numeric
range prefixes for seed files while retaining numeric-only schema versions; the
focused migration suite passes 23 tests and source validation now covers 503
files. The candidate's read-only plan reports 382 schemas applied, zero pending
schemas, 121 pending seed files, and zero recorded applied seeds. No seed SQL
was run. Read-only inventory also confirmed five active mobile forms and ten
form revisions, while `seed:140_mobile_forms.sql` has no ledger row. The curated
path in `scripts/seed.sh` currently sends seed SQL through `psql_exec` without
recording ledger state. Exact row-to-source parity remains unverified, so no
existing seed is adopted and no seed is applied; `064-068` is particularly
sensitive because it contains pilot upserts and updates the seeded Adelphi
location owner. See
[preflight evidence](builds/2026-10-14-recovery/candidate-seed-ledger-reconciliation-preflight.json).

### Curated seed ledger tracking — 14 October 2026

The migration CLI now accepts an explicit repeated `--only-migration` list,
validates each ID against the discovered sources, rejects duplicates and
unknown IDs before applying anything, and preserves the supplied order. The
curated `seed.sh` path now sends its existing reference-seed list through that
transactional checksum-tracked runner; reference-only mode still omits the
mobile-form seed. A pending 140_mobile_forms.sql accepts only empty state or
a full match against the current source columns and active revision snapshots;
it checks before a selected batch and again under table locks in the seed
transaction. A read-only comparison found all five active 1.2.0 forms and their
active revisions match all 20 seed columns; five retired 1.1.0 revisions are
preserved. After a fresh encrypted checkpoint and the guarded source-derived
parity check, the candidate applied only `seed:140_mobile_forms.sql` as a
verified no-op for form data. Its ledger now records one applied seed; 120
other seeds remain pending. The before/after form and revision fingerprints
match, and the candidate app, database, Metabase, and proxy remain healthy.
Focused migration/upgrade suites passed 44 tests; Ruff, shell syntax, migration
source validation for 503 files, and diff checks passed. See
[reconciliation evidence](builds/2026-10-14-recovery/candidate-mobile-form-seed-ledger-reconciliation.json).

### Curated seed target inventory — 14 October 2026

A read-only transaction inventoried all 52 relations referenced by the curated
seed SQL in the candidate. Every relation exists; 50 are empty. The two
non-empty targets are the five mobile forms already tracked by the guarded seed
reconciliation and 63 existing `service_registry` rows. The four service keys
that seed 091 would add are absent. No curated SQL ran and no container was
recreated. This closes the candidate's row-count inventory, not clean-bootstrap
or fresh-database bootstrap acceptance; 120 seed sources stay pending while
that review continues. See
[candidate inventory evidence](builds/2026-10-14-recovery/candidate-curated-seed-target-inventory.json).

### Curated seed disposable replay — 14 October 2026

Restored the encrypted pre-reconciliation candidate checkpoint into a new
`template0` database in a database-only disposable Compose project. Age
plaintext streamed directly to `pg_restore`. The ordered runner applied all 31
curated seeds with zero failures; a second invocation reported all migrations
already applied. The scratch ledger retained 382 applied schemas and 31 applied
seeds, and representative table counts reflected the expected additions. The
scratch volume was removed after capture. The live candidate remained healthy,
with 382 applied schemas, one applied seed, 120 pending seed sources, 5 forms,
63 service-catalog rows, and protected-route 401. This confirms ordered replay against the candidate snapshot. The legacy stack
was not accessed ([replay evidence](builds/2026-10-14-recovery/curated-seed-disposable-replay.json)).

### Fresh curated-seed bootstrap — 14 October 2026

A separate empty database created from `template0` applied all 382 ordered
schema migrations through 391 and all 31 curated seed migrations with zero
failures. The ledger contained 382 applied schemas and 31 applied seeds, with
no non-applied rows. The representative results were 33 business capabilities,
38 dashboard datasets, 67 service catalog rows, and five current mobile forms
with five active revisions. The disposable database and volume were removed.
The live candidate stayed at 382 schemas, one applied seed, 120 pending seed
sources, and retained health 200/protected route 401. This closes clean-schema
bootstrap acceptance for the current curated list; applying the 30 missing
curated seeds to the candidate remains a separately gated rollout. The fresh
age-encrypted PostgreSQL checkpoint was restored transactionally into an
isolated `template0` database; migration and extension fingerprints and
selected form/service row counts matched, and its scratch project and volume
were removed. The exact 30-seed scope, 90 deferred sources, candidate
baseline, and rollback path are recorded. No seed SQL has run on the candidate
during this preflight ([bootstrap evidence](builds/2026-10-14-recovery/fresh-curated-seed-bootstrap.json); [rollout preflight](builds/2026-10-14-recovery/candidate-curated-seed-rollout-preflight.json)).

### Tenant/RLS call-site audit — 14 October 2026

A source-only audit mapped device-token lookup, one-time enrollment redemption,
tenant-scoped device queries, OIDC and API-key operator mutations, the legacy
transport CLI, preflight inventory, Directus, and legacy mobile views. It found
pre-context bearer-credential lookups plus capability/API-key mutation routes
without operator tenant context; the legacy CLI also has unscoped queue/list/
sync commands. The audit records the closure sequence and role boundary before
RLS. No RLS was enabled and no database state changed
([audit](mobile-tenant-rls-callsite-audit.md)).

### Legacy mobile registration guard — 14 October 2026

Disabled direct device creation in the older `services.analytics.mobile_offline`
CLI, which did not require the location owner's single-use enrollment. The
guard rejects before database writes and points operators to the governed
enrollment and registration endpoints. Sixteen focused offline tests and 50
mobile API/form-validation tests passed; Ruff and Python syntax checks are
clean. Legacy queue/sync admission remains transport-only and requires separate
assessment. MAN-CAP-053 remains partial.

### Gateway mobile-device mutation tenant context — 14 October 2026

Gateway middleware now places its authenticated resource/action/location
decision on an internal request-state marker. Enrollment, enrollment revoke,
and device revoke require the exact `mobile_device` route marker and establish
transaction-local current-owner context before their writes. The context query
share-locks the active location, owner verification, and organization so a
transfer serializes with each mutation. OIDC continues to use the
tenant-qualified operator-grant helper. A denied or stale scope rolls back
before mutation.

The context value is application-verified scope, not a database-verifiable
Gateway credential. PostgreSQL custom settings remain forgeable by a role with
arbitrary SQL; RLS is still disabled pending the database-role/function
boundary, pre-context device/enrollment credential paths, legacy CLI, workers,
and Directus/view review. Focused tenant-context, mobile API, and operator-auth
checks passed 126 tests; Ruff and Python compilation passed. No database or
container was accessed ([evidence](builds/2026-10-14-recovery/gateway-mobile-tenant-context.json)).

### Mobile credential lookup boundary — 14 October 2026

Added migration 392 to move mobile device-token lookup and one-time enrollment
redemption behind `kokonut_security` functions owned by a dedicated
`NOLOGIN`, `NOBYPASSRLS` role. Token resolution accepts only the presented
SHA-256 token hash and returns minimal device identity plus whether the current
owner binding still matches. Redemption locks the unused enrollment and
current owner, registers one device, and consumes the code in one transaction.
The role has no direct application login; column-level `UPDATE(id)` grants
exist only to allow PostgreSQL row locks on owner records, and do not grant
updates to their business state. The migration also replaces migration 391's
trigger body with a fixed search path and qualified public relations so the
trigger remains valid inside restricted credential functions.

The network-disabled PostgreSQL 16 acceptance applied migrations 391 and 392,
replayed 392, and passed constrained-role direct-table denial, token current,
legacy, and unknown outcomes, device conflict, one-time success/reuse, expiry,
owner transfer, concurrent redemption (one device and one code consumption),
and credential-owner attribute checks. The focused mobile API and tenant suite
passed 56 tests; Ruff, Python compilation, and whitespace
checks passed. The disposable container and synthetic rows were removed.
Candidate and legacy databases were untouched; the candidate remains at
migration 391 and RLS remains disabled. Migration 392 needs its separately
gated candidate checkpoint/rollout; legacy CLI, workers, Directus/views, final
app-role boundaries, and forced-RLS acceptance remain open. See the
[call-site audit](mobile-tenant-rls-callsite-audit.md) and
[disposable evidence](builds/2026-10-14-recovery/mobile-credential-functions-disposable.json).

### Signed mobile tenant context — 14 October 2026

Migration 393 adds a dedicated `NOLOGIN`, `NOBYPASSRLS` context-function role,
a private random HMAC key, and database functions that validate the presented
device-token hash/current owner and sign the resulting context for the current
PostgreSQL backend and transaction. `current_tenant_context()` accepts only a
valid signature for that backend/transaction. The application role cannot read
the signing key. Dormant SELECT/UPDATE policies and key-column-only update
privileges let the restricted credential/context functions lock current-owner
rows under forced RLS; the migrations do not enable RLS on application tables.

The network-disabled PostgreSQL 16 acceptance applied migration 391, applied
and replayed 392–393, and forced RLS only in the disposable database. It passed
valid mobile context, cross-tenant filtering, caller-GUC and payload/signature
tampering denial, invalid-token clearing, context reset at transaction end,
private-key and direct-table denial, single-use enrollment, owner transfer,
and concurrent redemption. The test also confirmed both definer roles are
non-login, non-bypass, without role memberships, and that application-table RLS
remains disabled after migration replay. The disposable container and all
synthetic rows were removed. Seventy-six focused tests passed; Ruff, Python
compilation, and ordered migration validation (505 files) passed. Evidence is
at `docs/refactor/builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json`.

The test uncovered PostgreSQL's requirement for an UPDATE policy on rows read
with `FOR SHARE` under forced RLS. Migration 393 now adds matching dormant
policies for the narrowly scoped no-login roles while preserving column-level
update grants. The disposable runner's readiness probe also waits for a stable
postmaster start time so it cannot mistake the temporary initdb server for the
final PostgreSQL process.

Migrations 392–393 were not applied to the candidate or legacy database. The
candidate remains at migration 391, and application-table RLS stays disabled.
The OFU-18 checkpoint, ordered rollout, candidate-app rebuild, and protected
route verification remain separately gated. Operator/Gateway signed context,
legacy CLI reads/sync, worker and Directus/view boundaries, and broader tenant
RLS remain open. CI #306 and Security #30 passed on pushed head
`333507e844cd3937761087f1e7e03f895c509250`; they do not cover this unpushed
migration-393 batch or the local commit ahead of that head.

### Signed OIDC operator tenant context — 14 October 2026

Migration 394 adds a dedicated `NOLOGIN`, `NOBYPASSRLS` operator-context
definer role. The Gateway binds the SHA-256 hash of its authenticated opaque
OIDC session to request-local context, then each protected transaction passes
that proof to PostgreSQL. The function checks the active, unexpired,
nonrevoked session and enabled operator; current location; tenant-qualified
resource/action grants; active organization membership; current verified
location owner or unexpired explicit share; and that all additional scopes
resolve to the same organization. It share-locks the validated rows and signs
the resulting tenant/location/operator tuple for the current backend and
transaction. The shared `current_tenant_context()` accessor now accepts only
valid signatures for `mobile_device` and `operator` actors. Middleware resets
the request-local session proof after the response.

Disposable PostgreSQL 16 acceptance applied migration 394 twice, forced RLS
only on the synthetic source/probe tables, and verified owner and shared
tenant visibility; cross-tenant multi-scope, legacy NULL-tenant grant,
disabled identity, revoked/expired session, unknown token, and expired/revoked
share denial; forged diagnostic GUC and modified HMAC-payload rejection;
denial cleanup; grant-revocation blocking while a signed transaction holds its
scope; transaction-end cleanup; and private signing-key denial. The focused
tenant-context and OIDC operator-auth suites passed 20 tests (one skipped);
Ruff and Python compilation passed. Evidence is at
`docs/refactor/builds/2026-10-14-recovery/operator-tenant-context-disposable.json`.

This does not enable RLS or establish the final runtime database boundary.
`provision_runtime_role()` currently grants broad DML across public tables,
including read access to `operator_session.session_token_hash`; that undermines
the session-proof boundary if the constrained role is used. Session-table
isolation, Gateway API-key context, worker/legacy CLI integration, and
Directus/view access remain explicit RLS prerequisites. The candidate remains
at migration 391 under OFU-18; no candidate or legacy database was touched.
