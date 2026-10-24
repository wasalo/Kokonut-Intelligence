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

The legacy `record_waste` writer now inserts into `waste_stream` with the
canonical `record_date`, `quantity_unit='kg'`, JSONB metadata, and `recorded`
status. Its `organic` input maps to canonical `organic_waste`; `chemical` and
other unsupported legacy type/disposal labels map to `other` and remain in
metadata to avoid misclassification. The optional source value is also
preserved in metadata. Function arguments, response shape, and CLI remain
compatible. This is a trusted local CLI write path without tenant
authorization; the database lifecycle still requires human verification
before the summary includes a row.

The legacy `record_recycling` writer now inserts into migration-153
`recycling_log`, including its required `record_date` and `recorded` lifecycle
state. It preserves the existing CLI/function arguments and response fields,
including destination, optional revenue, notes, and metadata. A successful
insert is still only recorded; the verified-only summary does not include it
until separate human verification. This remains a trusted local CLI write path
without tenant authorization.

The legacy incident CLI now writes `incident_date` and schema-supported
incident types to `pollution_incident`; `air_pollution` maps to `air_emission`,
and unsupported labels map to `other` while the original type remains in
metadata. `reported_by` is kept in metadata rather than assigned to the
unrelated `reported_to` or UUID `created_by` columns. Resolution sets the
canonical `resolved` boolean, status, remedial action, resolution date, and
`updated_at`. The incident summary selects unresolved `open`, `investigating`,
and `remediation` records, retrieves reporter attribution from metadata, and
counts resolved rows using the lifecycle status/flag. These operations remain
trusted CLI paths and do not establish tenant authorization.

The legacy `get_composting_efficiency` read also uses schema-153 columns:
`finished_volume_kg` supplies output values, per-batch yield is calculated
from finished volume over positive feedstock, and `compost_date` supplies the
recent-row date. Method and recent-measurement reads require `verified` status;
the overall totals include all verified batches so incomplete output continues
to count toward feedstock totals as in the legacy formula. Its response keeps
the existing recent-quality fields and reads numeric pH from the canonical
JSONB metadata extension when present. The legacy `record_composting` writer
uses migration-153 columns and the `recorded` state, maps accepted method and
feedstock categories to the schema constraints, and preserves unsupported
freeform labels plus pH in metadata. Its external function/CLI parameters and
response remain compatible. These remain trusted local CLI operations, not
authenticated tenant-scoped APIs.

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
