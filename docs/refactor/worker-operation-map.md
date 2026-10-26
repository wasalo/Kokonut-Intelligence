# Kernel worker operation map

**Reviewed:** 26 October 2026

**Status:** entrypoint inventory, scheduler argument contracts, static
local-import closure, signed worker identity primitive, and transaction-bound
Python adapter are implemented. Source integration now exists for the sensor
anomaly handler, all four registered cache invalidation handlers, and the two
global notification enqueue handlers. Signed cache invalidation, isolated notification enqueue, and isolated delivery
remain opt-in. Migrations 418–419 and the runtime-role
bootstrap enforce the mobile/worker ACL boundary. Default-off dedicated worker
paths cover sensor anomaly, cache invalidation, notification enqueue and
delivery, NOI snapshots, current weather, forecasts, climate, CSV sensor ingestion, remote
sensing, market data, EAS, RPC, Gnosis Moloch, Baal governance, and data
freshness. The global
Baal indexer has migration 644's execute-only database contract and a
worker-specific HTTPS endpoint; migration 644 has disposable PostgreSQL
acceptance but is not rolled out to the candidate. Migration 645 adds the
default-off global freshness worker with a dedicated identity and bounded
functions; its disposable PostgreSQL acceptance passes, but it is not rolled
out to the candidate. The legacy manual CLI remains available. Credentials
and grants for live isolated workers remain unprovisioned. Candidate migration
state is recorded in per-rollout evidence; earlier documentation that cited
migration 433 is a historical checkpoint, not the current schema ledger. See the
[worker context contract](worker-tenant-context-contract.md).

The machine-readable [operation inventory](worker-operation-map.json) covers
the exact 32 modules in `ALLOWED_SCHEDULED_MODULES`, three isolated worker
entrypoints, seven in-process signed source-reader functions, and all seven
pairs in `ALLOWED_EVENT_HANDLERS`. The signed source-reader functions are
function-level roots, not new OS processes or scheduler entries. Notification
delivery and the agent worker CLI remain outside the scheduler allowlist. The
agent worker lists its 12 synthesis-task identities plus the deterministic
summary identity separately; it does not collapse those credentials into a
shared key. Regression tests compare each category with its source registry
and require source evidence, scope, data effects, and idempotency/retry notes.

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
  credential or location grant is provisioned. Migrations through 433 have
  been rolled out to the candidate, but the worker features remain disabled.
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
  local `services.*` import edges and source files reachable from the 32
  scheduled modules, the event-dispatch, notification-delivery, and agent
  worker entrypoints, seven signed source-reader function roots, and seven
  allowlisted handler pairs. It covers 136 distinct local source files across
  49 operation roots, with no unresolved
  local modules and 4 recorded dynamic-import sites. The agent worker's twelve
  synthesis modules are resolved through its literal immutable task registry.
  Other dynamic sites include the
  EventBus handler runner, the general driver registry, and the code-allowlisted
  scheduled sensor-driver loader. EventBus dispatch is constrained by
  `validate_event_handler` and the exact allowlist. The general driver registry
  resolves nine built-ins from `BUILTIN_DRIVER_TARGETS`; third-party adapters
  load only through one matching installed `kokonut.drivers` entry point. A
  persisted module/class pair cannot select an import target. The native sensor
  worker has the narrower `SCHEDULED_SENSOR_DRIVER_TARGETS` registry, and its
  driver class/methods are linked from that source map in the function graph.
  Package `__main__.py` entrypoints are included.
- Regenerate or verify the source closure with
  `python3 scripts/worker_source_closure.py --output docs/refactor/worker-source-closure.json`
  or `python3 scripts/worker_source_closure.py --check docs/refactor/worker-source-closure.json`.
  The inventory follows imports conservatively, including imports under
  conditional branches; it is not a function-level call graph and does not
  establish that imported code executes for a particular operation.
- The agent worker CLI uses task-specific source credentials for each fixed
  synthesis task and the deterministic summary reader. Persistence requires a
  database-registered operator request receipt, while read-only execution does
  not write. The static graph maps all twelve synthesis task keys to the
  instantiated agent classes and follows `synthesize` and
  `collect_source_references`. This records source code reachability, not the
  authentication of a process that invokes the CLI; the request-receipt gate
  remains the write authorization boundary.
- Seven exact agent source-reader functions are separately rooted in the static
  graph: four summary list/digest readers plus EBF evidence-gap, CIDS export,
  and Delphi facilitation readers. They establish their signed, location-scoped
  read context inside the function, validate the relevant location/object IDs,
  and expose only their bounded projections. They are called in-process by
  first-party agent flows; this inventory does not create or imply a separate
  worker credential, scheduler entry, or process boundary.
- The deterministic summary worker's default `summary_builder or build_summary`
  path is represented explicitly, then linked through the literal
  `GENERATORS` registry for operations, financial, environmental, and combined
  summaries. The combined path reaches only the three component generators;
  the worker's validated deterministic-type tuple must stay in the same order
  as the registry. A test-injected builder remains outside this production
  dispatch model. This makes its shared signed summary query helpers visible
  without treating arbitrary callbacks as trusted registry entries.
- A generated [direct function reachability graph](worker-function-reachability.json)
  starts scheduled operations at calls under each executed `__main__` guard,
  the agent worker at its `main` command, event-dispatch and notification
  workers at their source-registered `run_once` entries,
  and event operations at their allowlisted handler. It resolves local/imported
  function calls, module aliases, `self`/`cls` methods, and instance methods
  whose candidate types can be inferred locally. The `services.metrics`
  operation also records each of the 20 functions from its literal
  `CALCULATORS` registry as an explicit registry-dispatch edge. The scheduled
  sensor worker follows `SCHEDULED_SENSOR_DRIVER_TARGETS` to its literal CSV
  driver class, inherited constructor, and `discover`, `fetch_scheduled`, and
  `transform` methods. The agent worker follows its literal task registry to
  the `synthesize` and `collect_source_references` methods for each of twelve
  registered agents. The graph
  resolves callbacks passed to the shared `services.common.cli.run(main)`
  wrapper. EventBus subprocess dispatch is described separately by the worker
  effect inventory, since the handler runner is selected by its process
  command/request protocol rather than a local function call. Across 49
  operation roots and 138 source files, entry functions reach 1,172 function
  memberships through 1,658 direct-call, two exact callback, and 56
  dynamic-dispatch edges, with no unresolved operation roots. The callback
  model includes both the CLI wrapper and the compatibility outbox's bounded
  completion callback. This remains a conservative source map: callbacks and
  dynamic dispatch outside the pinned registry, unresolved instance types,
  extension code, and database/provider behavior may be absent. Use
  `python3 scripts/worker_function_reachability.py --check docs/refactor/worker-function-reachability.json`
  to check it. The graph is a review aid, not an authorization boundary.
- The direct [SQL execution inventory](worker-sql-inventory.json) finds 471
  Python `.execute` sites in 136 statically imported files. It fingerprints
  384 literal statements and flags 87 composed/variable statements. Candidate
  relation tokens are extracted for review, but the scanner is regex-based and
  records no query text or values. Use
  `python3 scripts/worker_sql_inventory.py --check docs/refactor/worker-sql-inventory.json`
  to check it. These counts identify review targets and do not establish a
  complete read/write set or a least-privilege grant list.
- A generated [SQL-to-function reachability report](worker-sql-reachability.json)
  joins those 471 sites to the operation graph without including SQL text or
  values. It links 404 unique sites across 585 operation/site memberships;
  67 sites have no current static function match, and each belongs to a
  function absent from all current worker-root graphs. That status does not
  prove the code is dead: external or unmodeled dynamic callers may still
  invoke it. Generic database adapters and other effects remain in review. Use
  `python3 scripts/worker_sql_reachability.py --check docs/refactor/worker-sql-reachability.json`
  to check the report.
- A static-only [worker boundary preflight](worker-boundary-preflight.json)
  combines the allowlists, import closure, function graph, and SQL join. It
  confirms all 49 operation roots and local imports, reports that the scheduler
  and EventBus dispatchers do not establish signed tenant context, and keeps
  RLS blocked. The seven signed source-reader function roots establish context
  within their own calls, not at dispatch. Its database-identity summary now records that source policy
  varies by operation and live provisioning is not assessed. The anomaly, optional cache, NOI snapshot, current-weather,
  weather-forecast, climate, sensor-ingestion, and remote-sensing integrations establish
  context within exact worker paths. Global freshness, RPC, EAS, and chain-indexer
  workers intentionally do not establish farm tenant context. It
  explicitly leaves live grants, migration state, active schedules, and owner
  mappings `not_assessed`; it never connects to PostgreSQL. Use
  `python3 scripts/worker_boundary_preflight.py --check docs/refactor/worker-boundary-preflight.json`
  to verify the generated summary.
- A generated [worker effect inventory](worker-effect-inventory.json) scans
  functions in the current reachability graph for high-confidence direct
  process, filesystem, HTTP, email, and EVM call patterns. The current pass
  finds 70 unique candidate sites across 98 operation/site memberships: HTTP
  (12 unique / 24 memberships), email delivery (3 / 9), process (1), EVM RPC
  (9 / 13), EVM client setup (6 / 10), filesystem (37 / 38), and dynamic import
  (2 / 3), across 49 operation roots. Filesystem matching includes path
  resolution/directory checks, descriptor opens, metadata checks, and cleanup;
  the scheduled CSV driver's constrained openat walk is visible in the
  sensor-worker trace. These are review candidates,
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

The manual driver-loader boundary was hardened after the preceding inventory
snapshot. Built-in registry rows must exactly match a source-owned target;
custom code is resolved by installed Python package entry point and the row's
module/class fields must match that entry point. The loader checks the adapter
class contract and closes the metadata-read transaction before importing code.
This does not sandbox installed packages, inspect their dependencies, or prove
that a driver is safe to install. `DriverRegistry.load` is not statically
reachable from the allowlisted scheduled sensor operation; that worker
continues to use only `SCHEDULED_SENSOR_DRIVER_TARGETS`.
- The earlier source-pattern review covered 48 composed/variable statements
  and the isolated dispatcher's parameterized call to seven fixed,
  source-owned migration functions. With the agent task modules included, the
  generated SQL inventory now reports 87 composed/variable sites across 49
  operation roots. The 36 new non-literal sites exposed by the added worker
  closure (34 in agent modules and two imported modules) have a source-pattern
  review in [worker-sql-source-pattern-review.json](worker-sql-source-pattern-review.json).
  It found source-owned SQL fragments and separately bound values for those
  call paths. The scanner retains its conservative `fstring` and
  `composed_or_variable` labels; this review does not approve those statements
  as ACL input or verify live grants. The original 30-site
  review found that 21 use fixed
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
  scheduler contract exposes only the read-only adjustment check. The
  reviewed fragments use fixed identifiers and bound values; synthesis SQL
  findings are recorded separately in the source-pattern review artifact.
- The `services.events` operation entry describes the legacy event and optional
  notification processors. Migration 648 has a separate isolated dispatcher
  entry and identity: it owns global queue claims and handler receipts, while
  event publication remains in the caller's transaction. The `services.metrics` entry includes the
  code-owned NOI snapshot reconciliation view and natural-key upsert. It now
  links all 20 registered metric calculator implementation files, guarded
  against registry drift by `tests/test_worker_operation_map.py`. Its
  per-calculator direct SQL reads, composed calculator calls, and the consent
  eligibility function's referenced relations are recorded; they still do not
  establish least-privilege grants or tenant context. The legacy freshness
  operation maps all seven fixed source-table identifiers to required reads,
  with a regression test tying that list to the code map. The isolated path
  replaces direct reads and writes with migration 645 functions and a dedicated
  global control-plane identity; it reads bounded timestamps for both global
  and explicitly location-scoped sources without establishing farm context.
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
- The legacy climate entry names the five provider-output relations and keeps
  the `climate_data` CLI available for manual compatibility. The native JobSpec
  now routes through `services.ingestion.climate_worker`, which requires one
  explicit location, uses only the exact climate worker DSN/credential/GEE key
  path, and reaches location/bbox data and the five summary/audit writes only
  through migration 429's signed bounded functions. The latitude proxy remains
  explicit, and GEE requests remain external provider effects. All five source
  writes, failure audit, retries, scope denial, and forced-RLS privilege
  boundaries pass disposable PostGIS checks; no real provider, key, schedule,
  or candidate database was used.
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
  compares all 22 shared job templates with the 30-module Kernel allowlist and
  command validation. Nine no-input defaults pass and thirteen jobs require
  validated runtime inputs; EAS and RPC each require one supported chain.
  Scheduled sensor ingestion requires one
  `--location-id` and one `--driver-instance-id`; the registry accepts only an
  enabled sensor instance assigned to that exact location, and the loaded
  driver must explicitly opt into scheduled pull. The built-in CSV driver is
  pull-capable; MQTT remains event-driven. This source contract does not prove
  a configured instance, active schedule, tenant authorization, or RLS. The
  legacy current-weather entrypoint now writes each observation and success
  audit in the same transaction, with a savepoint per location; a failed
  location is rolled back before its sanitized failure audit, and projection
  failure rolls back observations and audits together. This compatibility path
  still has no receipt or source watermark, so a retry can duplicate a
  PostgreSQL observation. The native default-off current-weather JobSpec uses
  its isolated signed worker; persisted legacy schedules still need owner
  reconciliation. Remote
  sensing requires one `--location-id` for every legacy CLI mode and its
  due-job API. New native JobSpecs use the default-off
  `services.ingestion.remote_sensing_worker`; migration 432 gives it a distinct
  login, signed `remote_sensing/run` location grant, and bounded atomic claim,
  attempt, observation, audit, and outbox functions. Its provider adapters
  return normalized records without opening a database connection. The optional
  runtime-role bootstrap provisions that login only after migration 432 and
  grants it a non-inheriting SET boundary to the worker execution role; Compose
  keeps its database password in the one-shot bootstrap environment. No
  deployment credential is configured by this source slice. The legacy
  `remote_sensing_fetcher` remains allowlisted for manual use and persisted task
  compatibility until owners reconcile those rows. The signed worker accepts
  one location and a bounded batch, while ClickHouse projections are limited
  to one bounded `--run-once` delivery
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
  defaults inactive until their source/input contracts are defined. Remote
  sensing and climate workers remain disabled until their dedicated credentials,
  signed location grants, provider configuration, and owner-reviewed schedules
  are provisioned. Neither disposable acceptance nor these source contracts
  prove live-provider parity or candidate deployment.

## What remains open

This map, import closure, SQL inventories, effect candidates, job-template
comparison, and argument schemas are not an ACL, tenant policy, or complete
dynamic call graph. The prior source-pattern review covered 48 of the earlier
composed/variable SQL sites. The current inventory reports 87 across 42
operation roots. The 36 new non-literal sites exposed by the registered agent
worker closure are source-pattern reviewed in
[worker-sql-source-pattern-review.json](worker-sql-source-pattern-review.json);
they remain excluded from ACL approval pending live role and view-grant
verification. The prior review covered the
remote-sensing update builder, signed
context cleanup, the anomaly worker's query helpers, shared database helper
calls, the NOI reconciliation's fixed location-filter fragment with a bound
UUID, the climate worker's fixed migration-function calls, and the isolated
EventBus adapter's fixed bounded-function calls. The anomaly
worker's `_one`/`_many` helpers now accept only one of twelve named operations
from an immutable map of fixed SQL; an AST regression pins every call site to a
literal operation name, and unknown names fail before cursor access. The worker
and runtime SQL inventories recognize this guarded immutable map and record
all twelve variants for each of its two execution sites using operation names,
statement kinds, relation candidates, and hashes only. The three shared
database-adapter sites remain `UNKNOWN`. Three additional statements are also
kept `UNKNOWN` by the automated inventory: the registered agent provenance
query, organic-readiness fixed query map, and CIDS fixed query tuple. Their
source patterns are reviewed in the linked artifact, but their scanner
classification remains conservative. The worker-closure regression now
pins their known callers to two literal `SELECT` templates in carbon-balance
code and one source-owned `INSERT` f-string in the manual NOI command. These
checks do not cover every application caller or turn the generic wrappers into
bounded APIs. The isolated EventBus, Baal, Gnosis, and freshness worker
adapters are now traced through exact same-class caller bindings: 32 literal
query variants are recorded as statement kinds, relation candidates, and
hashes, without storing query text or parameter values. Gnosis storage no
longer interpolates a caller-supplied function name into SQL; each operation
uses its own literal bounded-function query. The GEE climate persistence helper
is resolved from its four same-module callers, each of which supplies a literal
query template and binds values separately. Reviewed application fragments use
fixed source-controlled SQL and bound values.
No user-derived identifier interpolation was found in the reviewed call sites.
Keep this review current as the inventory changes. The static call graph
follows local instance types, explicit metric-registry dispatch, and exact
keyword-bound class instances passed into statically resolved functions. This
now traces the injected Baal, Gnosis, and freshness persistence adapters
through their legacy processing functions. The scheduled ClickHouse outbox
compatibility route now follows its nested `command` callback and the
`deliver_claimed_batch` completion callback into `_finish`; its six direct SQL
sites are visible in that operation path. This is source tracing only: the
compatibility route still uses its legacy shared application identity, while
the separate isolated worker uses the dedicated bounded-function identity. At
that callback-tracing snapshot, 69 SQL sites had no direct static function
match. The unused private `_query_latest_ingestion` and `_query_active_jobs`
helpers have since been removed after repository-wide caller searches;
freshness continues through `_query_latest_data_at`, and remote-sensing
execution uses the location-scoped lease claim. The refreshed inventory has
67 unmatched sites.
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
   separate exact login route. Synthesis, EBF evidence gaps, CIDS, and Delphi
   now have separate source credentials and narrowly granted reader roles.
   These remain unprovisioned in deployment until controlled credential and
   grant setup is completed. Do not infer a single location for cross-location
   work.
5. Re-run the reviewed worker operations under the final role in disposable
   PostgreSQL, then repeat lease/retry/effect tests. Candidate rollout and RLS
   remain separate gates.

The source-closure regression is `tests/test_worker_source_closure.py`, the
call-graph regression is `tests/test_worker_function_reachability.py`, and
`tests/test_worker_sql_inventory.py` pins the SQL inventory and current
generic-wrapper caller contract plus bounded worker-adapter variants; the
operation-contract tests are in
`tests/test_worker_operation_map.py`.
The focused source, scheduler and event checks pass 37 tests; the retained
[check record](builds/2026-10-14-recovery/worker-operation-map-check.json)
contains that inventory test evidence. The separate
[scheduler argument contract check](builds/2026-10-14-recovery/scheduled-command-contract-check.json)
passes 77 focused tests across command validation, worker dispatch, and the
curated job runner.


## Isolated notification delivery worker (25 October 2026)

Migration 647 adds a dedicated login with only bounded notification claim and
attempt-completion functions. The function owner has table-level UPDATE on the
outbox because PostgreSQL requires it for `SELECT ... FOR UPDATE`; that owner
is NOLOGIN and the delivery login has no direct table, column, or sequence
access. The worker commits claims before external sends and fences completion
by worker ID, lease token, attempt number, and lease expiry. The legacy
`--notification-worker` and reviewed operator stats/dead-letter actions remain
available. The `notification-isolated` Compose profile and both feature flags
remain inactive until credential/DSN provisioning and the separate candidate
rollout gate close. Disposable PostgreSQL 16 forced-RLS acceptance and evidence
are in [the batch record](batches.md) and
[the migration evidence](builds/2026-10-25-recovery/notification-delivery-worker-disposable.json).
