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

Verified composting also returns bounded efficiency and process aggregates by
feedstock and method from the canonical `composting_record` columns. Recorded
output uses `finished_volume_kg`; weighted yield is total recorded output
divided by all verified feedstock in the group, while mean batch yield and
duration use only batches with output and positive feedstock. Mean temperature
and moisture include all verified batches. `graded_batches` is only a count;
grade labels, notes, and source rows are not returned. The schema has no pH
column, so pH is not inferred. These summaries are descriptive and advisory,
not a compost-quality score, certification, or compliance result.

Pollution incident aggregation reports count and first/last date by the
schema-controlled severity and lifecycle status. It exposes no incident type,
narrative, affected area, remedial action, reporter/recipient, notes, IDs, or
arbitrary metadata. These counts are descriptive and do not determine
compliance, severity response, or closure.

## Legacy CLI summary compatibility

The existing `services.analytics.waste_management.get_waste_summary` now reads
the canonical `waste_stream` table and `record_date` column from migration 153.
Its output shape is unchanged. It filters to `verified` rows, matching the
schema's lifecycle constraint, and computes the requested window with a bound
integer day count (`CURRENT_DATE - (%s - 1)`), which includes exactly the
requested number of calendar dates including today. Invalid, non-positive,
non-integer, and boolean windows fail before cursor acquisition. Its cursor
closes on both success and query failure. This remains a trusted local CLI
path; it does not add an authenticated API or tenant authorization boundary.

The console is hidden unless the session has an exact location grant. It uses
same-origin/no-store requests, validates the response location and bounded
schema categories, discards stale responses, and renders fixed fields with
`textContent`.

## Verification and rollback

Focused fake-connection and Gateway tests cover route policy, missing-grant
denial, invalid identifiers before connection, signed context ordering,
location filters on each source query, lifecycle filters, output omission,
compost yield/process calculations, and connection cleanup. Console contracts
cover grant gating, compost numeric/count bounds, field allowlists,
stale-response checks, no-store requests, and inline JavaScript syntax. The
focused Gateway/console selection passes 11 tests with Ruff, Python
compilation, SQL inventory, capability validation, and diff checks. No schema
migration or database was used. Rollback is a source rollback: remove the
projection and console fields, then regenerate the runtime SQL inventory. No
data rollback is necessary.

## Remaining acceptance

This is an initial CAP-006 read path, not full energy/waste/landscape parity.
Compost quality scoring and certification, waste calculation parity,
landscape habitat and pollinator workflows, populated legacy output parity,
runtime ACL/RLS, live ZITADEL/browser behavior, and MAN-CAP-006 remain open.
