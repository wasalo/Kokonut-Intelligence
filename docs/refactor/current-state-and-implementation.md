# Kokonut Intelligence refactor: candidate completion guide

**Authority:** this is the sole active status, completion register, and execution queue.
**Baseline:** source `cd65f1d9`; documentation consolidation 5 November 2026.
**Finish line selected by owner:** candidate accepted, not production cutover.

## Definition of done and frozen scope

Finish when G1–G7 below pass on an identified candidate with linked evidence and owner sign-off. Retain all 67 capabilities; a prepared or deployed matrix label is not candidate acceptance. Do not add capabilities during closure. New findings must attach to a gate; scope changes require an explicit recorded decision.

PostgreSQL/PostGIS remains canonical; Gateway and Python services own native policy. Directus, ClickHouse, Redis, Prefect, MQTT, gRPC and ingress remain optional or replaceable adapters. Preserve lifecycle `draft → submitted → verified → published`, independent human review, consent, private evidence, bounded retries, leases, idempotency and additive checksummed migrations. Do not retire a supported caller before replacement parity.

Standard is the primary acceptance profile. Preserve minimal/core/Edge compatibility and AMD64/ARM64 software support. Physical Pi, production scale/failover, public deployment and legacy retirement are separate milestones, never implied by candidate sign-off.

## Current baseline and immediate actions

- Local maintained-Debian PostGIS builds and OCI inventory acceptance passed on AMD64 and ARM64/QEMU: 229/228 packages, only the reviewed `libquadmath0` difference. Profile/release checks passed 134 tests. [Evidence](builds/2026-11-05-recovery/maintained-debian-postgis-multiarch.json).
- Source `cd65f1d9`: [Security #807](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41963624399) passed; [CI #1091](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41963624500) was still running at consolidation. Recheck every pushed SHA; no inherited green release claim.
- Standard disposable recovery passed through migration 746; native and QEMU full two-tenant probes remain through 745. These are synthetic/disposable checks, not current persistent deployment. [Recovery](builds/2026-11-03-recovery/standard-profile-recovery-746-disposable.json).
- API and general worker still share `kokonut_runtime`. Dedicated operation roles do not close C1. Historical privilege counts measure reach, not confirmed leaks.
- Persistent candidate revision, migrations, login and grants require fresh read-only inspection. Older rollout records cannot establish today's deployment state.

**Next:** verify exact-head CI; capture the candidate inventory without changing it; finish G2 caller/identity review and G3 capability acceptance mapping; collect G4–G6 external inputs now. No production operation is authorized by this document alone.

## Completion register

Only this register changes active status. Status vocabulary: **open**, **in progress**, **blocked**, **passed**, **deferred**. A gate passes only when every applicable requirement has evidence; missing inputs remain blocked, not silently deferred. Responsible roles below are assignments of work, not claims that named people have accepted ownership.

| Gate / status | Responsible role; dependencies | Next action and acceptance criteria |
| --- | --- | --- |
| **G1 — Baseline/builds: in progress** | Implementer + reviewer; none | Capture source/schema/seed inventories and exact-head CI/Security. Verify both architecture images and package contracts; record artifact digests. Maintained signed Debian repositories may change transitive packages between builds: deployment reproducibility belongs to the tested image digest. Ordinary CI still rebuilds PostGIS; protected registry publication is separate. |
| **G2 — Database security: open** | Security implementer + caller owners; G1 | Attribute remaining API/worker/CLI/ORM/dynamic SQL, Directus and external writers; separate API/general-worker credentials; remove first-provisioning broad compatibility grants through reviewed cohorts. Use bounded functions/roles and tenant enforcement or approved global boundaries. Cover object-ID/location binding, wallet/account custody grants, credit-class administration, metric source lineage, append-only ledgers and same-transaction context. Prove fresh/repeated provisioning, table/column denials, two-tenant denial and supported-caller parity. No blanket revocation based on source absence. |
| **G3 — Capability/compatibility parity: open** | Domain implementer + capability owners; G1, with G2 for security acceptance | Audit all 67 capabilities against routes, SDK, console, CLI, retained scopes and Directus fields/rows/hooks/schedules. Resolve actual gaps, including organization/network scopes and agent attribution/provenance. Preserve credit custody and independent retirement confirmation. Each capability needs an acceptance row, supporting contract, automated evidence and MAN-CAP owner outcome; unavailable prepared integrations remain explicitly unaccepted until owner disposition. |
| **G4 — Identity/workflows: blocked** | Identity operator + browser reviewer; G2/G3, client/account/certificate inputs | Verify trusted candidate HTTPS, ZITADEL discovery/client/callback, login/session/logout, CSRF, grants, enrollment/revocation, audit attribution and cross-location denial. Exercise governed draft/review/publication and Collector encrypted offline capture, reconnect/sync, consent withdrawal, retired forms, media and downstream disposition. Mocked browser/API checks alone cannot pass this gate. |
| **G5 — Data/reports/providers: blocked** | Data/provider/report owners + implementer; G3, populated fixtures and access | Verify Adelphi `farm.location_id` and approved ownership; compare retained reports, calculations and workflows against populated legacy references. Port repository-defined provider jobs, reconcile activation/cadence/owners, test delivery, retries and deduplication. Validate source-record lineage and analytical projection rebuild/outage behavior. Review per-report audiences; stakeholder review does not grant public access. Synthetic fixtures do not close populated parity. |
| **G6 — Candidate rollout/recovery: blocked** | Candidate operator + independent reviewer; G1–G5 and agreed availability window | Capture exact target/revision and encrypted checkpoint; restore-rehearse before applying reviewed migrations. Verify schema replay, runtime identities, workflows, health, outage/stalled-child recovery, retry/lease cleanup and rollback. Test selected SMTP and bucket-scoped backup transport/restore. Verify no ClickHouse TTL pruning; retain no-prune until approved policy/hold acceptance. Complete the existing 24-hour recovery requirement after defining its measurable observation/failure/restoration procedure and RPO with the owner; do not substitute a short restart check. |
| **G7 — Candidate sign-off: open** | Owner + release reviewer; G1–G6 | Confirm evidence matches accepted source, schemas, artifacts and target; all candidate requirements pass, required hosted checks/reviews pass and remaining production/device work has explicit disposition. Record independent owner acceptance and rollback location. Candidate acceptance does not retire legacy services or claim production readiness. |

Execute G1 first; progress G2 and G3 together where dependencies allow, collect external inputs immediately, then close G4/G5, G6 and finally G7. Run focused checks once per changed cohort; broaden only for changed integration surfaces, failures or unresolved concerns. Do not repeat costly builds for documentation-only updates.

## Owner inputs and deferred milestones

Existing decisions stand: Gateway-native farm activity, optional Directus, self-hosted ZITADEL, all repository-backed reports first, Kokonut Network's five named locations, Maileroo SMTP, R2 production/backups buckets, USA/Dominican Republic dynamic retention, and 24-hour recovery target. Do not re-ask settled choices. Keep unconfirmed tenant sharing ungranted.

Inputs still needed: operator memberships/scopes and identity provisioning; trusted local certificate; populated farm references; report disclosure review; alert recipient/severity/on-call ownership; least-privilege provider/storage access; approved candidate downtime and recovery window. Secrets go through SOPS, never the guide or chat. Reconcile historical access requests against current authorization before asking again.

**Deferred beyond candidate completion:** public DNS/TLS and production topology/RPO acceptance, production failover/scale, physical Pi thermal/storage/power-loss testing, production retention activation, release promotion and legacy retirement. Candidate scope/tenant, populated parity, backup restoration and required human review cannot be deferred by an implementer. Production pruning remains disabled until policy owners approve periods and holds; the candidate must prove no-prune and hold behavior. No hardware acceptance is claimed without hardware.

## Evidence and maintenance protocol

For each acceptance result record gate/capability, source SHA and dirty state, schema snapshot, image digest, target/project, command, time, outcome, limitations and cleanup/rollback. Distinguish source tests, disposable acceptance, candidate acceptance and owner decisions. Preserve dated artifacts unchanged and supersede by link.

Update this guide's register and capability acceptance rows after each batch. Capability-matrix classifications remain supporting catalog metadata; update them only when their existing criteria change and run its validator. Append history to progress; do not synchronize competing active TODOs or checklist totals. A newly pushed SHA reopens exact-head CI acceptance until checks pass.

Validation commands: `python3 scripts/check-capability-matrix.py`, `python3 -m services.migration validate --schemas-only`, plus cohort-specific checks in contributor instructions and specialist runbooks. Use [Standard procedures](standard-profile.md), [candidate procedures](kernel-candidate.md), [C1 technical detail](c1-runtime-acl-closure-plan.md), [recovery preparation](recovery-preparation.md) and [provider inputs](open-follow-ups.md) as references; they cannot override this register.

## Requirement reconciliation index

The entries below account for every unchecked checkbox found in the pre-consolidation Markdown corpus. They are **source references, not another task queue**. Repeated historical CI/replay items roll into current-head G1/G6. Historical implementation items remain under their gate until source/evidence review proves supersession; their old checkbox is not authority to repeat work. Mixed requirements map to multiple gates. Detailed prose, tables, decisions and contracts remain supporting specifications under G2–G6, including requirements without checkboxes.

- **R001 → deferred physical-device milestone:** [batches.md, original line 2577](batches.md) — Exercise physical-device/power failure. The code-only portability assessment now includes local source head `403ea03d` and a synthetic sensor-anomaly ML smoke under a 1 GiB/2-CPU container limit (188 MiB AMD64 and 325 MiB ARM64/QEMU peak RSS in the locked-image smoke; [evidence](builds/2026-10-26-recovery/sensor-anomaly-ml-hash-locked-image-builds.json)). Physical Raspberry Pi, power-loss, thermal, and storage-endurance acceptance remains unavailable:
- **R002 → G2, G6:** [batches.md, original line 2664](batches.md) — Configure USA/Dominican Republic purpose-specific retention and archive periods for terminal notification, attempt, and operator-audit records through reviewed runtime policy data when owners approve them; exact periods are intentionally not hardcoded or selected now. Keep no-prune until each policy and hold process is configured, and never prune pending, processing, retryable, or undisposed dead-letter rows.
- **R003 → G1, G2, G3, G4, G5, G6:** [batches.md, original line 2683](batches.md) — Complete scoped parity for the optional Directus adapter's retained collections, fields, hook effects, and schedules under its runtime identity. The owner selected Gateway operations for farm activity and keeping Directus optional. A role template maps six legacy farm-activity roles into explicit location grants; the native Field Collector 1.2.0 workflow has bounded list/detail/draft/lifecycle routes and an Analyst-only verified/published read path. One hundred four focused role, query, route, and lifecycle tests pass, along with four disposable PostgreSQL role-provisioning checks; a later migration-404 Gateway slice now supplies bounded non-Field-Collector farm-activity operations, with 13 focused service/HTTP/policy tests and 11 disposable PostgreSQL checks; migration 404 is applied on the candidate; this still does not prove parity for other Directus collections ([implementation](directus-parity-inventory.md); [evidence](builds/2026-10-16-recovery/farm-activity-gateway-role-mapping.json)). The fail-closed Directus adapter maps authenticated external subjects to enabled Kokonut operators and checks collection/action/location grants on 22 collections, including read-only `metric_value`; it rejects unscoped nested `deep` queries and dotted/wildcard relation fields. Pinned-image Field Note own-location read and cross-location hiding pass. The optional Kernel profile uses `kokonut_directus_runtime`; disposable PostgreSQL checks confirm DML-only grants, DDL/ownership denial, future-object grants, stale-ACL removal, and application-database-only access. `farm_activity` remains denied in the unlicensed Directus API; the Gateway now owns this operations contract. Historical permissions for nine managed roles are removed from the seed, and fresh Directus runtime apply/replay leaves zero managed `farm_activity` rules while retaining other permissions ([runtime evidence](builds/2026-10-15-recovery/directus-profile-disposable.json)). Remaining: historical-row reconciliation, other collection parity, field/relationship parity, configured provider/grants, live operator mapping, and hook/schedule ownership. A source-only inventory now records 175 declared permission rows: 123 wildcard-field rows and 52 explicit-field rows, plus six permission updates and one deletion; it is not effective deployed permission state and does not authorize narrowing roles ([profile](kernel-directus-profile.md); [inventory](directus-parity-inventory.md); [permission source report](builds/2026-10-20-recovery/directus-permission-source-inventory.json); [role evidence](builds/2026-10-15-recovery/directus-runtime-role-disposable.json); [unit evidence](builds/2026-10-15-recovery/directus-tenant-authorization-unit.json)).
- **R004 → G2, G3, G5, G6:** [batches.md, original line 2725](batches.md) — Complete remaining provider recovery, external delivery, and runtime recovery acceptance. The approved eight-suite platform-integrity suite passes 290 tests on local commit `238e2ef` ([evidence](builds/2026-10-14-recovery/platform-integrity-290-tests.json)); its Gateway tests use a private temporary audit journal on the host. A current-source scheduler outage run on 16 October confirms the worker process survives a disposable PostgreSQL stop/start and resumes successful ticks, with the scheduler engine stubbed ([evidence](builds/2026-10-16-recovery/scheduler-worker-postgres-reconnect.json)). The signed sensor-anomaly EventBus path now also passes a real child-process crash, lease reclaim, and attempt-two idempotent retry on disposable PostgreSQL 16. Exact mapped EventBus handlers drop shared PostgreSQL and global geospatial provider credentials while retaining their dedicated worker identity, and the Kernel supervisor derives its scheduler credential allowlist from the exact scheduled-module map. The legacy EventBus process receives the source-mapped handler identities and filters each child to its exact identity; the isolated notification-delivery worker uses only its outbox identity, and migration 648 now gives optional event dispatch a separate queue identity. Unmapped legacy handler environments remain unchanged. The expanded scheduler/EventBus boundary suite passes 224 checks ([evidence](builds/2026-10-17-recovery/event-handler-dedicated-environment.json). The weather forecast producer now has mocked source coverage for per-location rollback, mandatory outbox failure propagation, and connection cleanup without commit ([evidence](builds/2026-10-16-recovery/weather-forecast-atomic-projection.json). The other canonical PostgreSQL-to-ClickHouse producers now have typed enqueue-failure propagation and rollback boundaries; 158 focused tests pass ([evidence](builds/2026-10-16-recovery/ingestion-outbox-failure-atomicity.json). The ClickHouse outbox now applies capped exponential retries from 60 seconds to a one-hour maximum; 57 focused outbox, failure-injection, and producer tests pass with mocked boundaries only ([evidence](builds/2026-10-16-recovery/clickhouse-outbox-backoff.json). Its shared enqueue/delivery boundaries now suppress database/provider exception text while preserving typed errors, rollback, and retry behavior; 101 focused outbox/producer checks pass ([error evidence](builds/2026-10-17-recovery/clickhouse-outbox-error-sanitization.json)). The remote-sensing worker and legacy runner now sanitize provider errors before attempt/job persistence, and adapter logs omit raw exception text; 74 focused mocked tests pass, including legacy outbox failure redaction with rollback preserved ([evidence](builds/2026-10-17-recovery/remote-sensing-error-sanitization.json)). Legacy and isolated EAS status, audit, logs, and scheduler errors now omit raw provider exceptions; typed outbox rollback is preserved and persistence causes are suppressed. Its 184-test focused suite passes ([evidence](builds/2026-10-17-recovery/eas-error-sanitization.json)). The legacy subgraph indexer also redacts provider/database errors before status, audit, and logs; three mocked boundary checks pass ([evidence](builds/2026-10-17-recovery/subgraph-indexer-error-sanitization.json)). The RPC indexer now bounds wallet/outbox errors while preserving transaction recovery; six focused checks pass ([evidence](builds/2026-10-17-recovery/rpc-indexer-error-sanitization.json)). The Baal indexer now aborts on a failed event query and retains its last committed block; four mocked cursor/error tests pass ([evidence](builds/2026-10-17-recovery/baal-indexer-error-recovery.json)). Legacy current-weather and forecast runners now redact per-location audit/log failures and direct ClickHouse fallback details; four mocked regressions pass within 26 scope/atomicity tests. GEE climate initialization and MODIS/SMAP/Sentinel-1/ERA5 failures now return and log bounded summaries; six mocked regressions pass within 44 climate checks. No provider or database was contacted ([weather](builds/2026-10-17-recovery/weather-legacy-error-redaction.json); [GEE](builds/2026-10-17-recovery/gee-climate-error-redaction.json)). Freshness measurement error metadata/logs are also bounded while savepoint rollback and prior alert state remain intact (33 focused checks pass; [evidence](builds/2026-10-17-recovery/freshness-query-error-redaction.json)). MQTT callback and ClickHouse fallback logs are bounded, and QoS 1 failures remain unacknowledged for broker retry; three new mocked regressions pass in the 74-test MQTT/producer suite ([evidence](builds/2026-10-17-recovery/mqtt-subscriber-error-redaction.json)). HTTP sensor credential/processing errors now return bounded retryable responses and log only classes; three TestClient regressions pass within 50 HTTP/MQTT checks ([evidence](builds/2026-10-17-recovery/http-sensor-error-redaction.json)). Anomaly SMTP/Directus/actuator failure logs are also bounded; critical actuation remains approval-gated (three new tests in the 72-test anomaly/IoT suite; [evidence](builds/2026-10-17-recovery/anomaly-notification-error-redaction.json)). Direct actuator MQTT client/publish failure logs are bounded too (two new tests in the 64-test actuator/anomaly suite; [evidence](builds/2026-10-17-recovery/mqtt-actuator-error-redaction.json)). Live provider state, external delivery, other real task recovery, and broader runtime recovery remain open.
- **R005 → G5:** [batches.md, original line 2854](batches.md) — Port all repository-defined provider and scheduled-job capabilities first, as requested by the owner. Before enabling any in production, reconcile active provider state and accountable owners; resolve each
- **R006 → G2, G3, G5, G6:** [batches.md, original line 2904](batches.md) — Close projection, named-query, report and dashboard parity gaps in scoped groups. The owner asked us to port all repository-verified Kokonut surfaces first and decide retain/remove/improve after review; populated semantic fixtures follow farm-data ingestion. Batch 4e closed the initial PostgreSQL reporting contract and three first-party cards against copied fixtures. A source-defined CAP-006 compatibility slice also restores monthly carbon-offset and net-emissions estimates from active registered offsets; both remain advisory pending populated review ([evidence](builds/2026-10-24-recovery/cap-006-carbon-offset-monthly-compatibility.json)). The archived Metabase inventory found 39 generic e-commerce cards on sample H2 and no Kokonut PostgreSQL/ClickHouse source; do not label those sample cards as Kokonut products ([source inventory](metabase-source-inventory.md); [reporting contract](metabase-reporting-contract.md); [parity inventory](reporting-parity-inventory.md); [card parity](builds/2026-10-11-recovery/metabase-card-output-parity.json)).
- **R007 → G2, G3, G5:** [batches.md, original line 2926](batches.md) — Have accountable capability owners review report audiences, scopes, measures, and reference outputs after the planned farm-data ingestion, then decide which repository-backed surfaces to keep, remove, or improve. Direct and bounded helper query scans now identify mixed/no-visible-scope paths and report-to-helper query reachability, but they do not determine whether reads are intentionally network-level/reference data or have incorrect tenant scope; owner scope contracts and populated fixtures remain required ([direct-query inventory](report-generator-query-scope-inventory.json); [helper-query inventory](report-generator-helper-scope-inventory.json)).
- **R008 → G6:** [batches.md, original line 2928](batches.md) — Complete live worker recovery acceptance for leases, retries, idempotency,
- **R009 → G4, G6:** [batches.md, original line 3148](batches.md) — Complete browser acceptance through the candidate Caddy HTTPS origin after the repository owner trusts the local development certificate; the isolated tab returned `ERR_CERT_AUTHORITY_INVALID`, and the browser security interstitial was not bypassed ([evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json)).
- **R010 → G1, G2, G3, G4, G5, G6:** [batches.md, original line 3159](batches.md) — Configure the owner-selected self-hosted ZITADEL provider, then accept login/session, operator grant provisioning, CSRF, and browser console enrollment/revocation. Source route/auth checks pass; `.env.example` lists encrypted-provider inputs, the `--zitadel` planner selects the provider, Caddy route, and Gateway client, and 25 focused Compose/planner tests pass. Read-only registry inspection confirms ARM64 manifests for the digest-pinned API/Login, identity PostgreSQL, and Caddy defaults, and merged ARM64 profile configuration passes ([current manifest/config evidence](builds/2026-10-16-recovery/zitadel-arm64-profile.json); [transport profile evidence](builds/2026-10-16-recovery/kernel-arm64-transport-smokes.json)). The owner-selected identity host is `auth.kokonut.network`; the expected issuer and `hub.kokonut.network` callback now have commented production examples and pass an exact-value Compose rendering regression. Live discovery/client registration, provider credentials, test identity, and browser acceptance remain open. Kokonut's Gateway sessions and org/location grants remain the authorization authority. The synthetic API-key enrollment route is covered by the isolated end-to-end check.
- **R011 → G2, G3:** [batches.md, original line 3396](batches.md) — Extend the same-transaction context pattern across remaining Gateway
- **R012 → G5:** [batches.md, original line 3709](batches.md) — Verify external and operator-edited dashboard/report consumers against
- **R013 → G1, G2, G3, G4, G5, G6:** [batches.md, original line 3765](batches.md) — Complete remaining live Field Collector acceptance: configure the selected self-hosted ZITADEL provider; exercise live authenticated Gateway reconnect/sync; test retired-form consent withdrawal in the browser; and define downstream human disposition. A fresh isolated Chrome context now reports `navigator.onLine=false`, reopens the candidate app shell offline, saves a synthetic note into the encrypted queue, preserves it after a mocked 503, then clears it after a mocked 200 retry ([evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)). All mobile API calls in that browser check were intercepted, so it closes client offline behavior only—not live server sync or OS airplane-mode acceptance. Candidate Gateway service-outage/reconnect browser acceptance also passes with automatic retry and cleanup ([evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json)). Active and synthetic retired required-consent withdrawal handling passed through Gateway ASGI/HTTP on disposable clones; seeded retired `1.1.0` forms are `not_required`, so a synthetic reviewed revision was used. Accepted transport remains ineligible as `transport_pending`. Real OIDC, tenant/RLS, retention/erasure, and semantic content review remain open. The S3 media adapter now rejects keys outside the private Field Collector prefix before upload/head/delete, with 49 focused storage/reconcile/cleanup tests passing; live R2 inventory/deletion acceptance remains open; the public media-download route remains disabled.
- **R014 → G2, G3, G7:** [batches.md, original line 3796](batches.md) — Complete remaining live route, authorization, tenant-scope and broader SDK parity; publish only after explicit release authorization.
- **R015 → G1, G3, G4, G5, G6:** [batches.md, original line 3814](batches.md) — Configure the owner-selected self-hosted ZITADEL provider, then verify login/session/logout, grant provisioning, scope denials, enrollment-code delivery/revocation, audit attribution, and browser queue/detail behavior. A fresh isolated provider now starts and returns the configured synthetic issuer from internal discovery ([evidence](builds/2026-10-26-recovery/sprint-zitadel-provider-smoke.json)); planner/profile checks and isolated token-volume permissions also pass. The production hostname is `auth.kokonut.network`, but production issuer discovery, OIDC client/secrets, browser login, and Gateway session are not configured or exercised. Kokonut's Gateway sessions and org/location grants remain the authorization authority ([deployment plan](zitadel-provider.md)).
- **R016 → G3:** [batches.md, original line 3890](batches.md) — With verification authorization, exercise transport and Directus parity gates.
- **R017 → G6:** [batches.md, original line 3913](batches.md) — Complete the 24-hour recovery and scale-concurrency checks against the agreed recovery target; the owner deferred replica/failover acceptance to production. Schedule/resource budget and the verification window still need coordination.
- **R018 → G1, G7:** [batches.md, original line 3966](batches.md) — Obtain passing release CI and Security checks for the latest pushed PR head. Check GitHub Actions against the exact current PR commit and keep this gate open until both required contexts, `CI / ci` and `Security / gitleaks`, pass on that same SHA. On the latest pushed head `892944b120e290941c8cb7eff5f84346ee5823ee` for PR #71 (30 October), Security run [#733](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41010769891) passed and CI run [#1009](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/41010769939) is in progress. Each pushed batch starts a new exact-head gate; keep this item open until both required contexts pass together on the current head ([Actions](https://github.com/wasalo/Kokonut-Intelligence/actions)).
- **R019 → G7:** [batches.md, original line 3969](batches.md) — Execute the reviewed cutover and retire dependencies only after the readiness gates close. The owner has approved cutover once ready; no gate may be skipped.
- **R020 → G2, G3, G4, G5, G6:** [batches.md, original line 4054](batches.md) — Complete CAP-035 item-level workflow parity and acceptance. The Kernel now has location-scoped summary/status reads for gates, experiments, funding/tranches, adoption, scale gates, replications, learning, and retirements; bounded writes/reviews cover adoption-program draft creation, immutable consent-policy configuration, independent submission/review, consent-aware participant event capture and reviewed redesign revisions, independently reviewed readiness and configuration, gate evaluation/transition, experiment review, funding/tranche decisions, replication proposal/review/activation/completion, learning proposal/review/application, scale-gate assessment/review, and retirement proposal/approval/migration/sunset/post-review. The source-to-route audit is recorded; remaining work includes populated legacy fixture comparison, live ZITADEL OIDC/browser acceptance, broader runtime ACL/RLS, recovery, and MAN-CAP-035 owner acceptance. Keep location links and grants exact and human approval independent.
- **R021 → G2, G3, G4, G5, G6:** [batches.md, original line 4150](batches.md) — Complete CAP-036 populated/archived subject lineage and acceptance. Ordered item-level evidence/posterior reads and the repository-source audit are complete; compare populated legacy fixtures and complete live OIDC/browser, broader ACL/RLS, recovery, and MAN-CAP-036 owner acceptance. Keep source and tenant scope exact, immutable event ordering intact, and threshold actions advisory until a separate governed approval.
- **R022 → G2, G3, G4, G5, G6:** [batches.md, original line 4158](batches.md) — Verify the populated active Adelphi farm maps to the owner-confirmed location through `farm.location_id`, then compare populated operating data against legacy outputs. The bounded item-level Gateway/console workflows are implemented for capacity, demand, work claims, learning plans, coaching, resources, and competency assessments, including separate owner draft/revision/submission, independent review, and applicable activation/allocation/fulfillment actions ([contract](operating-pilot-kernel-read-contract.md)). No further first-party item workflow gap is identified by the current source inventory. Populated parity, audience/privacy review, live OIDC/browser behavior, recovery, broader ACL/RLS, and MAN-CAP-037 owner acceptance remain open. Keep internal-scope records out of location reads and preserve independent human review.
- **R023 → G2, G3, G5, G6:** [batches.md, original line 4228](batches.md) — Complete authenticated agent runtime identities and database least privilege; assess Directus runtime-role parity; extend human attribution beyond the deterministic and registered-synthesis receipt paths to non-synthesis human-triggered agents; compare populated task behavior and provider outputs; complete source-record provenance across legacy/background agents, other global reference tables, and source snapshots; exercise runtime recovery and obtain MAN-CAP-038 owner acceptance. The legacy Delphi study/panel CLI fails closed before database access. The Kernel Gateway now has signed study and participant lifecycle paths through migration 639; direct panel administration/calibration remains unavailable. Migrations 578–579 enforce worker lifecycle restrictions on insert/update for the existing 43 trigger-covered governed tables. Migrations 595–597 bind signed worker and operator-created drafts to registered tasks/requests. Migration 628 now binds a Gateway operator receipt to a registered synthesis worker before retry lookup, source reads, or draft write; the CIDS export labels each JSON-LD node with its contributing source view/table categories, and the registered task validator requires the exact normalized location and six signed views while rejecting empty graphs, unapproved node views, and missing, malformed, empty, or unsorted node provenance. CIDS property-to-row lineage is now recorded in a bounded per-property sidecar; a canonical digest binds the JSON-LD artifact to that sidecar without retaining source values. Full source snapshots remain open. Exact production grants, broader source-query least privilege, automatic dispatch, populated output parity, and remaining runtime/owner gates remain open.
- **R024 → G3:** [batches.md, original line 4335](batches.md) — Obtain owner acceptance for the operator administration model and verify the selected local database principal; review global-list privacy, grantor authority on direct grants/membership changes, and whether caller-supplied disablement attribution is acceptable or must be session-authenticated. Checklist: 811 complete / 24 open.
- **R025 → G2, G3:** [batches.md, original line 4765](batches.md) — Complete the authenticated runtime boundary and live test-network acceptance for CAP-067. The current commit supplies source helpers and a transport-injected client interface, but no registered Gateway routes, task-specific database identity/tenant ACL, concrete NEAR/EVM adapter, signing or broadcast integration, or live-chain finality evidence. Keep the feature prepared and disabled until exact operator authorization, idempotent proposal/retry, destination effect verification, and separate human reconciliation review are accepted. No KI transaction signing or source-record publication is in scope.
- **R026 → G2:** [batches.md, original line 9582](batches.md) — Add authenticated network/organization scope contracts before retiring
- **R027 → G3:** [batches.md, original line 9610](batches.md) — Confirm whether any external importer writes this table through
- **R028 → G3, G5:** [batches.md, original line 9638](batches.md) — Complete populated-data parity and retire the legacy metric CLI writer
- **R029 → G6:** [batches.md, original line 9674](batches.md) — Apply the conditional no-prune helper and verify table TTLs on each
- **R030 → G1:** [batches.md, original line 9741](batches.md) — Obtain passing CI and Security checks on the current pushed PR head.
- **R031 → G1, G6:** [batches.md, original line 9760](batches.md) — Complete the ARM64/QEMU ordered replay through migration 706 with the
- **R032 → G1:** [batches.md, original line 9887](batches.md) — Obtain a complete hosted CI run on the repair SHA and close the remaining
- **R033 → G1:** [batches.md, original line 9927](batches.md) — Obtain a complete hosted CI run for the pushed repair head. The linked
- **R034 → G1:** [batches.md, original line 9978](batches.md) — Obtain a complete passing hosted CI and Security run on the pushed repair
- **R035 → G1:** [batches.md, original line 10008](batches.md) — Obtain a complete hosted CI and Security run on the pushed repair head.
- **R036 → G1:** [batches.md, original line 10039](batches.md) — Obtain green hosted CI and Security on the pushed repair SHA. CI #1033
- **R037 → G2:** [batches.md, original line 10079](batches.md) — Confirm no external SQL caller depends on `kokonut_runtime` writes before
- **R038 → G2:** [batches.md, original line 10087](batches.md) — Check for external SQL callers and older deployed binaries before any
- **R039 → G1:** [batches.md, original line 10089](batches.md) — Wait for CI #1034 on pushed commit `3854d818` to finish before pushing
- **R040 → G6:** [batches.md, original line 10111](batches.md) — Run the migration-718 focused price-writer disposable checker and obtain
- **R041 → G2:** [batches.md, original line 10113](batches.md) — Reconcile external `kokonut_runtime` callers before any persistent
- **R042 → G2, G3:** [batches.md, original line 10151](batches.md) — Continue per-relation source, Directus, ORM/dynamic SQL, external-consumer,
- **R043 → G2:** [batches.md, original line 10171](batches.md) — Keep first-creation compatibility DML removal, broad grants on existing
- **R044 → G2, G6:** [c1-runtime-acl-closure-plan.md, original line 1386](c1-runtime-acl-closure-plan.md) — Confirm the event-retention policy/jurisdiction owner and review the
- **R045 → G2, G6:** [c1-runtime-acl-closure-plan.md, original line 1389](c1-runtime-acl-closure-plan.md) — Obtain owner/operations decision for the legacy replay/disposal writer:
- **R046 → G2, G3:** [c1-runtime-acl-closure-plan.md, original line 1398](c1-runtime-acl-closure-plan.md) — Obtain owner/operations approval before granting a global outbox capability
- **R047 → G2:** [c1-runtime-acl-closure-plan.md, original line 1402](c1-runtime-acl-closure-plan.md) — Review the current 3,636 unattributed SQL sites, 56 worker
- **R048 → G2, G3:** [c1-runtime-acl-closure-plan.md, original line 1406](c1-runtime-acl-closure-plan.md) — Reconcile Directus field/row permissions, extension hooks, ORM/dynamic SQL,
- **R049 → G2:** [c1-runtime-acl-closure-plan.md, original line 1477](c1-runtime-acl-closure-plan.md) — Add location fields to object-ID mutation requests and bind each object
- **R050 → G2:** [c1-runtime-acl-closure-plan.md, original line 1479](c1-runtime-acl-closure-plan.md) — Add a separately provisioned wallet/account grant for operations that
- **R051 → G2:** [c1-runtime-acl-closure-plan.md, original line 1482](c1-runtime-acl-closure-plan.md) — Keep class/basket definition mutations behind explicit global admin
- **R052 → G2:** [c1-runtime-acl-closure-plan.md, original line 1485](c1-runtime-acl-closure-plan.md) — Migrate direct credit-class CLI writers to an explicit operator or
- **R053 → G2:** [c1-runtime-acl-closure-plan.md, original line 1487](c1-runtime-acl-closure-plan.md) — Revoke credit-class table DML only after every affected writer is moved
- **R054 → G2, G3, G5:** [c1-runtime-acl-closure-plan.md, original line 1492](c1-runtime-acl-closure-plan.md) — Group the current 277 analytics write-target relations by capability
- **R055 → G2, G5:** [c1-runtime-acl-closure-plan.md, original line 1497](c1-runtime-acl-closure-plan.md) — Separate the current 444 analytics write-candidate SQL sites into
- **R056 → G2, G5:** [c1-runtime-acl-closure-plan.md, original line 1501](c1-runtime-acl-closure-plan.md) — Preserve current calculations and reports with synthetic/populated
- **R057 → G2:** [c1-runtime-acl-closure-plan.md, original line 1503](c1-runtime-acl-closure-plan.md) — Revoke DML per completed relation cohort, never by broad source absence.
- **R058 → G2, G5:** [c1-runtime-acl-closure-plan.md, original line 1507](c1-runtime-acl-closure-plan.md) — Reconcile the current 269 unique non-analytics/non-credit-class write
- **R059 → G2, G3:** [c1-runtime-acl-closure-plan.md, original line 1512](c1-runtime-acl-closure-plan.md) — Add bounded APIs/functions or dedicated writer identities per capability
- **R060 → G2:** [c1-runtime-acl-closure-plan.md, original line 1514](c1-runtime-acl-closure-plan.md) — Keep global reference and administrative writes distinct from
- **R061 → G2:** [c1-runtime-acl-closure-plan.md, original line 1524](c1-runtime-acl-closure-plan.md) — Remove the first-creation all-public-table compatibility grant as
- **R062 → G2, G3, G5:** [c1-runtime-acl-closure-plan.md, original line 1537](c1-runtime-acl-closure-plan.md) — Keep reader, API, worker, indexer, report, Directus, and maintenance
- **R063 → G2:** [c1-runtime-acl-closure-plan.md, original line 1539](c1-runtime-acl-closure-plan.md) — Add a migration-backed privilege contract per cohort, including table
- **R064 → G2, G6:** [c1-runtime-acl-closure-plan.md, original line 1545](c1-runtime-acl-closure-plan.md) — On disposable PostgreSQL 16, replay all migrations, provision all runtime
- **R065 → G2:** [c1-runtime-acl-closure-plan.md, original line 1548](c1-runtime-acl-closure-plan.md) — Repeat database portability checks on ARM64/QEMU; record clearly that
- **R066 → G2, G5:** [c1-runtime-acl-closure-plan.md, original line 1556](c1-runtime-acl-closure-plan.md) — Use synthetic data for cross-tenant denial and representative populated
- **R067 → G2, G6:** [c1-runtime-acl-closure-plan.md, original line 1559](c1-runtime-acl-closure-plan.md) — Before candidate or production rollout, create and restore-rehearse a
- **R068 → G2, G7:** [c1-runtime-acl-closure-plan.md, original line 1562](c1-runtime-acl-closure-plan.md) — Keep production cutover separate from code completion; retain a reversible
- **R069 → G3:** [sprint-kernel-workflow-acceptance.md, original line 71](sprint-kernel-workflow-acceptance.md) — Build an isolated Compose project with synthetic organizations, two
- **R070 → G4:** [sprint-kernel-workflow-acceptance.md, original line 115](sprint-kernel-workflow-acceptance.md) — Start the existing optional ZITADEL, dedicated identity database, Caddy,
- **R071 → G3:** [sprint-kernel-workflow-acceptance.md, original line 121](sprint-kernel-workflow-acceptance.md) — Use a locally trusted HTTPS test origin. Verify real discovery, PKCE,
- **R072 → G3:** [sprint-kernel-workflow-acceptance.md, original line 126](sprint-kernel-workflow-acceptance.md) — Provision location-qualified Kokonut grants for the synthetic operators;
- **R073 → G3:** [sprint-kernel-workflow-acceptance.md, original line 171](sprint-kernel-workflow-acceptance.md) — Through the authenticated console, issue a single-use enrollment for one
- **R074 → G3:** [sprint-kernel-workflow-acceptance.md, original line 177](sprint-kernel-workflow-acceptance.md) — Exercise the existing eligibility and content-review gates. If the
- **R075 → G5:** [sprint-kernel-workflow-acceptance.md, original line 184](sprint-kernel-workflow-acceptance.md) — Compare one bounded farm activity metric/report or registered dashboard
- **R076 → G6:** [sprint-kernel-workflow-acceptance.md, original line 207](sprint-kernel-workflow-acceptance.md) — Reuse the disposable [scheduler reconnect](../../scripts/check-scheduler-engine-reconnect-disposable.py)
- **R077 → G6:** [sprint-kernel-workflow-acceptance.md, original line 213](sprint-kernel-workflow-acceptance.md) — Create and restore an isolated encrypted checkpoint of the synthetic
- **R078 → G3:** [sprint-kernel-workflow-acceptance.md, original line 218](sprint-kernel-workflow-acceptance.md) — Repeat the relevant software checks on ARM64/QEMU where feasible, using
- **R079 → G3:** [sprint-kernel-workflow-acceptance.md, original line 222](sprint-kernel-workflow-acceptance.md) — Update [batches](batches.md), [progress](progress.md), and the affected
- **R080 → G1:** [todo-kernel-refactor.md, original line 79](todo-kernel-refactor.md) — Obtain a complete passing CI and Security run on the next pushed PR head.
- **R081 → G1:** [todo-kernel-refactor.md, original line 172](todo-kernel-refactor.md) — Complete hosted full CI for the latest pushed head. The S108 repair and
- **R082 → G1, G6:** [todo-kernel-refactor.md, original line 217](todo-kernel-refactor.md) — Complete ARM64/QEMU full ordered schema replay through 706 and the
- **R083 → G1:** [todo-kernel-refactor.md, original line 226](todo-kernel-refactor.md) — Obtain passing CI and Security checks on the next pushed PR head. The
- **R084 → G4:** [todo-kernel-refactor.md, original line 270](todo-kernel-refactor.md) — Replace the Field Collector's fixed 30-day unattached-media expiry with
- **R085 → G6:** [todo-kernel-refactor.md, original line 273](todo-kernel-refactor.md) — Apply `scripts/apply-clickhouse-retention.py` and verify all eight tables
- **R086 → G5:** [todo-kernel-refactor.md, original line 276](todo-kernel-refactor.md) — Define source-type semantics and validate metric `source_record_ids`
- **R087 → G2:** [todo-kernel-refactor.md, original line 1143](todo-kernel-refactor.md) — **C1 — Replace broad runtime database privileges with scoped contracts.**
- **R088 → G3:** [todo-kernel-refactor.md, original line 1358](todo-kernel-refactor.md) — **C2 — Finish Gateway and SDK contract parity.** Audit registered routes,
- **R089 → G3:** [todo-kernel-refactor.md, original line 1629](todo-kernel-refactor.md) — **C3 — Finish the optional Directus adapter boundary.** Close code-verifiable
- **R090 → G5:** [todo-kernel-refactor.md, original line 1678](todo-kernel-refactor.md) — **C4 — Port repository-defined provider jobs and workflows.** Compare each
- **R091 → G5:** [todo-kernel-refactor.md, original line 1742](todo-kernel-refactor.md) — **C5 — Close source-verifiable analytics and reporting gaps.** Port
- **R092 → G3:** [todo-kernel-refactor.md, original line 1807](todo-kernel-refactor.md) — **C6 — Complete source-only capability slices.** Continue unresolved
- **R093 → G6:** [todo-kernel-refactor.md, original line 1818](todo-kernel-refactor.md) — **C7 — Finish software-only ARM64 and recovery evidence.** A current
- **R094 → G3:** [todo-kernel-refactor.md, original line 1881](todo-kernel-refactor.md) — **C8 — Reconcile all ledgers after each batch.** Keep the sprint TODO,
- **R095 → G4:** [todo-kernel-refactor.md, original line 1936](todo-kernel-refactor.md) — **H1 — Live ZITADEL login:** confirm issuer discovery, provision/register
- **R096 → G4:** [todo-kernel-refactor.md, original line 1941](todo-kernel-refactor.md) — **H2 — Browser trust:** trust the local development CA or provide an
- **R097 → G5:** [todo-kernel-refactor.md, original line 1944](todo-kernel-refactor.md) — **H3 — Populated data and report review:** ingest the owner-held Genesis,
- **R098 → G6:** [todo-kernel-refactor.md, original line 1950](todo-kernel-refactor.md) — **H4 — Retention operations:** accountable owners configure dynamic
- **R099 → G3:** [todo-kernel-refactor.md, original line 1954](todo-kernel-refactor.md) — **H5 — External delivery and storage:** provide alert recipient/severity
- **R100 → G6:** [todo-kernel-refactor.md, original line 1958](todo-kernel-refactor.md) — **H6 — Production topology and recovery:** supply trusted proxy hops,
- **R101 → deferred physical-device milestone:** [todo-kernel-refactor.md, original line 1963](todo-kernel-refactor.md) — **H7 — Physical device check:** if a Raspberry Pi becomes available,
- **R102 → G1, G7:** [todo-kernel-refactor.md, original line 1966](todo-kernel-refactor.md) — **H8 — Release and cutover:** obtain green required CI/Security checks on
- **R103 → G3:** [todo-kernel-refactor.md, original line 4648](todo-kernel-refactor.md) — Before applying migration 704 to a persistent target, confirm whether any
- **R104 → G3:** [todo-kernel-refactor.md, original line 4663](todo-kernel-refactor.md) — Add migration-backed action receipts and atomic location-bound tension,
- **R105 → G2:** [todo-kernel-refactor.md, original line 4666](todo-kernel-refactor.md) — Design authenticated organization/network scope contracts before
- **R106 → G3:** [todo-kernel-refactor.md, original line 4669](todo-kernel-refactor.md) — Keep migration 704 out of persistent targets until the owner confirms
- **R107 → G2:** [todo-kernel-refactor.md, original line 4698](todo-kernel-refactor.md) — Implement the corresponding bounded SQL functions, database receipts,
- **R108 → G2, G3, G6:** [todo-kernel-refactor.md, original line 4700](todo-kernel-refactor.md) — Add/run focused Gateway, console, and disposable PostgreSQL checks after
- **R109 → G3:** [todo-kernel-refactor.md, original line 4702](todo-kernel-refactor.md) — Only after parity acceptance, migrate the remaining direct writers and
- **R110 → G3:** [todo-kernel-refactor.md, original line 4720](todo-kernel-refactor.md) — Add bounded metric list/draft/verification functions, grants, receipts,
- **R111 → G6:** [todo-kernel-refactor.md, original line 4722](todo-kernel-refactor.md) — Verify all C1 source cohorts together, then replay migrations and run
- **R112 → G1:** [todo-kernel-refactor.md, original line 4749](todo-kernel-refactor.md) — Obtain a complete green hosted CI and Security result on the repair SHA.
- **R113 → G2:** [todo-kernel-refactor.md, original line 4766](todo-kernel-refactor.md) — Confirm external SQL callers and older deployed binaries do not invoke
- **R114 → G1:** [todo-kernel-refactor.md, original line 4768](todo-kernel-refactor.md) — Include this migration in the next reviewed commit/push after CI #1034
- **R115 → G2:** [todo-kernel-refactor.md, original line 4786](todo-kernel-refactor.md) — Verify external SQL callers do not use `kokonut_runtime` to write
- **R116 → G1:** [todo-kernel-refactor.md, original line 4812](todo-kernel-refactor.md) — Run the focused migration-718 price-writer checker and obtain hosted
- **R117 → G2, G6:** [todo-kernel-refactor.md, original line 4815](todo-kernel-refactor.md) — Confirm external `kokonut_runtime` consumers before persistent rollout;
- **R118 → G2:** [todo-kernel-refactor.md, original line 4834](todo-kernel-refactor.md) — Continue retiring broad DML on existing relations; this guard does not

- **R119 → G4:** [mobile-form-operations.md, original line 169](mobile-form-operations.md) — Verify real-provider grant.

## Capability acceptance coverage

All rows remain open for candidate acceptance until linked gate evidence and the corresponding MAN-CAP outcome are recorded. Existing catalog classifications are preserved; no capability is dropped.

| Capability | Name | Required gates | Candidate acceptance |
| --- | --- | --- | --- |
| CAP-001 | Governed farm operations | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-002 | Precision agriculture | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-003 | Traceability | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-004 | Extension & peer learning | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-005 | Farmer identity & cooperatives | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-006 | Energy, waste & landscape | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-007 | Metrics & analytics | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-008 | Trend analysis & geostatistics | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-009 | Systems thinking | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-010 | OODA loop & adaptive decisions | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-011 | Process intelligence | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-012 | Process architecture & costing | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-013 | Impact accountability | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-014 | CRISP risk scoring | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-015 | Organic certification readiness | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-016 | True cost accounting | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-017 | Emergency response | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-018 | EAS on Celo | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-019 | Ecocredit module | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-020 | Credit custody & retirement | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-021 | Linked data infrastructure | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-022 | Data Stream | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-023 | Governance framework abstraction | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-024 | Governance circles & roles | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-025 | Stakeholder ecosystem | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-026 | Threatcasting & backcasting | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-027 | Real-time Delphi | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-028 | Strategy system | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-029 | Competitive landscape | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-030 | Management workflow | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-031 | Planning & budgeting | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-032 | Business architecture | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-033 | Pitch & business planning | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-034 | Coordination & alliance system | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-035 | Solution lifecycle | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-036 | Sequential evidence & decisions | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-037 | Operating pilot | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-038 | Agent ecosystem | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-039 | Unified meta-CLI | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-040 | dMRV architecture | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-041 | Digital soil mapping | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-042 | Guild protocol | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-043 | Credit Token | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-044 | Price Oracle | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-045 | Selective Disclosure | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-046 | KokonutResolver | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-047 | Platform integrity | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-048 | Strategic reserve | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-049 | Capital accounting | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-050 | Tactical layer & simulation | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-051 | Data governance | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-052 | Platform upgrade system | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-053 | Field data collection | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-054 | Silvi tree tracking | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-055 | Oracle infrastructure | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-056 | Revenue model & channels | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-057 | Environmental scanning | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-058 | Marketplace | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-059 | Abundance Protocol | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-060 | Schema.org alignment | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-061 | Regen Network parity | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-062 | ARKIV parity | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-063 | GeoNode parity | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-064 | gRPC API | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-065 | Business Model Canvas | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-066 | State of Kokonut | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |
| CAP-067 | Kokonut Protocol execution bridge | G2–G6; sign-off G7 | open; consult [catalog](capability-matrix.md) for contract/manual evidence |

## Supporting document index

Every pre-consolidation Markdown record is listed below. Contracts and runbooks retain technical authority for their specified behavior; historical status and task lists are superseded by this guide. Evidence files remain immutable supporting artifacts.

- [README](README.md)
- [agent-ecosystem-kernel-contract](agent-ecosystem-kernel-contract.md)
- [agent-output-provenance-inventory](agent-output-provenance-inventory.md)
- [agent-task-attribution-inventory](agent-task-attribution-inventory.md)
- [analytics-broker-recovery](analytics-broker-recovery.md)
- [analytics-overlay](analytics-overlay.md)
- [analytics-read-views-v2](analytics-read-views-v2.md)
- [application-package-inventory](application-package-inventory.md)
- [arm64-application](arm64-application.md)
- [arm64-database](arm64-database.md)
- [arm64-image-pair-refresh](arm64-image-pair-refresh.md)
- [arm64-public-reads](arm64-public-reads.md)
- [backup-object-storage](backup-object-storage.md)
- [batches](batches.md)
- [README](builds/2026-10-10-batch1/README.md)
- [README](builds/2026-10-10-readiness/README.md)
- [README](builds/2026-10-10-recovery/README.md)
- [business-architecture-kernel-read-contract](business-architecture-kernel-read-contract.md)
- [business-planning-kernel-edit-contract](business-planning-kernel-edit-contract.md)
- [business-planning-kernel-read-contract](business-planning-kernel-read-contract.md)
- [business-planning-kernel-write-contract](business-planning-kernel-write-contract.md)
- [c1-runtime-acl-closure-plan](c1-runtime-acl-closure-plan.md)
- [canonical-sensor-recovery](canonical-sensor-recovery.md)
- [capability-matrix](capability-matrix.md)
- [code-first-execution-plan](code-first-execution-plan.md)
- [competitive-landscape-kernel-read-contract](competitive-landscape-kernel-read-contract.md)
- [comprehensive-status-kernel-read-contract](comprehensive-status-kernel-read-contract.md)
- [cooperative-management-kernel-read-contract](cooperative-management-kernel-read-contract.md)
- [coordination-kernel-read-contract](coordination-kernel-read-contract.md)
- [crop-simulation-runs-kernel-read-contract](crop-simulation-runs-kernel-read-contract.md)
- [decisions](decisions.md)
- [delphi-consultation-kernel-contract](delphi-consultation-kernel-contract.md)
- [directus-parity-inventory](directus-parity-inventory.md)
- [directus-polymorphic-lineage-preflight](directus-polymorphic-lineage-preflight.md)
- [edge-profile](edge-profile.md)
- [energy-monitoring-kernel-read-contract](energy-monitoring-kernel-read-contract.md)
- [event-handler-concurrency](event-handler-concurrency.md)
- [extension-learning-kernel-read-contract](extension-learning-kernel-read-contract.md)
- [farm-activity-workflow-map](farm-activity-workflow-map.md)
- [field-collector-downstream-source-audit](field-collector-downstream-source-audit.md)
- [finalization-plan](finalization-plan.md)
- [gateway-audit-spool](gateway-audit-spool.md)
- [gateway-farm-activity-operations](gateway-farm-activity-operations.md)
- [gateway-tenant-context-contract](gateway-tenant-context-contract.md)
- [geostatistics-kernel-read-contract](geostatistics-kernel-read-contract.md)
- [governance-assignment-review-contract](governance-assignment-review-contract.md)
- [governance-definition-lifecycle-contract](governance-definition-lifecycle-contract.md)
- [governance-tactical-action-contract](governance-tactical-action-contract.md)
- [governance-tactical-content-mutation-contract](governance-tactical-content-mutation-contract.md)
- [governance-tactical-session-creation-contract](governance-tactical-session-creation-contract.md)
- [grpc-authentication](grpc-authentication.md)
- [grpc-database](grpc-database.md)
- [grpc-overlay](grpc-overlay.md)
- [grpc-shutdown](grpc-shutdown.md)
- [http-sensor-limits](http-sensor-limits.md)
- [http-sensor-overlay](http-sensor-overlay.md)
- [http-sensor-transactions](http-sensor-transactions.md)
- [implementation-plan-alignment](implementation-plan-alignment.md)
- [irrigation-status-kernel-read-contract](irrigation-status-kernel-read-contract.md)
- [kernel-candidate](kernel-candidate.md)
- [kernel-directus-profile](kernel-directus-profile.md)
- [kernel-operations-console](kernel-operations-console.md)
- [kernel-operator-cli](kernel-operator-cli.md)
- [kernel-proxy](kernel-proxy.md)
- [kernel-release-inputs](kernel-release-inputs.md)
- [kernel-supervision](kernel-supervision.md)
- [landscape-pollinator-kernel-read-contract](landscape-pollinator-kernel-read-contract.md)
- [legacy-logical-restore](legacy-logical-restore.md)
- [legacy-storage-preservation](legacy-storage-preservation.md)
- [live-outbox-recovery](live-outbox-recovery.md)
- [local-data-inventory](local-data-inventory.md)
- [local-private-media](local-private-media.md)
- [location-api-contract](location-api-contract.md)
- [management-work-kernel-read-contract](management-work-kernel-read-contract.md)
- [metabase-kernel-profile](metabase-kernel-profile.md)
- [metabase-reporting-contract](metabase-reporting-contract.md)
- [metabase-source-inventory](metabase-source-inventory.md)
- [migration-checksum-drift](migration-checksum-drift.md)
- [mobile-access-contract](mobile-access-contract.md)
- [mobile-form-classification-review](mobile-form-classification-review.md)
- [mobile-form-operations](mobile-form-operations.md)
- [mobile-retention-disposition](mobile-retention-disposition.md)
- [mobile-tenant-isolation](mobile-tenant-isolation.md)
- [mobile-tenant-rls-callsite-audit](mobile-tenant-rls-callsite-audit.md)
- [mqtt-delivery](mqtt-delivery.md)
- [mqtt-overlay](mqtt-overlay.md)
- [mqtt-readiness](mqtt-readiness.md)
- [mqtt-recovery](mqtt-recovery.md)
- [mqtt-transactions](mqtt-transactions.md)
- [native-location-reads](native-location-reads.md)
- [native-metric-reads](native-metric-reads.md)
- [noi-snapshot-reconciliation](noi-snapshot-reconciliation.md)
- [notification-outbox-operations](notification-outbox-operations.md)
- [nutrient-balances-kernel-read-contract](nutrient-balances-kernel-read-contract.md)
- [nutrient-events-kernel-read-contract](nutrient-events-kernel-read-contract.md)
- [nutrient-operations-console-contract](nutrient-operations-console-contract.md)
- [nutrient-soil-tests-kernel-read-contract](nutrient-soil-tests-kernel-read-contract.md)
- [open-follow-ups](open-follow-ups.md)
- [operating-pilot-kernel-read-contract](operating-pilot-kernel-read-contract.md)
- [operator-cli-boundary-inventory](operator-cli-boundary-inventory.md)
- [optional-database-roles](optional-database-roles.md)
- [orchestration-jobs](orchestration-jobs.md)
- [outbox-operator-audit](outbox-operator-audit.md)
- [pending-migration-compatibility-review](pending-migration-compatibility-review.md)
- [planning-budget-kernel-read-contract](planning-budget-kernel-read-contract.md)
- [portability-database](portability-database.md)
- [portability-runtime](portability-runtime.md)
- [portability-workers](portability-workers.md)
- [postgres-rate-limits](postgres-rate-limits.md)
- [profile-selection](profile-selection.md)
- [progress](progress.md)
- [projection-failure-boundaries](projection-failure-boundaries.md)
- [projection-job](projection-job.md)
- [provider-clone-inventory](provider-clone-inventory.md)
- [provider-configuration](provider-configuration.md)
- [public-relation-readiness](public-relation-readiness.md)
- [public-response-models](public-response-models.md)
- [public-summary-contracts](public-summary-contracts.md)
- [rate-limit-boundary](rate-limit-boundary.md)
- [recovery-fixture-setup](recovery-fixture-setup.md)
- [recovery-media-fixture](recovery-media-fixture.md)
- [recovery-preparation](recovery-preparation.md)
- [reference-seed-scope](reference-seed-scope.md)
- [report-snapshot-export-contract](report-snapshot-export-contract.md)
- [reporting-parity-inventory](reporting-parity-inventory.md)
- [retention-policy-operations](retention-policy-operations.md)
- [retention-policy-scope-contract](retention-policy-scope-contract.md)
- [runtime-role-policy](runtime-role-policy.md)
- [schedule-ownership-inventory](schedule-ownership-inventory.md)
- [scheduler-activation](scheduler-activation.md)
- [scheduler-graph-audit](scheduler-graph-audit.md)
- [scheduler-job-planning](scheduler-job-planning.md)
- [scheduler-run-windows](scheduler-run-windows.md)
- [sensor-anomaly-delivery](sensor-anomaly-delivery.md)
- [sensor-anomaly-ml-worker-contract](sensor-anomaly-ml-worker-contract.md)
- [sensor-device-authorization](sensor-device-authorization.md)
- [sensor-driver-scheduled-contract](sensor-driver-scheduled-contract.md)
- [sensor-entrypoint-recovery](sensor-entrypoint-recovery.md)
- [sensor-projection](sensor-projection.md)
- [sensor-quality-parity](sensor-quality-parity.md)
- [sensor-rollups-v2](sensor-rollups-v2.md)
- [sensor-timestamp-identity](sensor-timestamp-identity.md)
- [sequential-decision-kernel-read-contract](sequential-decision-kernel-read-contract.md)
- [sequential-evidence-subject-lineage-inventory](sequential-evidence-subject-lineage-inventory.md)
- [solution-lifecycle-kernel-read-contract](solution-lifecycle-kernel-read-contract.md)
- [solution-lifecycle-kernel-write-contract](solution-lifecycle-kernel-write-contract.md)
- [solution-lifecycle-source-route-audit](solution-lifecycle-source-route-audit.md)
- [sprint-kernel-workflow-acceptance](sprint-kernel-workflow-acceptance.md)
- [stakeholder-identity-kernel-contract](stakeholder-identity-kernel-contract.md)
- [standard-profile](standard-profile.md)
- [strategy-kernel-read-contract](strategy-kernel-read-contract.md)
- [tenant-owner-map-reconciliation](tenant-owner-map-reconciliation.md)
- [tenant-owner-transfer-contract](tenant-owner-transfer-contract.md)
- [threatcasting-kernel-read-contract](threatcasting-kernel-read-contract.md)
- [todo-kernel-refactor](todo-kernel-refactor.md)
- [traceability-kernel-read-contract](traceability-kernel-read-contract.md)
- [trend-analysis-kernel-read-contract](trend-analysis-kernel-read-contract.md)
- [unified-cli-kernel-contract](unified-cli-kernel-contract.md)
- [waste-management-kernel-read-contract](waste-management-kernel-read-contract.md)
- [work-media-recovery](work-media-recovery.md)
- [worker-operation-map](worker-operation-map.md)
- [worker-tenant-context-contract](worker-tenant-context-contract.md)
- [yield-monitoring-kernel-read-contract](yield-monitoring-kernel-read-contract.md)
- [zitadel-provider](zitadel-provider.md)
