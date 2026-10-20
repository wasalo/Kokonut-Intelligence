# Solution lifecycle Kernel write contract

**Status:** prepared implementation contract; migrations 488–504 are additive and are
not applied to the local candidate or legacy database.

This document specifies the operator Gateway's bounded write boundary for the
solution lifecycle. Existing CLI and Directus workflows remain legacy adapters;
the Gateway path is the Kernel-owned interface.

## Location-origin solution creation

`POST /operator/api/solution-lifecycle/{location_id}/solutions` creates one
discovered solution with `originating_scope_type='location'` and the exact
requested location ID. It requires a signed `solution_lifecycle:create` grant,
an active operator-to-person binding, explicit acknowledgement, a bounded
opening rationale, and at most 100 JSON evidence references. The canonical key
is globally unique; a collision returns a generic conflict without revealing
the existing record. The operation assigns the bound person as creator and
leaves `owner_party_id` unset for a separately governed ownership decision.

The solution, discovered opening lifecycle event, and private receipt commit
atomically. Request IDs are operator-scoped: exact retries return the original
creation receipt, while changed input under the same ID fails. Creation does
not add a `solution_link`, publish the solution to other locations, configure a
stage gate, or advance lifecycle state. The console form is hidden unless the
operator has both exact location read and create grants; it uses acknowledgement,
CSRF, same-origin no-store requests, and stable request IDs.

The non-login function owner has column-scoped access only to the active human
binding, solution insert, opening event, and private receipt fields needed by
the operation. Runtime can execute the function but cannot read the receipt
directly; Directus cannot execute it. The legacy
`solution_lifecycle.create_solution` helper now fails before database access.
`add_link` and `create_gate` likewise fail closed until reviewed sharing and
gate-definition policies have dedicated routes.

Disposable PostgreSQL 16 acceptance applies and replays migration 504 after the
CAP-035 chain. It verifies exact-location grants, active-human attribution,
input validation, origin, opening-event atomicity, exact retries, changed-input
rejection, and private receipt access. Candidate and legacy databases remain
untouched; migration 504 has not been rolled out.

## Funding draft proposal

### Routes and grants

`GET /operator/api/solution-lifecycle/{location_id}/funding/targets` requires an
exact `solution_lifecycle:read` grant and signed tenant context. It returns
bounded solution labels only for solutions whose origin is that location. A
network-origin solution merely linked to the location is not a funding target;
the current funding-case schema has no independent location scope for shared
solutions.

`POST /operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/funding`
requires an exact `solution_lifecycle:create` grant, signed tenant context, and
an active operator-to-human-party binding. PostgreSQL rechecks all three and
requires the solution's origin to match the exact location.

### Request

The body contains exactly these fields:

```json
{
  "request_id": "UUID",
  "capital_stage": "pilot",
  "funding_instrument": "community_fund",
  "requested_amount": "1000.00",
  "minimum_viable_amount": "500.00",
  "maximum_authorized_amount": "1200.00",
  "currency": "cUSD",
  "risk_adjusted_expected_value": "900.00",
  "public_goods_value": "1100.00",
  "community_share": "100.00",
  "downside_exposure": "250.00",
  "rationale": "Draft rationale",
  "evidence": [],
  "tranches": [
    {"amount": 400.00, "milestone_conditions": {"milestone": "review"}}
  ]
}
```

`capital_stage` is one of discovery, experiment, pilot, replication, scale, or
maintenance. `funding_instrument` is grant, budget, bounty, loan, investment,
community_fund, or in_kind. Monetary values must be finite and precise to cents;
the schema's numeric bounds apply. Optional valuations may be negative where
they represent downside or net value. Currency is a 2–10 character code.
Rationale is 1–4,000 characters. Evidence is at most 100 JSON values and 64 KiB.
There may be at most 50 tranches; each has exactly an amount and an object of
milestone conditions (at most 8 KiB). Proposed tranche totals cannot exceed the
maximum authorized amount, or the requested amount when no maximum is given.

### Effects and retry behavior

The function creates one `solution_funding_case` in `draft` state and zero or
more `solution_funding_tranche` rows in `proposed` state. The case, tranches, and
private request receipt are one transaction. The response contains the case ID,
`draft` status, tranche count, creation time, and whether this was an exact
replay; it does not echo amounts, rationale, or evidence.

The request ID is scoped to the authenticated operator. Repeating the same
location, solution, active human identity, and payload returns the original
receipt. Reusing the request ID with changed fields or another scope fails
closed. Two-cent precision, amount bounds, JSON shape/size, and tranche totals
are checked in both Gateway validation and PostgreSQL.

The action does not submit the case, approve a case or tranche, release funds,
create a release ledger row, change the solution stage, or create a lifecycle
event. Those remain separately authorized human workflows. The proposer role
is non-login and cannot update or delete proposal receipts or update/approve
case and tranche rows. Runtime can call the bounded function but cannot read
the private receipt; Directus cannot execute the proposal function.

## Funding draft submission

`POST /operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/submit`
requires a separate exact-location `solution_lifecycle:submit` grant and signed
tenant context. The body contains only a UUID `request_id` and literal
`acknowledged: true`; the database also requires an active human binding and a
draft receipt created by the same operator and party at the same location.

The function locks the exact location-origin solution and draft, verifies the
case is still in `draft` with no submitter or approval attribution, and checks
that every tranche remains `proposed`. It atomically changes only the case to
`submitted`, records the active human submitter, and writes an immutable retry
receipt. Exact retries return the original submission; request collisions,
another operator's draft, duplicate submission, or a missing submit grant fail
closed. Tranches remain proposed, and the action cannot approve the case,
approve/release a tranche, create a release, or advance the solution stage.

The dedicated non-login submitter role has only the reads and case columns
needed for this transition. Runtime can execute the bounded function but cannot
read its receipt; Directus cannot execute it. Submission is not independent
approval; that remains a separate review action.

## Funding submission review reads

`GET /operator/api/solution-lifecycle/{location_id}/funding/review` and
`GET /operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/review`
require an exact `solution_lifecycle:review` grant and signed tenant context.
PostgreSQL rechecks the signed location and active human binding. The queue
contains only submitted, unapproved requests whose solution origin is exactly
the granted location. It returns bounded financial labels and self-authorship
and submitter-attribution booleans, but no person IDs or rationale. Detail reads
return bounded case terms, rationale, evidence, and proposed tranche terms as
private reviewer data; the Gateway uses read-only transactions and no-store
responses.

A separate non-login reviewer function owner has only the column grants needed
for these projections. The runtime can execute the bounded functions but cannot
read funding cases, tranches, or submission receipts directly; Directus cannot
execute either review function. Legacy submitted cases without recorded
submitter attribution remain visible as unattributed, with no inferred identity.
The review reads themselves do not mutate funding state. Case approval is a
separate action described below; the read/detail surface does not approve
tranches, disburse funds, or transition a solution stage.

## Independent funding case approval

`POST /operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/approve`
requires the exact `solution_lifecycle:review` grant, signed tenant context, and
an active human operator-to-party binding. The body contains only a UUID
`request_id` and literal `acknowledged: true`. PostgreSQL rechecks the exact
location-origin solution, submitted state, review grant, current human binding,
and that the reviewer differs from the attributed submitter. Cases without
submitter attribution remain visible for review but cannot be approved.

The transaction changes only `solution_funding_case.decision_status` to
`approved` and records reviewer party/time. It appends an immutable receipt in
the same transaction. Exact retries return the receipt; changed request reuse,
duplicate decisions, self-approval, stale or missing grants, wrong-location
cases, and unattributed legacy submissions fail closed. Proposed tranches remain
proposed. Approval does not approve a tranche, create a release, disburse funds,
or change the solution stage.

The dedicated non-login approver owner receives only the case decision columns,
the checks needed for tenant/human identity validation, and append-only receipt
access. Runtime can invoke only the bounded function and cannot read cases or
receipts directly; Directus cannot invoke it. The console shows the acknowledged
action only for a submitted case with a recorded submitter that is not
self-authored. CSRF, same-origin/no-store requests, stale-case guards, and a
stable request ID cover uncertain retries.

## Independent funding tranche approval

`GET /operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/review` requires an exact signed `solution_lifecycle:review` grant and returns bounded tranche terms for the exact location-origin solution. The response includes milestone conditions and eligibility booleans, not reviewer identities. `POST /operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/approve` accepts only a UUID `request_id` and literal `acknowledged: true`.

Migration 492 rechecks the signed location and active review grant, locks the case/tranche rows, and requires an approved case with a proposed tranche. The bound human reviewer must differ from both the attributed case submitter and case approver. The transaction changes only `solution_funding_tranche.status`, `approved_by_party_id`, and `approved_at`, then appends an immutable receipt. Exact retries replay that receipt; changed request reuse and duplicate approval fail closed. The action does not update release fields, create disbursement records, or change the solution stage.

The dedicated non-login tranche approver role can read only the columns needed to verify scope, identity, case state, and tranche terms. It can update only tranche decision columns; narrow `UPDATE(id)` grants on related rows support row locking inside the bounded functions. It can insert/read its receipt, but cannot update or delete it. Runtime can call those functions but cannot read funding tables or receipts directly. Directus cannot execute the functions. The console offers tranche review only for approved cases with proposed tranches and an exact review grant; private milestone terms are rendered as text, while approval uses explicit acknowledgement, CSRF, no-store, same-origin requests, and a stable request ID.

## Location-scoped replication proposal

`POST /operator/api/solution-lifecycle/{location_id}/replications` requires
signed `solution_lifecycle:create` context at the exact location, an active
create grant, and an active OIDC-to-person binding. Migration 494 independently
rechecks those conditions. The selected source experiment must have
`status='validated'`, a reviewed `validated` result, and an active human result
reviewer distinct from the experiment owner and protocol approver. Its solution
must be active and visible at the target location either by originating there
or through an explicit location link. The required target context can describe
a distinct deployment context within the same farm or a linked deployment
elsewhere; the proposal remains discoverable in the location replication read.

The body contains a UUID `request_id`, `source_experiment_id`, a required target
context of at most 2,000 characters, optional adaptation text of at most 4,000
characters, and a JSON object replication protocol limited to 64 KiB. The
function creates one `solution_replication` with `status='proposed'`, exact
location target scope, empty evidence, and null result, maturity, and reviewer.
The proposal and append-only receipt commit atomically. Exact retries return the
same receipt; changed input under the same operator/request ID, invalid source
lineage, missing grant, or missing active human binding fails closed.

The response includes only receipt and replication IDs, proposed status,
creation time, and replay status. It does not echo target narratives or
protocol. The operation does not approve, activate, review, complete, or add
evidence to the replication and does not change solution lifecycle stage. The
dedicated proposer role has only the source reads, proposal inserts, and
append-only receipt access needed by the function; it cannot update replication
review or outcome fields. Runtime can invoke the bounded function but cannot
read replication or receipt rows directly, and Directus cannot execute it. The
console offers active solutions with validated, reviewed experiments under both
exact read and create grants, then submits through CSRF-protected same-origin no-store requests with
stable request IDs for uncertain retries.

Disposable PostgreSQL 16 acceptance applies and replays migration 494 after
the prior solution lifecycle fixtures and verifies exact location scope,
validated source and exact location visibility, human attribution, changed-input
retry rejection, draft-only state, unchanged solution stage, and role boundaries.
It uses synthetic rows only; candidate and legacy databases are untouched.
Before rollout, disable the route and console panel while retaining migration
494. After application, use a reviewed forward migration for any schema change.

## Independent replication review

Migration 495 adds a separate review queue, private detail, and decision action:

- `GET /operator/api/solution-lifecycle/{location_id}/replications/review`
- `GET /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review`
- `POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review`

All three require signed exact-location `solution_lifecycle:review` context and
an active human identity. The queue and detail include only pending proposals
created by the location-scoped proposal flow and recheck target location plus
solution origin or explicit location link. Queue rows expose bounded solution
labels/stage, source-validation indicators, creation time, and proposer/self-
authorship booleans. Detail adds bounded target context, adaptation notes,
protocol, and source experiment/result status; neither projection returns
proposer or reviewer identities.

The POST body requires a UUID `request_id`, `decision` (`approved` or
`rejected`), and literal `acknowledged: true`; `review_reason` is optional for
approval and required for rejection. Rejection
requires a reason of 10–4,000 non-whitespace characters; an optional approval
reason is bounded to 4,000 characters. PostgreSQL rechecks the active exact
grant and human binding, proposal/source lineage and review state, and requires
the reviewer to differ from the attributed proposer. It atomically updates the
proposal decision, reviewer/time/reason, and append-only receipt. Exact retries
replay; changed request reuse, duplicate decisions, stale source eligibility,
missing attribution, and self-review fail closed.

Approval or rejection does not start or complete replication, add an outcome,
evidence, or maturity, or advance solution stage. A dedicated non-login reviewer
owner has bounded source access and may update only the decision fields. Runtime
can invoke the bounded functions but cannot read replication or review receipts
directly; Directus cannot execute them. The console gates the queue and action on
the exact review grant, suppresses the decision form for self-authored
proposals, and uses text rendering, no-store requests, CSRF, and stable retry
IDs.

Disposable PostgreSQL 16 applies and replays migration 495 and verifies nine
grouped acceptance areas, including independent approve/reject, retry and
collision behavior, exact location scope, direct-table denial, and unchanged
replication/solution lifecycle state. The 97-test focused Gateway, proposal,
console, route-policy, and migration selection passes. Candidate and legacy
databases are untouched; migration 495 is not rolled out.

## Independent replication activation

`POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/start`
requires signed exact-location `solution_lifecycle:transition` context and a
literal `acknowledged: true` with a UUID `request_id`. Migration 496 rechecks
the current transition grant, active operator identity, active human-party
binding, exact location target, independent approval receipt, and current
validated source experiment/result and solution visibility. A reviewed result
whose reviewer is also the experiment owner or protocol approver is not
eligible.

The database atomically changes only `status` from `approved` to `active` and
sets `started_at` and `started_by_party_id`, with an append-only idempotency
receipt. Exact retries replay the original result; request-key reuse with
different input fails. A new table trigger blocks direct lifecycle edits and
rejects elevated proposal-role inserts that try to start a replication; the
proposal role may still create a proposed draft. Runtime can call only the
bounded activation function and cannot read the receipt. Directus cannot call
the function. Activation does not set outcome, evidence, maturity, or
completion fields, and it does not advance the solution stage.

The console shows Start only for an approved replication when the exact
location transition grant is present. It uses explicit acknowledgement,
CSRF-protected same-origin no-store requests, and retains one request ID for
uncertain retries. The focused Gateway, proposal, review, console, route-policy,
and migration selection passes 108 tests. Disposable PostgreSQL 16 applies and
replays migration 496 and passes ten grouped activation, trigger, retry,
lineage, and privilege checks. Candidate and legacy databases are untouched;
migration 496 is not rolled out.

## Replication completion report proposal

`POST /operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals`
requires signed exact-location `solution_lifecycle:submit` context, an active
human binding, a UUID `request_id`, literal `acknowledged: true`, an allowlisted
outcome (`successful`, `failed`, `mixed`, or `inconclusive`), evidence maturity
from 1 through 6, a 10–4,000 character summary, and a JSON evidence array with at
most 100 items and 64 KiB. Migration 497 rechecks that the exact-location
replication is active and started, its independent approval receipt remains
valid, its source experiment/result is still validated and independently
reviewed, and the solution remains visible at that location.

The function records a private `proposed` completion report with an
operator-scoped idempotency key. Exact retries return the same proposal;
changed-payload key reuse and a second pending report for the same replication
fail closed. The report body is inaccessible directly to runtime and Directus;
runtime can call only the bounded submission function. Submission does not
change replication status, result, evidence, maturity, completion time, or
solution stage. An independent review action must accept the report before any
completion values are written; the legacy `failed` replication state remains a
separate operational disposition. A submitted report with outcome `failed` is
still a report result; migration 498 records it as `result = 'failed'` only
after review and sets the replication's operational status to `completed`.

The submission Gateway path and operator console now feed a separate
independent-review queue and decision. Migration 498 stores immutable review
receipts and reviewer attribution, and only an accepted report completes the
replication. Migration 497 remains unrolled out, as does migration 498.
The replication status view also exposes a completion-report form only to
operators with exact location read and submit grants. It validates the allowed
outcome, evidence maturity, bounded summary, and JSON evidence array; CSRF,
acknowledgement, and unchanged-request retry IDs are required. Submission leaves
the report proposed and the replication active until independent review.

## Replication completion report review

Migration 498 adds bounded queue/detail functions and a decision function under
the exact signed location `solution_lifecycle:review` grant and active human
binding. The reviewer must differ from the report author, replication starter,
initial approver, source experiment owner/protocol approver, and source result
reviewer. Queue/detail return conflict flags for the console; PostgreSQL repeats
all checks when a decision is recorded. Detail exposes only the private report
summary, bounded evidence references, outcome/maturity, solution context, and
independence/source-current flags. Runtime uses the bounded functions and
cannot read report/receipt tables directly; Directus receives no execute grant.

Decision requests require an idempotency UUID, literal acknowledgement, and
`accepted` or `rejected`; rejection requires a 10–4,000 character reason.
Acceptance atomically marks the replication `completed`, copies the accepted
report's outcome/evidence/maturity, and records reviewer attribution. A report
whose domain outcome is `failed` still produces operational replication status
`completed` with `result = 'failed'`; these fields represent distinct concepts.
Rejection leaves the replication `active` so the operator can submit a revised
report. Both decisions preserve the solution's current stage. The console uses
exact review-grant gating, text-only detail rendering, same-origin no-store
requests, CSRF on decisions, and stable request IDs for uncertain retries.

The focused replication proposal/review/activation/completion, console, and
route-policy regression selection passes 89 tests; a separate Gateway,
console, route-policy, and migration-metadata selection passes 87 tests. The
console suite passes 41 tests, including inline JavaScript syntax. Ruff,
Python compilation, inline JavaScript syntax, dependency-group alignment,
capability validation, runtime SQL inventory validation, and diff checks pass.
Disposable PostgreSQL 16 applies and replays migration 498 with the ordered
CAP-035 chain; twelve grouped checks cover detail independence flags, reviewer
separation, rejection/revision, acceptance, retries, lifecycle separation,
private tables, and role boundaries. Candidate and legacy databases are
untouched; migrations 497–498 are not rolled out.

## Independent learning proposal review

Migration 499 adds a private, exact-location review queue and detail read plus
an independent decision action for learning records created by the learning
proposal flow:

- `GET /operator/api/solution-lifecycle/{location_id}/learning/review`
- `GET /operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review`
- `POST /operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review`

Each route requires the signed exact-location `solution_lifecycle:review` grant
and an active human identity. PostgreSQL revalidates that the learning record
was proposed from a completed, independently reviewed replication targeting
this location, that the source experiment/result remains validated and
independently reviewed, and that the solution remains active and visible at
the location. Queue/detail responses expose bounded lesson fields and actor
conflict booleans, not party identifiers. A reviewer must be distinct from the
learning proposer, replication starter, initial replication approver,
completion-report reviewer, source experiment owner/protocol approver, and
source result reviewer.

The decision accepts only `accepted` or `rejected`, requires explicit
acknowledgement, and requires a 10–4,000 character reason for rejection. The
decision and immutable idempotency receipt commit atomically; exact retries
return the original receipt while changed-input reuse fails closed. The
decision changes only learning review status and attribution. It does not
apply the lesson or change the solution stage. The former direct legacy
learning-application helper is retired and fails closed; application is now
available only through the separately scoped Gateway operation in migration
500.

The dedicated non-login review owner has narrow source/tenant-check reads and
decision-column writes. Runtime can call only the bounded functions, cannot
read the private receipt directly, and cannot bypass the proposed-to-reviewed
trigger. Directus has no execute grant. The operator console renders private
lesson text as text, gates queue/detail and decisions on exact review grants,
and uses no-store reads, CSRF, acknowledgement, stale-record checks, and stable
retry IDs. Migrations 499–500 are not applied to candidate or legacy.

## Accepted learning application

Migration 500 adds a paged accepted-learning application queue and an apply
action:

- `GET /operator/api/solution-lifecycle/{location_id}/learning/application`
- `POST /operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/apply`

Both require exact signed location `solution_lifecycle:apply` scope. The
operator must be an active human and must differ from the learning reviewer.
The bounded queue revalidates current completed replication and independent
completion review, validated experiment/result, and active location-visible
solution lineage before returning private lesson content. The action requires
explicit acknowledgement and a target version of 1–80 non-whitespace
characters. PostgreSQL repeats authorization, source-state, identity, and
reviewer-independence checks, then atomically marks only the learning record
applied and stores an immutable retry receipt. Exact retries replay the
original result; changed-payload reuse and stale or unauthorized records fail
closed. Solution stage is unchanged.

A dedicated non-login applier role owns only the narrow source columns and
bounded functions. Runtime cannot directly update learning records or read
application receipts; Directus has no function access. The console renders
lesson content as text, gates queue and action on the apply grant, and uses
same-origin no-store/CSRF requests, explicit acknowledgement, bounded paging,
and a stable request ID for retry. The legacy application helper fails closed.
Migration 500 passed disposable PostgreSQL 16 apply/replay and nine grouped
application, scope, identity, idempotency, lifecycle, and privilege checks;
candidate and legacy were untouched.

## Legacy direct learning-proposal boundary

`solution_scale.record_learning` no longer writes `solution_learning_record`
through the legacy shared-role connection. It fails before opening a cursor;
proposals must use the exact-location replication learning route, then pass
independent review before the separately authorized apply action. This closes
the duplicate direct write without removing the proposal/review/application
capability. The source audit records other lifecycle write helpers that still
need equivalent scoped paths or retirement at
`solution-lifecycle-source-route-audit.md`.

## Adoption-event consent boundary

The legacy `solution_adoption.record_event` helper no longer accepts
`consent_checked=True` as evidence and fails before database access for every
event type. The canonical consent stream is party-linked, while adoption
programs currently have no configured consent policy and event references have
no canonical participant-party link. Do not restore the legacy write by adding
another caller-supplied flag. The replacement must bind the participant to a
canonical party, resolve the program's reviewed policy, validate the current
exact-scope consent decision, and write through a bounded location-scoped
Gateway action. Adoption event ingestion remains an open capability until that
path exists.

## Legacy gate-evaluation and approval boundary

The legacy `solution_lifecycle.evaluate_gate` and `approve_gate` helpers no
longer write directly to shared tables. Evaluation uses the exact-location
Gateway action backed by migrations 483 and 484; independent gate review and
approval use the review path, with compatibility behavior for gates that do
not require a distinct reviewer preserved by migration 485. The helpers fail
before database access, leaving the protected paths as the supported write
surface. The legacy `transition` helper now fails before database access for
all valid non-retirement stages. Migration 486 supports exact-location,
gate-backed promotion transitions and rechecks the approved current-stage gate
and its prerequisites in one transaction. Scoped transitions to the other
non-retirement stages do not yet have a replacement route and remain an open
capability-parity item. Retirement stays separate and uses migration 502's
migration-start, effective-sunset, and post-retirement-review workflow. The
experiment integration test sets its initial stage as fixture state; no
production service caller remains on the legacy helper.

## Legacy retirement-helper boundary

The old `solution_scale.propose_retirement` and
`solution_scale.approve_retirement` helpers no longer write directly to shared
tables. They fail before opening a connection and direct operators to the
location-scoped Gateway proposal and independent approval routes backed by
migrations 476 and 475. The Gateway routes preserve the proposal/review
capability with signed location grants, active human attribution, independent
review, bounded evidence/plan fields, and immutable retry receipts. Remaining
retirement execution, sunset, and post-retirement workflows stay open; this
change only closes the unscoped legacy write path.

The focused Gateway, route-policy, console, solution-application, and migration
selection passes 94 tests; the database-backed solution-scale test is skipped
because no permitted local PostgreSQL connection was available. Ruff, Python compilation,
inline JavaScript parsing, and diff checks pass. Disposable PostgreSQL 16
applies and replays migrations through 499 and passes eleven grouped learning
review checks covering lineage, reviewer conflicts, accept/reject, retry
receipts, privilege boundaries, and the accepted-only apply path. Candidate and
legacy databases are untouched.

For rollout, disable the three review routes and console panel while retaining
migration 499. After applying the migration, use a separately reviewed forward
migration to change its schema or ACL objects; do not edit or reverse an
applied migration.

## Scale-gate assessment and independent review

Migration 501 adds exact-location assessment target listing, submission, private
review queue/detail, and independent accept/reject routes:

- `GET /operator/api/solution-lifecycle/{location_id}/scale-gates/assessment-targets`
- `POST /operator/api/solution-lifecycle/{location_id}/scale-gates/{gate_id}/evaluations`
- `GET /operator/api/solution-lifecycle/{location_id}/scale-gates/review`
- `GET /operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}`
- `POST /operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}`

Submission requires signed exact-location `solution_lifecycle:create`, an active
human identity, a pending or failed location gate, bounded sample/evidence, and
a stable request UUID. PostgreSQL derives typed numeric results from the stored
comparator and threshold and enforces the configured minimum sample; untyped
gates require an explicitly proposed result. Assessments begin pending, retain
append-only measured values and evidence references, and allow only one pending
assessment per gate. Exact request retries replay; changed reuse fails closed.

Queue/detail and decision require signed exact-location
`solution_lifecycle:review`. The reviewer must be an active human distinct from
the evaluator. Acceptance records reviewer attribution and applies only the
assessment's result, measurement, and evidence to the gate. Rejection records a
reason and leaves the existing gate state unchanged. Neither decision changes
the solution stage. The console requires acknowledgement, uses text-only
evidence rendering, bounded pagination, CSRF/no-store requests, and stable
request IDs. Legacy direct scale-gate helpers fail before database access.
Runtime and Directus cannot read or write these tables directly; bounded
security-definer functions use a dedicated non-login owner with column-scoped
privileges.

Migration 501 passed disposable PostgreSQL 16 apply/replay and nine grouped
checks for typed threshold/sample behavior, exact signed scope, actor separation,
review and retry semantics, unchanged stage, and role boundaries. Candidate and
legacy databases were untouched. Migration 501 has not been rolled out.

## Retirement migration, sunset, and post-retirement review

Migration 502 advances an independently approved location retirement through
three separately authorized actions:

- `POST /operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/migration`
  requires exact `solution_lifecycle:transition`, a current/future timezone-aware
  effective timestamp selected by the operator, the approved migration plan and
  evidence, and an active human distinct from proposer and approver. It records
  status `migration` and leaves the solution active.
- `POST /operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/sunset`
  requires the same exact transition grant and becomes eligible only at or after
  the stored effective timestamp. It atomically moves the retirement to
  `sunset`, sets the solution lifecycle stage/status to `retired`, records
  `retired_at`, and appends the canonical solution lifecycle event.
- `POST /operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/post-retirement-review`
  requires exact `solution_lifecycle:review` and a separate active human who is
  distinct from the proposer, approver, and sunset actor. It records the
  evidence-backed review date and moves the retirement to `completed`.

All requests require acknowledgement, bounded notes and evidence, a stable
request UUID, and signed exact-location tenant context. PostgreSQL locks the
retirement and solution while transitioning, writes immutable receipts in the
same transaction, replays exact retries, and rejects changed-content reuse or
out-of-order transitions. Runtime and Directus cannot read or write the receipt
table directly. Neither sunset nor review deletes or prunes source, farm, or
evidence data. Retention periods and legal holds are governed by separately
configurable policy; migration 502 hardcodes no archive or deletion interval.
The old shared-role `solution_lifecycle.transition(..., to_stage="retired")`
path fails before database access.

Migration 502 passed disposable PostgreSQL 16 apply/replay after the CAP-035
chain and nine grouped checks for independent approval, effective-time gating,
unchanged active state during migration, atomic sunset, separate post-review,
stable retries, and runtime/Directus access boundaries. Candidate and legacy
databases were untouched; migration 502 has not been rolled out.

### Non-promotion stage transitions

Migration 503 adds a bounded exact-origin target read and a separate action for
nonterminal stages that do not use promotion gates:

- `GET /operator/api/solution-lifecycle/{location_id}/stage-transition-targets`
  requires signed exact-location `solution_lifecycle:read`. It returns at most
  50 location-origin solutions per page, with fixed labels, current stage,
  solution status, and update time. It excludes retired and superseded records;
  explicit location links do not authorize mutation.
- `POST /operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/stage-transition`
  requires signed exact-location `solution_lifecycle:transition`, an active
  operator-to-person binding, the exact location-origin relationship, explicit
  acknowledgement, a 10–4,000 character rationale, 1–100 evidence references
  capped at 64 KiB, and an optional rollback plan capped at 4,000 characters.
  `expected_from_stage` is compared under a solution row lock so stale console
  views fail with a conflict.

The allowed targets are `discovered`, `triaged`, `framed`, `experiment_ready`,
`testing`, `investment_ready`, `pilot_active`, `adopting`, `maintained`,
`paused`, and `failed`. `validated`, `funded`, `adoption_ready`, and `scaled`
remain behind migration 486's approved gate transition. `retired` and
`superseded` remain behind the reviewed retirement/replacement workflow;
generic stage writes cannot bypass its independent approval or replacement
selection. `adopting` also retains the legacy requirement for approved location
readiness and configuration. The generic transition never changes solution
status, creates an approval, or retires data.

The stage update, canonical lifecycle event, and private append-only request
receipt commit atomically. Exact retries replay the original event; reusing a
request UUID with changed input is rejected. Runtime can call only the bounded
functions, Directus cannot execute either function, and runtime/Directus cannot
read or write the receipt table directly. The dedicated function owner has
column-scoped privileges and no role memberships.

Focused Gateway, route-policy, console-contract, and existing gate-transition
checks pass 38 tests. Disposable PostgreSQL 16 applies and replays migration
503 after the CAP-035 chain and passes 14 grouped checks for exact location
scope, active human identity, adoption prerequisites, promotion/retirement/
supersession separation, stale-stage rejection, idempotency collisions,
atomicity, and role boundaries. The synthetic fixture adds canonical columns
omitted by earlier compact test fixtures. Candidate and legacy remain
untouched; migration 503 is not rolled out.

### Acceptance and rollback

Focused Gateway, route-policy, console, and migration checks cover exact grants,
active human context, strict request bounds, stable retries, the draft-only
state boundary, separately authorized submission, private reviewer reads, and
independent funding, tranche, replication review, replication activation,
completion-report proposal/review, learning proposal/review, accepted learning
application, scale-gate assessment/review, and retirement execution. Disposable
PostgreSQL 16 applies and replays migrations 488–504 and checks location-origin
targeting, create/submit/review/transition authorization, private receipts,
tranche ceilings, atomic writes, self-authorship, legacy unattributed records,
approval retries and collisions, role boundaries, unchanged proposed tranche
states, independent reviewer separation, immutable receipts, unchanged release
state, exact learning-application grant and actor separation, retries, private
receipts, unchanged solution/replication lifecycle stage, effective retirement
timing, sunset, and separate post-retirement review. The checker uses synthetic
rows only; candidate and legacy databases are not involved.

Before rollout, the routes and UI can be disabled while retaining migrations
488–504. After application, do not edit or reverse them; disable the routes and
use a separately reviewed forward migration if their schema objects must be
removed.
