# Business planning Kernel read contract

CAP-033 adds a location-scoped, read-only Gateway projection for stored
business-model canvases. It preserves the existing canvas table and its
`draft → submitted → verified → published` lifecycle. This is the first Kernel
slice, not a replacement for the legacy pitch generator or business-plan
assembler.

## Route and authorization

`GET /operator/api/business-planning/{location_id}/canvases` requires an
authenticated operator and an exact active `business_planning:read` grant for
that location. The Gateway establishes signed tenant context on the same
read-only PostgreSQL transaction that calls the bounded projection. Responses
are `no-store` and vary by the operator cookie; unknown paths and methods stay
protected.

## Included data

The projection returns at most 50 canvases per page when both `entity_type` and
`entity_id` and the canonical `location_id` match the requested location. It
preserves the canvas name/description, fiscal year, lifecycle state, schema
version, version, health score, tags, timestamps, nine JSON content blocks, and
source system/reference. Draft and approved lifecycle rows remain distinguishable;
the read does not verify, publish, or edit them.

## Excluded data and boundaries

Raw import payloads, arbitrary metadata, creator/updater identities, and
organization-level canvases are excluded. The function is owned by a dedicated
non-login reader role that can only read the canvas table and authorization
support data; runtime receives function execution only, and Directus has no
function access or reader-role membership. This migration does not establish
universal RLS or external dashboard ACL parity.

## Acceptance boundary

Focused Gateway, exact route-policy, source, and disposable PostgreSQL 16
checks verify content preservation, lifecycle visibility, location coherence,
grant/context enforcement, page bounds, migration replay, and privilege
boundaries. Candidate and legacy databases are untouched. CAP-033 remains
prepared pending generated-pitch and assembled-plan parity, evidence/claim
review against populated fixtures, live OIDC/browser acceptance, broader
ACL/RLS, and MAN-CAP-033 owner acceptance.
