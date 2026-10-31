# Architecture implementation plan alignment

**Source:** owner-provided *Architecture refactor implementation plan*,
prepared 9 October 2026. The supplied file is in the owner's Downloads folder
and is not copied into this repository. This crosswalk maps its Phase 0–8
criteria to the tracked phase ledger and dated evidence. For current readiness,
read [the consolidated current-state guide](current-state-and-implementation.md);
the phase table in [progress.md](progress.md#phase-ledger) and sprint notes below
are historical snapshots unless explicitly refreshed.

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
| 8 — ARM64, scale and retire transition dependencies | ARM64 builds and emulated schema/runtime checks exist; current full-schema replay status is tracked in the consolidated guide and dated evidence. | Complete constrained-runtime, offline backup/restore, scale reliability, and removal/rollback criteria. Physical Raspberry Pi measurement cannot be claimed without hardware; use ARM64 emulation and code-based resource checks until hardware is available. |

## How the current sprint maps

The [authenticated farm workflow and recovery sprint](sprint-kernel-workflow-acceptance.md)
is a Phase 7 vertical slice, with Phase 2's minimal runtime and Phase 8's
recovery/ARM64 criteria as prerequisites and acceptance checks. It exercises
the source plan's canonical API, same-policy transports, location scope,
governed lifecycle, and durable recovery invariants. It is deliberately not a
claim that any full source phase is complete.

The 642-schema replay and the 1,101-relation runtime-DML observation were
reported in an earlier sprint snapshot and are superseded by the migration-699
ACL report and later migration/replay evidence. They measure different schema
revisions and must not be read as current counts. The ZITADEL
startup/discovery check supports only the identity infrastructure prerequisite
for Phase 7; browser PKCE, trusted HTTPS, client provisioning, Gateway sessions
and end-to-end tenant authorization remain open. Current C1 counts and replay
status are maintained in the [consolidated guide](current-state-and-implementation.md)
and [C1 closure plan](c1-runtime-acl-closure-plan.md).

## Deployment-profile alignment

The source plan's Standard profile includes Caddy as the TLS ingress layer.
The current `scripts/kernel-profile.py standard` composition now includes
`docker-compose.kernel-proxy.yml` by default, with host listeners bound to
loopback. `standard --no-proxy` selects an externally managed ingress, and
`standard --oidc` keeps Caddy without a redundant flag. This closes the
source-plan/profile-selection mismatch; it does not establish public ingress,
trusted-proxy, DNS, firewall, certificate-trust, or production acceptance.
See the [current profile summary](current-state-and-implementation.md#deployment-profiles-in-the-current-planner)
and [Standard profile guide](standard-profile.md).

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
