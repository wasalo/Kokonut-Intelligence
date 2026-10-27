# Architecture implementation plan alignment

**Source:** owner-provided *Architecture refactor implementation plan*,
prepared 9 October 2026. The supplied file is in the owner's Downloads folder
and is not copied into this repository. This crosswalk maps its Phase 0–8
criteria to the current tracked phase ledger and the 26 October sprint evidence.
The phase table in [progress.md](progress.md#phase-ledger) remains the detailed
repository status record.

The source plan's governing decisions remain the right frame for implementation:
PostgreSQL/PostGIS is canonical, Kokonut owns policy and domain behavior,
capabilities remain available behind replaceable adapters, migrations are
additive, and analytics are rebuildable projections. The plan explicitly says
not to rewrite the schema or domain modules just to reduce deployment weight.
The current work therefore proceeds capability by capability, and preserves
human review, consent, evidence privacy, and Web3 as a proof layer.

| Source phase | Current repository status | What is still required by the source plan |
| --- | --- | --- |
| 0 — Pin baseline and freeze capabilities | Inventory and matrix are established; closure remains partial. | Reconcile owners and consumers, active provider state, logical data, and recovery/retention for every external store. The source plan requires this before retiring data or dependencies. |
| 1 — Introduce ports without behavior changes | Typed settings and ports exist in selected paths; acceptance remains open. | Complete import/config/contract checks and audit remaining storage and domain construction paths; prove optional dependencies can be absent. |
| 2 — Ship minimal PostgreSQL + Kokonut runtime | Minimal profiles and current-source app runtime exist; full governed workflow acceptance remains open. | Demonstrate create, submit, independent verify, publish, metric/report, scheduled retry, Field Collector sync and accepted-work recovery without optional hosts. |
| 3 — Make analytics and Metabase optional | Partial; Postgres query contracts and selected reporting paths exist. | Close report/dashboard output and tenant parity, projection rebuild/outage recovery, and demonstrate Metabase remains optional. |
| 4 — Move orchestration to the owned scheduler | Scheduler durability and job contracts are implemented for selected jobs; provider reconciliation/transfer remains open. | Assign owners and state to all active schedules, migrate one job at a time, and prove retry/cancellation/recovery without duplicate side effects. |
| 5 — Make Redis optional | Optional cache path exists; complete minimal-without-Redis acceptance remains open. | Show cache loss only affects performance and prove durable auth, revocation, audit, retry, and multi-replica behavior. |
| 6 — Make IoT, gRPC and proxy optional edges | Compose/profile boundaries and substantial transport tests exist; external transport parity remains open. | Verify HTTP/MQTT semantics, gRPC authorization parity, trusted proxy behavior, and Caddy/external ingress paths while minimal has no edge dependency. |
| 7 — Replace Directus as primary application API | Active, partial route-by-route Gateway migration. | Complete collection/workflow parity for fields, authorization, lifecycle, audit, consent, exports, SDKs, and reviewer/agent boundaries; keep unmigrated Directus paths available during transition. |
| 8 — ARM64, scale and retire transition dependencies | ARM64 build and emulated schema/runtime preparation exists; the current full schema replay passed. | Complete constrained-runtime, offline backup/restore, scale reliability, and removal/rollback criteria. Physical Raspberry Pi measurement cannot be claimed without hardware; use ARM64 emulation and code-based resource checks until hardware is available. |

## How the current sprint maps

The [authenticated farm workflow and recovery sprint](sprint-kernel-workflow-acceptance.md)
is a Phase 7 vertical slice, with Phase 2's minimal runtime and Phase 8's
recovery/ARM64 criteria as prerequisites and acceptance checks. It exercises
the source plan's canonical API, same-policy transports, location scope,
governed lifecycle, and durable recovery invariants. It is deliberately not a
claim that any full source phase is complete.

The recent isolated 642-schema replay and two-tenant operator probe support
Phase 0/2/7/8 evidence. The ZITADEL startup/discovery check supports only the
identity infrastructure prerequisite for Phase 7; browser PKCE, trusted HTTPS,
client provisioning, Gateway sessions and end-to-end tenant authorization
remain open. The observed 1,101 public tables with runtime DML and RLS disabled
are a concrete Phase 7 least-privilege/RLS gap, not proof of cross-tenant data
exposure in every table.

## Source-plan caveats for current execution

The attached plan describes a cached repository snapshot and lists OneDev
build files/workflow assumptions. The current repository has since returned to
GitHub and uses the branch/PR procedure in [AGENTS.md](../../AGENTS.md); the
historical OneDev paths are not instructions for current Git operations. Its
suggested file names are inspection leads, not commitments: use the current
profile planner, Compose overlays, Gateway, migrations, tests and phase ledger
as implementation truth. The plan's completion definition still applies:
minimal runtime parity, independently optional dependencies, durable canonical
state, proven governance/privacy/Web3 behavior, and ARM64 recovery evidence.
