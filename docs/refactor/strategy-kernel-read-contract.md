# Strategy Kernel location read contract

## Scope

This first CAP-028 Kernel slice exposes a bounded read projection for strategy
plans owned by one location. It does not create or modify plans, allocate
funds, approve execution, or expose organization-wide plans to a location grant.

## Gateway API

`GET /operator/api/strategy/{location_id}/plans?limit=50&offset=0` requires an
active OIDC operator session and the exact location-scoped `strategy:read`
grant. The handler binds signed tenant context and calls the bounded
`kokonut_security.list_location_strategy_plan_summaries` function on the same
read-only transaction. The response is paginated, `no-store`, and location
qualified.

Each plan item contains its identifier, name, version, lifecycle status,
visibility, planning horizon, update time, cascade mode/status and a boolean
indicating whether a parent plan exists. It also contains bounded aggregate
counts for objectives, initiatives, investment cases, coherence findings,
structural gate blockers, open review tasks, and submitted/approved allocation
decisions. The projection does not return diagnosis, guiding policy, theory of
change, cascade rationale, allocation rationale, costs, evidence, or party
identities. Parent organization plan identifiers and details are withheld.

`structural_gate_status` reports the source view's structural checks only. It
does not indicate human approval, authorize execution, or change a plan's
lifecycle state. Strategy mutations and the complete CAP-028 parity contract
remain separate work.

## Database and authorization boundary

Migration 452 creates a non-login, non-inheriting reader role and a security-
definer read function. The function validates operator context, exact location,
active `strategy:read` grant, page bounds, and `scope_type='location'` before
returning any plan. The runtime receives function execution only from this
migration; Directus is not given the function. The function owner receives
read access only to the relations required for this projection and tenant
grant validation.

This narrow Gateway contract does not establish universal tenant RLS or remove
any pre-existing runtime privileges used by legacy services. Those boundaries
remain open in the tenant/RLS and Directus parity inventories.

## Verification and rollback

Focused source tests cover input validation before database access, transaction
context, exact location and grant policy, projection field allowlisting, route
authentication, no-store responses, and paging. Disposable PostgreSQL 16
acceptance applies and replays migration 452, verifies exact location scope,
grant denial, bounded pagination, aggregate lineage, free-text exclusion, and
role/function privileges. It does not modify the candidate or legacy database.

Before migration 452 is applied anywhere, remove the Gateway route and
registration. After an ordered migration has been applied, roll back the app
surface while retaining the additive function and role; do not edit or reverse
the migration. Re-enable the route only after the focused checks pass.
