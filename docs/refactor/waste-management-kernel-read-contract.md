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

The legacy `record_waste` Python helper and `record-waste` CLI now fail closed
because the old location argument was caller-selected and did not establish an
authenticated tenant identity. The helper rejects before opening a cursor; the
CLI is marked database-free and directs operators to the authenticated Gateway
capture form. This removal applies only to that unscoped waste-stream writer;
other local composting, recycling, and incident CLI writes still lack tenant
authorization and remain separate parity work. The Gateway replacement checks
`waste_management:create`, writes canonical kilogram rows as `recorded`, and
uses an idempotency receipt. Human verification remains separate.

The legacy `record_recycling` writer now inserts into migration-153
`recycling_log`, including its required `record_date` and `recorded` lifecycle
state. It preserves the existing CLI/function arguments and response fields,
including destination, optional revenue, notes, and metadata. A successful
insert is still only recorded; the verified-only summary does not include it
until separate human verification. This remains a trusted local CLI write path
without tenant authorization. Material labels outside the schema enum map to
`other` and are preserved under `legacy_material_type` in metadata, avoiding a
database constraint error while retaining the caller's value.

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

The legacy CLI contract was exercised against the actual migration-153 schema
in disposable PostgreSQL 16. Migration apply/replay and synthetic inserts
verified the retired waste helper fails closed, three remaining local writers,
initial recorded/open states, canonical enum constraints, JSONB preservation,
verified-only waste summary, compost yield/pH, reporter attribution, and incident
resolution. Waste rows in this run are synthetic read fixtures, not helper writes. This does not
exercise tenant roles or populated legacy outputs
([runner](../scripts/check-waste-management-disposable.py);
[evidence](builds/2026-10-24-recovery/cap-006-waste-management-disposable.json)).

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

The console gates its summary on `waste_management:read` and the capture form on
`waste_management:create` independently. It uses same-origin/no-store requests,
validates the response location and bounded schema categories, discards stale
responses, and renders fixed fields with `textContent`.

## Kernel waste-stream capture

`POST /operator/api/waste/{location_id}/records` records one waste-stream row
under the exact location `waste_management:create` grant. Middleware requires
an authenticated OIDC session and CSRF token; the service validates UUIDs,
canonical waste/disposal categories, a positive kilogram amount with at most
two decimal places, a non-future ISO date, bounded text, and an exact request
shape before opening PostgreSQL. The route caps streamed JSON at 4 KiB and
returns `no-store` responses.

Migration 613 adds a bounded `SECURITY DEFINER` function owned by the isolated
`kokonut_waste_stream_writer` role. It checks signed operator/location context
and the live exact create grant, writes `status='recorded'` and `quantity_unit='kg'`,
and records a private SHA-256 idempotency receipt. Exact retries return the
original record ID; changed input with the same operator/request ID conflicts.
The response contains only record ID, location, record date, lifecycle state,
and replay indicator. The console preserves the exact payload and request ID
for same-page retries, and never presents capture as verification or
publication. Newly captured rows remain absent from verified aggregates until
a separate human verification path exists.

The receipt table is not directly readable by runtime or Directus, and the
bounded function is not executable by Directus. The legacy `record_waste` helper and CLI fail closed before cursor/database
acquisition; other local write CLIs still lack tenant authorization.
Runtime/Directus access to canonical waste rows still needs a separate ACL/RLS
decision. Entry notes are stored in the
canonical table and omitted from this Gateway response and aggregate projection;
this slice does not claim Directus field-level privacy parity.

## Verification and rollback

Migration 613 applies and replays against the canonical migration-153 table
with synthetic identity/grant/context helpers in disposable PostgreSQL 16.
The helper is not cryptographic acceptance; the shared tenant-context suite
covers the signed context implementation. Native and linux/arm64 checks cover exact-grant
success, recorded-only state, replay identity, changed-input conflict,
mismatched location, absent grant, wrong actor type, invalid category, and
runtime/Directus receipt and function ACLs. The ARM64 run is software
emulation evidence, not physical Raspberry Pi acceptance. Candidate and legacy
databases are not used. Source rollback disables the POST route, exact route
policy, form, and migration reference; if migration 613 has been applied, keep
the append-only receipts and function until dependent requests are resolved.

The earlier read-only summary batch's focused fake-connection and Gateway tests cover route policy, missing-grant
denial, invalid identifiers before connection, signed context ordering,
location filters on each source query, lifecycle filters, output omission,
compost yield/process calculations, and connection cleanup. Console contracts
cover grant gating, compost numeric/count bounds, field allowlists,
stale-response checks, no-store requests, and inline JavaScript syntax. That
focused read selection passed 11 tests without a schema migration or database.
Its rollback removes the projection and console fields and regenerates the
runtime SQL inventory; no data rollback is necessary.

## Remaining acceptance

This is an initial CAP-006 read path, not full energy/waste/landscape parity.
Compost quality scoring and certification, waste calculation parity,
landscape habitat and pollinator workflows, populated legacy output parity,
runtime ACL/RLS, live ZITADEL/browser behavior, and MAN-CAP-006 remain open.
