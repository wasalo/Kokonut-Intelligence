# Solution lifecycle Kernel read contract

**Status:** CAP-035 location-scoped summary, gate, experiment, funding, adoption,
scale-gate, and replication read slices prepared; not owner-accepted.
**Migrations:** `459_location_scoped_solution_lifecycle_summary.sql`,
`466_location_scoped_solution_gates.sql`,
`467_location_scoped_solution_experiments.sql`,
`468_location_scoped_solution_funding.sql`,
`469_location_scoped_solution_adoption.sql`,
`470_location_scoped_solution_scale_gates.sql`, and
`471_location_scoped_solution_replications.sql`.
**Routes:** `GET /operator/api/solution-lifecycle/{location_id}/summary`,
`GET /operator/api/solution-lifecycle/{location_id}/gates`,
`GET /operator/api/solution-lifecycle/{location_id}/experiments`,
`GET /operator/api/solution-lifecycle/{location_id}/funding`,
`GET /operator/api/solution-lifecycle/{location_id}/adoption`,
`GET /operator/api/solution-lifecycle/{location_id}/scale-gates`, and
`GET /operator/api/solution-lifecycle/{location_id}/replications`.
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

The experiments route returns a bounded page of experiment lifecycle state for
the same exact origin-or-location-link solution set. Each row contains the
solution and experiment IDs, solution name/type/stage/status, protocol version,
experiment status and duration, counts of primary and secondary metric keys,
experiment timestamps, and only the latest explicitly reviewed result outcome
and its review timestamp. Rows without `reviewed_at` are suppressed. It omits
the hypothesis, baseline/treatment/comparator protocol,
metric names and values, observation records, raw result JSON, adverse-event
details, evidence, and owner/reviewer identities. Pages accept 1–50 rows with
an offset up to 10,000; SQL fetches at most 51 to determine `has_more`, and the
Gateway applies the same 256 KiB response limit. This is status visibility,
not experiment approval, result review, or a mutation path.

The funding route returns a bounded flat page of location-scoped funding cases
and tranche lifecycle states. Cases without tranches remain visible. Rows
contain solution and funding-case IDs, solution labels/state, capital stage,
instrument, currency, case decision state and timestamps, plus nullable tranche
ID/number/status and approval/release timestamps. It never returns requested,
authorized, tranche, or released amounts; milestone conditions; case rationale;
funding or release evidence; or submitter, approver, and releaser identities.
The `kokonut_solution_reader` role receives column-level SELECT only for the
case and tranche fields needed by this projection and the existing aggregate
summary. It cannot select monetary, narrative, evidence, or party columns. Pages
accept 1–50 rows with an offset up to 10,000, use stable case/tranche ordering,
and share the 256 KiB response cap. The route does not approve funding cases,
approve or release tranches, or expose release execution.

The adoption route returns a bounded page of programs whose target is the exact requested location and whose solution originates there or has an explicit location link. It includes solution/program identifiers and labels, lifecycle state, and timestamps. `consented_adopter_reference_count` is null unless at least five distinct, nonempty, case- and whitespace-normalized `adopter_ref` values have consent-checked events; repeated events carrying the same reference do not increase the threshold, and non-consented events are excluded. The count is an aggregate of source references, not a verified count of natural persons. Adopter references, cohort IDs, event type/time, fidelity, support needs, outcomes, evidence, and party identities are omitted from the response. The security-definer owner receives column access to the pseudonymous adopter reference solely for the distinct count; runtime and Directus cannot read the source tables. Pages use the same 1–50 limit, 10,000 offset ceiling, no-store response, and 256 KiB serialized response cap. This does not expose event detail or mutate adoption state.

The scale-gates route returns a bounded page of gates whose scope is exactly the requested location and whose solution originates there or has an explicit location link. It includes solution/gate IDs and labels, gate type/status, a boolean indicating whether an approver reference exists, and the nullable approval timestamp. It omits free-text requirements, configured thresholds, measured values, metric keys, units, evidence, and approver identity. The non-login reader has column access to `approved_by_party_id` only to derive the boolean; neither that value nor party details are returned. Pages follow the same bounds and response cap. This read does not evaluate, waive, approve, or mutate a scale gate.

The replications route returns a bounded page only when both the solution lineage and replication target match the exact requested location. It shows solution/replication IDs and labels, replication state/result, evidence-maturity level, whether a reviewer reference exists, and creation/completion timestamps. It omits the source experiment ID, target context, similarity, adaptation plan, replication protocol, raw evidence, and reviewer identity. The non-login reader has column access to the reviewer reference solely to derive the boolean. Pages use the shared limits and response cap. The route does not approve, start, complete, or otherwise change a replication.

## Database boundary

The stable read function is owned by `kokonut_solution_reader`, a non-login,
non-inheriting role with SELECT only on the source relations required to compute
the projection. The function rechecks actor type, signed location context, and
the exact `solution_lifecycle:read` grant. Runtime can execute the bounded
function but cannot select the solution tables directly; Directus has neither
function nor table access. The reader has no identity-table access and no write
privileges. Migrations 466–471 add bounded gate, experiment, funding, adoption, scale-gate,
and replication functions under the same reader role and exact signed-location grant checks.

## Verification and remaining parity

The summary, gate, experiment, funding, adoption, scale-gate, and replication source checks and their
disposable PostgreSQL 16 apply/replay acceptance are recorded in
`builds/2026-10-19-recovery/cap-035-solution-lifecycle-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-gates-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-experiments-disposable.json` and
`builds/2026-10-19-recovery/cap-035-solution-funding-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-adoption-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-scale-gates-disposable.json`, and
`builds/2026-10-19-recovery/cap-035-solution-replications-disposable.json`. Candidate
and legacy databases are untouched; migrations 459 and 466–471 have not been
rolled out. This is not parity acceptance. Remaining work includes
item-level read and write workflows beyond status projections, gate and
experiment evidence detail under reviewed grants,
funding/tranche and adoption event detail, populated legacy-to-Kernel fixture
comparison, browser/OIDC acceptance, broader ACL/RLS, recovery behavior, and
MAN-CAP-035 owner review.

## Rollback

Before migration rollout, remove a route registration, route-policy entry, read
service, migration source, and tests together. After migration application,
disable the route but retain its ordered migration and ACL. Do not edit or
reverse an applied migration; any schema rollback requires a separately
reviewed forward migration after checking for location links and dependent data
created since rollout.
