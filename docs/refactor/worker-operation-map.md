# Kernel worker operation map

**Reviewed:** 14 October 2026  
**Status:** entrypoint inventory, scheduler argument contracts, and static
local-import closure implemented; runtime effects and authorization boundaries
remain open.

The machine-readable [operation inventory](worker-operation-map.json) covers
the exact 13 modules in `ALLOWED_SCHEDULED_MODULES` and all five pairs in
`ALLOWED_EVENT_HANDLERS`. A regression test compares those sets with the code
allowlists and checks that each entry has source evidence, a scope description,
data effects, and an idempotency/retry note.

## What this establishes

- Scheduler and spawned event-handler processes inherit the configured shared
  runtime PostgreSQL identity. Neither dispatch path establishes signed tenant
  context.
- Module-specific command schemas validate persisted `command_args` before
  schedule activation, `run-now`, generated plans, scheduler-allowlisted
  code-owned job runs, and subprocess creation.
  They check supported options, value formats, required arguments and option
  relationships. Human-review commands, unbounded event workers, event cleanup
  without a retention decision, and source-less recurring sensor ingestion are
  rejected.
- A rejected runtime command fails without spawning a process or scheduling a
  retry. The task row is not automatically rewritten; active legacy rows need
  operator review before deployment.
- Each entry records the source-visible read/write objects, source scope,
  provider/effect boundary, and known replay behavior. The five event handlers
  also have detailed concurrency and replay evidence in
  [event-handler-concurrency.md](event-handler-concurrency.md).
- A generated [static source closure](worker-source-closure.json) records the
  local `services.*` import edges and source files reachable from each of the
  13 scheduled modules and five allowlisted handler modules. It covers 73
  distinct local source files across 18 operation roots and 429 import edges,
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
  `CALCULATORS` registry as an explicit registry-dispatch edge. A focused
  callback edge follows the EventBus's statically named multiprocessing target
  to `_handler_process` and its local resolver. Across 18 operation roots, 46
  entry functions reach 367 function memberships through 503 direct-call,
  one callback, and 20 registry-dispatch edges, with no unresolved
  operation roots. This remains a conservative source map: callbacks and
  dynamic dispatch outside the pinned registry, unresolved instance types,
  extension code, and database/provider behavior may be absent. Use
  `python3 scripts/worker_function_reachability.py --check docs/refactor/worker-function-reachability.json`
  to check it. The graph is a review aid, not an authorization boundary.
- The direct [SQL execution inventory](worker-sql-inventory.json) finds 244
  Python `.execute` sites in those 73 files. It fingerprints 208 literal
  statements and flags 36 f-string/composed/variable statements; three
  generic adapter statements have an unknown leading kind. Candidate relation tokens are
  extracted for review, but the scanner is regex-based and records no query
  text or values. Use
  `python3 scripts/worker_sql_inventory.py --check docs/refactor/worker-sql-inventory.json`
  to check it. These counts identify review targets and do not establish a
  complete read/write set or a least-privilege grant list.
- A generated [SQL-to-function reachability report](worker-sql-reachability.json)
  joins those 244 sites to the operation graph without including SQL text or
  values. It links 210 sites across 251 operation/site memberships;
  34 sites have no current static function match, and each belongs to a
  function absent from all current worker-root graphs. That status does not
  prove the code is dead: external or unmodeled dynamic callers may still
  invoke it. Generic database adapters and other effects remain in review. Use
  `python3 scripts/worker_sql_reachability.py --check docs/refactor/worker-sql-reachability.json`
  to check the report.
- A static-only [worker boundary preflight](worker-boundary-preflight.json)
  combines the allowlists, import closure, function graph, and SQL join. It
  confirms all 18 operation roots and local imports, reports the shared runtime
  database identity with no signed tenant context, and keeps RLS blocked. It
  explicitly leaves live grants, migration state, active schedules, and owner
  mappings `not_assessed`; it never connects to PostgreSQL. Use
  `python3 scripts/worker_boundary_preflight.py --check docs/refactor/worker-boundary-preflight.json`
  to verify the generated summary.
- A generated [worker effect inventory](worker-effect-inventory.json) scans
  functions in the current reachability graph for high-confidence direct
  process, filesystem, HTTP, email, object-storage, EVM, notification, cache,
  and dynamic-import call patterns. The current pass finds 40 unique candidate
  sites across 45 operation/site memberships: HTTP (8), email delivery (6),
  process lifecycle (5), EVM RPC (6), EVM client setup (6), filesystem (8),
  and dynamic import (1), across 18 operation roots. These are review candidates,
  not confirmed runtime effects:
  the module graph conservatively includes mutually exclusive CLI branches,
  so the carbon-credit entry also surfaces on-chain functions that its
  scheduled `--check-adjustments` contract rejects. Absence from the inventory
  is not proof that an operation has no external effect. Its callback section
  traces the EventBus process target through `resolve_handler`, the allowlist
  validator, dynamic import, and the five code-allowlisted handler names. The
  graph follows the local child and resolver functions but not the dynamically
  selected handlers; persisted handler configuration and runtime dispatch are
  unverified. The reachable actuation helper only records
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
- The climate worker entry names all five provider-output relations and records
  that `--worldclim` is a latitude proxy, while four other branches call Google
  Earth Engine. The proxy upsert and location fallback have focused source,
  migration-discovery, and PostgreSQL restored-checkpoint replay coverage; live
  provider acceptance remains open.
- The carbon-credit job now has a bounded command contract for the existing
  `credit_adjustment` JobSpec: only read-only `--check-adjustments` is accepted,
  optionally scoped to one location. It does not schedule or enable the Prefect
  flow. Mutation and retirement-review flags remain outside the scheduler
  contract; cadence, tenant identity, output handling, and owner acceptance stay
  open.
- The legacy schedule seed contains known mismatches: the sensor task has no
  declared input source, and its empty argument list does not create a sensor
  reading; the climate CLI requires one `--location-id`, while the old seed
  supplies only `--all`; the event-cleanup seed invokes a retention-sensitive
  delete operation. These commands now fail the Kernel argument contract. The
  legacy seed remains excluded from normal Kernel bootstrap.

## What remains open

This map, import closure, SQL inventories, effect candidates, and argument
schemas are not an ACL, tenant policy, or complete dynamic call graph. All 36 composed/variable sites
have source-pattern review; the static call graph follows local instance types
and the explicit metric registry, but 34 SQL sites still have no direct static
function match. It does not account for all callback/provider dispatch,
database functions/views, extension behavior, or external effects. The map
also does not prove that external Prefect/host schedules are inactive or that
effects are replay-safe on populated data.

Before worker RLS or runtime-grant reduction:

1. Reconcile already-enabled database tasks and external schedule definitions
   against the contracts; review the sensor, climate and cleanup seed rows
   before any activation.
2. Finish the transitive call graph across calculators, helpers, dynamic SQL,
   providers and file/network effects.
3. Design a non-forgeable system-worker identity and narrow database operation
   grants. Do not infer a single location for cross-location work.
4. Re-run the reviewed worker operations under the final role in disposable
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
