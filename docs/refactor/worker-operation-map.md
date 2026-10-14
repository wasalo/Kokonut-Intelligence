# Kernel worker operation map

**Reviewed:** 14 October 2026  
**Status:** entrypoint inventory, scheduler argument contracts, and static
local-import closure implemented; runtime effects and authorization boundaries
remain open.

The machine-readable [operation inventory](worker-operation-map.json) covers
the exact 12 modules in `ALLOWED_SCHEDULED_MODULES` and all five pairs in
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
  12 scheduled modules and five allowlisted handler modules. It covers 69
  distinct local source files across 17 operation roots, with 407 import edges,
  no unresolved local modules, and the EventBus's one dynamic handler-import
  site. That site is dispatched through `validate_event_handler` and the exact
  allowlist. Package `__main__.py` entrypoints are included.
- Regenerate or verify the source closure with
  `python3 scripts/worker_source_closure.py --output docs/refactor/worker-source-closure.json`
  or `python3 scripts/worker_source_closure.py --check docs/refactor/worker-source-closure.json`.
  The inventory follows imports conservatively, including imports under
  conditional branches; it is not a function-level call graph and does not
  establish that imported code executes for a particular operation.
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
- The legacy schedule seed contains known mismatches: the sensor task has no
  declared input source, and its empty argument list does not create a sensor
  reading; the climate CLI requires one `--location-id`, while the old seed
  supplies only `--all`; the event-cleanup seed invokes a retention-sensitive
  delete operation. These commands now fail the Kernel argument contract. The
  legacy seed remains excluded from normal Kernel bootstrap.

## What remains open

This map, import closure, and argument schemas are not an ACL, tenant policy,
or complete dynamic call graph. Imported helpers still need function-level
effect tracing; dynamic SQL fragments, database functions/views, provider
implementations, and external effects remain to be traced. The map also does
not prove that external Prefect/host schedules are inactive or that effects
are replay-safe on populated data.

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

The source-closure regression is `tests/test_worker_source_closure.py`; the
inventory-only contract test is `tests/test_worker_operation_map.py`.
The focused source, scheduler and event checks pass 37 tests; the retained
[check record](builds/2026-10-14-recovery/worker-operation-map-check.json)
contains that inventory test evidence. The separate
[scheduler argument contract check](builds/2026-10-14-recovery/scheduled-command-contract-check.json)
passes 77 focused tests across command validation, worker dispatch, and the
curated job runner.
