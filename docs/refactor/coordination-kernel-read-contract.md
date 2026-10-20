# Coordination Kernel read contract

CAP-034 adds one location-scoped, read-only governance summary for alliances.
The legacy coordination service and its database triggers remain authoritative
for approval, quorum, consent, activation, publication, learning, and remedy
behavior.

## Route and authorization

`GET /operator/api/coordination/{location_id}/summary` requires an authenticated
operator and an exact active `coordination:read` grant for the requested
location. The Gateway establishes signed tenant context on the same read-only
PostgreSQL transaction that invokes the projection. Responses are `no-store`
and vary by the operator cookie. Unknown routes and methods remain protected.

## Projection

The summary counts only alliances with `scope_type = location` and an exact
`scope_id` match. It reports lifecycle totals, overdue active/paused reviews,
unreviewed conflict declarations and harm analyses, open appeals/remedies,
preserved minority views, completed knowledge exchanges, open learning links,
and draft/rejected metric observations. It includes no alliance names, party
identities, text, evidence, metric values, or organization/network rows.

The SQL function is owned by a dedicated non-login reader role with aggregate
source-table SELECT only. Runtime receives function execution only; Directus
has no function access or reader-role membership. The endpoint does not mutate
coordination state or authorize legal, financial, or operational action.

## Acceptance boundary

Focused Gateway, exact route-policy, source, and disposable PostgreSQL 16 checks
verify location isolation, aggregate correctness, signed context/grants,
migration replay, and least-privilege boundaries. Candidate and legacy
databases are untouched. CAP-034 remains prepared pending populated alliance
parity, live OIDC/browser acceptance, trigger and worker outage acceptance,
broader ACL/RLS, and MAN-CAP-034 owner review.

## Operator console

The operator console displays the aggregate summary only when the signed session
contains an exact `coordination:read` grant for the selected location. It uses a
fixed allowlist of the 19 projection counters and inserts labels and values as
text. Requests are same-origin and no-store; stale responses are discarded when
the selected location changes. The panel has no alliance mutation or approval
controls and does not constitute live OIDC/browser acceptance.
