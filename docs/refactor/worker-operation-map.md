# Kernel worker operation map

**Reviewed:** 16 October 2026

**Status:** entrypoint inventory, scheduler argument contracts, static
local-import closure, signed worker identity primitive, and transaction-bound
Python adapter are implemented. Source integration now exists for the sensor
anomaly handler, all four registered cache invalidation handlers, and the two
global notification enqueue handlers. Signed cache invalidation and isolated
notification enqueue remain opt-in. Migrations 418–419 and the runtime-role
bootstrap now enforce the mobile/worker function ACL boundary in disposable
PostgreSQL. Production credentials and candidate rollout remain open. See the
[worker context contract](worker-tenant-context-contract.md).

The machine-readable [operation inventory](worker-operation-map.json) covers
the exact 16 modules in `ALLOWED_SCHEDULED_MODULES` and all seven pairs in
`ALLOWED_EVENT_HANDLERS`. A regression test compares those sets with the code
allowlists and checks that each entry has source evidence, a scope description,
data effects, and an idempotency/retry note.

The sensor anomaly handler's reads, writes, row scope, and required
authorization boundaries are tracked in the
[sensor anomaly effect contract](worker-sensor-anomaly-effects.json), with a
regression check against this operation inventory. Migrations 405–414 enforce
the anomaly handler's bounded operations in disposable PostgreSQL; this is not
application-wide RLS or proof for other workers.

## What this establishes

- Event dispatch and notification outbox sending now have separate CLI modes
  and Kernel supervisor children; the legacy combined `--worker` mode remains
  available. The handler child keeps service logs on stderr so its JSON result
  stays isolated on stdout. This is process separation only, not a distinct
  database identity.
- Scheduler tasks and EventBus queue/receipt control still use the shared
  runtime PostgreSQL identity. The anomaly handler and all four registered
  cache invalidators have exact source-controlled worker credential routing
  and dedicated connection paths; the cache path remains disabled by default.
  The `data_stale` and `threshold_breached` handlers can opt into a distinct
  notification-enqueue login and bounded function. That path also remains off
  by default, with no shared-DSN fallback when enabled. No actual worker
  credential or location grant is provisioned, and migrations 405–422 have not
  been rolled out to the candidate.
- Module-specific command schemas validate persisted `command_args` before
  schedule activation, `run-now`, generated plans, scheduler-allowlisted
  code-owned job runs, and subprocess creation.
  They check supported options, value formats, required arguments and option
  relationships. Human-review commands, unbounded event workers, event cleanup
  without a retention decision, scheduled sensor ingestion without one
  location-bound driver instance, and weather/anomaly scans without an explicit
  location are rejected.
- A rejected runtime command fails without spawning a process or scheduling a
  retry. The task row is not automatically rewritten; active legacy rows need
  operator review before deployment.
- Each entry records the source-visible read/write objects, source scope,
  provider/effect boundary, and known replay behavior. Event handlers with
  concurrency and replay evidence are documented in
  [event-handler-concurrency.md](event-handler-concurrency.md).
- A generated [static source closure](worker-source-closure.json) records the
  local `services.*` import edges and source files reachable from each of the
  18 scheduled modules and seven allowlisted handler pairs. It covers 85
  distinct local source files across 25 operation roots and 632
  operation/import-edge memberships,
  with no unresolved local modules and the EventBus's one dynamic handler-import
  site. That site is dispatched through `validate_event_handler` and the exact
  allowlist. Package `__main__.py` entrypoints are included.
- Regenerate or verify the source closure with
  `python3 scripts/worker_source_closure.py --output docs/refactor/worker-source-closure.json`
  or `python3 scripts/worker_source_closure.py --check docs/refactor/worker-source-closure.json`.
  The inventory follows imports conservatively, including imports under
  conditional branches; it is not a function-level call graph and does not
  establish that imported code executes for a particular operation.
- A generated [direct function reachability graph](worker-function-reachability.json)
  starts scheduled operations at calls under each executed `__main__` guard and
  event operations at their allowlisted handler. It resolves local/imported
  function calls, module aliases, `self`/`cls` methods, and instance methods
  whose candidate types can be inferred locally. The `services.metrics`
  operation also records each of the 20 functions from its literal
  `CALCULATORS` registry as an explicit registry-dispatch edge. The graph
  resolves callbacks passed to the shared `services.common.cli.run(main)`
  wrapper. EventBus subprocess dispatch is described separately by the worker
  effect inventory, since the handler runner is selected by its process
  command/request protocol rather than a local function call. Across 25
  operation roots and 85 source files, entry functions reach 506 function
  memberships through 714 direct-call and 20 dynamic-dispatch edges, with no unresolved
  operation roots. This remains a conservative source map: callbacks and
  dynamic dispatch outside the pinned registry, unresolved instance types,
  extension code, and database/provider behavior may be absent. Use
  `python3 scripts/worker_function_reachability.py --check docs/refactor/worker-function-reachability.json`
  to check it. The graph is a review aid, not an authorization boundary.
- The direct [SQL execution inventory](worker-sql-inventory.json) finds 307
  Python `.execute` sites in those 85 files. It fingerprints 265 literal
  statements and flags 42 composed/variable statements. Candidate relation tokens are
  extracted for review, but the scanner is regex-based and records no query
  text or values. Use
  `python3 scripts/worker_sql_inventory.py --check docs/refactor/worker-sql-inventory.json`
  to check it. These counts identify review targets and do not establish a
  complete read/write set or a least-privilege grant list.
- A generated [SQL-to-function reachability report](worker-sql-reachability.json)
  joins those 307 sites to the operation graph without including SQL text or
  values. It links 235 unique sites across 289 operation/site memberships;
  72 sites have no current static function match, and each belongs to a
  function absent from all current worker-root graphs. That status does not
  prove the code is dead: external or unmodeled dynamic callers may still
  invoke it. Generic database adapters and other effects remain in review. Use
  `python3 scripts/worker_sql_reachability.py --check docs/refactor/worker-sql-reachability.json`
  to check the report.
- A static-only [worker boundary preflight](worker-boundary-preflight.json)
  combines the allowlists, import closure, function graph, and SQL join. It
  confirms all 25 operation roots and local imports, reports that the scheduler
  and EventBus dispatchers do not establish signed tenant context, and keeps
  RLS blocked. The anomaly, optional cache, NOI snapshot, and weather forecast
  integrations establish context within exact worker paths. It
  explicitly leaves live grants, migration state, active schedules, and owner
  mappings `not_assessed`; it never connects to PostgreSQL. Use
  `python3 scripts/worker_boundary_preflight.py --check docs/refactor/worker-boundary-preflight.json`
  to verify the generated summary.
- A generated [worker effect inventory](worker-effect-inventory.json) scans
  functions in the current reachability graph for high-confidence direct
  process, filesystem, HTTP, email, and EVM call patterns. The current pass
  finds 35 unique candidate sites across 39 operation/site memberships: HTTP
  (12 unique / 15 memberships), email delivery (6), process (1), EVM RPC (3),
  EVM client setup (4), filesystem (8), and dynamic import (1), across 25 operation roots. These are review candidates,
  not confirmed runtime effects. Other worker roots may still conservatively
  include mutually exclusive CLI branches. The credit-adjustment schedule now
  uses a dedicated read-only entrypoint; the interactive issuance/retirement
  CLI is no longer scheduler-allowlisted. Absence from the inventory
  is not proof that an operation has no external effect. Its callback section
  traces the EventBus `subprocess.Popen` child through
  `services.events.handler_runner`, the exact worker-secret environment filter,
  resolver, allowlist validation, dynamic import, and all seven allowlisted
  handler pairs. The trace does not verify persisted handler configuration or
  runtime dispatch. The reachable actuation helper only records
  a human-approval command; no MQTT publisher is called by the worker paths.
  Rebuild or check it
  with `python3 scripts/worker_effect_inventory.py --output
  docs/refactor/worker-effect-inventory.json` or
  `python3 scripts/worker_effect_inventory.py --check
  docs/refactor/worker-effect-inventory.json`. The inventory does not inspect
  provider internals, arbitrary callbacks, database-side effects, or establish
  replay safety, tenant context, or database grants.
- Source-pattern review now covers all 36 dynamic/composed sites. The original
  30-site review found that 21 use fixed
  application-owned fragments with bound values (including two timeout
  constants); three use the fixed `freshness_scope` savepoint name; one builds
  table names from the fixed freshness-source map; one adds fixed optional
  predicates to the anomaly query; and one wraps saved dashboard SQL through
  the separately restricted read-only analytics reader. A worker-source check
  found two imported `query()` callsites in `services.analytics.carbon_balance`
  outside the bounded adjustment-check call path, plus no direct
  `DatabaseConnection.execute()` callers beyond the static SQL reconciliation
  statement in `services.metrics.cli`. Six newly reachable inventory sites
  are also reviewed: carbon-balance queries use fixed SQL strings; the credit
  listing/check queries append only fixed predicates and bind values; and the
  retirement-review f-string selects only fixed timestamp fragments. The
  scheduler contract exposes only the read-only adjustment check. No
  user-derived SQL identifier interpolation was found in these fragments.
- The `services.events` operation entry includes the optional notification
  processor's outbox/attempt writes; the `services.metrics` entry includes the
  code-owned NOI snapshot reconciliation view and natural-key upsert. It now
  links all 20 registered metric calculator implementation files, guarded
  against registry drift by `tests/test_worker_operation_map.py`. Its
  per-calculator direct SQL reads, composed calculator calls, and the consent
  eligibility function's referenced relations are recorded; they still do not
  establish least-privilege grants or tenant context. The freshness operation
  also maps all seven fixed source-table identifiers to required reads, with a
  regression test tying that list to the code map.
- Migration 417 gives the two global notification handlers a bounded enqueue
  function. It verifies the dedicated login, source event ID/type, optional
  location lineage, supported channels and destination, payload size, and
  stable idempotency key before inserting. The login has no direct table or
  sequence privileges; runtime-role provisioning grants only the bounded
  function and rejects other executable `SECURITY DEFINER` functions.
  Notification sending, retry, and dead-letter mutations remain a separate
  worker boundary. Migration application and credential provisioning are
  still deployment gates.
- Scheduled metric computation uses `--compute --all` or a single
  `--metric` with one required `--location-id`. The scheduler rejects the
  service CLI's `--all-locations` mode. The optional Prefect adapter preserves
  its all-location behavior by running one bounded catalog command for each
  active location directly assigned to `kokonut-network`; the lookup is
  read-only and does not establish signed worker tenant context.
- The climate worker entry names all five provider-output relations and records
  that `--worldclim` is a latitude proxy, while four other branches call Google
  Earth Engine. The proxy upsert and location fallback have focused source,
  migration-discovery, and PostgreSQL restored-checkpoint replay coverage; live
  provider acceptance remains open.
- The carbon-credit job's `credit_adjustment` JobSpec uses a dedicated
  `services.analytics.carbon_credit_adjustment_check` entrypoint and requires
  one explicit `--location-id` at the CLI, schedule-plan, and scheduler-command
  boundaries. Unscoped cross-location scans fail before database access. It
  runs inside a database-enforced read-only transaction and only calls the
  recompute-and-report path. The interactive
  credit-management module is no longer scheduler-allowlisted, so its issuance,
  mutation, retirement, and review paths do not enter the worker graph. The
  optional Prefect flow fans out only over active locations assigned to
  `kokonut-network`; native plans remain one disabled task per location.
  Cadence, signed worker identity, output handling, and owner acceptance remain
  open.
- The legacy schedule seed contains known mismatches: the sensor task has no
  declared input source, and its empty argument list does not create a sensor
  reading; the climate CLI requires one `--location-id`, while the old seed
  supplies only `--all`; the event-cleanup seed invokes a retention-sensitive
  delete operation. These commands now fail the Kernel argument contract. The
  legacy seed remains excluded from normal Kernel bootstrap.
- The generated [JobSpec/contract inventory](worker-job-contract-inventory.json)
  compares all 16 shared job templates with the Kernel module allowlist and
  command validation. Five no-input defaults pass and eleven jobs require
  validated runtime inputs; EAS and RPC each require one supported chain.
  Scheduled sensor ingestion requires one
  `--location-id` and one `--driver-instance-id`; the registry accepts only an
  enabled sensor instance assigned to that exact location, and the loaded
  driver must explicitly opt into scheduled pull. The built-in CSV driver is
  pull-capable; MQTT remains event-driven. This source contract does not prove
  a configured instance, active schedule, tenant authorization, or RLS. Remote
  sensing requires one `--location-id` for every CLI mode and
  its due-job API, and scheduled runs remain limited to a sequential
  `--run-jobs --limit` batch of 1–10 due jobs (the default JobSpec runs one),
  while ClickHouse projections are limited to one bounded `--run-once` delivery
  batch. The five-day weather forecast has a default-off
  `services.ingestion.weather_forecast_worker` JobSpec, requires one explicit
  location, and rejects aggregate mode. Its exact scheduler secret route strips
  shared PostgreSQL settings; migration 426 bounds lookup and writes to a signed
  `weather_forecast/ingest` grant. Natural-key upsert, ingestion audit, and
  projection outbox are atomic and replay-safe. Existing persisted tasks using
  `services.ingestion.weather_forecast` remain allowlisted under the shared
  identity until schedule owners reconcile them. The provider key, grant,
  cadence, and active task state remain unconfigured.
  The scheduler contract permits only the bounded run operation; the
  operator CLI and helper APIs require one canonical location for listing,
  lookup, creation, provider dispatch, and due-job claims; there is no global
  queue-claim mode. These query filters do not establish tenant authorization.
  Focused source checks and a disposable PostgreSQL claim probe verify the
  location predicate ([evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-scope.json);
  [PostgreSQL evidence](builds/2026-10-16-recovery/remote-sensing-cli-location-postgres.json)).
  The projection
  contract rejects manual list/replay/disposal/reconcile actions. No task or
  provider is activated. This is the source catalog only; it does not
  reconcile persisted tasks or external schedules. Check it with
  `python3 scripts/worker_job_contract_inventory.py --check
  docs/refactor/worker-job-contract-inventory.json`. Keep the two rejected
  defaults inactive until their source/input contracts are defined. Provider
  credentials, tenant context, and worker identity remain separate gates for
  both provider jobs.

## What remains open

This map, import closure, SQL inventories, effect candidates, job-template
comparison, and argument schemas are not an ACL, tenant policy, or complete
dynamic call graph. Source-pattern review now covers all 42 composed/variable
SQL sites: the prior 36-site review, the remote-sensing update builder, signed
context cleanup, the anomaly worker's generic query wrappers, shared database
helper calls, and the NOI reconciliation's fixed location-filter fragment
with a bound UUID. Reviewed application fragments bind values and use
fixed source-controlled fragments; three generic database-adapter sites remain
`UNKNOWN` because their SQL is supplied by callers, so their complete caller
set still needs tracing. No user-derived identifier interpolation was found
in the reviewed call sites. Keep this review current as the inventory changes. The static call graph
follows local instance types and the explicit metric registry, but 72 SQL sites
still have no direct static function match.
It does not account for all callback/provider dispatch,
database functions/views, extension behavior, or external effects. The map
also does not prove that external Prefect/host schedules are inactive or that
effects are replay-safe on populated data.

Before worker RLS or runtime-grant reduction:

1. Reconcile already-enabled database tasks and external schedule definitions
   against the contracts; review the sensor, climate and cleanup seed rows
   before any activation.
2. Finish the transitive call graph across calculators, helpers, dynamic SQL,
   providers and file/network effects.
3. Extend relation-specific effects and signed context to remaining operations
   using the [worker tenant-context contract](worker-tenant-context-contract.md).
   Keep queue, notification-enqueue, notification-delivery, and
   actuator-transmission identities separate; anomaly and isolated notification
   enqueue now have bounded source paths, while live credentials and candidate
   rollout remain open.
4. Provision worker credentials and exact grants for remaining operations.
   Child environment filtering is implemented, with exact routing for the
   anomaly and cache handlers; the two global notification handlers have a
   separate exact login route. Do not infer a single location for
   cross-location work.
5. Re-run the reviewed worker operations under the final role in disposable
   PostgreSQL, then repeat lease/retry/effect tests. Candidate rollout and RLS
   remain separate gates.

The source-closure regression is `tests/test_worker_source_closure.py`, the
call-graph regression is `tests/test_worker_function_reachability.py`, and
`tests/test_worker_sql_inventory.py` pins the SQL inventory and current
generic-wrapper caller contract; the operation-contract tests are in
`tests/test_worker_operation_map.py`.
The focused source, scheduler and event checks pass 37 tests; the retained
[check record](builds/2026-10-14-recovery/worker-operation-map-check.json)
contains that inventory test evidence. The separate
[scheduler argument contract check](builds/2026-10-14-recovery/scheduled-command-contract-check.json)
passes 77 focused tests across command validation, worker dispatch, and the
curated job runner.
