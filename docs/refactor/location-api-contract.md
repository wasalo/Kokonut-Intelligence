# Public location API contract

This bounded contract map covers the two existing gateway routes. It is not a
full location collection migration or Directus parity certification.

## Versioned native contract

The additive `GET /api/v1/locations` and
`GET /api/v1/locations/{location_id}` routes define the first versioned native
contract. FastAPI publishes their request/response schemas in the gateway's
OpenAPI document. Both return a conventional JSON envelope: the list route
returns `{ "data": [...] }`; detail returns `{ "data": { ... } }`. The list is
bounded to 100 eligible records, ordered by name and ID, and currently has no
filter or pagination parameters. Detail accepts a UUID; malformed identifiers
return 400 and absent or ineligible locations return the same 404 response.

These routes read only `v_public_farm_summary`, so they do not depend on the
Directus provider flag and cannot expand fields based on credentials. Public
visibility remains the view's active-location plus verified/published farm
registry rule. The existing unversioned `/api/locations` routes remain intact
for their historical double-encoded wrapper and Directus behavior; they have no
deprecation date. Consumers should move only after response and authorization
parity is reviewed. The API version namespace does not certify other unversioned
gateway routes. Additive `/api/v1/metrics/{location_id}`,
`/api/v1/crisp/{location_id}`, and
`/api/v1/analytics/{location_id}/summary` aliases now expose existing governed
read handlers with strict OpenAPI response models and explicit public read
policies; see [public summary contracts](public-summary-contracts.md). The
Python and JavaScript SDKs expose typed clients for these reads, while
schema-driven SDK generation and runtime parity remain future work.

| Contract | List | Detail |
| --- | --- | --- |
| Route | GET /api/locations | GET /api/locations/{location_id} |
| Policy | location/read, explicitly public | location/read, explicitly public |
| Input | no filters/pagination exposed | UUID; invalid syntax returns 400 |
| Native source | v_public_farm_summary | same view filtered by location ID |
| Visibility | active location plus verified/published farm registry record | same rule |
| Fields | id, name, country, region, status | same fields |
| Bound | 100 rows ordered by name then ID | at most the matching row |
| Output | outer data string containing JSON with inner data array | outer data string containing JSON with inner data object |
| Missing record | empty array | 404; nonexistent and excluded records share the response |
| Write/lifecycle behavior | none | none |

## Repository owners and consumers

`services/gateway/router.py` owns route policy and the versioned handlers;
`services/gateway/public_models.py` defines their strict response envelopes;
`services/gateway/locations.py` owns the native read and database cleanup.
`schemas/postgres/018_public_views.sql` owns governed public visibility.
`services/core/features.py` selects the legacy Directus branch. That branch proxies
`/items/location?limit=100` or `/items/location/{UUID}` through the shared HTTP
client and retains its serialized response wrapper.

The native projection excludes metadata, coordinates/geometry, financial
baselines, and ownership fields. It does not expand fields for authenticated
callers. Directus field/row permissions and hooks remain a separate reference
that must be compared before retiring that provider.

An initial literal search in the SDKs, API-reference/OpenAPI files, mobile code,
and gateway tests found no consumer of these exact public location routes.
The mobile location enrollment/revocation routes are separate authenticated
operations and are not migrated by this slice. Dynamic consumer URL construction,
external integrations, and live Directus clients still need a complete audit.
Do not normalize the double-encoded legacy wrapper without versioning and a
consumer migration.

## Acceptance still required

Review fixtures for active/inactive locations and draft/submitted/verified/published
registry records. Confirm list/detail field visibility, ordering, 100-row bound,
UUID handling, excluded-record 404 behavior, response compatibility, and unchanged
gateway authorization. Compare scoped responses with actual Directus policies.
Exercise database timeout/error cleanup and concurrent requests before claiming
availability or resource budgets. Existing gateway authorization tests are a
starting point; no tests were added or run here.

The versioned native route implementation has source-level contract coverage
through explicit response models and generated OpenAPI metadata. Runtime payload,
role/grant, authorization, and Directus comparison evidence has not yet been
collected; this slice must not be treated as accepted parity.

Full location access, relations, filters/pagination, exports, writes, audit
semantics, lifecycle transitions, reviewer identity, consent scopes, and SDK
generation remain unmigrated. These require explicit domain contracts; do not
replace them with unrestricted generic table CRUD.

Rollback selects the preceding gateway image or routes existing consumers back
to `/api/locations`. No schema change was made in this slice. Retain the governed
view and Directus metadata/permissions during the transition.
