# CAP-035 source-to-route effects audit

**Snapshot:** 20 October 2026. This is a repository source audit, not runtime,
provider, populated-data, or tenant-isolation acceptance.

## Scope and method

Reviewed the legacy lifecycle modules under `services/innovation/`, the
location-scoped Gateway lifecycle routes/actions/reads, and module-qualified
service call sites under `services/`. The search found no module-qualified
production service callers for these legacy functions; tests and external
imports may still call them. No candidate, legacy, archived, or populated
database was inspected.

The audit asks whether a legacy write has an equivalent scoped Kernel path and
whether the old helper itself is prevented from bypassing it. A matching route
does not retire a shared-role helper automatically.

## Closed in this slice

`services.innovation.solution_scale.record_learning` used to insert directly
into `solution_learning_record` without a signed location grant, validated
replication lineage, independent review, or an idempotency receipt. It now fails
before database access. Learning proposals remain available through
`POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning`;
independent review and accepted-only application remain separate exact-location
actions. A mocked regression verifies rejection before cursor/commit access,
and the existing database-backed regression now expects the legacy helper to
reject the write.

`services.innovation.solution_adoption.record_event` also trusted a
caller-supplied `consent_checked` boolean before inserting events. The canonical
`stakeholder_consent` stream is party-linked, but adoption programs do not yet
carry a consent policy and adoption references are not linked to a canonical
participant party. The helper now fails before database access even when
`consent_checked=True`. Mocked regressions cover both boolean values. This
retires the unsafe legacy write; it does not replace adoption event collection.
A consent-aware, exact-location Gateway write remains required.

`services.innovation.solution_lifecycle.transition` also issued direct stage and
lifecycle-event SQL outside the signed tenant boundary. Its direct writer now
fails before database access. Migration 486 covers only the gate-backed
promotion targets through
`POST /operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/transition`.
Migration 503 adds bounded target reads and an exact-location Gateway action for
the remaining nonterminal, non-promotion stages. It rejects promotion stages,
retirement, and supersession so those cannot bypass gate review or the reviewed
retirement/replacement workflow. Transitioning to `adopting` retains the
approved location readiness/configuration prerequisite. The experiment test
fixture now sets its starting stage directly as fixture data rather than
calling the legacy writer.

`solution_lifecycle.create_solution` now fails before database access. Migration
504 adds `POST /operator/api/solution-lifecycle/{location_id}/solutions`, which
creates one discovered solution with an immutable exact location origin, active
human attribution, opening lifecycle event, and private idempotency receipt.
The console exposes it only under exact location read/create grants. The
operation creates neither a cross-location link nor a custom stage gate.
`solution_lifecycle.add_link` and `create_gate` also now fail before database
access: links need a reviewed network/location sharing policy, and gate
definitions need a location-scoped configuration/review contract. Their
capabilities remain open; shutting the unscoped helper does not claim parity.

Other legacy direct mutation helpers already fail closed:

| Legacy helper | Scoped path |
| --- | --- |
| `create_gate`, `evaluate_gate` | Scale-gate assessment and independent review |
| `record_learning`, `apply_learning` | Learning proposal/review/application |
| `propose_retirement`, `approve_retirement` | Retirement proposal and independent review |
| `solution_adoption.record_event` | No write route yet; the helper is now fail-closed until policy-backed participant and consent linkage is implemented. |
| `solution_lifecycle.approve_gate`, `evaluate_gate` | Exact-location human review/approval and evidence-backed evaluation actions remain available through the Gateway. |
| `solution_lifecycle.transition` | Shared-role writer retired. Gate-backed promotion transitions remain available through migration 486; retirement uses migration 502. |
| `solution_lifecycle.create_solution` | Exact-location discovered-solution creation is available through migration 504; the legacy shared-role helper is retired. |
| `solution_lifecycle.add_link` | No link-management route yet; legacy writer is retired pending explicit sharing policy. |
| `solution_lifecycle.create_gate` | The legacy writer is retired; use migration 505's exact-origin, location-scoped draft gate definition route. |

## Remaining source-to-route effects

These source paths still need action-level decisions and parity work. Do not
mark CAP-035 complete or claim universal tenant isolation while they remain.

| Legacy module and effect | Current Gateway coverage | Remaining work |
| --- | --- | --- |
| `solution_lifecycle.transition` for non-promotion stages | Migration 503 provides a bounded exact-origin target read and a signed exact-location action for nonterminal, non-promotion stages. It requires an active human binding, explicit acknowledgement, rationale/evidence, expected-stage compare-and-set, and an atomic immutable retry receipt. `adopting` rechecks approved location readiness/configuration; `superseded` and `retired` remain on the reviewed retirement workflow. | Compare behavior against populated legacy fixtures; complete live OIDC/browser acceptance, broader ACL/RLS review, recovery acceptance, and remaining source-to-route parity. |
| `solution_lifecycle.create_solution` | Migration 504 adds exact-location discovered creation with signed create grant, active human attribution, an opening lifecycle event, bounded inputs, and an immutable retry receipt. | Compare created records against populated legacy fixtures; complete live OIDC/browser acceptance, ACL/RLS review, and recovery acceptance. |
| `solution_lifecycle.add_link` | No link-management route. The direct helper now fails before database access. | Define reviewed network/location sharing, owner authority, revocation, and lineage rules before adding a route. |
| `solution_lifecycle.create_gate` | Migration 505 adds exact-origin promotion-gate definition at `POST /operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/gates`. The legacy direct helper remains retired. New definitions are immutable drafts with a bounded criterion and thresholds, one of four fixed current-stage promotions, one required evaluation, and independent human approval. The existing review projection exposes criterion only to the owning location. | Compare gate criteria and threshold semantics against populated legacy records; complete live OIDC/browser acceptance, broader ACL/RLS review, recovery acceptance, and remaining source-to-route parity. Gate evaluation, approval, and transition remain separate actions. |
| `solution_experiments.create_experiment`, `submit_protocol`, `approve_protocol`, `start_experiment`, `record_observation`, `complete_experiment`, `analyze_sequentially` | Migrations 506–510 provide exact-origin immutable protocol drafts, owner submission, private independent approval, exact-location start, and consent-aware observation capture. Migration 510 requires signed `solution_lifecycle:collect` context, validates the protocol-declared participant consent purpose/version or approved non-personal basis, rechecks participant link and current consent, and records an immutable retry receipt atomically. Forced RLS hides withdrawn and unassessed legacy rows. All legacy direct create, submit, approval, start, observation, analysis, and completion helpers fail before database access; migration 509/510 prevent direct experiment/observation writes from shared runtime and Directus roles. | Implement exact-location scoped analysis and completion; compare observation and result semantics against populated fixtures; complete live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance. |
| `solution_experiments.review_result`, `create_replication` | Scoped independent result-review and replication-proposal paths exist; both legacy direct helpers now fail before database access. | Compare review and proposal semantics against populated legacy fixtures and preserve reviewer separation and validated-source checks. |
| `solution_adoption.create_program`, `assess_readiness`, `approve_configuration` | Location-scoped adoption summaries and aggregate adoption-event summaries are reads only. `record_event` now fails closed and has no replacement write route. | Add scoped program/readiness/configuration writes and a consent-aware event route. Configure policy on the program, bind event references to canonical participant identity, and validate current consent at write time. |
| `solution_funding.create_case`, `submit_case`, `approve_case`, `add_tranche`, `approve_tranche` | Scoped proposal/submission/review/approval routes exist. Legacy helpers still write directly. | Retire duplicate helpers after callers migrate and add fail-before-database regressions. |
| `solution_funding.release_tranche` | No release route was found. | Keep execution gated until a separate disbursement authority, custody, evidence, and retry contract is defined; do not expose the legacy shared-role writer as a substitute. |

This inventory is a source-level checkpoint. It does not show whether any
external consumer calls a legacy helper, prove populated-record parity, or
establish universal database ACL/RLS boundaries. CAP-035 remains prepared.

## Verification and rollback

The focused Gateway/route-policy/console selection covers migrations 503–505;
disposable PostgreSQL 16 checkers apply and replay these migrations after the
CAP-035 chain. Migration 504 acceptance exercises exact scope, active human
attribution, input validation, opening-event atomicity, exact retry replay,
changed-payload rejection, and receipt privacy. Migration 505 acceptance
exercises draft gate creation, fixed promotion mapping, exact-origin reads,
criterion redaction, retries, and role boundaries. Candidate and legacy
databases were untouched; migrations 503–505 have not been rolled out. Before
rollout, disable the new route and console form while retaining the additive
migrations; do not edit or reverse an applied migration.
