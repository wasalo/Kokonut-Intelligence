# Farm energy Kernel read contract

**Status:** prepared source capability; populated-data and manual acceptance are open.

## Route and authorization

`GET /operator/api/energy/{location_id}/summary` is private and requires the
exact OIDC location grant `energy_monitoring:read`. The Gateway verifies the
operator and location grant in PostgreSQL through signed tenant context before
the query. Unknown paths, wrong methods, disabled OIDC, and missing grants fail
closed. The HTTP response is `no-store` and varies on the session cookie.

## Projection

The service opens one read-only, repeatable-read PostgreSQL transaction, sets
statement and lock timeouts, then groups `energy_reading` by reading type,
energy source type, and activity type. Both reading and source rows must match
the requested location. Only `verified` and `approved` readings are included.
The bounded response reports reading count, total kWh, and first/last reading
date per fixed schema grouping.

The projection omits costs, source names, equipment/device IDs, notes, and
arbitrary metadata. It does not calculate carbon intensity, savings, cost,
renewable share, or recommendations. Source rows are not changed and no
schedule/device control is exposed. The console shows this aggregate only when
the session provides the exact location grant; fields are allowlisted and
rendered with `textContent`, with response location/unit checks and stale
request suppression.

## Verification and rollback

Focused fake-connection and Gateway tests cover exact authorization, denied
route preflight, signed context ordering, location join/filter, verified-state
selection, response projection, connection cleanup, console grant gating,
no-store behavior, and inline JavaScript syntax. No schema migration is
required. Rollback is a source rollback: remove the registered route/service
and console panel, then regenerate the runtime SQL inventory and capability
records. No data rollback is necessary.

## Remaining acceptance

This prepares an initial CAP-006 read path only. It does not establish parity
for energy calculations, waste management, habitat/pollinator features,
populated farm outputs, runtime database ACL/RLS, live ZITADEL/browser behavior,
or MAN-CAP-006. Do not infer those capabilities from this route.
