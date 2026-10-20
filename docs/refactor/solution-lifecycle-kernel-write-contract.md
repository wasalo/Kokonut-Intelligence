# Solution lifecycle Kernel write contract

**Status:** prepared implementation contract; migration 488 is additive and is
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

### Acceptance and rollback

Focused Gateway, route-policy, console, and migration tests cover exact grants,
active human context, strict request bounds, stable retries, and the draft-only
state boundary. Disposable PostgreSQL 16 applies and replays migration 488 and
checks location-origin targeting, create authorization, private receipts,
tranche ceilings, atomic writes, and unchanged solution stage. The checker uses
synthetic rows only; candidate and legacy databases are not involved.

Before rollout, the route and UI can be disabled while retaining migration 488.
After application, do not edit or reverse it; disable the route and use a
separately reviewed forward migration if the schema objects must be removed.
