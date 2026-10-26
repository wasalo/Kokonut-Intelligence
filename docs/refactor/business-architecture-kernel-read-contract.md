# Business architecture Kernel read contract

CAP-032 adds a location-scoped, read-only Gateway projection over the existing
governed business-architecture model. It does not replace the legacy capability
map, technology roadmap, value-stream definitions, or vision/mission workflow.

## Route and authorization

`GET /operator/api/business-architecture/{location_id}/summary` requires an
authenticated operator and an exact active `business_architecture:read` grant
for that location. The Gateway establishes signed tenant context on the same
read-only PostgreSQL transaction that calls the bounded functions. Responses
are `no-store` and vary by the operator cookie. Unknown paths and methods remain
protected.

## Included data

- The latest approved vision, mission, or values statement assigned directly to
  the requested location.
- Bounded roadmap and requirement mapping rows from roadmaps explicitly owned
  by that location and in `approved`, `active`, or `reviewed` state.
- Capability and value-stream names linked from those requirements.
- Strategy perspective only when the linked legacy strategy entry is itself
  explicitly location-scoped to the requested location.
- Requirement status, need type, and priority, so reviewers can distinguish
  governed state without receiving the full requirement payload.

Draft/unreviewed mission statements, unapproved roadmaps, retired requirements,
and other-location rows are excluded. Organization/network roadmaps and
organization/platform strategy entries do not enter the projection.

## Excluded data and boundaries

The projection omits descriptions, evidence, objective statements, stakeholder
or party identity, sponsor/owner identity, target values, metadata, maturity
assessment notes, and strategy rationale. It does not edit, approve, publish,
or otherwise transition any lifecycle state. Capability and value-stream names
are shown only when referenced by a qualifying location roadmap; this endpoint
does not provide a global catalog listing.

The SQL functions are owned by a dedicated non-login reader role, enforce the
signed actor/location context and `business_architecture:read` grant again, and
bound mapping pages to 50 rows. Runtime receives function execution only for
this projection; Directus receives neither function execution nor reader-role
membership. As with adjacent Kernel slices, this migration does not claim
universal RLS or prove the ACLs of external reporting consumers.

## Acceptance boundary

Mocked Gateway, exact route-policy, source, and disposable PostgreSQL 16 checks
verify location isolation, approved-state filters, exact grants, bounded
pagination, output allowlisting, migration replay, and least-privilege role
boundaries. Candidate and legacy databases are not touched. These checks do not
complete CAP-032: representative populated-data parity, live OIDC/browser
acceptance, broader runtime ACL/RLS, and the named MAN-CAP-032 owner acceptance
remain open.
