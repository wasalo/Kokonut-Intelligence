# Batch 4 job schedule ownership and cutover inventory

**Reviewed:** 18 October 2026
**JobSpec catalog count reconciled:** 30 October 2026 (23 entries; no external
or persisted schedule state was inspected by this source update).
**Status:** Source-level inventory and target ownership policy; no schedule was
registered, enabled, paused, or executed by this review.

## Ownership rule

The Kernel's minimal profile should use the durable PostgreSQL scheduler as the
default owner for recurring Kernel jobs. `services/core/jobs.py` is the shared
operation catalog; it is not itself a schedule registry. Prefect may remain an
optional workflow adapter for deployments that need its UI, but each recurring
job must have exactly one active dispatcher at a time. A cron entry, Prefect
deployment, `scheduled_task`, or operator trigger must not run the same work
concurrently without a reviewed idempotency and overlap contract.

The repository does not establish which Prefect schedules are currently active
in an external Prefect server. The checked-in deployment file is configuration,
not runtime evidence. The recovery record says the restored legacy database had
no `scheduled_task` or `task_run` rows; the local candidate scheduler has also
been observed with zero tasks. The historical seed
`schemas/seeds/050_scheduled_tasks.sql` inserts enabled rows, so it must not be
applied to a target until its ownership and duplication implications are
reviewed. The default `scripts/seed.sh` migration call uses `--schemas-only`,
which excludes seed data, and its curated seed list does not include seed 050.
This seed is not applied by normal bootstrap; do not add or manually apply it to
a Kernel target without first disabling its schedules and reviewing their
contracts. Reconcile live provider state immediately before any cutover.

The legacy metrics row in seed 050 uses `--compute --all-locations`; the
database-driven Kernel command contract now rejects that cross-location mode.
Translate it to one disabled location-scoped task per approved location only
after reconciling active schedules and outputs. Do not edit or apply the legacy
seed as part of that translation.

A read-only status query inside the healthy local candidate app on 12 October
local time (13 October UTC) reported zero enabled, disabled, running, or failing
native scheduler tasks. The candidate project has no Prefect container. This
confirms the candidate has no registered native schedules; it says nothing
about a remote Prefect service or host process. A read-only Docker name filter
also found no running local container matching `prefect`. See the
[candidate scheduler snapshot](builds/2026-10-12-recovery/candidate-scheduler-owner-snapshot.json).

## Configured recurring flows

`config/prefect/deployment.yaml` declares four UTC schedules and one manual
deployment. The flow contents below come from
`services/flows/pipelines.py`; an external Prefect service's actual activation
state remains unknown.

| Declared owner | UTC schedule | Work declared by the flow | Cutover/replay notes |
| --- | --- | --- | --- |
| Prefect `scheduled-hourly` | `0 * * * *` | anomaly detection, freshness | The source-less sensor CLI was removed from the composite hourly workflow so it cannot stop monitoring. Sensor capture remains available through explicit CLI, HTTP, and MQTT paths; do not schedule it until a real source is defined. |
| Prefect `scheduled-every-6h` | `0 */6 * * *` | weather, dashboard refresh, remote-sensing flow | Weather and remote-sensing adapters fan out only over locations assigned to the owner-confirmed Kokonut Network organization. Remote sensing claims due durable jobs one location at a time; keep one outer trigger and let the internal worker own child attempts. Inspect `no_data`, skipped, retryable, and terminal outcomes before replay. |
| Prefect `scheduled-daily` | `0 6 * * *` | market data, metrics, credit-adjustment check | Metrics create draft, unverified values; metrics and credit checks now fan out one location at a time over active Kokonut Network locations. The old metrics cron/seed cadence is every four hours and its global `--all-locations` seed command is rejected by the Kernel scheduler contract. Reconcile cadence and existing output before cutover. Credit checks use the dedicated read-only entrypoint; output handling, signed worker context, and accountable operator remain open. |
| Prefect `scheduled-weekly` | `0 3 * * 0` | climate-data flow | The flow now fans out over active locations assigned to Kokonut Network; each climate invocation uses `--all` to select datasets and a required `--location-id`. Native plans remain one location per scheduled task. The flow docstring mentions ML retraining, but the flow body does not run it. |
| Prefect `full-pipeline` | Manual only | ingestion, monitoring, analytics, then remote sensing | Manual runs can overlap scheduled deployments. Require an operator to check current run state or route through a single guarded workflow before enabling native schedules. |

## Owner-scoped Prefect fan-out

The optional Prefect adapter preserves all-location intent for
location-required catalog jobs by selecting active `location` rows whose
`organization_id` resolves to the active organization with key
`kokonut-network`, then invoking each job once with that location UUID. The
lookup uses a read-only transaction and excludes unassigned or other-organization
locations. Anomaly, weather, metrics, credit-adjustment, climate, and
remote-sensing adapters use this filter. A caller may still request one explicit location on
weather, metrics, or credit-adjustment flows; climate and remote sensing remain
sequential.

This selection is code-level scope based on the owner's mapping of Genesis,
Seeds, Adelphi, Terra Viva, and V1 to Kokonut Network. It is not signed worker
tenant context or a database authorization boundary. No scheduled task or
Prefect deployment was inspected or changed, and application-table RLS remains
blocked until worker-specific identity and grants are implemented.

The deployment file does not declare schedules for EAS, RPC, Gnosis indexing,
NOI snapshots, or ClickHouse projections. The full pipeline includes EAS, RPC,
and Gnosis as manual ingestion tasks, but that does not create recurring
ownership for them.

## JobSpec ownership map

The source inventory below compares the 23 `JOBS` entries with Prefect flows,
the active and deprecated entries in `config/worker/crontab`, and the historical
database seed. “Declared” describes repository configuration only. “Target” is
the intended single-owner policy after the gates close; it does not assert that
a job is currently running.

| JobSpec | Current source declarations | Target owner and cutover/replay policy |
| --- | --- | --- |
| `weather` | Prefect every six hours; deprecated cron and seed also say every six hours | The native `weather` JobSpec now targets the dedicated default-off `services.ingestion.weather_worker`, which requires one explicit location and uses signed `weather_observation/ingest` context plus a bounded atomic store function. Existing persisted tasks and the legacy Prefect/cron paths are not migrated or reconciled and remain on `services.ingestion.weather` pending owner review. Do not auto-catch-up missed windows; reconcile source watermark, duplicate keys, cadence, and owner first. No feature, credential, grant, provider, or schedule was activated ([worker](../services/ingestion/weather_worker.py); [migration](../../schemas/postgres/427_signed_weather_observation_worker.sql); [evidence](builds/2026-10-17-recovery/weather-observation-worker-disposable.json)). |
| `weather_forecast` | No separate active Prefect or cron schedule is established by the repository inventory; the five-day forecast CLI is a repository-defined capability | A disabled native JobSpec accepts only one explicit location and rejects aggregate mode. Forecast rows upsert by location/date/hour/source, with ClickHouse projection intent queued in the same transaction. Keep the plan disabled until provider credentials, per-location authorization, cadence, and source parity are reviewed; no missed-window catch-up is automatic. |
| `sensors` | The legacy Prefect pipeline used to call the no-input flow; deprecated cron and seed say every five minutes | The source-less sensor call is no longer in the composite hourly or full-ingestion Prefect pipelines. A disabled native task now requires a location UUID and registered driver-instance UUID; lookup requires an enabled sensor driver assigned to that exact location. Only code-installed pull drivers can opt in; the built-in CSV driver is bounded to 100 sources/10,000 records, while MQTT remains event-driven. PostgreSQL readings, audit, outbox projections, and new-reading events commit atomically; timestamp uniqueness rejects conflicting retries and suppresses duplicate event publication. This is source/mock evidence only: no active driver instance, schedule, tenant identity, or provider source was configured. Reconcile the actual source path, ownership, replay watermark, and source parity before transfer ([contract](worker-operation-map.json); [focused evidence](builds/2026-10-16-recovery/sensor-driver-scheduled-source-contract.json); [prior CLI evidence](builds/2026-10-15-recovery/sensor-ingester-explicit-input-contract.json)). |
| `market_data` | Prefect daily at 06:00 UTC; deprecated cron and seed match | Live World Bank failures now propagate instead of silently seeding; explicit reference rows use a separate source key, and each price batch plus its ingestion audit is atomic. Keep the native schedule disabled until provider parity, historical correction policy, owner/cadence reconciliation, and runtime recovery are verified. Reconcile requested periods before replay; no blind backlog. |
| `eas` | Deprecated cron and seed every 15 minutes; EAS flow is included in the manual full ingestion pipeline | Each native scheduled task now requires exactly one supported `--chain`; a missing or repeated chain fails pre-dispatch. The optional Prefect adapter preserves all three configured chains in Celo-first order (`celo`, `optimism`, `base`). Keep plans disabled until cursor/finality, duplicate-attestation and reorg behavior are verified; no task, provider or Prefect deployment was activated ([evidence](builds/2026-10-16-recovery/eas-chain-scoped-job-contract.json)). |
| `eas_legacy` | No independent schedule; compatibility fallback selected by the `eas` dispatcher while `isolated_eas_indexer_worker` is disabled | Preserve it only as the default-off compatibility target of `eas`; it still requires one explicit supported `--chain`. Do not register or activate a separate schedule for it. Retire the fallback only after the isolated worker's credential, grant, cursor, and runtime acceptance gates close. |
| `rpc` | Deprecated cron/seed every 30 minutes; RPC flow is included in the manual full ingestion pipeline | Native `rpc` plans target the default-off `services.ingestion.rpc_worker`, require exactly one supported `--chain`, and pass an optional wallet filter only within that chain. Migration 436 gives the worker an exact login, bounded chain-lock/wallet/snapshot/status functions, and no direct table access; its worker-specific DSN and endpoint JSON are isolated from shared database and global RPC variables. The Prefect adapter and disabled-feature dispatcher retain the legacy CLI path. One chain lock coordinates worker and legacy runs. Do not enable schedules until credentials/grants, provider parity, and persisted/external schedule ownership are reconciled. This remains balance snapshots only; transaction-history scans, confirmation depth, finality, and reorg recovery are open ([worker](../services/ingestion/rpc_worker.py); [migration](../../schemas/postgres/436_isolated_rpc_indexer.sql); [disposable evidence](builds/2026-10-18-recovery/rpc-indexer-worker-disposable.json)).
| `rpc_legacy` | No independent declaration; selected by the `rpc` dispatcher while `isolated_rpc_indexer_worker` is disabled, and retained for the Prefect compatibility path | Compatibility target only; preserve the manual all-wallet CLI and historical task command. The CLI now compares/locks a matching activity row instead of issuing `ON CONFLICT (tx_hash)`, for which the schema has no unique constraint. Do not register a second RPC schedule. Retire this fallback only after the isolated worker login/grants and persisted/external schedule ownership are reviewed. |
| `gnosis` | Deprecated cron and seed every two hours; Gnosis flow is included in the manual full ingestion pipeline | Each scanned range and its status checkpoint now commit together; migration 423 receipts suppress identical event logs first processed after rollout and fail closed if the same transaction/log index reappears with different block data. Migration 424 separates the `gnosis_moloch` cursor from wallet RPC by preserving the last shared boundary in a paused, provenance-marked row; the legacy `(gnosis, rpc)` row remains for wallet activity. An unreviewed inherited cursor now requires an operator-supplied `--from-block`, and records review only after the first committed range. Historical receipts are not backfilled, and removed-log/deep-reorg rollback is not automatic. Keep disabled until those canonical-history/reorg gates, active dispatcher, and operator ownership are reconciled. Replay only from a reviewed canonical checkpoint. |
| `gnosis_legacy` | No independent declaration; compatibility fallback selected by `gnosis` while `isolated_gnosis_indexer_worker` is disabled | Preserve the existing Prefect/persisted-task path as the fallback, not as a second dispatcher. Retire it only after the isolated worker's login, grant, cursor, canonical-history recovery, and owner gates close. |
| `baal` | Repository-native JobSpec; no recurring Prefect, cron, or historical seed schedule is declared | The JobSpec selects the signed `baal_worker` only when `isolated_baal_indexer_worker` is enabled; otherwise it dispatches the compatibility command. Keep the worker disabled until identity/grant, cursor/reorg, output parity, and accountable schedule owner are reviewed. No recurring schedule is registered by this inventory. |
| `baal_legacy` | No independent schedule; compatibility fallback selected by `baal` while `isolated_baal_indexer_worker` is disabled | Preserve as the existing manual/compatibility path only; do not register an additional Baal schedule. Retire after the isolated worker's identity, grants, cursor recovery, and output parity are accepted. |
| `anomaly` | Prefect hourly; deprecated cron and seed hourly | Scheduled execution requires one location and the Prefect adapter fans out over active Kokonut Network locations. Manual anomaly, baseline, and ML checks now require one `--location-id` or explicit `--all-locations`; no-argument invocation prints help, ML training requires one location, and `--list-rules` is an explicit global read. Scoped runs do not bootstrap shared alert-rule references. Native scheduler activation still requires signed worker context, per-location effect/idempotency review, and reconciliation of active external schedules. Retry the same source window only; inspect emitted alerts and actuation approvals first. |
| `anomaly_legacy` | No independent schedule; compatibility fallback selected by `anomaly` while `isolated_sensor_anomaly_scan_worker` is disabled | Keep its required location input and existing manual/Prefect compatibility behavior; do not register a second hourly dispatcher. Retire after the signed worker's identity, per-location effects, and recovery parity are accepted. |
| `freshness` | Prefect hourly; deprecated cron and seed hourly | Native scheduler after its read/alert effects are classified. Recompute the missed interval only if any emitted notification can be deduplicated. |
| `freshness_legacy` | No independent schedule; compatibility fallback selected by `freshness` while `isolated_freshness_worker` is disabled | Preserve the existing compatibility path as the same hourly owner; do not add a duplicate schedule. Retire after the signed read/alert worker and notification idempotency are accepted. |
| `metrics` | Prefect daily at 06:00 UTC; deprecated cron and seed every four hours; legacy seed uses `--all-locations` | The Prefect adapter fans out over active Kokonut Network locations. Native scheduler requires one location and uses `--compute --all`; the database-driven contract rejects `--all-locations`. Reconcile cadence and duplicate output keys before cutover. Recompute creates drafts only; verification remains an independent human action. Do not promote computed output automatically. |
| `noi_snapshots` | Prepared daily native job; not registered in the candidate; no legacy cron/Prefect deployment | Native scheduler after owner approval, exact next-run selection, and reconciliation parity. Upsert by crop-cycle key; rerun reconciliation for the same source state rather than replaying every missed cadence. |
| `dashboards` | Prefect every six hours; deprecated cron and seed every six hours | Native scheduler after named-view and saved-card output parity. Refresh is rebuild-oriented; compare the affected time range and published-only filters before accepting a rerun. |
| `credit_adjustment` | Prefect daily check and manual full-pipeline path; no legacy cron/seed entry | Migration 599 adds a default-off signed, exact-location read worker with a bounded function-only source boundary; the Prefect adapter retains the previous read-only command until `signed_credit_adjustment_worker` is enabled. Disposable PostgreSQL 16 replay verifies latest-summary/fallback parity, cross-location denial, direct-table denial, and no writes. Native plans remain disabled per location; no worker credential/grant or schedule is provisioned. Review output handling, cadence, accountable operator, and owner parity before activation. Never auto-confirm retirement. |
| `remote_sensing` | Prefect every six hours and manual full-pipeline path; internal durable fetch jobs | Every operator CLI and queue-helper mode requires one canonical `--location-id`; list, lookup, provider dispatch, and atomic due-job claim remain within that location. Prefect fans out over active Kokonut Network locations and each worker claims due jobs for one location. Keep one reviewed outer trigger and let the internal durable job system own child attempts; do not also create scheduler rows for the same provider jobs. Reconcile per-provider terminal and no-data states before replay. These query scopes do not establish tenant authorization or RLS ([evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-scope.json); [PostgreSQL evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-postgres.json)). |
| `climate` | Prefect weekly; deprecated cron and seed weekly | `climate_worker` now performs all five sources for one explicit location under default-off signed `climate/ingest` context; the Prefect flow still fans out sequentially over active Kokonut Network locations. Migration 429 bounds location lookup and each source summary/audit write; migration 428 provides GEE location/date/source upserts. Keep native tasks disabled until the feature, exact worker credentials/location grants, real GEE key mount, provider parity, and active schedule ownership are reviewed. The legacy CLI remains manual compatibility; no schedule was activated. |
| `projections` | One-shot ClickHouse outbox command; not declared in Prefect, cron, or seed schedules | Keep under the durable outbox/projection delivery owner. Do not add periodic scheduler rows until the worker, module policy, sink checkpoint, and reconciliation behavior are explicitly defined. Replay from the durable outbox cursor, never from an untracked wall-clock window. |

## Work outside the 23-job catalog

| Work | Current source owner | Policy |
| --- | --- | --- |
| `scripts/health-alert.sh` | The only active entry in the worker crontab, every five minutes | Keep as a separate host/worker health timer until a provider-neutral health and alert contract replaces it. It is a shell/Docker-oriented check, not a `JobSpec`; do not silently add it to database scheduling. |
| `services.events --event-worker` + `services.events --notification-worker` | Separate long-running event dispatcher and notification outbox sender in the worker overlay / Kernel supervisor; `--worker` remains the combined compatibility mode | Keep event claims and notification delivery under their respective durable lease, retry, and dead-letter loops. Do not also run the legacy seed's `services.events --process` every two minutes. |
| `services.events --cleanup` | Historical daily 04:00 UTC task in seed 050; no Prefect or crontab declaration | No recurring owner is established. Cleanup remains default-off and derives its window only from exactly one approved dynamic `event_bus` / `platform_event` policy; there is no `--days` override. It blocks on missing/ambiguous policy and preserves active record-level holds, pending dead letters, and incomplete handler deliveries. Migration 401 adds the policy/hold model, but no period is configured and candidate rollout/acceptance remains open. Add cleanup scheduling only after owner approval and deployment acceptance. |
| ML model retraining | Mentioned only in the weekly flow docstring in the checked-in body | No executable schedule or JobSpec exists. Treat as unscheduled until a concrete operation, artifact versioning, approval, and rollback contract exist. |

The deprecated crontab examples and seed cadences are historical configuration,
not a recovery schedule to reactivate automatically. In particular, sensor and
metrics cadence/input differences must be resolved before any transfer. The
historical seed's event-processing tasks also predate the current long-running
event worker and should not be used alongside it.

## Safe cutover sequence

1. Inventory active schedules and in-flight runs from every configured owner
   (Prefect, crontab, `scheduled_task`, and internal provider queues). Export
   definitions and record the current checkpoint and output counts.
2. Select the accountable operational owner and one dispatcher per job. Confirm
   required secrets, profile dependencies, source inputs, side effects,
   idempotency keys, overlap behavior, timeout, retry ceiling, and manual approval
   boundaries.
3. Resolve each row's open contract above. Set the initial `next_run_at`
   deliberately; never let an overdue schedule imply an automatic catch-up.
4. Disable the previous recurring owner, wait for or reconcile active runs, and
   then register the native definition disabled. Audit its graph and compare its
   arguments, cadence, timeout, retries, dependencies, and window to the reviewed
   export.
5. Enable one job at a time. Observe output lineage and error/retry state for an
   agreed window. Keep a reference query or legacy output for comparison where
   the operation produces derived data.
6. Roll back by disabling the new definition first, reconciling its durable run
   state and side effects, then restoring the prior owner from the export. Never
   enable both owners to “catch up.”

The scheduler's bounded retries and durable leases do not prove application
idempotency. A process retry is permitted only after the domain-side effects
are safe to repeat. Unknown outcomes require operator reconciliation, not
automatic replay.

## Acceptance to close the Batch 4 item

- Reconcile runtime provider state and identify an accountable schedule owner
  for each activated job.
- Resolve all input/cadence discrepancies and no-owner rows.
- Verify each operation's idempotency, dependency/window, bounded retry, and
  replay policy against a scoped fixture.
- Complete one-at-a-time cutover with a retained export, non-overlap evidence,
  output parity, and exercised rollback.

No external Prefect server was queried and no runtime job was run for this
inventory. See [job catalog](orchestration-jobs.md), [schedule planner](scheduler-job-planning.md),
[scheduler activation](scheduler-activation.md), [run windows](scheduler-run-windows.md),
and the [Batch 4 checklist](batches.md).
