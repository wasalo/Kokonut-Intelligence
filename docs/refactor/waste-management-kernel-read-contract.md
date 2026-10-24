# Waste management Kernel read contract

**Status:** prepared source capability; populated-data and manual acceptance are open.

## Route and authorization

`GET /operator/api/waste/{location_id}/summary` is private and requires the
exact OIDC location grant `waste_management:read`. The Gateway verifies the
operator and location grant in PostgreSQL through signed tenant context before
the data queries. Unknown paths, wrong methods, disabled OIDC, and missing
grants fail closed. The response is `no-store` and varies on the session
cookie.

## Projection

The service uses one repeatable-read, read-only transaction with statement and
lock timeouts. Every source query repeats the requested location. Waste-stream,
composting, and recycling aggregates include only `verified` records; their
grouping preserves waste type/disposal method/recorded unit, compost feedstock
and method, and recycling material respectively. Quantity values remain in
their source units and are never combined across groups.

Pollution incident aggregation reports count and first/last date by the
schema-controlled severity and lifecycle status. It exposes no incident type,
narrative, affected area, remedial action, reporter/recipient, notes, IDs, or
arbitrary metadata. These counts are descriptive and do not determine
compliance, severity response, or closure.

The console is hidden unless the session has an exact location grant. It uses
same-origin/no-store requests, validates the response location and bounded
schema categories, discards stale responses, and renders fixed fields with
`textContent`.

## Verification and rollback

Focused fake-connection and Gateway tests cover route policy, missing-grant
denial, invalid identifiers before connection, signed context ordering,
location filters on each source query, lifecycle filters, output omission, and
connection cleanup. Console contracts cover grant gating, field allowlists,
stale-response checks, no-store requests, and inline JavaScript syntax. No
schema migration is required. Rollback is a source rollback: remove the route,
service, console panel, and route inventory row, then regenerate the runtime
SQL inventory. No data rollback is necessary.

## Remaining acceptance

This is an initial CAP-006 read path, not full energy/waste/landscape parity.
Waste calculation parity, composting quality/scoring, landscape habitat and
pollinator workflows, populated legacy output parity, runtime ACL/RLS, live
ZITADEL/browser behavior, and MAN-CAP-006 remain open.
