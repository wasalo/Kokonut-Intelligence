# Kernel execution checklist

Updated: 11 October 2026. Current architecture focus remains Phase 7; batch
numbers group work across phases and do not replace the phase acceptance gates.

## Working agreement

Each batch delivers one reviewable outcome, lists evidence and rollback, and
updates progress.md, affected capability rows and the ignored root plan. Stop at
the batch boundary to report completed items and unresolved gates. No capability
is accepted solely because source exists or an image starts. Verification work
below requires an explicit request before adding or running test suites.

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
- [ ] Exercise physical-device/power failure; select external alert routing and production retention ownership. Also verify candidate provider activation/restart, replica failover/scale, non-loopback/public ingress, multi-hop trusted-proxy policy, mobile/upload/auth parity and CORS on successful authenticated/credentialed responses; expand handler effects/retries and cover operator authorization, dashboard parity, external/populated-target lineage and remaining provider ownership.
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
- [x] Implement a PostgreSQL notification outbox for alert/stale-data webhook and Directus sends, with stable event/channel identities, leases, bounded retries and audited dead-letter actions.
- [x] In a fresh internal-only PostgreSQL fixture, exercise notification enqueue idempotency, stable source event-id propagation, retry/backoff, lease recovery, crash-after-fake-send duplicate behavior, provider pause and operator replay/disposal; retain evidence ([record](builds/2026-10-11-recovery/notification-outbox-check.json)).
- [x] Add read-only notification outbox capacity reporting for row counts, oldest open age, and combined relation bytes, with configurable warning/critical thresholds ([policy and operation](notification-outbox-operations.md); [isolated evidence](builds/2026-10-11-recovery/notification-outbox-capacity.json)).
- [ ] Confirm product/jurisdiction retention and archive periods for terminal notification, attempt, and operator-audit records; keep the interim no-prune policy and never prune pending, processing, retryable, or undisposed dead-letter rows.
- [x] Kill the real sensor anomaly event-worker after handler commit but before receipt acknowledgement; verify lease reclaim, attempt-two completion, single-copy effects, and human approval for critical actuation ([design and recovery evidence](sensor-anomaly-delivery.md); [machine record](builds/2026-10-11-recovery/sensor-anomaly-crash-retry.json)).
- [x] Implement an opt-in PostgreSQL runtime DML role and verify its bounded privileges, repeatable provisioning, and denial paths in an internal-only scratch database ([policy](runtime-role-policy.md); [machine evidence](builds/2026-10-11-recovery/runtime-role-isolation.json)).
- [x] Rehearse the opt-in role against a fresh populated restore; verify the native public-location read, PostGIS, DML/sequence access, DDL denial and unrelated-database denial ([fixture](../../scripts/fixtures/kernel-db-runtime-role-populated-check.py); [machine evidence](builds/2026-10-11-recovery/runtime-role-populated-restore.json)).
- [x] Define and verify separate Directus DML, Metabase metadata-owner, and curated analytics read-only roles against fresh populated restores; exercise owner-run Directus bootstrap and DML-only Directus startup on the isolated network ([policy](optional-database-roles.md); [fixture](../../scripts/fixtures/kernel-optional-db-roles-check.py); [evidence](builds/2026-10-11-recovery/optional-consumer-db-roles.json)).
- [x] Start the pinned Metabase image with its non-superuser role against a separate empty metadata database; confirm first-start migrations and health without configuring a saved source ([startup evidence](builds/2026-10-11-recovery/optional-consumer-startup.json)).
- [ ] Verify Directus API role/field/row and extension-hook parity with its runtime identity.
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
- [ ] Configure optional Metabase against the reviewed views, build Kokonut-specific cards, and compare card outputs to independent/native reference fixtures before profile promotion.
- [ ] Complete remaining provider recovery and broader event-handler/platform-integrity acceptance.
- [x] Retain and compare a local development mirror (user-selected scope); defer independent R2 production backup to Batch 6.

Preparation evidence: [recovery record](recovery-preparation.md). Batch 2 remains
open; logical provider ownership and remaining recovery evidence are unresolved.

Gate: restore evidence covers schema, domain rows, private media and durable work;
legacy storage remains recoverable. Rollback: use isolated volumes and keep original
backups/volumes; no production cutover in this batch.

## Batch 3 — One complete minimal pilot workflow (Phases 2, 7)

- [ ] Map one farm activity through draft, submission, independent review and publication.
- [ ] Implement shared lifecycle/authorization contracts and the native API slice.
- [ ] Connect draft metric computation and one governed report to that workflow.
- [ ] With verification authorization, exercise role/field/row policy and failure paths.

Gate: retained end-to-end evidence for the selected CAP rows, with explicit
uncovered domains. Rollback: additive migrations and optional API routing; preserve
the existing governed provider path until parity is accepted.

## Batch 4 — Native orchestration and analytics parity (Phases 3–5)

- [ ] Assign each known job a schedule owner and cutover/replay policy.
- [ ] Close projection, named-query, report and dashboard parity gaps in scoped groups.
- [ ] Resolve Redis session/cache inventory and shared limiter requirements.
- [ ] With verification authorization, exercise leases, retries, idempotency and outages.

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
  target is not ready: `kokonut` is its only login/superuser role, PUBLIC has CONNECT
  (and TEMPORARY on the application database), and migration 377/reporting views
  are still pending. No source role or Metabase connection was provisioned
  ([ACL review](builds/2026-10-11-recovery/candidate-reporting-acl-review.json)).
- [ ] After the migration-history gate is resolved and the reporting schema is
  applied, provision a dedicated analytics login on the exact target; verify
  only approved named view access, database isolation, and extension ACLs.

Evidence: [populated report-view parity](builds/2026-10-11-recovery/populated-report-view-parity.json).
The farm summary matched 2 rows, the Celo attestation summary matched 1 row,
and both had zero bidirectional differences. The metric view and its independent
query both returned zero because no metric publication policy is published.
The separate rollback-only synthetic role fixture passed the published metric
period/method/review-field probe ([fixture evidence](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json)).
The pre-migration ACL review found no analytics role and default PUBLIC
CONNECT/TEMPORARY exposure. Migrations 371–379 are now applied and the three
reporting views exist, but no analytics role/source is configured. The database
and inherited extension ACL review remains a prerequisite for provisioning.
Rollback: no source rows or source grants were changed; the copied database was
discarded after evidence capture.

## Batch 5 — Optional transports and application access (Phases 6, 7)

- [ ] Complete HTTP/MQTT sensor, gRPC and proxy deployment contracts in separate slices.
- [ ] Complete mobile media/offline sync and consent/tenant boundaries.
- [ ] Publish versioned API contracts/SDK and an operations console slice.
- [ ] With verification authorization, exercise transport and Directus parity gates.

Gate: each optional adapter can be enabled/disabled independently with documented
capability impact. Rollback: restore adapter selection and retained legacy interfaces.

## Batch 6 — Certification and release (Phase 8)

- [ ] Lock release inputs and add architecture CI gates.
- [ ] With verification authorization, exercise ARM bootstrap/restore and a real 4 GB Pi/SSD.
- [ ] With verification authorization, complete 24-hour recovery and scale concurrency checks.
- [ ] Review capability matrix, submit branch PR and obtain passing release CI.
- [ ] Execute a reviewed cutover and retire dependencies only after their gates close.

Gate: all required deployment profiles and selected capability acceptance criteria
have retained evidence; production cutover has an executable restore path.
Rollback: recorded prior images, provider configuration and recoverable data snapshots.

Batch 2 scoped restore milestone: [evidence](builds/2026-10-10-recovery/README.md).
Schema inventory matches; empty workloads do not close complete recovery acceptance.
