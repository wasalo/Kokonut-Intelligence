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
- [ ] Define participant-to-party consent mapping and form/version enforcement, then implement and verify the approved mobile policy.
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
- [ ] Complete JavaScript SDK runtime/import acceptance and Python/JavaScript API parity; publish only after explicit release authorization.
- [x] Document the operator identity, scope, audit, browser session, and rollback boundary ([contract](kernel-operations-console.md)).
- [x] Select OIDC and implement the optional Gateway login/session/CSRF adapter, explicit identity and location-grant storage, local provisioning CLI, and principal-only browser shell ([implementation](kernel-operations-console.md)).
- [ ] Configure a real OIDC provider, apply migration 380, and verify login/session/CSRF/revocation, scope denials, audit attribution, and browser queue/detail behavior.
- [x] Select `report_snapshot` as the first location-scoped submitted-record source; implement its bounded read-only queue/detail routes, explicit OIDC location-scope enforcement, and same-origin browser view ([contract and acceptance gates](kernel-operations-console.md)).
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
