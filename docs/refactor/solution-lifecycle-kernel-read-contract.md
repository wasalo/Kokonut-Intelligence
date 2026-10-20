# Solution lifecycle Kernel read contract

**Status:** CAP-035 location-scoped summary, gate, experiment, funding, adoption,
scale-gate, replication, reviewed-replication learning, exact-origin retirement
reads, independently reviewed retirement and learning proposal actions, the
private retirement-review view, and append-only gate-evaluation submission are
prepared; not owner-accepted.
**Migrations:** `459_location_scoped_solution_lifecycle_summary.sql`,
`466_location_scoped_solution_gates.sql`,
`467_location_scoped_solution_experiments.sql`,
`468_location_scoped_solution_funding.sql`,
`469_location_scoped_solution_adoption.sql`,
`470_location_scoped_solution_scale_gates.sql`, and
`471_location_scoped_solution_replications.sql`,
`472_location_scoped_solution_learning.sql`, and
`473_location_scoped_solution_retirements.sql` plus
`474_solution_retirement_independent_review.sql` and
`475_location_solution_retirement_review.sql` and
`476_location_solution_retirement_proposal.sql`, and
`477_location_solution_learning_proposal.sql`,
`481_location_solution_retirement_candidates.sql`, and
`482_location_solution_retirement_review_queue.sql`, and
`483_location_solution_gate_evaluation.sql`.
**Routes:** `GET /operator/api/solution-lifecycle/{location_id}/summary`,
`GET /operator/api/solution-lifecycle/{location_id}/gates`,
`GET /operator/api/solution-lifecycle/{location_id}/experiments`,
`GET /operator/api/solution-lifecycle/{location_id}/funding`,
`GET /operator/api/solution-lifecycle/{location_id}/adoption`,
`GET /operator/api/solution-lifecycle/{location_id}/scale-gates`,
`GET /operator/api/solution-lifecycle/{location_id}/replications`,
`GET /operator/api/solution-lifecycle/{location_id}/learning`,
`GET /operator/api/solution-lifecycle/{location_id}/retirements`,
`GET /operator/api/solution-lifecycle/{location_id}/retirement-candidates`, and
`POST /operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/approve`,
`POST /operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/retirements`, and
`POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning`,
`GET /operator/api/solution-lifecycle/{location_id}/retirements/review`, and
`GET /operator/api/solution-lifecycle/{location_id}/retirements/review/{retirement_id}`, and
`POST /operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/evaluations`.
**Authorization:** reads require exact `solution_lifecycle:read`; retirement,
learning proposals, and gate evaluations require exact `solution_lifecycle:create`;
approval requires exact `solution_lifecycle:review`; retirement review reads and
gate evaluations also require an active human party binding. Mutations use signed
operator tenant context checked in Gateway and PostgreSQL.

## Purpose and boundary

The legacy innovation services already implement solution discovery, stage
gates, experiments, funding decisions, adoption, replication, scale gates,
learning, and retirement. This slice adds optional-Kernel-compatible,
location-scoped Gateway reads, retirement proposal/review routes, and a limited
retirement-review action. The reads do not mutate lifecycle state. The action records an independent retirement
approval but does not execute migration, sunset, or retirement of a solution. The
review inbox exposes the pending proposal context needed for that decision only to
operators with the exact review grant.
The proposal action creates a `proposed` record only for an exact location-origin
solution and an active OIDC-to-person binding; an independent reviewer must
approve it separately before later lifecycle execution.
The learning proposal action creates a `proposed` learning record only from a
completed, actively reviewed replication targeting the exact location and
linked to a solution originated in or explicitly associated with that location.
The receipt attributes the OIDC proposer separately from the learning record's
optional owner identity; it does not accept, reject, or apply the lesson.
These routes do not replace the domain services, change stage-transition rules,
approve gates, release funding, or activate adoption. A gate evaluation appends
a pass/fail observation and evidence references for an exact location-origin
gate; it does not change the gate status or approve a stage transition. Gate
approval remains a separate human review.

Canonical `solution` records can be network-wide. The projection includes a
solution only when it is explicitly originated in the requested location or
has a `solution_link` whose `entity_type = 'location'` and `entity_id` exactly
matches that location. Migration 459 adds this supported link type without
rewriting existing links. Location-specific adoption, configuration, readiness,
and scale indicators are additionally filtered by their exact location scope.
An unlinked network solution is intentionally absent from this location read.

## Response

The response contains `location_id`, `solution_count`, and aggregate counts for
solution stages/status, stage-gate status, each gate's latest evaluation,
experiment status/outcome, replication, funding decision state, location-scoped
adoption/configuration/readiness/scale state, learning decision, and retirement
state. Count objects use the source table's allowlisted enumerated values; they
contain no row IDs, names, canonical keys, actor or party identities, free text,
evidence, funding amounts, or raw JSON payloads. Responses are `no-store` and
vary on the session cookie.

The gates route returns a bounded page of gate items only for solutions that
originate in the requested location or have an explicit `solution_link` to that
location. Each item includes solution/gate identifiers, the solution's display
name/type/stage/status, gate transition and requirement counts, approval-needed
flag, gate status/creation time, and only the latest evaluation pass/fail value
and timestamp. It omits gate requirements JSON, observed values, evaluation and
gate evidence, reviewer/actor identities, narratives, funding data, and raw
payloads. Pages accept 1–50 items and an offset up to 10,000; the database
function receives at most 51 rows to compute `has_more`, and the Gateway caps
the serialized page at 256 KiB. The read does not approve, fail, or otherwise
mutate a gate.

The experiments route returns a bounded page of experiment lifecycle state for
the same exact origin-or-location-link solution set. Each row contains the
solution and experiment IDs, solution name/type/stage/status, protocol version,
experiment status and duration, counts of primary and secondary metric keys,
experiment timestamps, and only the latest explicitly reviewed result outcome
and its review timestamp. Rows without `reviewed_at` are suppressed. It omits
the hypothesis, baseline/treatment/comparator protocol,
metric names and values, observation records, raw result JSON, adverse-event
details, evidence, and owner/reviewer identities. Pages accept 1–50 rows with
an offset up to 10,000; SQL fetches at most 51 to determine `has_more`, and the
Gateway applies the same 256 KiB response limit. This is status visibility,
not experiment approval, result review, or a mutation path.

The funding route returns a bounded flat page of location-scoped funding cases
and tranche lifecycle states. Cases without tranches remain visible. Rows
contain solution and funding-case IDs, solution labels/state, capital stage,
instrument, currency, case decision state and timestamps, plus nullable tranche
ID/number/status and approval/release timestamps. It never returns requested,
authorized, tranche, or released amounts; milestone conditions; case rationale;
funding or release evidence; or submitter, approver, and releaser identities.
The `kokonut_solution_reader` role receives column-level SELECT only for the
case and tranche fields needed by this projection and the existing aggregate
summary. It cannot select monetary, narrative, evidence, or party columns. Pages
accept 1–50 rows with an offset up to 10,000, use stable case/tranche ordering,
and share the 256 KiB response cap. The route does not approve funding cases,
approve or release tranches, or expose release execution.

The adoption route returns a bounded page of programs whose target is the exact requested location and whose solution originates there or has an explicit location link. It includes solution/program identifiers and labels, lifecycle state, and timestamps. `consented_adopter_reference_count` is null unless at least five distinct, nonempty, case- and whitespace-normalized `adopter_ref` values have consent-checked events; repeated events carrying the same reference do not increase the threshold, and non-consented events are excluded. The count is an aggregate of source references, not a verified count of natural persons. Adopter references, cohort IDs, event type/time, fidelity, support needs, outcomes, evidence, and party identities are omitted from the response. The security-definer owner receives column access to the pseudonymous adopter reference solely for the distinct count; runtime and Directus cannot read the source tables. Pages use the same 1–50 limit, 10,000 offset ceiling, no-store response, and 256 KiB serialized response cap. This does not expose event detail or mutate adoption state.

The scale-gates route returns a bounded page of gates whose scope is exactly the requested location and whose solution originates there or has an explicit location link. It includes solution/gate IDs and labels, gate type/status, a boolean indicating whether an approver reference exists, and the nullable approval timestamp. It omits free-text requirements, configured thresholds, measured values, metric keys, units, evidence, and approver identity. The non-login reader has column access to `approved_by_party_id` only to derive the boolean; neither that value nor party details are returned. Pages follow the same bounds and response cap. This read does not evaluate, waive, approve, or mutate a scale gate.

The replications route returns a bounded page only when both the solution lineage and replication target match the exact requested location. It shows solution/replication IDs and labels, replication state/result, evidence-maturity level, whether a reviewer reference exists, and creation/completion timestamps. It omits the source experiment ID, target context, similarity, adaptation plan, replication protocol, raw evidence, and reviewer identity. The non-login reader has column access to the reviewer reference solely to derive the boolean. Pages use the shared limits and response cap. The route does not approve, start, complete, or otherwise change a replication.

The learning route returns a bounded page only for records linked to a human-reviewed replication whose target scope is exactly the requested location and whose solution is originated in or explicitly linked to that location. It shows solution/learning IDs and labels, lesson type, confidence/transferability bands, decision state, and creation time. It omits learning text, recommendations, affected assumptions or metrics, evidence, source IDs, version details, and party identities. Records without a linked reviewed location replication are omitted, including experiment-only, network-wide, unreviewed, cross-location, and unlinked-solution records. This read does not accept, reject, or apply learning.

The retirements route returns bounded retirement metadata only for solutions originated at the exact requested location. It shows retirement type/status, whether a human approval reference exists, and approval/effective/post-review/creation timestamps. It omits trigger reasons, evidence, affected users, dependencies, replacement links, migration/remedy plans, residual risk, and party identities. It does not include solutions that are merely linked to the location: `solution_retirement` has no target-scope column, so a shared solution's global retirement state must not be inferred as location-specific. This read does not propose, approve, schedule, or execute a retirement.

Migration 474 adds a database trigger and service preflight so a newly approved retirement has a recorded proposer, an independent reviewer, and immutable proposer/reviewer attribution. Approval without proposer attribution and self-approval fail closed. The migration does not rewrite or validate historical rows at install time; legacy approvals remain untouched and require separate review before they are changed.

Migration 475 adds the first bounded Kernel approval action. The Gateway accepts
only a request UUID, establishes signed `solution_lifecycle:review` context, and
calls `kokonut_security.approve_location_solution_retirement`. PostgreSQL checks
the exact location-originated solution (a location link alone is insufficient),
an active exact review grant, and an active OIDC operator-to-person binding. The
reviewer must differ from the recorded proposer. The retirement must remain
proposed or in impact review and include nonempty evidence, a migration plan,
and a distinct replacement for `superseded` decisions. The status update and
append-only idempotent review receipt are one transaction. The action returns
only the receipt ID, retirement ID/status, approval timestamp, and retry flag;
request-key reuse across decisions is rejected. A dedicated non-login owner has
only the source columns and tenant-checking relations it needs, can insert but
cannot update/delete receipts, and is not directly callable by Directus.

Migration 477 adds a separate learning-proposal action. It requires a completed
replication with an active human reviewer, exact target location, and exact
solution origin/location-link lineage. The Gateway accepts only an idempotency
UUID, allowlisted lesson type, bounded finding/recommendation, confidence and
transferability bands, bounded assumption/metric references, and nonempty
bounded evidence references. PostgreSQL repeats the signed location grant and
source checks, writes `decision_status = 'proposed'` plus an append-only receipt
atomically, and returns only receipt/learning IDs, current proposal status,
timestamp, and replay state. Retries return the original receipt; request-key
reuse with changed input is rejected. A separate non-login owner cannot update
learning content/status or modify/delete receipts. Runtime can call the bounded
function but cannot access learning records or receipts directly; Directus
cannot call it.

## Database boundary

The stable read function is owned by `kokonut_solution_reader`, a non-login,
non-inheriting role with SELECT only on the source relations required to compute
the projection. The function rechecks actor type, signed location context, and
the exact `solution_lifecycle:read` grant. Runtime can execute the bounded
function but cannot select the solution tables directly; Directus has neither
function nor table access. The reader has no identity-table access and no write
privileges. Migrations 466–473 add bounded gate, experiment, funding, adoption,
scale-gate, replication, learning, and retirement functions under the same
reader role and exact signed-location grant checks. Migration 474 adds the
retirement independent-review trigger. Migration 475 assigns the write function
to a separate non-login `kokonut_solution_action_owner`; it receives narrow
source-column access, minimum tenant-check relations, and UPDATE only on the
retirement approval fields plus identity columns needed to lock active human
bindings. It can SELECT/INSERT receipts but cannot update or delete them.
Runtime can execute the bounded function but cannot access source or receipt
tables directly; Directus cannot execute the action.
Migration 477 uses `kokonut_solution_learning_proposal_owner`; it receives only
the source columns and tenant-check relations needed to validate a reviewed
replication and write a draft learning record, with no learning-record update
or receipt update/delete privileges. Migration 482 adds the separate non-login
`kokonut_solution_reviewer` role. It receives only proposal detail columns,
active-person attribution columns, and the tenant-grant relations consulted by
the security-invoker grant helper. Its functions return only pending exact-origin
proposals under signed review context; runtime cannot read retirement tables
directly and Directus cannot execute the functions. Migration 482 also installs
a trigger that rejects approval of a location-origin superseded retirement
when the replacement is absent, identical, or not from the same location.

## Operator console

The operator console exposes a read-only lifecycle summary when the signed
session includes an exact `solution_lifecycle:read` location grant. It displays
the aggregate solution total and fixed status-count groups through the
summary route; no solution names, IDs, narratives, evidence, funding amounts,
or identities are rendered in the overview. Groups are collapsed by default.
The same panel can load a bounded page of location-linked stage gates through
the existing `/gates` route. It shows fixed solution labels, stage transition,
structural requirement thresholds, gate status, and latest evaluation result/time;
it omits evidence payloads and reviewer identities. The evaluation is
informational and the panel cannot approve or change a gate. It can also load a
bounded experiment page showing lifecycle metadata and the latest explicitly
reviewed outcome only. Protocol narratives, metric names/values, observations,
adverse-event details, evidence, and reviewer identities remain excluded; the
panel cannot approve or review results. It also pages funding-case and tranche
lifecycle labels, currency, and timestamps only. Amounts, milestone terms,
rationale, evidence, and submitter/approver/releaser identities are excluded;
the panel cannot approve funding or release tranches. Five additional selector
views page adoption programs, scale gates, replications, learning records, and
retirement records through the existing exact-grant routes. They render only
fixed lifecycle labels, state bands, approval/review presence, timestamps, and
the consented adopter-reference count when the database projection returns it;
that count remains withheld below the five-reference threshold. Identifiers,
raw references, narratives, evidence, measurements, and person-level details
are not rendered. All reads are same-origin and no-store, limited to 25 rows per
page, and stale responses are discarded when the location or selected view
changes.

The console also offers a learning-proposal form only when the signed session
has both exact location `solution_lifecycle:read` and `solution_lifecycle:create`
grants. It selects sources from the existing bounded replication read and
filters to completed replications with an active review. The form sends only the
allowlisted fields accepted by the existing learning-proposal action, requires
bounded nonempty evidence and explicit acknowledgement, and uses same-origin,
no-store, CSRF-protected POSTs. It retains the request ID for an unchanged retry
if the response is uncertain. The action creates a `proposed` record that needs
independent human review; the console cannot approve, reject, or apply it. Source
checks do not constitute live OIDC/browser acceptance.

The console also offers a retirement-proposal form when the session has both
exact location `solution_lifecycle:read` and `solution_lifecycle:create` grants.
The source selector calls the bounded retirement-candidate read, which returns
only solutions whose canonical origin is the selected location. A location link
alone does not make a shared solution eligible. The form accepts the existing
retirement type allowlist, bounded trigger reason, evidence references, and
remedy plan; `superseded` requires a different location-origin replacement.
Same-origin no-store requests, CSRF protection, explicit acknowledgement, and a
stable request ID for unchanged retries are used. The existing action creates a
proposal for independent review. The console does not approve, schedule, or
execute retirements.


A separate retirement-review panel appears only for an exact location
`solution_lifecycle:review` grant. It pages pending location-origin proposals
and fetches private detail through dedicated review functions. The response
contains bounded trigger reason, evidence references, remedy plan, and fixed
solution labels; proposer identity is never returned, only attribution and
self-authorship booleans. The console renders all values as text, shows a
self-review warning, and disables approval for self-authored or unattributed
proposals. Approval requires an active session, explicit acknowledgement, and
CSRF-protected no-store request. An uncertain result retains its request ID for
an unchanged retry. A success message states that approval does not schedule or
execute the retirement. Review reads and approval remain separate from the
ordinary location-read views.

## Gate evaluation submission (migration 483)

`POST /operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/evaluations`
accepts exactly `request_id`, `passed`, `observed`, and `evidence`. It requires an
active signed operator session and exact location `solution_lifecycle:create`
grant, plus an active OIDC-to-person binding. The target must be a `draft` or
`ready` gate on a solution whose canonical origin is the exact requested
location; a network-wide or merely location-linked solution is not writable by
this action. Observations must be a JSON object and evidence a nonempty JSON array,
with each encoded payload capped at 64 KiB and evidence capped at 100 entries.

The dedicated non-login `kokonut_solution_gate_evaluator` owns a SECURITY
DEFINER function and receives narrow column privileges, including append-only
receipt insert/select. Runtime receives function execution only; Directus cannot
execute it and neither runtime nor Directus can read the idempotency receipt. A
receipt binds operator, human party, location, gate, evaluation, and request ID.
An identical retry returns the original evaluation; reuse with a different
location or payload fails. The route is no-store and protected by the operator
CSRF policy. The console requires both read and create grants, offers only draft
or ready gates, and clearly separates evaluation from approval.

Migration 483 is additive and has not been rolled out to candidate or legacy.
The disposable PostgreSQL 16 runner applies and replays it and checks exact
context/grant enforcement, human attribution, origin lineage, payload bounds,
append-only/idempotent behavior, runtime/Directus boundaries, and approval
separation.

## Verification and remaining parity

The retirement-candidate/proposal slice passes 176 focused tests; disposable PostgreSQL 16 applies/replays migration 481 and passes nine scope, grant, pagination, privacy, and role-boundary groups. Evidence is recorded in `builds/2026-10-20-recovery/cap-035-solution-retirement-candidates-disposable.json`. The review inbox/detail/approval-console slice passes 122 focused tests including Node.js syntax, with Ruff, compilation, and diff checks. Disposable PostgreSQL 16 applies/replays migration 482 after the ordered predecessors and passes seven grouped review, grant, privacy, privilege, and replacement-scope checks. Evidence is recorded in `builds/2026-10-20-recovery/cap-035-solution-retirement-review-disposable.json`. Both disposable containers are removed after their runs; candidate and legacy databases are untouched and migrations 481–482 are not rolled out.

The summary, gate, experiment, funding, adoption, scale-gate, replication,
learning, retirement, and independent-review source checks and their
disposable PostgreSQL 16 apply/replay acceptance are recorded in
`builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-gates-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-experiments-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-funding-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-adoption-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-scale-gates-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-replications-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-learning-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-retirements-disposable.json`.
`builds/2026-10-19-recovery/solution-retirement-independent-review-disposable.json`.
`builds/2026-10-19-recovery/solution-retirement-approval-disposable.json` records
migration 475 apply/replay and five PostgreSQL 16 acceptance groups. The 125-test
Gateway, route-policy, and migration-metadata selection passes. Candidate and
legacy databases are untouched. Migration 476 adds an exact-location proposal
action with bounded evidence and plan input, active human proposer attribution,
location-visible replacement validation, and atomic append-only idempotent
receipt. The function explicitly supplies retirement ID, `proposed` status, and
timestamp for legacy schemas that do not have column defaults. A separate
non-login proposal owner has no retirement update or approval-attribution
privileges. Migration 481 adds only the candidate-list function to the existing
read-only solution reader. That function has column SELECT access to solution ID,
name, type, stage, status, and canonical origin fields; runtime can execute it,
Directus cannot, and candidate/legacy rollout remains separate. The route/form
can be disabled before rollout; after application, retain the additive function
and ACLs until a separate ordered retirement migration is approved. The focused
Gateway, route-policy, and migration-metadata selection passes 137 tests.
Disposable PostgreSQL 16 applies/replays migrations 459 and 466–476 and passes
five proposal acceptance groups. Evidence is in
`builds/2026-10-19-recovery/solution-retirement-proposal-disposable.json`.
Candidate and legacy databases are untouched; migrations 459 and 466–476 have
not been rolled out. This is not parity acceptance. Remaining work includes
item-level read and write workflows beyond status projections, gate and
experiment evidence detail under reviewed grants,
funding/tranche and adoption event detail, populated legacy-to-Kernel fixture
comparison, browser/OIDC acceptance, broader ACL/RLS, recovery behavior, and
MAN-CAP-035 owner review.

Migration 477 adds the reviewed-replication learning proposal action. The
16-test Gateway/route-policy selection passes; disposable PostgreSQL 16 applies
and replays migration 477 and passes nine acceptance groups for source lineage,
reviewer status, exact tenant grants, idempotency/collision, draft-only state,
input bounds, and runtime/Directus boundaries. Candidate and legacy databases
are untouched; migration 477 is not rolled out. Evidence is in
`builds/2026-10-19-recovery/cap-035-solution-learning-proposal-disposable.json`.

## CAP-035 gate evidence review and approval

Migration 484 adds a private exact-location review projection and an independent
gate-approval action. `GET
/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/review` requires a
signed operator context, an active `solution_lifecycle:review` grant for the
exact location, an active OIDC-to-person binding, and a solution whose canonical
origin is that location. It returns only the gate transition/status and the
latest evaluation result, bounded observations, evidence, and timestamp. The
evaluator identity is intentionally withheld.

`POST
/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/approve` uses the
same review scope. PostgreSQL requires the gate to remain draft/ready and
explicitly require human approval, the latest evaluation to pass, and the active
reviewer party to differ from the evaluator. Approval updates gate status and
attribution with an append-only
request receipt in the same transaction; identical retries return the original
approval and request-key collisions fail closed. Approval does not advance the
solution's lifecycle stage. Gate evaluation remains a separate
`solution_lifecycle:create` action.

The review and approver functions have separate non-login owners with narrow
source-column access. The runtime can execute the bounded functions but cannot
read evaluation or approval-receipt tables directly; Directus cannot execute
them. The console renders reviewed evidence as text, requires explicit human
acknowledgement for approval, and does not offer a lifecycle transition.
Migration 484 has been applied and replayed only on disposable PostgreSQL 16;
the focused Gateway, console, route-policy, and migration-metadata selection
passes 82 tests. Evidence is recorded in
`builds/2026-10-20-recovery/cap-035-solution-gate-review-disposable.json`.
Candidate and legacy databases are untouched, and migration 484 is not rolled
out.

## Rollback

Before migration rollout, remove a route registration, route-policy entry, read
or action service, migration source, and tests together. If migrations 483 or
484 have been applied, disable the corresponding evaluation, review, or approval
routes and console panels, but retain the ordered migrations, roles, and ACLs
until separately reviewed forward migrations remove them. Do not edit or reverse
an applied migration; any schema rollback requires a separately reviewed
forward migration after checking for location links, evaluation evidence,
approval receipts, and dependent data created since rollout.
