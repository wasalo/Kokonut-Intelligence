# Kernel worker operation map

**Reviewed:** 14 October 2026  
**Status:** entrypoint inventory complete; transitive scope, argument, and
authorization contracts remain open.

The machine-readable [operation inventory](worker-operation-map.json) covers
the exact 12 modules in `ALLOWED_SCHEDULED_MODULES` and all five pairs in
`ALLOWED_EVENT_HANDLERS`. A regression test compares those sets with the code
allowlists and checks that each entry has source evidence, a scope description,
data effects, and an idempotency/retry note.

## What this establishes

- Scheduler and spawned event-handler processes inherit the configured shared
  runtime PostgreSQL identity. Neither dispatch path establishes signed tenant
  context.
- The scheduler validates `module_path`, but database-stored `command_args`
  have no per-module schema. Scope and side effects can therefore vary with
  arguments.
- Each entry records the source-visible read/write objects, source scope,
  provider/effect boundary, and known replay behavior. The five event handlers
  also have detailed concurrency and replay evidence in
  [event-handler-concurrency.md](event-handler-concurrency.md).
- The legacy schedule seed contains known mismatches: the sensor task has no
  declared input source, and its empty argument list does not create a sensor
  reading; the climate CLI requires one `--location-id`, while the old seed
  supplies only `--all`. The seed remains excluded from normal Kernel
  bootstrap.

## What remains open

This map is a source inventory, not an ACL, tenant policy, or complete dynamic
call graph. It does not trace every calculator, imported helper, dynamic SQL
fragment, provider implementation, or possible command argument. It also does
not prove external Prefect/host schedules are inactive or that effects are
replay-safe on populated data.

Before worker RLS or runtime-grant reduction:

1. Finish the transitive call graph and reconcile stored argument lists with
   each CLI parser and active schedule owner.
2. Give supported scheduled operations explicit argument contracts; preserve
   currently supported capabilities and keep unreviewed legacy schedules
   disabled.
3. Design a non-forgeable system-worker identity and narrow database operation
   grants. Do not infer a single location for cross-location work.
4. Re-run the reviewed worker operations under the final role in disposable
   PostgreSQL, then repeat lease/retry/effect tests. Candidate rollout and RLS
   remain separate gates.

The inventory-only contract test is `tests/test_worker_operation_map.py`.
The focused source, scheduler and event checks pass 31 tests; the retained
[check record](builds/2026-10-14-recovery/worker-operation-map-check.json)
contains the commands and limitations.
