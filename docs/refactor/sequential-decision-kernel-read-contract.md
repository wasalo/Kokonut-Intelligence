# Sequential evidence Kernel read contract

**Status:** CAP-036 location-scoped summary and redacted evidence timeline prepared; not owner-accepted.
**Migrations:** `460_location_scoped_sequential_decision_summary.sql` and
`478_location_sequential_evidence_timeline.sql`.
**Routes:** `GET /operator/api/sequential-evidence/{location_id}/summary` and
`GET /operator/api/sequential-evidence/{location_id}/events`.
**Authorization:** exact `sequential_evidence:read` location grant and signed
operator tenant context, checked by Gateway and again inside PostgreSQL.

## Purpose and scope

The existing `services/decision/` implementation maintains immutable evidence
events, applies likelihood ratios to posterior odds, evaluates decision
thresholds, and can hand a governed result to solution gates or strategy review.
This first Kernel slice adds a read-only aggregate for one location. It does not
write evidence, recalculate odds, evaluate a decision, or trigger a downstream
review or stage transition.

The SQL projection recognizes only three explicit source lineages:

- hypotheses about a strategy plan whose `scope_type` and `scope_id` exactly
  match the requested location;
- hypotheses about a threat whose `location_id` exactly matches;
- hypotheses about a solution originated in or explicitly linked to the
  requested location.

Unknown subject types, organization-scoped plans, other locations, and
unlinked solutions are excluded.

## Response

The summary returns counts for hypothesis lifecycle state, evidence quality,
total evidence events, events with posterior updates, posterior update count,
and each hypothesis's latest threshold action. It omits hypothesis statements,
source references and IDs, raw values, likelihoods, probabilities, parties,
and individual timestamps. The response is `no-store` and varies on the
operator session cookie.

The summary does not prove posterior sequence correctness by itself. The
immutable source ledger and existing sequential decision tests remain the
source for calculation behavior. The event timeline adds a bounded item-level
view of ordering and review metadata, without exposing decision content or
calculation values.

The timeline supports only the three source lineages explicitly checked by
migration 460: location-scoped strategy plans, threats at the exact location,
and solutions originated in or explicitly linked to the location. Unknown
subject types and organization-scoped plans remain excluded. Pages contain at
most 50 items, accept offsets through 10,000, and are capped at 128 KiB. Stable
ordering is by hypothesis creation/id, then event observed/ingested/created
timestamps and event ID as a private tie-breaker. Each item exposes only an
opaque hypothesis sequence, allowlisted subject type, event sequence, observed
and ingested timestamps, evidence class and quality status, plus a nullable
posterior update sequence, calculation version, and update timestamp. It does
not expose hypothesis/event IDs, statements, source IDs/references, raw values,
source reliability, dependence groups, likelihoods, posterior odds or
probabilities, threshold evaluations, or party identities.

## Database boundary

`kokonut_sequential_reader` is a dedicated non-login, non-inheriting role with
SELECT only on the ledger, the three source relations, and the tenant grant
relations required by the authorization helper. Its stable security-definer
function rechecks actor type, signed location context, and exact
`sequential_evidence:read`. Runtime may call the projection but cannot select
the ledger directly. Directus has no table or function access. The reader has
no identity-table or write privilege.

## Verification and remaining parity

Focused Gateway, route-policy, migration metadata, and legacy decision checks
plus disposable PostgreSQL 16 apply/replay acceptance are recorded in
`builds/2026-10-19-recovery/cap-036-sequential-decision-disposable.json`.
Migration 478 applies/replays on disposable PostgreSQL 16 and passes eight
acceptance groups for ordering, pagination, exact source lineage, privacy,
tenant grants, and role boundaries; evidence is in
`builds/2026-10-19-recovery/cap-036-sequential-evidence-timeline-disposable.json`.
Candidate and legacy databases are untouched; migrations 460 and 478 are not
rolled out. Remaining gates include complete source-type lineage, populated
reference comparison, live OIDC/browser, broader ACL/RLS, recovery acceptance,
and MAN-CAP-036 owner review.

## Rollback

Before rollout, remove the route, policy entry, read service, and tests together.
After migration application, disable the route and retain migration 460's
ordered function and ACL. Do not edit/reverse the migration; a later schema
rollback requires an appended migration after evaluating created dependencies.
