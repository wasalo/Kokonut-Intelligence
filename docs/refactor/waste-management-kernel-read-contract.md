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
column; for the ten most recent verified readings, the projection extracts
`metadata.ph` only when its JSON type is numeric. It never returns the metadata
object or other metadata keys. These summaries are descriptive and advisory,
not a compost-quality score, certification, or compliance result.

Pollution incident aggregation reports count and first/last date by the
schema-controlled severity and lifecycle status. It exposes no incident type,
narrative, affected area, remedial action, reporter/recipient, notes, IDs, or
arbitrary metadata. These counts are descriptive and do not determine
compliance, severity response, or closure.

## Legacy summary capability preservation

The unscoped `services.analytics.waste_management.get_waste_summary` and
`get_composting_efficiency` helpers now fail before database access because a
caller-selected location is not authenticated tenant context. Their useful
outputs remain available in the authenticated Gateway response rather than
through the shared local CLI credential.

`GET /operator/api/waste/{location_id}/summary` accepts `days` from 1 through
3650 (default 30). The selected window contains exactly that many calendar
dates including today and includes verified waste rows only. Its
`waste_summary` projection preserves total kilograms, record count, grouping by
waste type, and grouping by disposal method. The response also retains the
all-time verified waste-stream groupings and separate composting and recycling
aggregates. Composting efficiency preserves verified batch/feedstock/output
totals, overall yield, per-method averages, and the ten latest quality readings
(numeric pH from `metadata.ph`, moisture, temperature, yield, and date). No
arbitrary metadata, notes, identities, or source-row IDs are returned. The
console exposes 7/30/90/365-day windows and validates the requested period and
fixed response fields before rendering them as text.

The migration-owned aggregate checks the same signed operator/location context
and exact read grant before returning any projection. Its isolated reader role
has only the source columns needed for these aggregates. The legacy local CLI
commands remain database-free and direct operators to the authenticated
Gateway; rollback must not restore shared-role table access or unscoped reads.

The legacy `record_waste` Python helper and `record-waste` CLI now fail closed
because the old location argument was caller-selected and did not establish an
authenticated tenant identity. The helper rejects before opening a cursor; the
CLI is marked database-free and directs operators to the authenticated Gateway
capture form. The legacy `record_composting` helper and `record-composting` CLI
now fail closed for the same reason. The composting helper rejects before
cursor acquisition, and its CLI is database-free. Waste-stream and composting
capture both remain available through exact-grant Gateway operations guarded
by signed location context, bounded payload validation, private retry receipts,
and recorded-only lifecycle. Human verification remains separate. Recycling
capture now follows the same tenant-scoped Gateway pattern. Incident writers
still lack tenant authorization and remain separate parity work.

The legacy `record_recycling` Python helper and `record-recycling` CLI now fail
closed before opening a cursor or database connection because their
caller-selected location is not authenticated tenant context. Recycling
capture remains available through
`POST /operator/api/waste/{location_id}/recycling`, gated by the exact
`waste_management:create` grant. The service validates the exact payload,
location UUID, non-future date, bounded freeform material label, positive
quantity and decimal precision, destination, optional revenue, and notes
before connecting. Schema-supported material labels map to canonical enum
values; unsupported labels map to `other` and are preserved in bounded
`legacy_material_type` metadata. Revenue is stored as supplied without assigning
a currency or combining it with classified financial totals. The database
function independently checks signed operator/location context and the live
grant, stores only `recorded` rows, and writes a private SHA-256 idempotency
receipt. Exact retries replay the original ID; changed payload reuse conflicts.
The console exposes the form only for the exact create grant and keeps capture
separate from verification.

Legacy incident report, resolve, summary, and mixed-dashboard helper/CLI paths
fail before database access because caller-selected locations do not establish
tenant authorization. Incident capture and resolution are available through
the location-scoped Gateway operations below. Aggregate counts remain in the
exact-grant Gateway summary; narrative review is separately gated.

The legacy CLI contract was exercised against migration 153 in disposable
PostgreSQL 16. Migration apply/replay and synthetic records verify that the
unscoped waste, composting, recycling, and incident writers fail closed while
canonical read/lifecycle projections remain intact. Waste, compost, recycling,
and incident rows in this run are synthetic fixtures. Migrations
613/614/615/616 have separate authenticated Gateway acceptance on native AMD64
and linux/arm64 Docker/QEMU; QEMU is software portability evidence only, not
physical Raspberry Pi acceptance. These checks do not exercise populated
legacy outputs
([runner](../scripts/check-waste-management-disposable.py);
[legacy evidence](builds/2026-10-24-recovery/cap-006-waste-management-disposable.json);
[native capture evidence](builds/2026-10-24-recovery/cap-006-waste-incident-capture-disposable.json);
[ARM64 capture evidence](builds/2026-10-24-recovery/cap-006-waste-incident-capture-arm64-disposable.json)).

## Kernel pollution incident capture and review

`POST /operator/api/waste/{location_id}/incidents` requires the exact
`waste_management:create` grant and an authenticated CSRF-protected OIDC
session. The Gateway validates the exact request shape, UUID, non-future date,
canonical severity, and bounded description, affected-area, reporter, and
notes fields before connecting. Unsupported incident types map to `other`;
the original bounded label and reporter attribution are retained in metadata.
Capture creates only an `open`, unresolved incident and never decides
compliance or closure.

`GET /operator/api/waste/{location_id}/incidents?offset=N` requires the
separate exact `waste_management:review` grant. It sets signed tenant context
before a repeatable-read, read-only query, qualifies every row by location,
returns at most 100 rows per page, and orders critical/high/medium/low reports
before recency. Its fixed projection includes incident date, type, severity,
description, affected area, and status; it excludes reporter, notes, and
arbitrary metadata. `POST
/operator/api/waste/{location_id}/incidents/{incident_id}/resolve` also requires
the review grant, validates a bounded remedial action and date, locks only the
location-matched unresolved incident, and records the reviewing operator in
`updated_by`. Resolution sets the canonical `resolved` flag, `resolved` status,
resolution date, remedial action, and timestamp.

Migration 616 installs separate `SECURITY DEFINER` owners for capture and
resolution, revokes PUBLIC/runtime/Directus direct incident writes, and keeps a
private append-only request receipt unreadable to runtime and Directus. Exact
retries return the original operation result; changed request-ID reuse
conflicts. The console gates capture and review independently and renders
incident content through `textContent`. The unscoped analytics report/resolve
helpers and CLI commands fail before database access. Directus has no access to
the bounded functions; production Directus field/row parity and complete
canonical ACL/RLS still require separate review.

The historic local `open-incidents` and combined `dashboard` helpers and CLI
commands now fail before cursor or database access. They could return
caller-selected incident narratives through the shared database connection,
bypassing the review grant. The aggregate summary and narrative review queue
remain available through the authenticated Gateway surfaces above.

Migration 615 additionally removes runtime and Directus table/column write
privileges on `recycling_log` while preserving SELECT, then grants a dedicated
isolated writer only the required insert/receipt/function permissions. The
receipt remains private from runtime and Directus. This is a source and
disposable-role boundary; production ACL/RLS and Directus field/row parity
remain open until the reviewed rollout and tenant-wide access contract.

The legacy `get_composting_efficiency` read also uses schema-153 columns:
`finished_volume_kg` supplies output values, per-batch yield is calculated
from finished volume over positive feedstock, and `compost_date` supplies the
recent-row date. Method and recent-measurement reads require `verified` status;
the overall totals include all verified batches so incomplete output continues
to count toward feedstock totals as in the legacy formula. Its response keeps
the existing recent-quality fields and reads numeric pH from the canonical
JSONB metadata extension when present. Compost capture no longer uses the
legacy database writer. The authenticated Gateway accepts bounded freeform
feedstock and method labels, maps recognized values and the
`vermicomposting` alias to schema-supported categories, and retains other
original labels in the bounded `legacy_composting_inputs` metadata field while
classifying the row as `other`. Migration 614 independently checks signed
exact-location `waste_management:create` context, writes a recorded-only row,
stores optional pH in JSONB, and uses a private SHA-256 receipt for exact
retry. The old local helper and CLI fail closed before any database access.

The console gates its summary on `waste_management:read`, capture forms on
`waste_management:create`, and the incident queue/resolve controls on
`waste_management:review` independently. Waste-stream, composting, and
recycling captures remain recorded and do not imply human verification.
Requests use same-origin/no-store behavior, validate response location and
bounded schema fields, discard stale responses, and render fixed fields with
`textContent`.

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

Migrations 613–616 apply and replay against the canonical migration-153 tables
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

This is a prepared CAP-006 path, not full energy/waste/landscape parity.
Compost quality scoring and certification, waste calculation parity,
landscape habitat and pollinator workflows, populated legacy output parity,
remaining canonical-table ACL/RLS and Directus parity, live ZITADEL/browser
behavior, and MAN-CAP-006 remain open.

## Pollution incident reader isolation

Migration 617 gives narrative review and aggregate incident summaries a
separate, no-login database function owner. The queue function validates the
active operator/location context and exact `waste_management:review` grant;
the aggregate function independently requires `waste_management:read`. Both
queries qualify by the requested location. Runtime and Directus roles have no
table- or column-level `SELECT` on `pollution_incident`, and the legacy
`v_pollution_incidents` view is unavailable to those roles. The Gateway uses
only these bounded functions for incident rows. Disposable PostgreSQL 16
acceptance verifies distinct read/review grants, wrong-location rejection,
direct table/view denial, migration apply/replay, and existing capture/resolution
behavior ([evidence](builds/2026-10-24-recovery/cap-006-waste-incident-review-reader-disposable.json)). Migration 617 is not applied to candidate or
legacy databases. This boundary covers pollution incidents only; it does not
close ACL/RLS requirements for the other waste-management tables or broader
Directus parity.

## Waste, composting, and recycling summary reader isolation

Migration 618 routes the Gateway's verified waste-stream, composting, and
recycling aggregates through one security-definer function owned by a separate
no-login, non-inheriting reader. It validates current operator/location
context and the exact `waste_management:read` grant. Runtime and Directus lose
table/column reads on the three canonical relations and read access to the
legacy `v_waste_summary` and `v_composting_efficiency` views; only Gateway
runtime can execute the function. The unscoped local waste-summary and
composting-efficiency CLI operations fail before connecting. Native and
ARM64/QEMU disposable PostgreSQL checks apply/replay migrations 153 and
613–618, verify synthetic summary output and grant boundaries, and prove direct
table/view denial ([native evidence](builds/2026-10-24-recovery/cap-006-waste-summary-reader-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-24-recovery/cap-006-waste-summary-reader-arm64-disposable.json)). Candidate and legacy are untouched and migration 618 is not rolled out. QEMU does not establish physical Raspberry Pi acceptance. This closes only the direct read path for these aggregates; other waste-table ACL/RLS, populated parity, live OIDC/browser, Directus parity, and MAN-CAP-006 remain open.
