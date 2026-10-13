# Pending application migration compatibility review

**Status (11 October 2026):** all 25 migrations pending on the retained
archived application clone were reviewed in order and applied successfully to a
separate network-isolated copy. The retained archived clone still has 25 pending
migrations and was not changed. No active candidate or legacy service received
these migrations.

## Method and result

The archived clone began with 344 applied schema migrations and 32 applied seed
migrations. Its 25 pending source migrations were applied through the
transactional checksum runner to a fresh copied volume with `network_mode: none`
and no published ports. All 25 applied, the checksum plan reported zero pending,
and the final ledger contained 369 applied schema migrations and the same 32
seed migrations.

Before and after the replay, the review compared sorted row fingerprints across
16 existing populated tables. The comparison excluded only columns introduced
by the pending migrations, so it checked all fields that existed before the
replay. All 16 row counts and fingerprints matched. Expected additive state was
two seeded SAFE registry rows, three reporting views, and empty new workflow,
media, transport, outbox, and operator-audit relations. New expense/activity/
device fields retained their nullable/default values; the reporting publication
policy remained empty. The six expected `schema_version` markers for migrations
354–359 were the only legacy schema-version metadata rows added.

Read-only preflight found 0 weekly-plan/farm location mismatches and 0
farm-activity/plot location mismatches. The inspected source clone had 30
farm activities, 43 expenses, one attestation request, 0 credit orders, 0
weekly plans, 0 farm tasks, 0 scheduled tasks, 0 task runs, and 0 actuation log
rows. The three optional extensions added by migration 378 were already
installed at `postgis_topology` 3.4.3, `pg_trgm` 1.6, and `pg_stat_statements`
1.10.

The migration runner was also exercised with a synthetic migration that creates
a table and row, then fails on a duplicate table. Its schema changes and ledger
insert both rolled back (`0|0`). The temporary containers and networks were
removed; the source and review clone volumes were retained.

Evidence: [clone replay](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json),
[pre/post fingerprints](builds/2026-10-11-recovery/application-migration-review-fingerprints.json),
[transaction failure probe](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json),
[archived clone plan](builds/2026-10-11-recovery/application-migration-checksum-drift.json).

## Extended populated replay through migration 385 — 13 October 2026

A fresh restore of the encrypted populated archive began with 344 applied
schema migrations and 32 seed migrations. The current source planner found 32
pending schemas (353–385, with numbering gaps preserved) and no checksum drift.
The ordered transactional runner applied all 32 with zero failures, and the
final schema plan reported zero pending. The tenant preflight then found all
27 required columns and completed its read-only known-lineage inventory on the
same clone. This is a separate clone from the earlier 25-migration review; it
does not modify the retained archived source, active candidate, or legacy
deployment.

The populated inventory found one location whose direct organization
assignment lacks a confirming active owned-primary relationship, one
unassigned location, and no active organization-member rows. It also found
three report snapshots and 38 dashboard datasets without location. An initial
preflight output that showed false opaque owner references was discarded after
the PostgreSQL driver exposed an empty `uuid[]` as the string `{}`. The source
now casts the aggregate to `text[]` and rejects unexpected array shapes; the
corrected rerun reported zero relationship candidates. See the
[sanitized replay evidence](builds/2026-10-13-recovery/field-collector-tenant-populated-migration-replay.json).

The replay establishes schema-source and transactional compatibility for this
snapshot. It does not establish accountable ownership, complete downstream
lineage, least-privilege grants, or RLS behavior. No ownership assignment or
backfill was performed; owner review remains a separate deployment gate.

## Per-migration review

Migration 386 has been added after the populated replay through 385. It has not
yet been applied to a database, so its trigger behavior, existing-row backfill,
runtime query compatibility, and rollback-on-failure still require a focused
disposable populated-restore review before candidate rollout.

| Migration | Change and compatibility finding on the inspected clone |
| --- | --- |
| [353 crop-cycle NOI view](../../schemas/postgres/353_crop_cycle_noi_view.sql) | Replaces/creates a read view and adds two partial indexes. The view did not exist before this replay; sales (15), expenses (43), harvests (12), crop cycles (6), and allocations (126) remained unchanged. Index creation is non-concurrent and may take a write lock on larger deployments. Verify view output against the Python and TypeScript implementations before using it for finance decisions. |
| [354 SAFE treasury accounts](../../schemas/postgres/354_safe_treasury_accounts.sql) | Creates account/transaction tables and inserts two canonical SAFE rows. The tables were absent; constraints accepted the seeded thresholds and owner counts. Before operational use, an owner must confirm chain, addresses, owners, and thresholds against current deployment records. |
| [355 SAFE attestation flow](../../schemas/postgres/355_safe_attestation_flow.sql) | Adds three nullable/defaulted proposal fields and a check/index. One existing attestation request received the valid `pending` default; its prior fields matched their pre-replay fingerprint. |
| [356 SAFE settlement](../../schemas/postgres/356_safe_settlement.sql) | Adds settlement fields and checks to sell/buy orders. Both tables had zero rows; new status defaults are `pending`. |
| [357 field collector enrollment](../../schemas/postgres/357_field_collector_enrollment_hardening.sql) | Adds `mobile_form.is_public=false`, nullable device revocation time, and an enrollment table. Four devices and zero forms remained unchanged; the enrollment table was empty. |
| [358 private mobile media](../../schemas/postgres/358_mobile_private_media.sql) | Creates a device/location-scoped upload reference table with size, hash, status, expiry, and attachment checks. No table or media records existed; this migration does not copy object-store files. |
| [359 activity scope and outputs](../../schemas/postgres/359_activity_scope_and_outputs.sql) | Adds nullable activity scope/duration fields, checks, future-write scope triggers, and normalized staff/plot/output relations. All 30 existing activity rows passed; new columns remained null, and the existing plot/location mismatch count was zero. New relations were empty. |
| [360 job-role departments](../../schemas/postgres/360_job_role_department_relationships.sql) | Creates a provenance-aware many-to-many relation. Job-role and department populations were empty; no source edges are imported. |
| [361 farm-task relationships](../../schemas/postgres/361_farm_task_relationships.sql) | Adds optional task association to expenses, a future-write location trigger, and task dependency/framework/weekly-plan relations. There were 43 expenses and zero farm tasks; the added field stayed null and relation tables stayed empty. |
| [362 farm staff membership](../../schemas/postgres/362_farm_staff_membership.sql) | Creates an explicit farm/staff relation with optional source provenance. Two farms and four staff records exist, but no membership rows are inferred or backfilled. |
| [363 expense farm/plan scope](../../schemas/postgres/363_expense_farm_weekly_plan_scope.sql) | Adds nullable expense farm/plan links and future-write validation, including a farm reparent guard. Weekly plans were empty and both the migration's farm/location preflight and the activity/plot check returned zero. New expense links remained null. |
| [364 reported activity metrics](../../schemas/postgres/364_reported_activity_output_metrics.sql) | Creates source-reported indicator and output-link tables. No backfill occurs; these values remain distinct from verified `metric_value` records. New tables were empty. |
| [365 weekly-plan scope exception](../../schemas/postgres/365_expense_weekly_plan_scope_exception.sql) | Adds `false`/null exception fields and tightens future expense/plan scope checks. All 43 existing expenses received the valid false/null defaults; there were no weekly plans or existing exception links. |
| [366 crop-category documentation](../../schemas/postgres/366_crop_category_extensions.sql) | Adds a column comment only; no rows or constraints change. |
| [367 external grant tranches](../../schemas/postgres/367_external_grant_tranche.sql) | Creates tranche and funder relations with source identity. No tranche data or amount is imported; the schema intentionally keeps program dates separate from cash settlement. New tables were empty. |
| [369 activity source options](../../schemas/postgres/369_baserow_activity_source_options.sql) | Adds nullable JSONB source choices with an array check. Existing activity rows received null; the field does not choose or rewrite canonical activity type. |
| [370 expense source fields](../../schemas/postgres/370_baserow_expense_fields.sql) | Adds nullable payment state and people-count fields plus a nonnegative check. All 43 expenses retained null in both new fields. |
| [371 scheduler run windows](../../schemas/postgres/371_scheduler_run_windows.sql) | Adds `dependency_mode=last_completed` plus nullable scheduled windows and one index. Scheduled tasks and task runs were empty; old dependency semantics remain the default. |
| [372 MQTT delivery records](../../schemas/postgres/372_mqtt_delivery_records.sql) | Creates private delivery/action tables. No historical broker payloads or delivery rows are copied; both tables were empty. |
| [373 gateway rate buckets](../../schemas/postgres/373_gateway_rate_buckets.sql) | Creates shared limiter state. No caller buckets were imported; table was empty. Local limiter behavior remains a separate provider choice. |
| [374 ClickHouse operator audit](../../schemas/postgres/374_clickhouse_outbox_operator_audit.sql) | Creates audit history for operator transitions. No existing outbox work or audit table was present; no history was synthesized. |
| [375 notification outbox](../../schemas/postgres/375_notification_outbox.sql) | Creates durable notification, attempt, and operator-audit tables. No historical notifications are backfilled; all three tables were empty after replay. |
| [376 sensor anomaly delivery](../../schemas/postgres/376_sensor_anomaly_delivery.sql) | Adds email to the notification channel check, effect receipts, and `requires_approval` to actuation status. Actuation log had zero rows; the newly created outbox and effect tables were empty. |
| [377 Kokonut reporting contract](../../schemas/postgres/377_kokonut_reporting_contract.sql) | Creates a reporting schema, three aggregate views, and an empty metric publication policy, then revokes `PUBLIC` access on that new schema. The schema was absent before replay; the three views exist and the policy is empty afterward. Analytics-role provisioning remains separate. |
| [378 optional extensions](../../schemas/postgres/378_optional_extensions.sql) | Adds three `IF NOT EXISTS` extension declarations. All three extensions and versions were already installed; no domain rows changed. |

## Deployment gates and rollback

The clone replay found no data-dependent failure for this snapshot. It is not a
production approval. Before applying to an active target:

- Take and verify an independent backup; preserve the current image and provider
  configuration for the rollback window.
- Confirm the two seeded SAFE identities with the contract owner and verify
  migration 353 NOI results against the canonical metric implementation.
- Compare schema/object inventory and key preflight queries on the exact target;
  different installations may contain out-of-band objects or rows.
- Schedule migration 353's ordinary index builds with its table-lock impact in
  mind. The inspected clone is small; a larger database may need a maintenance
  window.
- Keep Directus, mobile, scheduler, MQTT, notification, gateway, and Metabase
  activation separately gated; successful DDL does not validate those runtime
  paths.

If an individual migration fails, the runner rolls its SQL and ledger update
back together. After a successful operational apply, do not use destructive down
migrations. Roll back compatible application/config selection, or restore a
verified database backup if schema/data restoration is required. For this review,
discarding the separate review volume returns to the unchanged source clone.
