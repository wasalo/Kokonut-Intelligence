# Solution lifecycle Kernel write contract

**Status:** prepared implementation contract; migrations 488–492 are additive and are
not applied to the local candidate or legacy database.

This document specifies the operator Gateway's bounded write boundary for the
solution lifecycle. Existing CLI and Directus workflows remain legacy adapters;
the Gateway path is the Kernel-owned interface.

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

### Acceptance and rollback

Focused Gateway, route-policy, console, and migration tests cover exact grants,
active human context, strict request bounds, stable retries, the draft-only
state boundary, separately authorized submission, private reviewer reads, and
independent funding case and tranche approval. Disposable PostgreSQL 16 applies and replays
migrations 488–492 and checks location-origin targeting, create/submit/review
authorization, private receipts, tranche ceilings, atomic writes, self-authorship, legacy unattributed records, approval retries and collisions,
role boundaries, unchanged proposed tranche states, independent tranche-reviewer separation, immutable tranche receipts, unchanged release state, and unchanged solution stage. The checker uses synthetic rows only; candidate and legacy databases are
not involved.

Before rollout, the routes and UI can be disabled while retaining migrations
488–492. After application, do not edit or reverse them; disable the routes and
use a separately reviewed forward migration if their schema objects must be
removed.
