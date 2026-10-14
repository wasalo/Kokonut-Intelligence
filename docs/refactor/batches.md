# Kernel execution checklist

Updated: 14 October 2026. Current architecture focus is Phase 8 acceptance;
batch numbers group work across phases and do not replace the phase gates.

## Working agreement

Each batch delivers one reviewable outcome, lists evidence and rollback, and
updates progress.md, affected capability rows and the ignored root plan. Stop at
the batch boundary to report completed items and unresolved gates. No capability
is accepted solely because source exists or an image starts. Verification work
below requires an explicit request before adding or running test suites.

The repository owner authorized focused test execution for this ongoing refactor
on 14 October 2026. Owner-only decisions and external access needed for
remaining gates are collected in [Open Follow Ups](open-follow-ups.md);
implementation and verification continue on independent work while answers are
pending.

Remaining work is ordered in [the code-first execution plan](code-first-execution-plan.md): finish repository-owned implementation and reproducible software checks before collecting owner decisions and production inputs. Raspberry Pi hardware is unavailable, so Batch 6 uses ARM64 emulation and constrained software checks; it does not claim physical-device acceptance.

## Batch 1 — Identify matching release artifacts (Phases 1, 8)

- [x] Embed a deterministic inventory of bundled Python/SQL/requirements/protobuf
  sources, version, project metadata and Docker recipe in each application target.
- [x] Keep configuration, credentials, runtime data and installed packages outside
  this source inventory; retain the separate package inventory.
- [x] Build matching minimal AMD64 and ARM64 artifacts including public relation readiness.
- [x] Retain image identities, source inventories and their comparison.
- [x] Update plan, matrix and phase ledger with evidence and limitations.

Evidence: [paired build record](builds/2026-10-10-batch1/README.md). Batch 1 complete.

Gate: both artifacts contain the same source digest and file hashes. This closes
artifact alignment only; dependency locking, ARM runtime and Pi certification
remain open. Rollback: running services retain their existing image identities;
these new tags are build candidates only.

## Batch 2 — Baseline data and recoverability (Phases 0, 2)

- [x] Map all locally attached legacy storage and inspect external-setting presence without exposing secrets.
- [x] Load isolated Redis/PostgreSQL clones and record aggregate Redis/Metabase state.
- [x] Capture encrypted logical dumps of all legacy databases and globals; compare the development mirror.
- [x] Inventory original persisted broker chunks; recover ClickHouse storage and enumerate all application databases/objects.
- [x] Map all four retained Redis keys to pinned Directus telemetry, collaboration and persistent failed-login state; retain encrypted originals.
- [x] Reconcile ClickHouse database selection and rehearse six schemas twice in the isolated analytics target.
- [x] Correct sensor daily/rate rollups in versioned views and exercise backfill, multi-block inserts and merges against raw aggregates.
- [x] Audit all 11 materialized rollups; add/exercise versioned wallet, Digital Lego and remote-sensing read corrections.
- [x] Harden outbox conflict/lease guards and exercise seven PostgreSQL durability checks with controlled transport.
- [x] Add and exercise atomic outbox replay/disposal audit, identity/reason validation and audit-failure rollback.
- [x] Exercise live sensor JSON delivery and one bounded crash-before-ack replay; v3 raw summary matches PostgreSQL outbox payloads.
- [x] Harden canonical sensor producer identity/unit/atomicity and exercise five live source-to-v3 helper checks.
- [x] Exercise the normal single-reading entrypoint through PostgreSQL events, outbox delivery, raw ClickHouse rows and v3 daily-summary parity in the isolated fixture; retain the read-after-delivery visibility observation ([details](sensor-entrypoint-recovery.md)).
- [x] Trace the first-read delay with sanitized ClickHouse query logs; same-database targeting and disabled async inserts/query cache confirmed, root cause still open ([evidence](builds/2026-10-10-recovery/sensor-e2e-clickhouse-visibility.json)).
- [x] Exercise CSV and authenticated HTTP single/batch entrypoints in the isolated fixture; verify rejection paths, platform events, outbox delivery, raw ClickHouse and v3 aggregate parity ([evidence](builds/2026-10-10-recovery/sensor-csv-http.json)).
- [x] Exercise the HTTP receiver over TCP from a second container on the isolated fixture network; verify health, HMAC rejection, authenticated single/batch writes, duplicate response and URL/payload mismatch ([evidence](builds/2026-10-10-recovery/sensor-http-listener.json)).
- [x] Deliver only the three HTTP listener projections through the live outbox; verify exact sink parity, leave their platform events pending, and restore unrelated outbox availability ([evidence](builds/2026-10-10-recovery/sensor-http-outbox-delivery.json)).
- [x] Reconcile sensor lineage in the retained local legacy snapshots: 15 PostgreSQL source rows, zero outbox rows and zero legacy ClickHouse raw rows; no local re-key or replay needed ([evidence](builds/2026-10-10-recovery/legacy-sensor-lineage.json)).
- [x] Validate the pinned Caddy config and a private localhost TLS/redirect/header/fail-closed smoke; verify the final proxy has no host bindings and its certificate survives container recreation ([scope and result](kernel-proxy.md)).
- [x] Send forged forwarding headers through Caddy; verify the gateway denies an unknown route and the exact audit row records Caddy's peer address ([evidence](builds/2026-10-10-recovery/proxy-forwarded-header-audit.json)).
- [x] Verify host-published loopback HTTP→HTTPS ingress: redirect includes the configured 8448 port and the followed TLS health request returns 200 ([evidence](builds/2026-10-10-recovery/proxy-loopback-ingress.json)).
- [x] Verify a non-default HTTPS port override controls both the Compose loopback binding and Caddy redirect target ([evidence](builds/2026-10-10-recovery/proxy-custom-port.json)).
- [x] Verify gateway CORS preflight accepts one configured localhost origin and rejects an untrusted origin; on an auth-denial response, decorate only the configured origin and retain exact audit evidence ([preflight](builds/2026-10-10-recovery/proxy-cors-preflight.json), [response](builds/2026-10-10-recovery/proxy-cors-auth-response.json)).
- [x] Include the Field Collector's complete custom upload-header set and auth aliases in explicit-origin CORS policy; source-reviewed only, authenticated upload preflight/response runtime acceptance remains open.
- [x] In an isolated current-source ASGI harness, verify local limiter consume/429/`Retry-After`, preflight bypass, CORS on 429, and allowed/denied audit capture in memory ([evidence](builds/2026-10-10-recovery/gateway-rate-limit-isolated.json)).
- [x] Rebuild and promote the local gateway limiter; verify loopback default-policy throttling, `Retry-After`, CORS/preflight behavior, and exact persisted audit rows ([runtime evidence](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json)).
- [x] In a network-isolated container from the promoted image, verify 100 concurrent local checks consume exactly five tokens and that least-recently-used caller eviction and fresh-instance reset semantics hold ([contract evidence](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json)).
- [x] Verify local-provider reset across two OS Python processes in the same network-isolated container: exhaust the default bucket in the first process, then confirm the same identity gets a fresh bucket in the next process ([evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json)).
- [x] Exhaust a synthetic local identity through the active candidate gateway, restart only its app container, confirm it returns healthy and the same identity is allowed again; verify PostgreSQL stayed up and read back exact retained audit counts ([evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json)).
- [x] In the migration-373 portability database, verify full-bucket consumption, retry calculation, distinct-caller isolation, and concurrent shared consumption across two PostgreSQL limiter instances; remove synthetic bucket rows afterward ([evidence](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json)).
- [x] With explicit PostgreSQL provider selection in a network-disabled container, send a source-level ASGI request against a closed local port; confirm no local fallback, 503 with `Retry-After: 30`, generic response text, and one denied-audit callback captured in memory ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-outage.json)).
- [x] Hold a synthetic PostgreSQL limiter row lock and confirm the shared provider fails within its configured two-second lock timeout; delete the synthetic bucket and confirm the table is empty ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json)).
- [x] Run 160 synthetic shared-limiter checks from four separate OS processes against the isolated portability database; verify the refill-aware bound and remove the bucket row ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json)).
- [x] Exercise the real GatewayAudit write path with PostgreSQL unreachable; verify it logs OperationalError, does not interrupt the 503 response, and does not claim a durable audit record ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json)).
- [x] Add a bounded SQLite outage journal with stable event IDs/timestamps, private file permissions, configurable queue bound, and PostgreSQL idempotent replay.
- [x] Exercise the real ASGI denial and replacement-container recovery: queue one event during database outage, restore PostgreSQL, replay once from the startup worker, preserve its timestamp, and drain the journal ([evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json)).
- [x] Verify duplicate event-ID idempotency and bounded-queue rejection in isolated checks; retain only the sanitized evidence.
- [x] Add unified-CLI journal status/integrity, online checkpoint, and no-overwrite restore commands; rebuild the portability app image and invoke status/checkpoint/verify/restore in disposable network-disabled containers with only a private temporary bind fixture ([image evidence](builds/2026-10-11-recovery/gateway-audit-spool-cli-image.json)).
- [x] Rehearse abrupt process exit before and after commit, checkpoint while the source changes, restore to a new private file, and reject overwrite ([evidence](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json)).
- [x] Exercise gateway ASGI middleware concurrently from four OS processes against the shared PostgreSQL limiter; verify the 200/429 split, Retry-After, refill-aware bound, and synthetic bucket cleanup ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json)).
- [x] Send 160 private-network HTTP requests across two separate gateway containers sharing the PostgreSQL limiter; verify 200/429 outcomes, Retry-After, the refill-aware bound, and synthetic bucket cleanup ([evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json)).
- [x] Characterize real GatewayAudit behavior across an isolated PostgreSQL outage and recovery: the outage event is not replayed, a new post-recovery event persists, and the synthetic audit row is removed ([evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json)).
- [x] Exercise cold-start SQLite contention across 12 writer processes, warm concurrent writes, and an online checkpoint while 8 writers remain active; retain only aggregate synthetic evidence ([evidence](builds/2026-10-11-recovery/gateway-audit-spool-contention.json)).
- [x] Add an 80%-of-cap default alert threshold, an absolute override, health/CLI status, and a pre-handler 503 write restriction when the journal is unavailable or at threshold; exercise saturation, unavailable path, observed journal loss, injected ENOSPC, and status-only output ([evidence](builds/2026-10-11-recovery/gateway-audit-spool-write-guard.json)).
- [x] Reserve mutation headroom atomically across 16 local worker processes sharing the SQLite spool, reap an abandoned reservation after forced process exit, and verify ASGI success/error release ordering ([evidence](builds/2026-10-11-recovery/gateway-audit-spool-admission.json)).
- [x] Activate the candidate edge local-media provider and verify a synthetic encrypted object survives an app restart with authenticated plaintext digest, private permissions, zero upload rows, and no database/Metabase recreation ([evidence](builds/2026-10-12-recovery/field-collector-candidate-edge-media-activation.json)).
- [x] Add config-only Compose contracts for minimal, edge, standard, analytics, portability, and optional OIDC profiles; verify resource/media/provider boundaries and retain the explicit ARM64 guard. Eighteen focused Compose/planner checks pass; this does not certify profile runtime or Raspberry Pi hardware.
- [ ] Exercise physical-device/power failure; select external alert routing and production retention ownership. Verify replica failover/scale, non-loopback/public ingress, multi-hop trusted-proxy policy, mobile/upload/auth parity and CORS on successful authenticated/credentialed responses (cookie-authenticated PATCH preflight and edit success now pass in-process; browser/runtime acceptance remains open); expand handler effects/retries and cover operator authorization (all 28 registered OIDC operator method/path policies now have an exact source regression inventory), dashboard parity, external/populated-target lineage and remaining provider ownership.
- [x] Document scoped backup and restore commands, destinations and retention.
- [x] Prepare an isolated recovery deployment and a governed pilot fixture plan.
- [x] Restore the scoped portability PostgreSQL checkpoint and retain aggregate evidence.
- [x] Encrypt all attached stopped legacy volumes and selected configuration.
- [x] Restore all four legacy logical database archives and compare 13 selected populated table fingerprints.
- [x] Prepare bounded local-media checkpoint/restore commands and exact active-work/media fixture specification.
- [x] Prepare isolated fixture deployment and guarded disabled durable-work loader; exercised against the isolated fixture.
- [x] Prepare authenticated synthetic device/media loader with shared target guards; exercised against the isolated fixture.
- [x] Provision synthetic fixture, exercise paired DB/media restore, compare 12 table fingerprints and authenticate both media objects.
- [x] Exercise scheduler expired lease/window recovery and stale completion rejection; retain evidence.
- [x] Exercise synthetic event lease/retry/replay/disposal recovery with controlled handler outcomes.
- [x] Inventory legacy ownership/roles/ACLs and rehearse missing schema grants in the isolated restore.
- [x] Exercise one synthetic sensor anomaly-handler effect and durable-receipt acknowledgement recovery; retain attempt/alert evidence.
- [x] Exercise 16 synthetic `metric_computed` deliveries across four workers; verify single-attempt receipts, target-only cache invalidation and sentinel preservation ([evidence](builds/2026-10-11-recovery/event-handler-concurrency.json)).
- [x] Exercise 16 synthetic `crisp_scored` deliveries across four workers; verify one-attempt receipts, CRISP-only target invalidation and sentinel preservation ([evidence](builds/2026-10-11-recovery/crisp-handler-concurrency.json)).
- [x] Hold one real CRISP handler in flight and confirm a second worker cannot claim that same unexpired event; retain receipt and cache-scope evidence ([evidence](builds/2026-10-11-recovery/same-event-claim-exclusion.json)).
- [x] Exercise one real handler timeout followed by durable same-event retry and successful completion; retain timeout/success log and cache-scope evidence ([evidence](builds/2026-10-11-recovery/same-event-timeout-retry.json)).
- [x] Exercise expired-lease takeover while the first CRISP handler remains blocked; retain the owner-switch snapshot, duplicate-success logs and target/sentinel cache evidence ([evidence](builds/2026-10-11-recovery/same-event-stale-lease-takeover.json)).
- [x] Separate stale-worker lease loss from handler failure in event-worker stats; stale workers no longer schedule retries or make one-shot CLI commands fail, and long-running workers back off when they only lost ownership ([details](event-handler-concurrency.md)).
- [x] Exercise a worker crash after the idempotent CRISP cache effect commits but before its delivery receipt; verify lease reclaim, retry and target/sentinel state ([evidence](builds/2026-10-11-recovery/event-crash-after-side-effect.json)).
- [x] Inventory the five registered/allowlisted handler contracts and classify database, notification and actuation side effects plus replay risks ([details](event-handler-concurrency.md)).
- [x] Create a test-guarded source inventory for all 12 scheduled modules and five allowlisted event-handler pairs, recording source-visible reads/writes, scope, external effects, and idempotency/retry limits. The map matches both executable allowlists and links each entry to source evidence; `services.metrics` records direct read tables for all 20 registered calculators and the data-freshness entry covers all seven fixed source-table mappings. It remains an inventory, not a grant list: other transitive helper/provider effects, existing enabled-task reconciliation, worker-specific identity/context, external schedule state, and populated-data replay guarantees remain open ([map](worker-operation-map.md); [machine contract](worker-operation-map.json); `tests/test_worker_operation_map.py`; [focused check](builds/2026-10-14-recovery/worker-operation-map-check.json)).
- [x] Validate scheduled command token arrays against module-specific operation schemas at graph activation/preflight, `run-now`, job-plan generation, the curated job runner, and worker process creation. Reject unsupported values/options, human-review commands, event cleanup without a retention decision, unbounded event workers, and recurring sensor ingestion without a source; invalid runtime commands do not spawn or retry ([implementation](../../services/security/scheduled_command_contracts.py); [scheduler integration](../../services/scheduler/engine.py); [focused tests](../../tests/test_scheduled_command_contracts.py); [evidence](builds/2026-10-14-recovery/scheduled-command-contract-check.json)). Existing active rows are not automatically rewritten; reconcile them before rollout.
- [x] Implement a PostgreSQL notification outbox for alert/stale-data webhook and Directus sends, with stable event/channel identities, leases, bounded retries and audited dead-letter actions.
- [x] In a fresh internal-only PostgreSQL fixture, exercise notification enqueue idempotency, stable source event-id propagation, retry/backoff, lease recovery, crash-after-fake-send duplicate behavior, provider pause and operator replay/disposal; retain evidence ([record](builds/2026-10-11-recovery/notification-outbox-check.json)).
- [x] Add read-only notification outbox capacity reporting for row counts, oldest open age, and combined relation bytes, with configurable warning/critical thresholds ([policy and operation](notification-outbox-operations.md); [isolated evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json)).
- [ ] Confirm product/jurisdiction retention and archive periods for terminal notification, attempt, and operator-audit records; keep the interim no-prune policy and never prune pending, processing, retryable, or undisposed dead-letter rows.
- [x] Kill the real sensor anomaly event-worker after handler commit but before receipt acknowledgement; verify lease reclaim, attempt-two completion, single-copy effects, and human approval for critical actuation ([design and recovery evidence](sensor-anomaly-delivery.md); [machine record](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json)).
- [x] Implement an opt-in PostgreSQL runtime DML role and verify its bounded privileges, repeatable provisioning, and denial paths in an internal-only scratch database ([policy](runtime-role-policy.md); [machine evidence](builds/2026-10-11-recovery/runtime-role-isolation.json)).
- [x] Rehearse the opt-in role against a fresh populated restore; verify the native public-location read, PostGIS, DML/sequence access, DDL denial and unrelated-database denial ([fixture](../../scripts/fixtures/kernel-db-runtime-role-populated-check.py); [machine evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json)).
- [x] Define and verify separate Directus DML, Metabase metadata-owner, and curated analytics read-only roles against fresh populated restores; exercise owner-run Directus bootstrap and DML-only Directus startup on the isolated network ([policy](optional-database-roles.md); [fixture](../../scripts/fixtures/kernel-optional-db-roles-check.py); [evidence](builds/2026-10-11-recovery/optional-consumer-db-roles.json)).
- [x] Start the pinned Metabase image with its non-superuser role against a separate empty metadata database; confirm first-start migrations and health without configuring a saved source ([startup evidence](builds/2026-10-11-recovery/optional-consumer-startup.json)).
- [x] Inventory Directus permissions, runtime-role boundary, native route surface, hooks, tenant scope and current source-test limits ([source inventory](directus-parity-inventory.md)); this is planning evidence only and makes no live parity claim.
- [ ] Verify Directus API role/field/row and extension-hook parity with its runtime identity using the scoped isolated procedure in the inventory.
  - [x] Run the pinned Directus image against a fresh populated clone: bootstrap and health passed, admin auth returned 200, anonymous collection reads were denied, and the Directus DML role fixture passed. The archived `directus_users` schema has no `location_id` despite permission filters using `$CURRENT_USER.location_id`; synthetic Field Worker reads returned 403 with no rows visible. This confirms fail-closed behavior only, not correct location scope. Identity retries hit `LIMIT_EXCEEDED`; hooks/schedules were not started. The disposable database volume/runtime/network were removed after API cleanup did not complete ([evidence](builds/2026-10-13-recovery/directus-api-parity.json); [inventory](directus-parity-inventory.md)).
- [x] Inventory the restored Metabase source and saved-card references without exposing connection values or SQL: all 39 cards and 22 dashboard placements reference the single sample H2 source; no PostgreSQL/ClickHouse source is configured ([report](metabase-source-inventory.md); [evidence](builds/2026-10-11-recovery/metabase-source-inventory.json)).
- [x] Start the pinned Metabase image against a fresh populated metadata restore with the non-superuser metadata role; verify health 200 and that post-startup counts match the encrypted-archive inventory baseline (39 cards, one dashboard, 22 placements, one user), without executing saved cards ([evidence](builds/2026-10-11-recovery/metabase-populated-startup.json)).
- [x] Inspect saved-card titles, source-table categories, visualization types, and aggregate query features without emitting SQL or executing cards. The only board is a generic e-commerce demo over sample H2; retain it only as an explicitly labeled demo/compatibility fixture and replace it with Kokonut-specific cards for real reporting ([decision](metabase-source-inventory.md); [sanitized evidence](builds/2026-10-11-recovery/metabase-content-inventory.json)).
- [x] Define the initial PostgreSQL-only Metabase reporting contract, source boundary, candidate views, and acceptance/rollback gates ([contract](metabase-reporting-contract.md)).
- [x] Add migration 377 with corrected `kokonut_reporting` views and an empty, lifecycle-governed public metric allowlist; extend the role fixture to exercise actual views with rollback-only synthetic data ([migration](../../schemas/postgres/377_kokonut_reporting_contract.sql); [fixture](../../scripts/fixtures/kernel-optional-db-roles-check.py)).
- [x] Apply all 368 current schema migrations, including 377, to `kokonut_reporting_scratch` via the checksum-tracked runner; verify zero pending migrations and exact role/view behavior, including equal-area farms, unsupported units, farm-specific registry scope, published metric allowlist, and Celo/lifecycle attestation counts ([sanitized evidence](builds/2026-10-11-recovery/kokonut-reporting-contract.json)). This was a clean current-schema scratch DB in a copied recovery volume, not the populated application DB.
- [x] Recover the deployment-era `schema:000_extensions.sql`, restore the active source to its exact archived checksum, and move later extension additions into new migration 378 ([triage](migration-checksum-drift.md); [historical source](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql); [migration](../../schemas/postgres/378_optional_extensions.sql); [evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json)).
- [x] Run a read-only schema-only migration plan against the retained archived clone; verify zero checksum mismatches and record all 25 pending migrations without applying them ([evidence](builds/2026-10-11-recovery/application-migration-checksum-drift.json)).
- [x] Rebuild reporting scratch from the corrected 369-source tree through migration 378; verify zero pending and rerun the actual-view role fixture on a second-generation volume copy ([source-aligned evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json)).
- [x] Make each migration body and its checksum-ledger write one transaction; normalize existing balanced transaction wrappers and reject unsupported nested/unmatched boundaries ([implementation](../../services/migration/cli.py); [focused tests](../../tests/test_migration.py)).
- [x] Replay all 369 current schema sources through the transactional runner on a third-generation disposable clone; verify zero pending and inject a duplicate-table failure that leaves zero probe tables and ledger rows (`0|0`) ([transactional evidence](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json)).
- [x] Run the focused migration suite after the transaction change: 17 passed; statically preflight all 488 schema and seed sources for wrapper compatibility.
- [x] Review all 25 pending migrations in order and apply them through the transactional runner to a separate network-isolated clone; verify zero pending, expected defaults/empty optional tables, and unchanged original-column fingerprints for 16 populated tables. The retained archived clone remains unchanged at 25 pending ([review](pending-migration-compatibility-review.md); [replay evidence](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json); [fingerprints](builds/2026-10-11-recovery/application-migration-review-fingerprints.json)).
- [x] Configure optional Metabase against the reviewed views, build Kokonut-specific cards, and compare card outputs to independent/native reference fixtures before profile promotion. Batch 4e completed source isolation, three first-party cards, populated-fixture output parity, and encrypted metadata restore ([reporting contract](metabase-reporting-contract.md); [card parity](builds/2026-10-11-recovery/metabase-card-output-parity.json); [Batch 4e](batches.md#batch-4e--kokonut-source-registration-and-card-parity-phase-3)). The candidate remains empty and optional; broader analytics and MAN-CAP-007 acceptance remain open.
- [ ] Complete remaining provider recovery, external delivery, and runtime recovery acceptance. The approved eight-suite platform-integrity suite now passes 290 tests on local commit `238e2ef` ([evidence](builds/2026-10-14-recovery/platform-integrity-290-tests.json)); its Gateway tests use a private temporary audit journal on the host. Live provider state, external delivery, and broader runtime recovery remain open.
- [x] Retain and compare a local development mirror (user-selected scope); defer independent R2 production backup to Batch 6.

Preparation evidence: [recovery record](recovery-preparation.md). Batch 2 remains
open; logical provider ownership and remaining recovery evidence are unresolved.

Gate: restore evidence covers schema, domain rows, private media and durable work;
legacy storage remains recoverable. Rollback: use isolated volumes and keep original
backups/volumes; no production cutover in this batch.

## Batch 3 — One complete minimal pilot workflow (Phases 2, 7)

- [x] Map `farm_activity_v1` from Field Collector capture through the proposed
  canonical draft, submission, independent review and publication handoffs;
  record consent-versus-semantic-review boundaries and missing code paths
  ([workflow map](farm-activity-workflow-map.md)).
- [x] Align the farm-activity workflow specification with reasoned rework or
  exception disposition and explicit human publication.
- [x] Add the native private intake queue/detail and explicit OIDC promotion
  route for eligible `farm_activity_v1` captures; create one location-derived,
  idempotent canonical draft with source lineage and operator event evidence.
- [x] Add migration 383 source uniqueness and append-only draft-event guards;
  validate DDL and trigger behavior in a disposable PostgreSQL database.
- [x] Implement governed submit/reject/rework/verify/publish/exception-close
  routes and database lifecycle enforcement, including independent verifier,
  rejection reviewer, and publisher checks ([workflow map](farm-activity-workflow-map.md)).
- [x] Add source-level location-scoped canonical activity list/detail reads and
  same-origin console controls for intake review, explicit draft promotion,
  decision history, and grant-filtered lifecycle actions. Promotion also
  requires the separate farm-activity detail grant and locks all required
  grants through commit ([console contract](kernel-operations-console.md)).
- [x] Run focused migration, route/query, immutable-schema, grant-lock,
  append-only rollback, and console checks for draft editing. The focused
  migration/workflow/lifecycle/OIDC/console suite passes 95 tests plus Ruff;
  all 376 ordered schema migrations applied in disposable PostGIS 16, and a
  synthetic native draft edit verified the content digest, immutable event,
  and rollback after an injected event-write failure ([evidence](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json)).
- [x] After separate rollout authorization, create and restore-test a fresh
  encrypted candidate checkpoint, apply migration 385 through the ordered
  runner, rebuild from `f854d47`, and recreate only the app. The candidate has
  376 applied schemas and zero pending; app health is 200, unauthenticated
  review/farm-activity/draft-edit routes return 401, and PostgreSQL, Metabase,
  and proxy stayed up ([rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json)).
- [x] Implement source-level native editing for draft farm activities against
  the immutable source form schema, with a location-scoped edit grant, required
  correction reason, and append-only content-edit evidence (migration 385);
  do not rely on Directus as the required Kernel path.
- [x] Add the published-only farm-activity summary to the governed farm report
  and include published lifecycle entities in `rework_rate_pct`, with period,
  source-record and reworked-subset provenance. The report snapshot remains
  hashed, unfrozen `draft`; metric values remain unverified drafts ([workflow
  map](farm-activity-workflow-map.md); [source-level evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json)).
- [x] Exercise scoped role/field/row policy and failure paths in focused tests and disposable PostgreSQL. The 91-test Batch 3 suite covers wrong-location query binding/no-write, duplicate retry, and stale eligibility; full-schema PostGIS confirmed a real PostgreSQL workflow-event trigger failure rolls back the activity status and both event ledgers.
- [x] Checkpoint and restore the exact local candidate PostgreSQL database;
  apply migrations 383–384 transactionally; rebuild and recreate only the
  candidate app; verify 375 applied schemas, zero pending, workflow guards,
  health, and anonymous route protection ([rollout evidence](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json)).

Gate: retained end-to-end evidence for the selected CAP rows, with explicit
uncovered domains. This branch checkpoint passes 77 focused migration,
workflow, service, and OIDC tests plus Ruff. Migrations 383–384 compiled and
their draft, submit, verify, reject, rework, publish, exception-close,
independent-actor, revoked-grant, content-immutability, append-only, deferred
draft-evidence, and legacy-row compatibility checks passed in disposable local
PostgreSQL ([evidence](builds/2026-10-12-recovery/farm-activity-lifecycle-isolated.json)).
The separate report/metric slice passes 11 focused tests and Ruff, including
published-only aggregation, private-field exclusion, period boundaries,
snapshot hashing/draft state, metric provenance, and unverified metric storage
([evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json)).
The report/metric integration also passed against the full repository schema:
the migration runner applied all 375 ordered schema migrations (schema-only, no
seeds) to a disposable PostGIS 16 database. Real service functions produced two
published activities and 5.25 hours, excluded a draft and private source marker,
stored a hash-matching unfrozen draft snapshot, and persisted a 50% rework metric
with two source records and `verified=false`. The disposable volume/network were
removed. The earlier expanded Batch 3 suite passed 91 tests and Ruff, including
wrong-location query binding/no-write checks and an injected workflow-event
failure. A second check replayed all 375 schema migrations in disposable
PostGIS 16, then used a real PostgreSQL trigger to reject the submitted
workflow event during the actual transition service call; the activity stayed
`draft`, and neither the workflow-event nor lifecycle-transition ledger
recorded `submitted`. Two simultaneous PostgreSQL promotion calls passed: one
created the draft, the other returned the same activity ID with `created=false`,
and the database retained one canonical row and one `draft_created` event. The earlier local candidate rollout applied migrations 383–384 with an exact-
target encrypted checkpoint and rollback image; OIDC remains disabled. The
canonical queue/detail, console, and migration-385 draft-edit source now pass
focused verification and are deployed to the candidate. Migration 385 has zero
pending schemas, and a fresh encrypted checkpoint restored with matching
migration fingerprints, extension versions, and workflow counts. Only the app
was recreated; PostgreSQL, Metabase, and proxy stayed healthy/running. The
candidate remains empty for farm activities, workflow events, and mobile
collections. Higher-contention stress, configured-provider OIDC, populated
workflow acceptance, and MAN-CAP-001 remain open. See [migration 383–384
rollout](builds/2026-10-12-recovery/candidate-farm-activity-rollout.json) and
[migration 385 rollout](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json).
Migration-385 source acceptance now passes a separate 95-test focused suite plus
Ruff. A fresh disposable PostGIS 16 replay applied 376 ordered schema
migrations, then validated a synthetic draft edit, its digest-backed
append-only event, rejection of event mutation, and transaction rollback after
an injected event-insert failure. The scratch container was removed and the candidate was unchanged during this source check. See [draft-edit evidence](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json).

The separately authorized candidate rollout then restored a fresh encrypted checkpoint into an isolated template0 database and matched migration fingerprints, extensions, and selected workflow counts. Migration 385 applied with zero pending schemas; the app rebuilt from `f854d47` and alone was recreated. Health returned 200 and protected review, activity, and draft-edit routes returned 401 without credentials. PostgreSQL, Metabase, and proxy stayed up; the temporary restore resources were removed. See [candidate rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-draft-edit-rollout.json).

Rollback: the API release can be reverted, but migration 384's native form
guards intentionally remain active and the legacy provider must not be used to
bypass lifecycle decisions for native 1.2.0 rows. Pause intake and use a
compatible transition API or a reviewed forward fix; preserve the additive
index and event evidence.

## Batch 4 — Native orchestration and analytics parity (Phases 3–5)

- [x] Inventory the 15 shared JobSpecs, configured Prefect deployment schedules,
  worker crontab, historical scheduled-task seed, and event-worker ownership;
  document the default single-dispatcher policy, per-job cutover/replay risks,
  and source/runtime evidence limits ([inventory](schedule-ownership-inventory.md)).
- [x] Read the healthy local candidate scheduler state: zero enabled, disabled,
  running, or failing tasks; no Prefect container in this candidate project
  ([evidence](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json)).
- [ ] Reconcile active provider state and accountable owners; resolve each
  operation's cadence/input gaps, idempotency, overlap, and recovery policy;
  transfer jobs one at a time with output parity and rollback evidence. The
  source inventory does not prove Prefect activation or native scheduler state.
- [ ] Close projection, named-query, report and dashboard parity gaps in scoped groups. Batch 4e closed the initial PostgreSQL reporting contract and three first-party cards against copied populated fixtures; the archived Metabase inventory found 39 generic e-commerce cards on sample H2 and no Kokonut PostgreSQL/ClickHouse source. The source map is now recorded, but owner selection, reference fixtures, and acceptance for each retained Kokonut report/dashboard surface remain open ([source inventory](metabase-source-inventory.md); [reporting contract](metabase-reporting-contract.md); [parity inventory](reporting-parity-inventory.md); [card parity](builds/2026-10-11-recovery/metabase-card-output-parity.json)).
- [x] Resolve Kernel Redis/session/cache and limiter requirements: operator sessions and computation cache are PostgreSQL-backed; minimal/edge default to the single-instance local limiter, while standard defaults to shared PostgreSQL limits; any future scale deployment must use a shared provider. Redis remains an optional Directus adapter. Direct and ASGI multi-process plus two-container HTTP shared-consumption checks pass. Production multi-host failover and Directus Redis state transfer/reset remain separate release gates ([boundary](rate-limit-boundary.md); [shared-provider evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json)).
- [x] Inventory report/projection/query source boundaries: three curated BI views/cards; the 94-type draft report-snapshot registry; one typed public analytics query; bounded evidence graph reads; optional ClickHouse rollups; and the legacy `dashboard_dataset.query_sql` runner. The inventory records that the runner executes stored SQL and discards rows after counting, so it is not a replacement reporting store ([inventory](reporting-parity-inventory.md)).
- [x] Keep data-freshness table/timestamp identifiers in fixed source maps, bind location values, and report unsupported configured sources as errors instead of misleading `no_data`; 29 focused source tests pass ([evidence](builds/2026-10-14-recovery/freshness-query-contract-check.json)). This does not establish live provider freshness or runtime database behavior.
- [x] Align the `--worldclim` compatibility path to the existing schema, commit its location-level latitude proxy with all 19 generated values retained as explicit metadata, and add a guarded partial unique key plus plot-specific/location-fallback reads. The migration refuses duplicate location-level rows without changing them; 51 climate/migration tests and 38 worker-map tests pass. Migration 397 passes isolated PostgreSQL 16 acceptance against a synthetic schema fixture; full-bootstrap and candidate rollout remain open ([evidence](builds/2026-10-14-recovery/climate-worldclim-schema-alignment.json)).
- [x] Make the legacy stored-SQL dashboard refresher opt-in and disabled by default; keep read-only dataset listing available. The false-by-default switch reaches candidate, portability, and standard app/worker profiles; 23 focused core and Compose-profile tests pass, as do Ruff and shell syntax checks. Query safety, least-privilege role, and retained-dashboard acceptance remain open ([provider settings](provider-configuration.md); [inventory](reporting-parity-inventory.md)).
- [x] Keep the opt-in stored-SQL refresh off the application connection. A dedicated analytics login is verified at connection time for non-elevated attributes, no role membership, no write grants, no non-system `SECURITY DEFINER` functions, one-database connectivity, and SELECT access only to the three curated reporting views. Queries run in a read-only transaction with search-path and statement/lock limits; only a row count is returned, diagnostics omit saved SQL, and a concurrent query edit blocks stale metadata updates. A fresh disposable PostgreSQL 16 fixture proved the application role can update refresh metadata without view access, while the reader is denied private base-table reads and a data-changing CTE; synthetic data remained unchanged. Focused Python/core checks (30), Compose-profile checks (15), Ruff, Python compilation, and diff checks passed. The feature remains disabled by default; retained external dashboards, unknown SQL, report selection, and tenant scoping stay open ([evidence](builds/2026-10-14-recovery/saved-reporting-reader-disposable.json)).
- [x] Inspect archived dashboard/report metadata in an isolated read-only transaction without returning or executing stored query text. Found 43 datasets, none previously refreshed, zero eligible for the `--all` selector, and three unlocated draft report snapshots; owner labels were counted but not retained ([sanitized evidence](builds/2026-10-13-recovery/reporting-archive-inventory.json)).
- [x] Review direct location lineage for the 38 unlocated dashboard definitions and three unlocated report snapshots on the retained isolated archive clone. No dashboard query/metadata references either known location or confirms Kokonut Network as owner; report location fields/lists do not match either location, and narrative mentions do not establish one owning location. Keep all 41 rows unassigned; no backfill was made ([lineage evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).
- [ ] Have accountable capability owners select retained report types and dashboards, confirm audience/scope and measures, and provide reference fixtures. The source registry is not an ownership or usage inventory.
- [ ] Complete live worker recovery acceptance for leases, retries, idempotency,
  and transport/database outages. The prescribed focused platform-integrity
  suite now passes 290 tests, including scheduler lease ownership/expiry,
  event lease reclaim, stale-worker rejection, idempotent delivery, and bounded
  retry/dead-letter handling ([evidence](builds/2026-10-14-recovery/platform-integrity-290-tests.json)); these are source/unit checks and do not close real-provider outage, worker-process recovery, or long-duration acceptance.

Gate: every migrated flow has durable recovery and output parity evidence.
Rollback: disable new schedules before restoring legacy ownership; avoid dual writers.

### Batch 4a — Crop-cycle NOI snapshot reconciliation (Phases 3–4)

- [x] Verify both migration-354 SAFE deployments, owner lists, thresholds,
  versions, and nonces against read-only Gnosis Chain calls.
- [x] Independently recompute NOI and loss rate on the populated review clone;
  confirm the view formula, identify six stale snapshots, and check duplicate
  crop-cycle keys.
- [x] Add migration 379, align Directus writes, and add the native reconciliation
  CLI plus a disabled daily job.
- [x] Apply migration 379 through the transactional runner and reconcile six
  rows on a separate network-disabled volume copy; verify zero view mismatches.
- [x] Preflight the active candidate: 361 of 370 schema rows were applied, no
  NOI snapshots or duplicate keys existed, and one exact-source checksum
  mismatch blocked the nine pending migrations; see the subsequent resolution.
- [x] Create an encrypted checkpoint of the exact candidate database and
  complete a network-isolated restore with matching ledger and selected table
  counts; retain a same-disk development mirror.
- [x] Apply all 370 current schema sources to a fresh network-disabled scratch
  database; post-run plan reports zero pending.
- [x] Resolve the candidate's two-history checksum mismatch through the
  existing audited repair path for the exact repository-base checksum. Require
  the six verified extension effects before recording the repair; keep all
  unknown checksum mismatches failing closed and do not edit applied SQL.
- [x] Re-run the exact-target plan and apply reviewed migrations 371–379 through
  the transactional runner; confirm zero pending, preserve the audit row, and
  confirm the scheduler reports zero tasks. Do not register/enable the NOI job
  until its owner approves cutover and retry policy.

Evidence: [NOI/SAFE record](noi-snapshot-reconciliation.md) and
[sanitized run output](builds/2026-10-11-recovery/noi-snapshot-parity.json),
[candidate preflight and backup restore](builds/2026-10-11-recovery/candidate-migration-preflight.json),
[audited checksum repair and active-target migration result](builds/2026-10-11-recovery/candidate-migration-apply.json).
Rollback: disable the new schedule and restore affected snapshot rows from the
verified pre-run backup; retain migration 379 unless a reviewed forward
migration removes its index.

### Batch 4b — Populated reporting-view parity (Phase 3)

- [x] Compare each curated reporting view bidirectionally against independently
  written queries over the populated canonical tables on a disposable copy.
- [x] Provision the analytics role's three named view grants on that copy; verify
  it can read those views and is denied on application tables, the private
  publication policy, and DDL.
- [x] Remove the disposable container, copied volume, and temporary manifest;
  retain only aggregate, sanitized evidence.
- [x] Exercise nonempty metric output with a published policy in the
  transaction-rolled-back role fixture; verify value, period, method, and review
  fields. The populated source itself has no published policies.
- [x] Review exact source grants and database ACLs on the active candidate. The
  pre-migration target had only the `kokonut` login/superuser, PUBLIC had CONNECT
  (and TEMPORARY on the application database), and the reporting schema was
  pending. No source role or Metabase connection was provisioned
  ([ACL review](builds/2026-10-11-recovery/candidate-reporting-acl-review.json)).
- [x] Review post-migration database and extension ACLs on the active candidate;
  provision `kokonut_analytics_ro` with one database connection and three named
  view grants; verify actual login, application-table/policy/DDL/temp denials,
  and cross-database denial. Its credential is in SOPS. The role can also read
  eight inherited extension metadata relations and execute 1,165 inherited
  extension functions; none is SECURITY DEFINER, and no unreviewed application
  relation is readable. Metabase remains unconfigured.

Evidence: [populated report-view parity](builds/2026-10-11-recovery/populated-report-view-parity.json).
The farm summary matched 2 rows, the Celo attestation summary matched 1 row,
and both had zero bidirectional differences. The metric view and its independent
query both returned zero because no metric publication policy is published.
The separate rollback-only synthetic role fixture passed the published metric
period/method/review-field probe ([fixture evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json)).
The pre-migration ACL review found no analytics role and default PUBLIC
CONNECT/TEMPORARY exposure. Migrations 371–379 are now applied and the three
reporting views exist. The exact active candidate now has a verified analytics
login and database isolation; its empty source returns zero rows from all three
views. Inherited extension metadata/function access is recorded in the candidate
role evidence. No Metabase source or card is configured.
For the populated parity fixture, no original source rows or candidate grants
were changed; its copied database was discarded after evidence capture. The
subsequent active-candidate role grants and rollback are recorded separately
below and in the candidate role evidence.

Candidate role evidence and rollback notes:
[analytics role record](builds/2026-10-11-recovery/candidate-analytics-role.json).
Rollback can disable the login and revoke its explicit reporting grants. The
instance-wide PUBLIC CONNECT hardening is retained unless an operator reviews
the exact pre-change ACL for every database in this dedicated candidate.

### Batch 4c — Active candidate image and schema alignment (Phases 2, 7, 8)

- [x] Preserve the prior candidate app image under a dated rollback tag.
- [x] Build the current Kernel target and compare every embedded source hash to
  the checkout: 1,293 of 1,293 bundled files match; 11 optional/development
  inputs are intentionally absent from this image.
- [x] Refresh the candidate app after adding the analytics-role bootstrap
  module, preserving both the pre-role and original pre-refactor images.
- [x] Recreate only the app container; preserve the existing candidate database
  container, PostgreSQL volume and the stopped legacy stack.
- [x] Confirm app/database health, loopback health endpoint, zero pending schema
  migrations, and zero scheduled tasks.
- [x] Record the newly created empty gateway-audit spool volume; no migrations,
  roles, grants or Metabase configuration changed in this batch.

Evidence: [candidate app rebuild](builds/2026-10-11-recovery/candidate-app-rebuild.json)
and [active candidate migrations](builds/2026-10-11-recovery/candidate-migration-apply.json).
Capability acceptance counts do not change. Runtime/API parity, analytics role
isolation, ARM64 and Raspberry Pi certification remain open. Rollback: retag
`kokonut-kernel-candidate-app:pre-analytics-role-20261011` as `latest` and
force-recreate only the app with the candidate Compose file; leave the database
volume intact. The earlier `pre-refactor-20261011` image remains available too.

### Batch 4d — Optional Metabase profile and metadata isolation (Phase 3)

- [x] Add a candidate-only `analytics` Compose overlay with Metabase pinned,
  loopback-only access, private database networking, sharing disabled, and a
  bounded JVM heap; keep it absent from the default candidate profile.
- [x] Add an explicit one-shot metadata-role bootstrap that creates a separate
  metadata database/login and rejects inherited PUBLIC database access.
- [x] Run the metadata bootstrap and verify the real login can create metadata
  objects inside its own database, with the create probe rolled back, while
  connection to the application database is denied.
- [x] Start Metabase under the opt-in profile and record HTTP/Docker health;
  confirm the candidate database remains unexposed on host ports and the
  default candidate manifest lists only `database` and `app`.
- [x] Preserve the previous candidate image as
  `pre-metabase-role-20261011`, rebuild after adding the bootstrap module, and
  verify all 1,294 bundled source hashes match the checkout; retain the 11
  expected protobuf/optional-dependency omissions.
- [x] Recreate only the app container. Verify app/Metabase HTTP health `200`,
  PostgreSQL container and volume unchanged, no database port published, and
  the legacy stack still stopped.

Gate: the metadata identity owns only Metabase metadata, and Metabase remains
stopped unless the `analytics` profile is selected. Source registration and
Kokonut report cards are a separate parity batch. Rollback: stop/remove only the
Metabase service; retain the PostgreSQL volume and metadata database until the
rollback window closes. **Batch 4d complete.** See [profile contract](metabase-kernel-profile.md)
and [runtime evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json),
plus the [current app image record](builds/2026-10-11-recovery/candidate-app-rebuild.json).

### Batch 4e — Kokonut source registration and card parity (Phase 3)

- [x] Complete local Metabase first-run setup with a generated administrator credential stored in SOPS; keep the generic H2 demo clearly separate.
- [x] Register `kokonut_intelligence` through `kokonut_analytics_ro` with an inclusion filter for `kokonut_reporting`; verify that Metabase lists only the three approved views.
- [x] Build first-party farm-summary, verified-metric, and Celo-attestation cards in a Kokonut collection and add them to a reporting dashboard.
- [x] Execute every saved card and compare empty-candidate row counts with direct PostgreSQL counts; all three return zero because the candidate has no pilot rows.
- [x] Compare exact exported card SQL outputs with independent base-table SQL on a copied populated fixture: farm summary (2 rows), Celo attestations (1 row), and a synthetic verified metric (visible only after its policy was published; unverified value excluded). In-window and out-of-window date checks matched. The temporary Metabase source and all scratch resources were removed ([parity evidence](builds/2026-10-11-recovery/metabase-card-output-parity.json)).
- [x] Retain sanitized source/card evidence and a credential-free card export ([export](metabase/kokonut-reporting-cards.json); [runtime evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json)).
- [x] Stream a fresh encrypted metadata backup into the ignored local `backups/` directory and verify decryption plus PostgreSQL archive listing; the Metabase encryption key remains in `.env.sops` ([backup manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json)).
- [x] Restore the current metadata archive into a separate, network-disabled disposable PostGIS 16 database with `pg_restore --no-owner --no-privileges --exit-on-error`; compare source, card, dashboard, placement, virtual-tile, and user counts against the live candidate, then remove the target. Counts matched exactly and the source metadata database was unchanged ([backup manifest](builds/2026-10-11-recovery/candidate-metabase-backup.json)).

Gate: source access satisfies the reviewed data boundary and every promoted
card matches independent reference results. Source isolation, card output
parity, and full metadata restore are confirmed. The active candidate remains
empty, so live card results there are zero until pilot data is added. Rollback: remove the source/cards from
Metabase and stop the optional profile; preserve the canonical database and
reporting views.

## Batch 5 — Optional transports and application access (Phases 6, 7)

- [x] Define the private HTTP sensor profile, request size/signature/failure behavior, rollback, and the distinction between receiver-fixture evidence and overlay acceptance ([contract](http-sensor-overlay.md)).
- [x] Define the opt-in MQTT broker/subscriber trust, credential, QoS 1 recovery, readiness, storage, and rollback contract; reconcile migration/image status ([contract](mqtt-overlay.md)).
- [x] Define the private gRPC profile's network, TLS, API-key, database-role, health, sizing, and rollback boundaries ([contract](grpc-overlay.md)).
- [x] Define the Caddy proxy's default exposure, route ownership, TLS trust, forwarded-header behavior, health boundary, and rollback ([contract](kernel-proxy.md)).
- [x] Map the existing device/location/media boundary and document the consent, form-validation, and tenant gaps ([contract](mobile-access-contract.md)).
- [x] Protect consent, Field Collector, private-media, and governed farm-activity tables from the generic soft-delete sweeper; define the restricted-pending-disposition baseline and record the remaining erasure limitations ([policy](mobile-retention-disposition.md)).
- [x] Add an OIDC location-granted, read-only disposition inventory for collection fields/attachments, media counts, canonical activity statuses, and review/workflow event counts; the route exposes no payload or participant IDs and does not execute a disposition ([policy](mobile-retention-disposition.md)).
- [x] Run focused service/query, dual-grant authorization, and console acceptance for the read-only disposition inventory (49 focused operator auth/review/console tests passed; Ruff clean); keep reports, external exports, on-chain references, and backup lineage explicitly uncovered until reconciled ([policy and boundary](mobile-retention-disposition.md)).
- [x] Inspect mobile enrollment, collection, forms, media, and append-only consent paths; draft the additive participant-link, consent, and immutable-form-version enforcement proposal ([contract](mobile-access-contract.md)).
- [x] Approve the collector/participant identity boundary, reviewer-controlled location link, consent source/check timing, withdrawal gate, and immutable/stale form handling baseline.
- [x] Implement migration 381 source, versioned form reads/sync validation, reviewer link create/revoke routes, opaque-ref UI capture, and the downstream eligibility view ([contract](mobile-access-contract.md)).
- [x] Close the stale required-form consent bypass: retired revisions remain private-review-only and now require the same unrevoked participant link and exact consent checks before media upload and sync ([contract](mobile-access-contract.md)).
- [x] Add same-origin OIDC console routes for location-scoped Field Collector enrollment and revocation; enrollment requires `mobile_device:enroll`, revocation requires `mobile_device:revoke`, unsafe requests require CSRF, and one-time codes return with `Cache-Control: no-store` ([console contract](kernel-operations-console.md)). Source route/auth coverage: 5 tests passed within 56 focused checks; provider and browser acceptance remain open.
- [x] Audit every `offline_collection` source reference; document the legacy CLI as transport-only and require future business/reporting consumers to read the eligibility view ([contract](mobile-access-contract.md), [field data guide](../field-data-collection-guide.md), [mobile README](../../services/mobile/README.md)).
- [x] Decide that custom form authoring must not depend on Directus and that retired/review-required records need a private location-scoped queue; preserve immutable revisions and the consent eligibility hard gate ([decision](mobile-form-operations.md)).
- [x] Add offline manifest validation and version-aware preview to the unified CLI; reject incomplete review evidence, open schemas, remote references, and same-version content changes. Twenty-one focused form/CLI checks and 10 governance checks passed in the validation batch ([contract](mobile-form-operations.md); [CLI](../../services/mobile/forms_cli.py)).
- [x] Add publish preview plus explicit transactional `--apply` through `mobile_form`; require a publisher distinct from the reviewer and an expected-current-version/absence assertion. Twenty-nine focused form/schema checks pass with a fake transaction adapter; Ruff and `git diff --check` pass.
- [x] Keep database setup and Baal client loading lazy so the unified CLI command tree and offline form validation run without decrypting database credentials.
- [x] Verify publication through the migration 381 snapshot trigger against a separate disposable PostGIS fixture: snapshot actor, active-to-retired transition, duplicate/stale/location rejection, transaction rollback, and immutable history all passed ([evidence](builds/2026-10-12-recovery/mobile-form-publication-transaction.json)). This applied the publication-trigger prefix only; full migration and candidate acceptance remain separate.
- [x] Implement the OIDC-scoped read-only Field Collector queue and console detail view; list and payload detail use separate location grants, SQL repeats grant/eligibility checks, and the UI exposes no identity or media downloads. Thirteen focused queue/auth checks pass; Ruff and JavaScript syntax checks pass ([contract](mobile-form-operations.md); [console contract](kernel-operations-console.md)).
- [x] Add append-only reviewer-note events without overriding consent eligibility or publishing records. The `review` grant also requires `read_detail`; migration 382 enforces current review eligibility, evidence shape, operator/location attribution, and append-only storage. Twenty-two focused route/query/auth tests and isolated PostGIS migration and service-function assertions pass, including cross-location and revoked-grant denial ([contract](mobile-form-operations.md); [evidence](builds/2026-10-12-recovery/mobile-review-event-migration-isolated.json)).
- [x] Replay all 373 ordered schema migrations through 382 with the repository runner against a clean no-volume PostGIS 16 database; verify zero failures, zero pending migrations, the review-event table and its two triggers, then remove the fixture ([evidence](builds/2026-10-12-recovery/mobile-review-event-ordered-migration-run.json)). The candidate stack was not targeted by this clean replay; its separate rollout is recorded below.
- [x] Restore the current candidate checkpoint into an isolated template0 database and compare 372 migration fingerprints, extensions, and selected mobile/operator counts; apply only migration 382 through the checksummed runner, rebuild/recreate only the candidate app, and verify zero pending, table/triggers, zero review events, health, disabled OIDC login, and protected anonymous queue access ([evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json)). The encrypted checkpoint remains; the restore fixture was removed.
- [x] Run source-level mobile API, media/storage, offline transport, and Gateway CORS checks (51 mobile tests and 4 CORS tests passed); cover all 14 browser request headers and retired required-form upload/sync behavior ([progress](progress.md#batch-5-field-collector-mobile-and-cors-source-acceptance--11-october-2026)).
- [x] Prepare a source-grounded reviewer worksheet for all five current form revisions; record source fields and leave policy decisions pending ([worksheet](mobile-form-classification-review.md)).
- [x] Record owner-delegated policy decisions for all five built-in operational forms as `not_required`, with explicit location scope, category, purpose, recipient, evidence, minimization guidance, and immutable `1.1.0` source revisions ([decision record](mobile-form-classification-review.md)).
- [x] Add the `140_mobile_forms.sql` seed after the ordered migration step and align the offline browser fallback with the same policy and form revisions.
- [x] Validate new sync payloads against the exact immutable form revision schema, reject undeclared fields in the five built-in `1.2.0` schemas, prevent remote `$ref` fetching, and return non-echoing validation errors ([validator](../../services/mobile/form_validation.py)). Focused mobile/schema acceptance: 60 passed; dependency groups and Ruff checks pass.
- [x] Disable legacy direct device registration in `services.analytics.mobile_offline`; direct inserts could bypass owner-issued, single-use enrollment. The guard fails before opening a cursor or committing. Focused checks passed: 16 offline service tests and 50 mobile API/form-validation tests; Ruff and Python syntax checks are clean. Legacy queue/sync remains transport-only and unassessed; this does not close MAN-CAP-053.
- [x] Retire the remaining `services.analytics.mobile_offline` query/write helpers and CLI commands because they had no authenticated tenant identity and no in-repository runtime callers. Every helper now fails before SQL, and every historic command fails before opening a database connection. Enrollment, collection, and sync continue through the consent-aware Field Collector. Focused mobile/API/form tests passed (67 tests plus five CLI subtests), Ruff, compilation, and diff checks passed ([evidence](builds/2026-10-14-recovery/legacy-mobile-cli-tenant-boundary.json)). Operator device inventory/global queue statistics still need a scoped surface; no candidate or legacy database was touched.
- [x] Checkpoint the `1.1.0` candidate, restore it into a fresh template0-derived database, compare 372 migration fingerprints plus extensions/schemas, seed immutable `1.2.0` revisions, rebuild only the app, and verify health and public/auth-denial endpoints ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)).
- [x] Exercise the current app's sync route over HTTP against an isolated checkpoint clone: an unknown field returned 422 with no value echo or stored row, and a valid `1.2.0` payload was accepted; remove the synthetic device/location/collection fixture afterward ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)).
- [x] Exercise scoped enrollment through device registration, authenticated retrieval of five active `1.2.0` forms, and one valid field-note sync over loopback HTTP against the restored clone. Verify that identity/location come from the enrollment, synced data remains `transport_pending` and ineligible, then remove synthetic rows and stop/detach the recovery database ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)).
- [x] Exercise private JPEG upload through the encrypted local adapter and sync attachment against the restored clone: verify authenticated `KKM1` ciphertext at mode `0600`, plaintext absence, wrong-key rejection, and `head_private` metadata parity; remove synthetic rows/files and stop/detach the recovery database ([media contract](local-private-media.md); [rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)).
- [x] Rehearse the local-media age-encrypted checkpoint/restore scripts with one synthetic KKM1 object; verify the restored object authenticates with the separate temporary media key, its plaintext digest matches, a wrong key fails, and the manifest binds a synthetic database-checkpoint hash. This initial run used a temporary age identity; production media-key custody/recovery and database upload-row parity remain unverified ([evidence](builds/2026-10-12-recovery/field-collector-media-backup-restore.json)).
- [x] Repeat the synthetic checkpoint/restore with the archive recipient derived from the user-provided SOPS age identity; restore with that identity, verify the KKM1 object and wrong-media-key rejection, and remove every temporary file. This confirms age identity access for the archive only; no `.env.sops` value, production media key, database, or upload row was read ([evidence](builds/2026-10-12-recovery/field-collector-media-sops-age-restore.json)).
- [x] With owner approval, provision a random 32-byte `MOBILE_MEDIA_LOCAL_KEY` through SOPS stdin, verify targeted readback without emitting the value, then rehearse one-object KKM1 backup/restore using that exact key and the supplied age identity; remove all synthetic fixtures ([evidence](builds/2026-10-12-recovery/field-collector-media-sops-key-provisioning.json)).
- [x] Exercise the edge Compose overlay media volume using the SOPS-managed key: write a synthetic KKM1 object in one disposable app container, authenticate and delete it from a second, verify private modes/plaintext absence/wrong-key rejection, and remove only the unique test project resources ([evidence](builds/2026-10-12-recovery/field-collector-edge-media-volume-recovery.json)).
- [x] Apply migration 358 in a disposable PostGIS project, create one synthetic `mobile_media_upload` row and edge-volume object, compare key/type/size/SHA-256, authenticate/decrypt the object, reject a wrong key, and remove all fixture rows and project resources ([evidence](builds/2026-10-12-recovery/field-collector-media-db-object-parity.json)).
- [x] Add the dry-run-default bounded expiry CLI: delete only registered, expired, unattached upload objects, then mark rows expired under a row lock; keep attached uploads and unregistered objects out of automatic cleanup ([contract](local-private-media.md)).
- [x] Verify expiry cleanup against disposable PostGIS and local media: dry-run count, one-row apply limit, next-batch apply, repeat no-op, and preservation of expired attached plus unexpired uploads ([evidence](builds/2026-10-12-recovery/field-collector-media-expiry-cleanup.json); 44 mobile/media/API/CLI tests and standard/security Ruff pass).
- [x] Add provider-neutral private-media inventory and dry-run-default orphan reconciliation; enforce a 24-hour minimum age, 500-object maximum batch, registration recheck, and sanitized reports. Thirty-one focused tests passed; candidate dry-run found zero objects; an isolated local apply deleted one aged synthetic object and preserved the younger object. Live S3/R2 acceptance remains open ([candidate evidence](builds/2026-10-12-recovery/field-collector-media-orphan-reconcile.json); [isolated apply evidence](builds/2026-10-12-recovery/field-collector-media-orphan-apply-isolated.json)).
- [x] Replace deprecated Gateway startup/shutdown event hooks with FastAPI lifespan management, verify replay-worker cancellation, use Starlette's `httpx2` TestClient backend, and refresh the route fixtures to the analytics contract (68 focused tests passed with zero warnings; standard Ruff and dependency-group alignment pass; [ledger](progress.md#batch-5-gateway-lifespan-deprecation-cleanup--12-october-2026)).
- [x] Start two disposable full Kernel runtime containers on the candidate network with an isolated edge-media volume; verify both health checks and encrypted-object recovery after replacement, then remove the synthetic object, containers, and volume without changing candidate services ([evidence](builds/2026-10-12-recovery/field-collector-media-runtime-volume-recreation.json)).
- [x] Add a secure-origin offline shell for `/mobile`, `/api/mobile/app`, and the Caddy `/field/` route. Cache only static app HTML and the vault helper; keep forms, sync, media, and other API traffic network-only. Verify route exposure and offline navigation with focused Python and dependency-free Node checks ([mobile README](../../services/mobile/README.md); [access contract](mobile-access-contract.md)).
- [x] Resolve PR #68's service-worker proxy finding: make `/mobile/` canonical and redirect `/mobile` there so the app, vault helper, and worker use paths forwarded by the existing proxy rule; all 33 mobile API tests and both offline-shell Node checks pass, and the candidate app-only recreation serves the redirect and worker asset ([evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json); [progress](progress.md#batch-5-field-collector-proxy-route-correction--12-october-2026)).
- [x] Run the local candidate Caddy ingress acceptance without dependencies: verify HTTP-to-HTTPS and `/mobile` canonical redirects, shell and service-worker delivery, health, and security headers while keeping app/database/Metabase healthy; external Traefik/public ingress remains open ([evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json); [progress](progress.md#batch-5-candidate-caddy-field-collector-proxy-acceptance--12-october-2026)).
- [ ] Complete browser acceptance through the candidate Caddy HTTPS origin after the repository owner trusts the local development certificate; the isolated tab returned `ERR_CERT_AUTHORITY_INVALID`, and the browser security interstitial was not bypassed ([evidence](builds/2026-10-12-recovery/field-collector-proxy-route.json)).
- [x] Exercise real-browser shell launch, encrypted capture, persistence across reload, and reconnect/sync using a temporary same-origin mock with its server stopped and restarted; remove the mock's browser cache, worker and vault afterward ([browser evidence](builds/2026-10-12-recovery/field-collector-browser-offline-reconnect.json)).
- [x] Run the online Field Collector browser against the candidate Gateway after the pending-badge fix: save two synthetic valid notes, confirm both receive successful sync receipts, and verify the home badge clears automatically without manual sync or navigation; remove the synthetic candidate location, device, enrollment, notes, and sync logs ([live browser evidence](builds/2026-10-12-recovery/field-collector-browser-candidate-gateway.json)).
- [x] Add an explicit-confirmation local vault delete/reset action for locked browsers, including IndexedDB deletion, legacy-key cleanup, blocked-delete status, cross-tab locking, and a warning that server enrollment requires separate revocation. Nine focused vault checks pass; the candidate browser exposes the control and its destructive action was not invoked ([progress](progress.md#batch-5-field-collector-local-vault-reset-control--12-october-2026); [evidence](builds/2026-10-12-recovery/field-collector-vault-reset-control.json)).
- [x] Add regression coverage that rejects a retired required-consent photo before private storage after withdrawal and rejects retired-record sync after withdrawal even when a later grant exists; the four focused mobile suites pass 62 tests ([evidence](builds/2026-10-12-recovery/field-collector-withdrawal-source-tests.json)).
- [x] Verify `v_mobile_collection_use_eligibility` in the running candidate PostgreSQL using rollback-only synthetic fixtures: an active grant is eligible, while a post-collection withdrawal remains disqualifying after a later grant; verify no fixture rows remain ([evidence](builds/2026-10-12-recovery/field-collector-postgres-consent-eligibility.json)).
- [x] Invoke the real sync handler against a disposable clone of the candidate database: verify 403 on a collection with a post-collection withdrawal despite a later grant, and no collection or success-log write; remove the clone and dump ([evidence](builds/2026-10-12-recovery/field-collector-postgres-sync-withdrawal.json)).
- [x] Send a real loopback HTTP request through the Gateway ASGI app and `/api/mobile/sync` using an isolated PostgreSQL clone; verify 403 after post-collection withdrawal despite a later grant, zero collection/upload-log writes, and unchanged audit spool; drop the clone and dump ([evidence](builds/2026-10-12-recovery/field-collector-gateway-http-consent-withdrawal.json)).
- [x] Exercise retired required-consent withdrawal/regrant through a real Gateway ASGI/HTTP request using a synthetic reviewed retired revision in an isolated clone; verify 403 and no collection or upload-success log. Seeded retired `1.1.0` revisions are `not_required`, so they were not used for this policy branch ([evidence](builds/2026-10-12-recovery/field-collector-retired-form-gateway-http-consent-withdrawal.json)).
- [x] Rerun the six focused Python suites (83 passed) and the two Node offline-shell/vault suites (11 passed) with a private temporary audit spool ([evidence](builds/2026-10-12-recovery/field-collector-consent-source-regressions.json)).
- [x] Complete the synthetic retired required-consent browser client case: native minlength validation blocked a 19-character participant reference; a valid synthetic reference stayed in the encrypted local queue after the mock returned 403. The isolated test vault retains one synthetic pending record; the mock server is stopped ([evidence](builds/2026-10-12-recovery/field-collector-consent-source-regressions.json)).
- [ ] Configure and accept a real OIDC provider, login/session, operator grant provisioning, CSRF, and browser console enrollment/revocation. Source route/auth checks pass; `.env.example` lists encrypted-provider inputs, the Compose contract test confirms OIDC stays opt-in and refuses missing settings, and the profile planner prints OIDC only with HTTPS proxy selection. Eighteen focused Compose/planner tests pass across the deployment profiles. No real provider credentials were configured; browser acceptance remains open. The synthetic API-key enrollment route is covered by the isolated end-to-end check.
- [x] Define the interim human retention/disposition baseline: restricted pending review, no automatic purge without accountable jurisdiction-aware ownership, and dual-control before destructive execution ([policy](mobile-retention-disposition.md)).
- [x] Document the tenant/RLS target from the current schema: organization is the tenant, location is operational scope, organization/location relationships do not grant users access, and unmapped ownership fails closed ([contract](mobile-tenant-isolation.md)).
- [x] Add a read-only ownership and known-lineage preflight CLI; emit opaque
  location/organization references and distinguish relationship-row counts
  from distinct organizations ([command](../../services/mobile/tenant_preflight.py)).
  Candidate execution evidence is recorded below.
- [x] Run the read-only preflight against the local candidate and record the
  sanitized result ([evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight.json)).
  It returned zero locations and zero inventoried rows; the candidate is empty.
- [x] Gate inventory SQL on required relation/column availability and report
  incomplete schema plus latest applied migration without running row counts.
- [x] Exercise the schema-incomplete response against a fresh isolated restore
  of the populated archived snapshot. It reported two locations and 376
  migration-history rows in a separate aggregate check, identified 11 missing
  inventory columns, and skipped ownership/lineage counts ([evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-gate.json)).
- [x] Run the same source against the current candidate's complete schema. It
  reported all 27 required columns, migration 385, and zero rows; the candidate
  is empty ([evidence](builds/2026-10-13-recovery/field-collector-tenant-preflight-schema-complete.json)).
- [x] Restore the populated archive into a fresh internal-only copy, apply the
  32 pending ordered schemas through migration 385, and verify zero pending
  migrations. The transactional runner reported no checksum drift or failures.
- [x] Run the complete read-only preflight on that migrated copy: 27/27 schema
  requirements, two locations, four mobile devices, and five location-scoped
  dashboard datasets. It found one direct owner assignment without a confirming
  active relationship, one unassigned location, three unlocated report
  snapshots, and 38 unlocated dashboard datasets ([evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json)).
- The archive contains **Kokonut Adelphi** (`a0000000-0000-0000-0000-000000000001`) and **Kokonut Genesis** (`a0000000-0000-0000-0000-000000000002`). Adelphi was assigned to the legacy Kokonut Adelphi organization (`a0000000-0000-0000-0000-000000000700`); Genesis was unassigned. The repository owner confirmed both are owned exclusively by Kokonut Network.
- [x] Record the owner decision and implement the scoped mapping in migration
  `387_kokonut_network_tenant_ownership.sql`; preserve the legacy Adelphi org
  record, and add `120_kokonut_network_ownership.sql` after Genesis is seeded.
- [x] Review direct location lineage for the three unlocated report snapshots
  and 38 unlocated dashboard definitions. No source-grounded mapping was found;
  keep all 41 unassigned ([evidence](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).
- [x] Run migration/seed acceptance on a network-disabled disposable
  PostgreSQL 16 fixture, including idempotency, wrong-owner refusal/transaction
  rollback, legacy member deactivation, and fresh pilot-seed ordering
  ([evidence](builds/2026-10-13-recovery/tenant-ownership-disposable-acceptance.json)).
- [x] Add the tenant-aware grant foundation in migration 388: explicit owner
  verification, server-managed operator organization membership, revocable
  location sharing, and tenant-qualified resource/action grants. CLI and
  application/query authorization paths enforce the shared predicate. Legacy
  NULL-tenant location grants remain compatible and are not backfilled.
- [x] Add migration 389 trigger guards so Field Collector draft creation,
  edits, and lifecycle events also recheck the shared tenant-aware predicate;
  legacy NULL-tenant grants retain their compatibility path.
- [x] Run a network-disabled disposable PostgreSQL 16 acceptance of the actual
  ordered migrations 387–389, then replay 388–389 for idempotency. Owner,
  partner/share, legacy NULL-tenant, revoked/expired/inactive, unverified and
  stale-owner cases passed; the 389 draft insert/edit and workflow triggers
  passed positive and denial cases ([evidence](builds/2026-10-13-recovery/tenant-grants-migrations-disposable.json)).
- [x] Exercise the operator CLI membership/share lifecycle and legacy-grant
  conversion against disposable PostgreSQL migrations 387–389
  ([evidence](builds/2026-10-13-recovery/tenant-grants-cli-disposable.json)).
  Ruff and Python syntax checks pass.
- [x] Replay the full ordered schema after migrations 387–389. All 380 source
  migrations validated and applied with zero pending or failed; migrations
  384, 385, and 389 coexist with 11 registered activity/workflow triggers.
  Candidate database and app remained healthy and untouched; the disposable
  database, internal network, and volume were removed
  ([evidence](builds/2026-10-13-recovery/tenant-grants-full-schema-replay.json)).
  This was a clean-schema replay, not a populated/archive or pilot-seed replay.
- [x] Define and implement migration 390's audited two-party location tenant
  transfer request/accept/cancel workflow and local operator CLI. Acceptance
  revokes existing shares and all active location grants, including legacy
  NULL-tenant grants; see the [transfer contract](tenant-owner-transfer-contract.md).
- [x] Run focused disposable PostgreSQL acceptance for transfer request,
  independent approval, stale/conflicting owner rejection, atomic owner-link
  change, all-grant/share revocation, cancellation, replay, and rollback.
  Fourteen CLI/SQL/context checks passed against actual migrations 387–390 on
  synthetic PostgreSQL 16; eight focused context unit checks also passed. The
  candidate and legacy databases were untouched by the acceptance run, and
  its temporary database, bridge, and source copy were removed
  ([evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
- [x] Roll out migrations 387–390 to the local candidate after a fresh
  age-encrypted checkpoint; the archive authentication and PostgreSQL listing
  passed, 381 schemas are applied with zero pending, and 120 seed files remain
  pending in the migration ledger. Five mobile-form rows and ten revision rows
  already exist without applied seed history and need reconciliation before any
  seed rollout. Only the candidate app was rebuilt/recreated;
  app/database/Metabase health and anonymous 401 responses on both protected
  routes passed ([rollout evidence](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json)).
- [x] Integrate transaction-local tenant context into the Gateway's report
  review queue/detail read transactions. The helper validates a tenant-qualified
  location grant on the same connection as the protected query; location-only
  legacy grants receive 403 on these routes. Route-specific verification is
  complete: 17 disposable PostgreSQL checks passed across migrations 387–390,
  including owner/shared reads, same-transaction context, legacy denial, and
  context cleanup; two focused Gateway HTTP denial checks passed. See
  [acceptance evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json).
  This narrow integration does not enable RLS.
- [x] Extend same-transaction context to the Field Collector collection list
  and detail reads. Actual migrations 387–390 passed 22 synthetic disposable
  PostgreSQL checks, including owner queue access, explicitly shared detail
  access, context-before-query on the same connection, rollback cleanup, and
  legacy-grant denial before collection reads. Twenty-four focused tenant
  context/mobile service checks and seven route checks passed, including HTTP
  403 behavior; Ruff and syntax checks pass. Candidate and legacy databases
  were untouched
  ([evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
- [x] Bind the two-grant Field Collector disposition inventory to one tenant
  context. Both `mobile_collection_retention:inventory` and
  `mobile_collection_review:read` must resolve to the same tenant; individually
  valid grants from different tenants fail closed and the route returns 403.
  Disposable PostgreSQL acceptance passed same-tenant and cross-tenant cases;
  24 tenant-context/mobile service checks and seven focused route checks passed
  with Ruff clean. This does not complete retention or erasure disposition
  ([contract](mobile-tenant-isolation.md),
  [evidence](builds/2026-10-14-recovery/tenant-owner-transfer-context-disposable.json)).
- [x] Bind append-only Field Collector reviewer-note writes to one tenant using
  both `mobile_collection_review:review` and
  `mobile_collection_review:read_detail` before the INSERT. Context is set on
  the same transaction/connection, and cross-tenant denial maps to HTTP 403.
  Fourteen mobile-review service tests, eleven tenant-context tests, and three
  focused auth-route tests pass. The service tests confirm tenant denial rolls
  back and closes the transaction before any INSERT; the route test returns
  HTTP 403 for cross-tenant denial. Ruff and `git diff --check` pass. Candidate
  and legacy databases were untouched.
- [x] Verify tenant-aware Field Collector farm-activity intake and canonical
  activity read/write paths. The workflow service suite passed 10 tests, the
  lifecycle suite passed 31, and 26 focused OIDC/auth route tests passed,
  including all seven HTTP 403 tenant-context denial paths. Service assertions
  confirm context precedes queries/writes on the same connection and that detail
  grants are included in the same-tenant context. Ruff, syntax, and diff checks
  pass; no database was accessed.
- [x] Bind the OIDC mobile-device enrollment and revocation routes to tenant
  context inside their PostgreSQL write transaction. Ten focused
  operator-route tests and the public enrollment authorization test pass; Ruff
  and syntax checks pass. No database was accessed.
- [x] Carry Gateway authorization into capability/API-key mobile-device
  enrollment and revocation writes. Middleware marks the exact authorized
  resource/action/location; the handler checks that marker, then the same
  transaction locks and validates the current verified owner before writing.
  Enrollment, enrollment revoke, and device revoke all fail closed on context
  denial. The helper documents that this is application scope, not a
  database-verifiable identity for RLS. The tenant-context, mobile API, and
  operator-auth suites pass (126 tests); Ruff and Python compilation pass.
  Candidate and legacy databases were not accessed
  ([source evidence](builds/2026-10-14-recovery/gateway-mobile-tenant-context.json)).
- [x] Pin new mobile enrollment codes and devices to the verified owner and
  require device-token forms, media uploads, sync, and sync-status to validate
  that binding in-transaction. Migration 391 leaves legacy device/enrollment
  tenant IDs NULL instead of inferring ownership. Owner transfer serializes
  against protected device transactions; old devices then receive a specific
  re-enrollment denial. The browser preserves and quarantines its encrypted
  queue for review, and will not upload those records under a replacement
  device identity. The focused Python suite passed 67 checks; two offline-shell
  Node checks passed; Ruff, Python syntax, dependency-group alignment, and
  provider-boundary checks passed. A disposable PostgreSQL 16 database applied
  migration 391 twice, preserved legacy NULL bindings, rejected wrong-owner
  inserts and binding edits, denied the former owner's device after transfer,
  and accepted a device re-enrolled by the new owner. Candidate and legacy
  databases were not accessed for these focused checks. The separately approved
  candidate rollout is recorded below; legacy and live-browser acceptance remain
  open.
- [x] Roll out migration 391 to the local candidate after a fresh age-encrypted
  PostgreSQL checkpoint. The ordered runner applied one schema migration with
  zero failures; 382 schemas are applied with none pending, while 121 seed files
  remain pending and existing mobile-form seed history still needs reconciliation.
  Only the app was rebuilt/recreated. App/database/Metabase are healthy, the proxy
  remains running, and anonymous health/protected-route checks return 200/401.
  No location, transfer, device, or enrollment rows were present; RLS remains
  disabled, the legacy stack was untouched, and the pre-migration checkpoint
  restored successfully into an isolated template0 target with matching schema
  fingerprints, extension versions, and selected aggregate counts. The recovery
  container is stopped and its volume retained
  ([evidence](builds/2026-10-14-recovery/candidate-mobile-tenant-binding-rollout.json)).
- [x] Fix migration discovery for the range-prefixed seed `064-068_impact_network.sql`; the candidate read-only plan now reports 121 pending seeds instead of silently omitting one. Migration source validation covers 503 files and the focused runner suite passes 23 tests. No seed SQL was run.
- [x] Route the explicit curated reference-seed list through the ordered migration runner so each selected file receives the normal checksum and ledger transaction. Preserve the curated order and reference-only exclusion for `140_mobile_forms.sql`; empty state or exact source-form/active-revision parity is accepted, while partial or divergent state blocks the batch and is rechecked under table locks in the seed transaction. Forty-four focused migration/upgrade tests, Ruff, shell syntax, source validation, and diff checks pass.
- [x] Reconcile only `seed:140_mobile_forms.sql` after a source-derived comparison matched all 20 form columns and active revision snapshots for the five forms. A fresh encrypted checkpoint was verified; the selected seed executed as a no-op for form data, the five retired 1.1.0 revisions remained, and the migration ledger now records its checksum ([evidence](builds/2026-10-14-recovery/candidate-mobile-form-seed-ledger-reconciliation.json)).
- [x] Inventory current curated-seed target state in a read-only candidate transaction: all 52 referenced relations exist; 50 are empty; the only non-empty targets are the five reconciled mobile forms and 63 service-catalog rows. The four `091_business_architecture.sql` service keys are absent ([evidence](builds/2026-10-14-recovery/candidate-curated-seed-target-inventory.json)).
- [x] Replay all 31 curated seeds in order against an isolated restore of the candidate checkpoint. All applied, a second ordered invocation skipped the completed ledger entries, and representative counts matched the expected inserts. The scratch database volume was removed; the live candidate remained at 382 schemas and one applied seed ([evidence](builds/2026-10-14-recovery/curated-seed-disposable-replay.json)).
- [x] Validate a fresh template0 bootstrap through all 382 ordered schema migrations and the exact 31-seed curated list, including migration 391; zero failures and expected representative counts. The isolated database and volume were removed ([evidence](builds/2026-10-14-recovery/fresh-curated-seed-bootstrap.json)).
- [x] Create and restore-rehearse a fresh age-encrypted candidate checkpoint in an isolated `template0` database. The applied-migration and extension fingerprints and selected form/service counts matched; the scratch project and volume were removed ([checkpoint and parity](builds/2026-10-14-recovery/candidate-curated-seed-rollout-preflight.json)).
- [ ] Await separate approval before applying only the 30 curated seeds still pending on the candidate. Keep the other 90 seed files unselected and exclude `064-068_impact_network.sql` because it contains pilot upserts and a location-owner update; the live candidate has not been changed by seed SQL ([scope and rollback](builds/2026-10-14-recovery/candidate-curated-seed-rollout-preflight.json)).
- [x] Bind OIDC participant-reference creation and revocation to tenant
  context before the party lookup or link mutation. The new same-origin
  `/operator/api/mobile/.../participants` routes use the OIDC cookie path,
  require location-scoped create/revoke grants plus CSRF, and return no-store
  responses. The original `/api/mobile/.../participants` routes retain their
  Gateway API-key/capability authorization. Five focused OIDC authorization and
  transaction checks plus one API-key regression check pass, including
  context-before-SQL, transaction completion, and HTTP 403 before SQL on tenant
  denial. Candidate and legacy databases were untouched; real-provider browser
  acceptance remains open.
- [x] Extend the read-only tenant preflight with aggregate operator affiliation
  and grant counts. It distinguishes legacy NULL-tenant grants from authorized
  and currently invalid tenant-qualified grants by location, and counts enabled
  operator identities and active organization memberships without returning
  identity fields or UUIDs. Five focused Python checks and Ruff pass; actual
  migrations 388 and 391 passed against a schema-targeted disposable PostgreSQL
  fixture, with exact expected counts and zero synthetic rows remaining after
  cleanup ([evidence](builds/2026-10-13-recovery/tenant-preflight-operator-access-disposable.json)).
  Neither the candidate nor legacy database was accessed. This identifies the
  size and state of affiliation/grant work; it does not map specific operators
  to organizations, infer ownership, backfill grants, or enable RLS.
- [ ] Reconcile other locations and legacy operator affiliations, extend the
  same-transaction context pattern across remaining Gateway routes and worker
  jobs, and establish least-privilege direct-database boundaries before RLS.
  The legacy `services.analytics.mobile_offline` service helpers and historic
  CLI commands have now been retired: they fail before opening a database
  connection because they have no authenticated tenant identity. Capture and
  sync remain available through the consent-aware Field Collector Gateway;
  operator inventory and global queue statistics still need a scoped surface.
  Focused tests cover every helper and command path. Worker and remaining CLI
  review is still open.
  The source audit identified pre-context mobile credential lookups, now
  closed by migration 392's bounded functions. Migration 394 and its
  network-disabled PostgreSQL 16 forced-RLS acceptance now establish signed
  OIDC operator context from a live session, tenant-qualified grants, current
  owner/share state, and consistent additional scopes. The context is bound to
  the PostgreSQL backend and transaction; denial clears old context and
  share/grant changes serialize with active transactions. Migration 395 now
  removes all runtime-role table/column access to `operator_session`; a distinct
  auth login can create, authenticate, and revoke sessions only through bounded
  functions. Disposable PostgreSQL 16 replay, forced-RLS, and privilege checks
  passed. The runtime role still has broad DML on other public tables. Gateway
  mobile credential context is now covered in migration 396; other Gateway
  routes, workers, and the Directus/view boundary need their
  own access contracts before RLS. Full request/worker/
  Directus coverage remains open
  ([audit](mobile-tenant-rls-callsite-audit.md)).
- [x] Move Field Collector token lookup and one-time enrollment redemption
  behind the bounded database API in migration 392. The dedicated credential
  function owner is NOLOGIN/NOBYPASSRLS and receives only table/column rights
  required for identity lookup, owner row locks, device creation, and code
  consumption. The existing tenant-binding trigger now has a fixed search path
  and qualified relation names. The disposable PostgreSQL 16 check applied 391
  and 392, replayed 392, denied direct credential-table reads/writes to a
  constrained app role, checked current/legacy/unknown tokens, conflict and
  single-use enrollment, concurrent redemption (one device/code consumption),
  expiry, and owner transfer; all checks passed. The
  mobile API/tenant suites passed 56 tests; Ruff and syntax/whitespace checks
  passed. No candidate or legacy database was touched; RLS remains disabled
  ([evidence](builds/2026-10-14-recovery/mobile-credential-functions-disposable.json)).
- [x] Replace forgeable mobile-device context GUC trust with migration 393's
  database-signed HMAC context, bound to the current PostgreSQL backend and
  transaction. `set_mobile_device_context` now validates the bearer-token hash
  and current owner, while `current_tenant_context` verifies the private-key
  signature before RLS can read scope. Narrow lock policies make the owner and
  credential definer roles work under forced RLS without broad application
  access. Disposable PostgreSQL 16 acceptance applied 391–393, replayed 392
  and 393, forced RLS only in the disposable database, and passed context
  tampering, invalid-token cleanup, cross-tenant filtering, direct key/table
  denial, enrollment/resolution under forced RLS, and transaction cleanup.
  Seventy-six focused Python tests, Ruff, syntax, and the 505-file migration
  validation pass. Candidate and legacy databases were untouched; RLS remains
  disabled ([evidence](builds/2026-10-14-recovery/mobile-tenant-context-proof-disposable.json)).
- [x] Add migration 394's signed OIDC operator tenant context. PostgreSQL now
  validates the active session hash, enabled identity, tenant-qualified
  location grant, active organization membership, current verified owner or
  unexpired share, and same-tenant additional scopes; it locks those rows and
  signs the result for the current backend/transaction. The shared accessor
  accepts only valid `mobile_device` or `operator` HMAC contexts. Disposable
  PostgreSQL 16 replay and forced-RLS checks passed owner and shared reads,
  legacy/mixed-tenant/disabled/revoked/expired denial, payload tampering,
  transaction cleanup, share revocation, and grant-revocation locking
  ([evidence](builds/2026-10-14-recovery/operator-tenant-context-disposable.json)).
  This is not candidate rollout or RLS enablement. Non-OIDC callers, workers,
  and Directus/view access remain open.
- [x] Add migration 395's operator-session database boundary. The general
  runtime role loses all table/column access to `operator_session` and cannot
  call session functions. OIDC uses a separate auth login that can only call
  bounded create/authenticate/revoke functions owned by a `NOLOGIN` role.
  PostgreSQL 16 disposable replay and forced-RLS acceptance passed, including
  denial of direct read/write/mint attempts by runtime, direct table reads by
  auth, successful bounded session lifecycle, and immediate revoked-session
  denial ([evidence](builds/2026-10-14-recovery/operator-session-role-disposable.json)).
  This does not establish the final app-table role allowlist or enable RLS.
- [x] Tighten runtime privileges on `mobile_device` and
  `mobile_device_enrollment`: the runtime role cannot read device-token, push,
  or enrollment-code hashes, insert/delete devices, delete enrollments, or
  edit enrollment hashes. Explicit column grants preserve the SQL shapes used
  for safe device reads, status updates, enrollment issue/revoke, and device
  revocation. Tenant preflight now reports active unbound devices without
  reading credential columns. The isolated PostgreSQL 16 role check denied
  direct hash reads, hash predicates, and `SELECT *`, while the allowed handler
  statements succeeded; no candidate/legacy DB was touched
  ([evidence](builds/2026-10-14-recovery/runtime-mobile-credential-role-disposable.json)).
  This does not verify every HTTP handler under the runtime login or close the
  broader app-table role, worker, Directus, or RLS gates. Gateway
  credential tenant context is covered in migration 396 below.
- [x] Bind Gateway API-key and capability-token mobile-device writes to signed
  database tenant context in migration 396. The database independently checks
  credential activity/expiry, exact location/resource/action scope, current
  verified ownership, unique API-key identity, and credential/owner row locks
  before signing the backend/transaction-bound context. Wildcard and
  location-free scopes fail closed; application RLS remains disabled. The
  runtime bootstrap now gives
  `api_key` read-only reviewed columns and denies key creation/rotation/revoke
  via the general runtime login, while continuing to permit existing gRPC
  authentication reads. The focused Gateway, mobile, context, and runtime-role
  source suites passed 98 tests; Ruff and the 508-file migration source
  validator passed. Network-disabled PostgreSQL 16 acceptance replayed
  migration 396, forced RLS on synthetic probe tables, and passed its scope,
  credential-state, duplicate-key rejection, capability last-use/over-limit,
  context-tampering, zero-use-limit, and cleanup checks. The role bootstrap
  acceptance replayed migrations
  391–396 and confirmed the runtime
  login can call the signed context function but cannot write API keys. Its
  disposable PostgreSQL runner now waits through the image's temporary initdb
  server before applying fixtures. See the
  [Gateway context contract](gateway-tenant-context-contract.md) and
  [disposable evidence](builds/2026-10-14-recovery/gateway-tenant-context-disposable.json).
  No candidate or legacy database was touched. The contract currently binds
  Gateway credentials to the verified location owner; shared-organization API
  key affiliation and production credential provisioning remain open.
- [x] Bind protected Gateway Data Stream draft creation to signed tenant context.
  `services/gateway/data_stream.py` opens one managed transaction, asks
  PostgreSQL to revalidate the exact credential/resource/action/location and
  current owner, then inserts the draft through that same connection using the
  database-derived actor UUID. Client-supplied `created_by` is ignored, scope
  denial maps to HTTP 403, and lifecycle remains `draft`. The focused Gateway,
  context, and database adapter suites pass (55 tests); Ruff passes. The
  migration-396 disposable PostgreSQL 16 forced-RLS fixture also passes a
  matching tenant/location/actor insert, cross-location denial, denial cleanup,
  and migration replay. No candidate or legacy database was touched. Search,
  file/proof routes, environment-key database provisioning, and other Gateway
  handlers remain open ([evidence](builds/2026-10-14-recovery/gateway-tenant-context-disposable.json)).
- [x] Fail closed on unscoped worker cache invalidation. The allowlisted cache
  event handlers now require a canonical location UUID before creating the
  cache provider, so a malformed event cannot flush every location's cached
  results. Producers for sensor and metric events already include location IDs.
  Missing, NULL, and malformed-location cases across all four handlers fail
  before adapter construction; the focused cache, architecture, and event-bus
  suites pass (59 tests), as do Ruff, Python syntax, and diff checks. This
  narrows one side effect only: the event worker still inherits the shared
  runtime DB identity and has no signed worker tenant context. No database or
  candidate was changed.
- [ ] Roll out migrations 392–397 to the local candidate only after a fresh encrypted
  checkpoint and restore rehearsal; recreate only the candidate app and verify
  health, migration state, and protected routes. Candidate remains at migration
  391 until separately authorized. Existing environment keys need reviewed
  matching database hash/scope rows before tenant-bound mobile writes can pass.
  Migrations 392–396 have isolated PostgreSQL acceptance; migration 397 also
  passes isolated PostgreSQL acceptance against a synthetic schema fixture.
  The ordered 392–397 replay and second no-op pass now also succeed on a restored
  encrypted candidate checkpoint ([evidence](builds/2026-10-14-recovery/candidate-migration-392-397-restored-replay.json)).
  Clean `template0` full-bootstrap acceptance and candidate rollout remain
  separate gates. This rollout alone will not enable RLS.
- [x] Restore the encrypted pre-392–397 candidate checkpoint into the isolated
  recovery project and apply migrations 392–397 through the ordered runner;
  verify exact checksum-ledger entries, a zero-pending second run, unchanged
  application-table RLS state, and no candidate or legacy database writes
  ([evidence](builds/2026-10-14-recovery/candidate-migration-392-397-restored-replay.json)).
- [x] Audit repository-owned downstream consumers of Field Collector data;
  the source review found an unguarded process-interface elapsed-time lookup
  and added the shared eligibility predicate. Reporting, export, metric,
  analytics, process-trace, Gateway review, hook, and repository-dashboard
  paths are inventoried in the [consumer audit](field-collector-downstream-source-audit.md).
- [ ] Verify external and operator-edited dashboard/report consumers against
  populated fixtures, and establish least-privilege direct-database boundaries
  before claiming universal downstream or tenant isolation. Unknown saved SQL
  is not rewritten, and archived unlocated reporting rows remain unassigned.
  The first-party legacy refresh runner now has a dedicated view-only reader
  boundary; this does not prove external dashboard roles or tenant scope.
- [x] Source-audit and gate canonical Field Collector use after capture:
  migration 386 adds a current source/form/consent eligibility function and
  blocks ineligible draft edits and forward lifecycle transitions. Reports,
  metrics, analytics, repository-owned dashboards, exports, process traces, and
  data-quality sampling now filter through that gate. Authorized lifecycle
  reads retain ineligible rows with a reason for human disposition.
- [x] Run focused migration/query/lifecycle acceptance for migration 386 in a
  network-isolated PostgreSQL 16 disposable database with synthetic schema and
  records. Withdrawal followed by regrant remained ineligible; retired forms
  entered review; malformed and mismatched lineage failed closed; provenance
  changes and productive transitions were blocked while rejection disposition
  remained available. Seeded queries were gated and Directus permissions
  preserved their prior scope while excluding Field Collector rows. The
  recursive JSONPath gate check also passed after existing scopes were nested;
  replaying the Directus permission repair twice made no second-run changes,
  including for a NULL permission. The focused application/query/console suites
  pass (56 passed, 18 skipped). The populated ordered-migration replay and
  separately approved candidate rollout are recorded below ([source evidence](builds/2026-10-13-recovery/farm-activity-use-gate-disposable-acceptance.json); [rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)).
- [x] Apply migration 386 through the ordered, checksummed runner to a fresh
  clone of the populated archived database. The read-only plan found one
  pending migration and no checksum drift; after application the schema plan
  reported zero pending. The migration marker, all 8/8 farm-activity Directus
  read gates, and the present seeded dashboard query were verified. The copy
  had two locations, four devices, 43 dashboard datasets, and 30 total
  `farm_activity` rows, with zero Field Collector-sourced canonical activities.
  After the final SQL checksum update, the replay was repeated against the
  restored `kokonut_restore` database; the migration ledger remained exact and
  the final plan reported zero pending. The retained source volume was not
  changed; the temporary clone volume, container, and network were removed,
  and the candidate services stayed healthy ([evidence](builds/2026-10-13-recovery/farm-activity-use-gate-populated-replay.json)).
- [x] Complete the separately approved local-candidate rollout: create and
  restore-rehearse a fresh age-encrypted checkpoint, apply migration 386 with
  the ordered runner, rebuild/recreate only the candidate app, and verify zero
  pending schemas, health 200, and anonymous protected-route 401 responses.
  The checkpoint and prior app image remain available for rollback ([evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)).
- [x] Apply migrations 380 and 381 through the ordered, checksummed runner, seed five reviewed `1.1.0` forms, rebuild only the candidate app, and rehearse the encrypted pre-migration checkpoint restore; the exact-target candidate plan has zero pending schemas ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json)). The candidate had no pre-existing form or collection rows; populated external databases still need their own reviewed rollout.
- [x] Roll out the follow-up `1.2.0` allowlisted schemas and payload validator to the candidate using a fresh checkpoint/rehearsal; retain the existing `1.1.0` app image as a rollback artifact. App rollback alone is not safe for mobile sync because it predates payload validation; see the access contract.
- [x] Recover the local candidate Docker app after its exact prior image digest was unavailable: rebuild from source commit `7c69510`, verify all three candidate services and `/health`, and retain the known-good image under a dated tag. Preserve the legacy stack and all data volumes ([evidence](builds/2026-10-12-recovery/docker-candidate-runtime-recovery.json)).
- [x] Verify live encrypted Field Collector queue retention while the candidate Gateway app is unavailable and automatic background sync after it returns; keep the transport-pending record ineligible, revoke the synthetic device, remove all fixture rows, and lock the browser vault ([evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json)). This is service-outage recovery, not OS airplane mode or `navigator.onLine=false`.
- [x] Probe macOS Wi-Fi-off behavior with user approval and restore Wi-Fi. The localhost candidate remained reachable and the browser still reported Online; no device or record was created, so this is not accepted airplane-mode/offline-queue evidence ([probe](builds/2026-10-12-recovery/field-collector-wifi-off-probe.json)).
- [ ] Complete remaining live Field Collector acceptance: configure a real OIDC provider; exercise live authenticated Gateway reconnect/sync; test retired-form consent withdrawal in the browser; and define downstream human disposition. A fresh isolated Chrome context now reports `navigator.onLine=false`, reopens the candidate app shell offline, saves a synthetic note into the encrypted queue, preserves it after a mocked 503, then clears it after a mocked 200 retry ([evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)). All mobile API calls in that browser check were intercepted, so it closes client offline behavior only—not live server sync or OS airplane-mode acceptance. Candidate Gateway service-outage/reconnect browser acceptance also passes with automatic retry and cleanup ([evidence](builds/2026-10-12-recovery/field-collector-gateway-outage-recovery.json)). Active and synthetic retired required-consent withdrawal handling passed through Gateway ASGI/HTTP on disposable clones; seeded retired `1.1.0` forms are `not_required`, so a synthetic reviewed revision was used. Accepted transport remains ineligible as `transport_pending`. Real OIDC, live S3/R2 inventory/deletion acceptance, tenant/RLS, retention/erasure, and semantic content review remain open; the public media-download route remains disabled.
- [x] Add an OpenAPI-backed, versioned v1 public-location list/detail contract while preserving the legacy location routes.
- [x] Add additive v1 metrics, published-CRISP, and location-summary read aliases with explicit authorization policy and strict response models.
- [x] Add typed v1 location, metrics, CRISP, and location-summary methods to the Python and JavaScript SDK sources.
- [x] Export the scoped Gateway v1 OpenAPI document, including explicit policy metadata, separately from the Directus OpenAPI file.
- [x] Generate the v1 response types and route templates from the native OpenAPI snapshot and make both SDK clients consume the generated definitions.
- [x] Install the declared TypeScript compiler and build the JavaScript SDK; fix compile-time Directus SDK API mismatches ([progress](progress.md#phase-7-javascript-sdk-compiler-compatibility--11-october-2026)).
- [x] Preflight the JavaScript ESM package archive; include its license, exclude test output, and align repository metadata ([progress](progress.md#phase-7-javascript-sdk-package-preflight--11-october-2026)).
- [x] Add a local, read-only Kernel CLI overview of build metadata and provider selection ([operator contract](kernel-operator-cli.md)).
- [x] Resolve the reported JavaScript development-tool audit findings with a locked Vitest 5.0.3 toolchain; npm reports zero vulnerabilities ([progress](progress.md#phase-7-javascript-sdk-package-preflight--11-october-2026)).
- [x] Prepare and inspect Python SDK 0.1.0 wheel/source artifacts with README, Apache license, typed marker, and distribution metadata ([progress](progress.md#phase-7-python-sdk-package-preflight--11-october-2026)).
- [x] Resolve the Python SDK generated-protobuf boundary with namespaced optional `kokonut.grpc` modules; generated stubs are included in the wheel and sdist ([ledger](progress.md#phase-7-python-sdk-optional-grpc-distribution--11-october-2026)).
- [x] Install the Python wheel and optional gRPC runtime into an isolated environment; import both REST clients and all 10 generated modules, and verify class-module and service identities ([ledger](progress.md#phase-7-python-sdk-isolated-wheel-import-check--11-october-2026)).
- [x] Make the TypeScript gRPC npm package self-contained by bundling its proto import closure and resolving service definitions from the installed package ([ledger](progress.md#phase-7-typescript-grpc-package-proto-boundary--11-october-2026)).
- [x] Build and preflight the TypeScript gRPC npm archive; confirm it includes the five required proto files and excludes test output ([ledger](progress.md#phase-7-typescript-grpc-package-proto-boundary--11-october-2026)).
- [x] Extract the TypeScript gRPC npm artifact into an isolated consumer and instantiate/close both service clients to verify bundled proto loading without RPC calls ([ledger](progress.md#phase-7-typescript-grpc-isolated-npm-package-import-check--11-october-2026)).
- [x] Align JavaScript SDK Directus pagination option handling with Python and compile the JavaScript SDK ([ledger](progress.md#phase-7-pythonjavascript-sdk-pagination-parity--11-october-2026)).
- [x] Extract the JavaScript REST SDK npm artifact into an isolated consumer, import its ESM entry point, instantiate both clients, and confirm no HTTP calls ([ledger](progress.md#phase-7-javascript-rest-sdk-isolated-package-import-check--11-october-2026)).
- [x] Compare the five generated v1 reads and Directus pagination across Python and JavaScript with injected fake adapters; cover path encoding, headers, response values, error envelopes and invalid JSON without network calls ([ledger](progress.md#phase-7-pythonjavascript-offline-api-parity--11-october-2026)).
- [x] Preserve the native public API SDK parity contract in Python and TypeScript regression suites: all five v1 reads, escaped path segments, API-key/accept headers, typed payloads, and normalized HTTP/JSON/envelope failures; fake transports make zero network calls ([evidence](builds/2026-10-14-recovery/sdk-public-api-parity.json); [progress](progress.md#phase-7-persistent-native-public-api-sdk-parity--14-october-2026)).
- [x] Pin exact resource/action/public policy tuples for every registered native and Field Collector `/api` route. Unknown paths, method mismatches, and near-miss paths remain protected; 26 focused Gateway authorization and route-policy tests pass ([evidence](builds/2026-10-14-recovery/gateway-route-policy-inventory.json)). This is route/auth source acceptance only; tenant/RLS, live OIDC, gRPC and broader SDK parity remain open.
- [ ] Complete remaining live route, authorization, tenant-scope and broader SDK parity; publish only after explicit release authorization.
- [x] Document the operator identity, scope, audit, browser session, and rollback boundary ([contract](kernel-operations-console.md)).
- [x] Select OIDC and implement the optional Gateway login/session/CSRF adapter, explicit identity and location-grant storage, local provisioning CLI, and principal-only browser shell ([implementation](kernel-operations-console.md)).
- [ ] Configure a real OIDC provider and verify login/session/logout, grant provisioning, scope denials, enrollment-code delivery/revocation, audit attribution, and browser queue/detail behavior. Migration 380 is applied on the local candidate; any other environment must run the ordered migration plan first. Provider-input placeholders and required Compose settings are documented and checked, the profile planner requires HTTPS proxy selection, and all 18 profile contract checks pass; no real provider or credentials were configured.
- [x] Select `report_snapshot` as the first location-scoped submitted-record source; implement its bounded read-only queue/detail routes, explicit OIDC location-scope enforcement, and same-origin browser view ([contract and acceptance gates](kernel-operations-console.md)).
- [ ] With verification authorization, exercise transport and Directus parity gates.

Gate: each optional adapter can be enabled/disabled independently with documented
capability impact. Rollback: restore adapter selection and retained legacy interfaces.

## Batch 6 — Certification and release (Phase 8)

- [x] Refresh ARM64 Kernel application and PostGIS build artifacts from the current checkout under unique local tags; retain image identities and build/runtime limitations ([record](arm64-image-pair-refresh.md)).
- [x] Add a SHA-256 build-input lock and GitHub Actions multi-platform OCI build gate for the default app, ClickHouse-enabled app, and PostGIS targets; the gate requires matching Python package versions across AMD64/ARM64 and checks the selected PostGIS versions ([contract](kernel-release-inputs.md)). A local AMD64 app build completed; the ARM64 counterpart stopped during package resolution after registry DNS failed. CI run 283 exposed the missing CA bundle; [run 284](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38449176283) confirmed the signed-snapshot CA bootstrap and built both PostGIS architectures, then the full package inventory comparison found the documented amd64-only `libquadmath0` delta. That exact architecture difference is locked; [CI run 287](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38466475973) passed the full AMD64/ARM64 build and inventory gate on commit `6549043`. Current branch-head CI remains pending ([attempt record](builds/2026-10-13-recovery/kernel-architecture-local-build.json)).
- [x] Replace the OneDev buildspec with GitHub Actions CI, Gitleaks, and manually gated deployment workflows; remove the tracked OneDev buildspec and update operational runbooks. Full-history Gitleaks passed on 13 October after a narrow allowlist was added for reviewed fixture, identifier, hash, and placeholder matches. Security workflow passed; CI run 284 completed the CA bootstrap and both PostGIS builds, then failed on the package-inventory delta now explicitly captured in the release lock. Remote GitHub runner/environment/branch-protection setup and retiring any remaining OneDev-side runner/settings remain owner actions ([setup and migration record](../github-actions.md); [progress](progress.md)).
- [x] Generate hash-locked Python dependency closures for the default Kernel runtime and optional ClickHouse profile, and wire each into `Dockerfile.kernel`; regeneration uses pip-tools 7.6.2 and the source manifests remain SHA-256-locked ([release-input contract](kernel-release-inputs.md)).
- [x] Run the updated default-app, ClickHouse-app, and PostGIS AMD64/ARM64 build gate on a pull request and retain the passing build record. [CI run 285](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38451953437) passed all six image builds and the locked package inventories, then failed later in the full Python/database suite (23 failures, 4,532 passed). [CI run 286](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38458613711) passed 4,556 tests but exposed one seed-idempotency failure: PostgreSQL evaluates the mobile-form `BEFORE INSERT` revision guard before `ON CONFLICT DO NOTHING`. Commit `6549043` filters already-present form IDs before insertion. [CI run 287](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38466475973) passed the default and ClickHouse app builds for AMD64/ARM64, PostGIS builds for both architectures, and package parity checks; its full suite passed 4,557 tests plus 75 subtests, including the database-backed seed-idempotency regression. This run covers commit `6549043`; later commits on the PR branch still need a fresh run.
- [x] Pin Debian Bookworm apt sources to an explicit snapshot date and use the PGDG released-package archive with exact PostGIS package versions; lock the source files and package record. CI run 287 completed the full package inventory comparison and workflow on commit `6549043`; current branch-head CI remains pending.
- [x] Extend the release checker to compare complete installed Debian package inventories across AMD64/ARM64 and report missing or version-different packages, with only exact, locked architecture-specific expectations allowed. CI run 285 passed this comparison for all image targets using the reviewed `libquadmath0` exception; further unexpected differences still fail.
- [x] Rerun the snapshot-aware PostGIS build and locked inventory comparison on both architectures and retain the passing result ([CI run 287](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38466475973): 229 AMD64 and 228 ARM64 packages, with the single documented architecture-specific difference).
- [x] Exercise ARM64 bootstrap, migration, health, restore, and restart under Buildx/QEMU with constrained containers. The minimal app and PostGIS images inspect as `linux/arm64`; 386 schemas applied with zero failures; app health passed before and after database restart and simulated app loss; the logical restore matched all migration checksums and passed Kernel readiness. Limits were 1.5 GiB for PostgreSQL and 1 GiB for the app, with two CPUs each and no published ports. Evidence: [arm64-qemu-runtime-acceptance.json](builds/2026-10-14-recovery/arm64-qemu-runtime-acceptance.json). This is emulator evidence only: no Raspberry Pi is available, so physical performance, thermal, storage, power-loss, and device restart behavior remain unverified.
- [ ] With verification authorization, complete 24-hour recovery and scale concurrency checks.
- [x] Review the capability matrix and obtain passing release CI for the current PR head. Commit `7953afe4d5267b040392a8fe52e1ae38c236cfd4` fixes CI #307's OIDC Compose test setup by providing the test-only operator-auth password before asserting the missing issuer. CI run [#308](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38598258026) and Security run [#32](https://github.com/wasalo/Kokonut-Intelligence/actions/runs/38598258017) both passed on this head. The preceding CI #304 failure analysis and local regression evidence remain in [the recorded fix batch](builds/2026-10-14-recovery/ci-304-regression-fix-checks.json).
- [x] Align the active `Main branch protection` ruleset (ID `18234835`) with `CI / ci` and `Security / gitleaks`. GitHub API verification confirms the obsolete `Python checks`, `Directus hooks`, and `Foundry contracts` contexts were removed; pull-request/review, CODEOWNERS, thread-resolution, strict up-to-date, linear-history, deletion, force-push, and bypass settings remain. The separate active version-tag ruleset (ID `18234836`) was not changed ([settings audit](../github-actions.md#current-required-check-audit--14-october-2026)).
- [ ] Execute a reviewed cutover and retire dependencies only after their gates close.

Gate: all required deployment profiles and selected capability acceptance criteria
have retained evidence; production cutover has an executable restore path.
Rollback: recorded prior images, provider configuration and recoverable data snapshots.

Batch 2 scoped restore milestone: [evidence](builds/2026-10-10-recovery/README.md).
Schema inventory matches; empty workloads do not close complete recovery acceptance.
