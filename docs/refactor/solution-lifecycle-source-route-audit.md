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

The six `solution_funding` direct writers (`create_case`, `submit_case`,
`approve_case`, `add_tranche`, `approve_tranche`, and `release_tranche`) now fail
before database access. The first five have exact-location Gateway proposal,
submission, case-review, and tranche-review actions backed by migrations
488–492. No disbursement route exists: tranche release stays disabled until a
separate custody, disbursement-authority, evidence, and retry contract is
approved and implemented. Focused mock coverage verifies every helper avoids
cursor, commit, and rollback access.

`solution_adoption.create_program` now fails before database access. Migration
513 adds a separate exact-location draft route; migration 515 extends it to
active location-origin solutions at `pilot_active`, `adoption_ready`, or
`adopting`, so a program can be prepared before the adoption-ready gate.
PostgreSQL derives the human party from the active operator binding, fixes the
target scope and empty population, and stores a private immutable retry
receipt. The operator console requires exact read and create grants and
preserves uncertain retries. This does not assess readiness, approve a local
configuration, record participant events, or launch adoption; those actions
remain separate and incomplete.

The legacy `solution_adoption.assess_readiness` and
`approve_configuration` helpers also now fail before database access. Their old
behavior could mark readiness `ready` directly or insert a configuration
already marked `approved`, with no tenant grant or independent reviewer.
Migration 514 revokes runtime and Directus table- and column-level DML on
`solution_adopter_readiness` and `solution_configuration` while preserving
their read access. Migration 517 now provides configuration draft, submission,
and independent approval/rejection through exact-location Gateway actions;
until migration 517 is applied in an environment, those writes remain disabled.

Migration 516 adds the scoped readiness portion: an exact-location human
assessment remains `not_ready`, and only a different active operator can review
the current immutable assessment. A new assessment expires the previous ready
state; historical ready rows without an independent receipt are also expired.

Migration 517 adds versioned exact-location configuration drafts for active
location-origin solutions at `pilot_active` or `adoption_ready`. The active
human proposer is derived from the signed operator binding. Submission is
creator-only, and a different active human can approve or reject the immutable
submitted version. Private receipts support exact retries; a database trigger
blocks unreviewed direct approval. Historical approved rows are preserved in a
private archive and returned to draft because their reviewer independence
cannot be verified. The legacy direct configuration helper remains fail-closed.
Program enablement review, participant consent/event linkage, and launch remain
separate open work.

Other legacy direct mutation helpers already fail closed:

| Legacy helper | Scoped path |
| --- | --- |
| `create_gate`, `evaluate_gate` | Scale-gate assessment and independent review |
| `record_learning`, `apply_learning` | Learning proposal/review/application |
| `propose_retirement`, `approve_retirement` | Retirement proposal and independent review |
| `solution_adoption.record_event` | No write route yet; the helper is now fail-closed until policy-backed participant and consent linkage is implemented. |
| `solution_adoption.create_program` | Migrations 513 and 515 provide exact-location draft creation for active location-origin solutions at `pilot_active`, `adoption_ready`, or `adopting`; the legacy direct helper is retired. Configuration approval and program enablement review remain open. |
| `solution_adoption.assess_readiness` | The legacy direct upsert is retired. Migrations 514 and 516 provide exact-location assessment submission and independent review; only review of the current immutable assessment can mark it ready. Historical unreviewed ready rows expire. |
| `solution_adoption.approve_configuration` | The legacy direct approved-row insert is retired. Migration 517 adds exact-location versioned draft creation, creator submission, independent human approval/rejection, idempotent receipts, a direct-approval trigger, and historical-approval archival; runtime and Directus retain no configuration DML or receipt access. Program enablement review remains open. |
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
| `solution_experiments.create_experiment`, `submit_protocol`, `approve_protocol`, `start_experiment`, `record_observation`, `complete_experiment`, `analyze_sequentially` | Migrations 506–512 provide exact-origin immutable protocol drafts, owner submission, private independent approval, exact-location start, consent-aware observation capture, protocol-bound advisory analysis, and protocol-bound completion. Migration 511 requires signed exact-location `solution_lifecycle:analyze`; directions, minimum sample, benefit/posterior thresholds, safety limit, and duration come from the immutable protocol. Migration 512 completes data collection only when every primary metric has a fresh, current-consent terminal analysis matching its protocol and source digest; completion stores a private immutable receipt and leaves result review separate. Forced RLS hides analyses when a source observation's consent is withdrawn or its link is revoked, and leaves historical unassessed runs hidden. Legacy direct create, submit, approval, start, observation, analysis, and completion helpers fail before database access; runtime and Directus cannot access private observation, analysis, or completion receipts directly. | Compare completion, analysis, and observation semantics against populated fixtures and retain independent result-review separation; complete live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance. |
| `solution_experiments.review_result`, `create_replication` | Scoped independent result-review and replication-proposal paths exist; both legacy direct helpers now fail before database access. | Compare review and proposal semantics against populated legacy fixtures and preserve reviewer separation and validated-source checks. |
| `solution_adoption.create_program`, `assess_readiness`, `approve_configuration` | Migrations 513/515 provide exact-location program draft creation for active exact-origin solutions at `pilot_active`, `adoption_ready`, or `adopting`. Migration 516 adds immutable readiness submissions and independent human review; below-target assessments cannot be marked ready, exact retries replay, and a trigger blocks unreviewed direct readiness updates. Migration 517 adds versioned location configuration drafts, creator-only submission, independent approval/rejection, immutable receipts, historical approval archival, and direct-approval protection. The console uses exact create/submit/review grants, no-store/CSRF, safe text rendering, and stable retry IDs. Runtime and Directus cannot write lifecycle tables or access private receipts; legacy helpers fail before database access. | Compare program/readiness/configuration semantics against populated legacy fixtures. Add the program enablement-review transition required by the adoption-ready gate. Add consent-aware participant events, reviewed program policy, canonical party linkage, and current-consent validation. Preserve separate review and launch boundaries; complete live OIDC/browser, broader ACL/RLS, recovery, and owner acceptance. |
| `solution_funding.create_case`, `submit_case`, `approve_case`, `add_tranche`, `approve_tranche` | Migrations 488–492 provide scoped proposal, submission, case review/approval, and tranche review/approval. The legacy funding helpers now fail before database access. | Compare semantics with populated legacy fixtures; complete live OIDC/browser acceptance, broader ACL/RLS review, and recovery acceptance. |
| `solution_funding.release_tranche` | No release route exists; the legacy shared-role writer now fails before database access. | Keep disbursement gated until a separate authority, custody, evidence, and retry contract is defined and independently reviewed. |

This inventory is a source-level checkpoint. It does not show whether any
external consumer calls a legacy helper, prove populated-record parity, or
establish universal database ACL/RLS boundaries. CAP-035 remains prepared.

## Verification and rollback

The focused Gateway/route-policy/console selection covers migrations 503–505
and 513–517; disposable PostgreSQL 16 checkers apply and replay these
migrations after the CAP-035 chain. Migration 504 acceptance exercises exact
scope, active human attribution, input validation, opening-event atomicity, exact retry replay,
changed-payload rejection, and receipt privacy. Migration 505 acceptance
exercises draft gate creation, fixed promotion mapping, exact-origin reads,
criterion redaction, retries, and role boundaries. Migrations 513 and 515
acceptance checks scoped adoption-program draft creation at pilot-active and
later adoption stages; migration 514 checks runtime/Directus privilege
revocation on readiness and configuration tables; migration 516 checks
assessment, independent review, current-assessment binding, replay, historical
ready expiration, and role boundaries. Migration 517 checks legacy approval
archival, location-qualified draft creation, versioning, retries, submission,
reviewer exclusion, approval/rejection, trigger enforcement, and private role
boundaries. Candidate and legacy databases were untouched; migrations 503–505
and 513–517 have not been rolled out. Before rollout, disable new routes and console forms while
retaining additive migrations; do not edit or reverse an applied migration.
