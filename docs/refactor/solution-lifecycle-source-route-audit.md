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

Other legacy direct mutation helpers already fail closed:

| Legacy helper | Scoped path |
| --- | --- |
| `create_gate`, `evaluate_gate` | Scale-gate assessment and independent review |
| `record_learning`, `apply_learning` | Learning proposal/review/application |
| `propose_retirement`, `approve_retirement` | Retirement proposal and independent review |
| `solution_adoption.record_event` | No write route yet; the helper is now fail-closed until policy-backed participant and consent linkage is implemented. |
| `solution_lifecycle.approve_gate`, `evaluate_gate` | Exact-location human review/approval and evidence-backed evaluation actions remain available through the Gateway. |
| `solution_lifecycle.transition` | Shared-role writer retired. Gate-backed promotion transitions remain available through migration 486; retirement uses migration 502. |

## Remaining source-to-route effects

These source paths still need action-level decisions and parity work. Do not
mark CAP-035 complete or claim universal tenant isolation while they remain.

| Legacy module and effect | Current Gateway coverage | Remaining work |
| --- | --- | --- |
| `solution_lifecycle.transition` for non-promotion stages | Migration 503 provides a bounded exact-origin target read and a signed exact-location action for nonterminal, non-promotion stages. It requires an active human binding, explicit acknowledgement, rationale/evidence, expected-stage compare-and-set, and an atomic immutable retry receipt. `adopting` rechecks approved location readiness/configuration; `superseded` and `retired` remain on the reviewed retirement workflow. | Compare behavior against populated legacy fixtures; complete live OIDC/browser acceptance, broader ACL/RLS review, recovery acceptance, and remaining source-to-route parity. |
| `solution_lifecycle.create_solution`, `add_link` | Location reads, gate evaluation/review/approval, and gate-backed promotion transitions exist; no matching scoped solution-create or link-management write was found in the audited route module. | Define location-origin creation and explicit network/location link policy, then add a bounded route or retire the old helper after callers migrate. |
| `solution_lifecycle.create_gate` | Evaluation, review/approval, and gate-backed promotion transition paths exist; no matching gate-creation path was found. | Move gate definition to an authorized, auditable location-scoped operation before disabling the legacy writer. |
| `solution_experiments.create_experiment`, `submit_protocol`, `approve_protocol`, `start_experiment`, `record_observation`, `complete_experiment`, `analyze_sequentially` | Experiment status/review reads and independent result review exist; replication proposal/activation/completion are separate. | Port protocol drafting/review, observation collection, analysis, and completion with location scope, consent/evidence rules, and atomic retry semantics; then retire direct writers. |
| `solution_experiments.review_result`, `create_replication` | Scoped independent result review and replication proposal paths exist. | Retire legacy writes after call sites/tests move, and preserve reviewer separation and validated-source checks. |
| `solution_adoption.create_program`, `assess_readiness`, `approve_configuration` | Location-scoped adoption summaries and aggregate adoption-event summaries are reads only. `record_event` now fails closed and has no replacement write route. | Add scoped program/readiness/configuration writes and a consent-aware event route. Configure policy on the program, bind event references to canonical participant identity, and validate current consent at write time. |
| `solution_funding.create_case`, `submit_case`, `approve_case`, `add_tranche`, `approve_tranche` | Scoped proposal/submission/review/approval routes exist. Legacy helpers still write directly. | Retire duplicate helpers after callers migrate and add fail-before-database regressions. |
| `solution_funding.release_tranche` | No release route was found. | Keep execution gated until a separate disbursement authority, custody, evidence, and retry contract is defined; do not expose the legacy shared-role writer as a substitute. |

This inventory is a source-level checkpoint. It does not show whether any
external consumer calls a legacy helper, prove populated-record parity, or
establish universal database ACL/RLS boundaries. CAP-035 remains prepared.

## Verification and rollback

The focused Gateway/route-policy/console selection covers migration 503's
route contracts; the disposable PostgreSQL 16 checker applies and replays 503
after the CAP-035 chain and exercises exact scope, human binding, stage bounds,
stale-state rejection, retries, atomicity, adoption readiness, and role
boundaries. Candidate and legacy databases were untouched, and migration 503
has not been rolled out. To roll back the feature before rollout, disable the
two routes and console panel while retaining the additive migration; do not edit
or reverse an applied migration.
