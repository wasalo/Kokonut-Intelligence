# Solution lifecycle Kernel read contract

**Status:** CAP-035 first location-scoped summary and gate-item read slices prepared; not owner-accepted.
**Migrations:** `459_location_scoped_solution_lifecycle_summary.sql` and
`466_location_scoped_solution_gates.sql`.
**Routes:** `GET /operator/api/solution-lifecycle/{location_id}/summary` and
`GET /operator/api/solution-lifecycle/{location_id}/gates`.
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

The gates route returns a bounded page of gate items only for solutions that
originate in the requested location or have an explicit `solution_link` to that
location. Each item includes solution/gate identifiers, the solution's display
name/type/stage/status, gate transition and requirement counts, approval-needed
flag, gate status/creation time, and only the latest evaluation pass/fail value
and timestamp. It omits gate requirements JSON, observed values, evaluation and
gate evidence, reviewer/actor identities, narratives, funding data, and raw
payloads. Pages accept 1–50 items and an offset up to 10,000; the database
function receives at most 51 rows to compute `has_more`, and the Gateway caps
the serialized page at 256 KiB. The read does not approve, fail, or otherwise
mutate a gate.

## Database boundary

The stable read function is owned by `kokonut_solution_reader`, a non-login,
non-inheriting role with SELECT only on the source relations required to compute
the projection. The function rechecks actor type, signed location context, and
the exact `solution_lifecycle:read` grant. Runtime can execute the bounded
function but cannot select the solution tables directly; Directus has neither
function nor table access. The reader has no identity-table access and no write
privileges. Migration 466 adds a second bounded function under the same reader
role and exact signed-location grant checks.

## Verification and remaining parity

The summary and gate-read source checks and their separate disposable PostgreSQL
16 apply/replay acceptance are recorded in
`builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-gates-disposable.json`.
Candidate and legacy databases are untouched; migrations 459 and 466 have not
been rolled out. This is not parity acceptance. Remaining work includes item-level
read and write workflows beyond stage gates, gate and experiment evidence detail under reviewed grants,
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
