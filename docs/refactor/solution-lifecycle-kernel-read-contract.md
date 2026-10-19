# Solution lifecycle Kernel read contract

**Status:** CAP-035 first location-scoped read slice prepared; not owner-accepted.
**Migration:** `459_location_scoped_solution_lifecycle_summary.sql`.
**Route:** `GET /operator/api/solution-lifecycle/{location_id}/summary`.
**Authorization:** exact `solution_lifecycle:read` location grant plus signed
operator tenant context, checked in both Gateway and PostgreSQL.

## Purpose and boundary

The legacy innovation services already implement solution discovery, stage
gates, experiments, funding decisions, adoption, replication, scale gates,
learning, and retirement. This slice adds an optional-Kernel-compatible,
read-only Gateway projection for operators. It does not replace those domain
services, change transition rules, approve gates, release funding, activate
adoption, or retire a solution.

Canonical `solution` records can be network-wide. The projection includes a
solution only when it is explicitly originated in the requested location or
has a `solution_link` whose `entity_type = 'location'` and `entity_id` exactly
matches that location. Migration 459 adds this supported link type without
rewriting existing links. Location-specific adoption, configuration, readiness,
and scale indicators are additionally filtered by their exact location scope.
An unlinked network solution is intentionally absent from this location read.

## Response

The response contains `location_id`, `solution_count`, and aggregate counts for
solution stages/status, stage-gate status, each gate's latest evaluation,
experiment status/outcome, replication, funding decision state, location-scoped
adoption/configuration/readiness/scale state, learning decision, and retirement
state. Count objects use the source table's allowlisted enumerated values; they
contain no row IDs, names, canonical keys, actor or party identities, free text,
evidence, funding amounts, or raw JSON payloads. Responses are `no-store` and
vary on the session cookie.

## Database boundary

The stable read function is owned by `kokonut_solution_reader`, a non-login,
non-inheriting role with SELECT only on the source relations required to compute
the projection. The function rechecks actor type, signed location context, and
the exact `solution_lifecycle:read` grant. Runtime can execute the bounded
function but cannot select the solution tables directly; Directus has neither
function nor table access. The reader has no identity-table access and no write
privileges.

## Verification and remaining parity

The focused Gateway, route-policy, and migration metadata selection and
disposable PostgreSQL 16 apply/replay acceptance are recorded in
`builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json`.
Candidate and legacy databases are untouched; migration 459 has not been rolled
out. This is not parity acceptance. Remaining work includes item-level read and
write workflows, gate and experiment evidence detail under reviewed grants,
funding/tranche and adoption event detail, populated legacy-to-Kernel fixture
comparison, browser/OIDC acceptance, broader ACL/RLS, recovery behavior, and
MAN-CAP-035 owner review.

## Rollback

Before migration rollout, remove the route registration, route-policy entry,
read service, and tests together. After migration application, disable the route
but retain migration 459 and its ordered function and ACL. Do not edit or
reverse the applied migration; any schema rollback requires a separately
reviewed forward migration after checking for location links created since
rollout.
