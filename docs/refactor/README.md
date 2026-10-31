# Kokonut Kernel refactor documentation

## Start here

Read the **[current-state and implementation guide](current-state-and-implementation.md)** first. It is the single consolidated status document for the target architecture, profiles, phase assessment, verified implementation state, open deployment/human gates, and recommended execution sequence.

This folder contains the detailed trackers, design records, inventories, and dated evidence that support that guide. They are intentionally retained for reviewability; they are not independent current-status summaries.

## Source of truth

1. **Current behavior:** source code, migration chain, profile planner, and CI definitions at the checked-out commit.
2. **Current refactor status:** [current-state and implementation guide](current-state-and-implementation.md).
3. **Current acceptance backlog:** [batches checklist](batches.md) and [code-first TODO queue](todo-kernel-refactor.md).
4. **Capability implementation classification:** [capability matrix](capability-matrix.md). A classification such as “prepared” is not production acceptance.
5. **Detailed C1 access-control status:** [C1 runtime ACL closure plan](c1-runtime-acl-closure-plan.md).
6. **Historical sequence:** [progress ledger](progress.md). Entries and counts are dated snapshots, not current deployment claims.
7. **Evidence:** the referenced JSON/log/report artifact, read with its recorded date, source revision, target, and test scope.

The source architecture plan was supplied by the repository owner outside this checkout. Its phase requirements are mapped in [implementation-plan alignment](implementation-plan-alignment.md). The ignored root plan copy is local-only and is not a tracked status source.

## Working records by purpose

| Need | Record |
| --- | --- |
| Understand architecture, current phase, risks, profile readiness, and remaining gates | [Current-state guide](current-state-and-implementation.md) |
| Map source-plan phases to current implementation | [Implementation-plan alignment](implementation-plan-alignment.md) |
| Select a profile and review the exact planner behavior | [Profile selection](profile-selection.md) |
| Prepare the isolated local candidate and its rollout | [Kernel candidate](kernel-candidate.md) |
| Review C1 least-privilege progress and closure criteria | [C1 runtime ACL closure](c1-runtime-acl-closure-plan.md) |
| Track capability coverage | [Capability matrix](capability-matrix.md) |
| Execute and update acceptance work | [Batches](batches.md), [TODO queue](todo-kernel-refactor.md) |
| Review progress over time | [Progress ledger](progress.md) |
| Understand named architecture choices | [Architecture decisions](decisions.md) |
| Inspect schemas, calls, workers, providers, schedules, and reports | The corresponding source inventories and contracts linked from the current-state guide and backlog |
| Find test/replay records | [`builds/`](builds/) |

## Acceptance and change discipline

- Distinguish implemented source, focused tests, disposable-database acceptance, candidate rollout, production acceptance, and owner approval.
- A disposable replay uses synthetic state and does not apply migrations to the candidate, legacy stack, or production.
- A historical evidence file remains immutable evidence of that run. Add a new dated result instead of rewriting its outcome.
- Update the matrix, checklist, TODO queue, and current-state guide when a capability changes status. Keep the detailed progress ledger append-only.
- Do not declare a phase, profile, or capability production-ready from a successful build, isolated unit test, or single migration replay.

## Repository checks

```sh
python3 scripts/check-capability-matrix.py
python3 -m services.migration validate --schemas-only
python3 scripts/runtime_sql_inventory.py --check docs/refactor/runtime-sql-inventory.json
python3 scripts/worker_sql_inventory.py --check docs/refactor/worker-sql-inventory.json
```

For current deployments, identity, recovery, ingress, and target-specific instructions, follow the guides linked from [the current-state document](current-state-and-implementation.md), not dated implementation notes in isolation.
