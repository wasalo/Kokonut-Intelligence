# CAP-037 Operating Pilot Kernel Read Contract

**Status:** Prepared (`P`), not MAN-CAP-037 accepted
**Current slices:** Location-scoped operating-pilot summary, redacted demand page, draft-only demand creation, aggregate capacity-period page, suppressed work-claim category page, and suppressed resource-request category page
**Migrations:** `schemas/postgres/461_location_scoped_operating_pilot_summary.sql`; `schemas/postgres/479_location_operating_pilot_demand_signals.sql`; `schemas/postgres/480_location_operating_pilot_capacity_periods.sql`; `schemas/postgres/526_location_operating_pilot_work_claims.sql`; `schemas/postgres/538_location_operating_pilot_resource_categories.sql`; `schemas/postgres/552_location_operating_pilot_demand_draft.sql`

## Route and authorization

`GET /operator/api/operating-pilot/{location_id}/summary` is an OIDC operator
route. It requires an exact `operating_pilot:read` grant for the requested
location. The Gateway validates both UUIDs, opens a read-only transaction,
sets signed tenant context on that connection, calls the bounded PostgreSQL
projection, rolls back the read transaction, and closes the connection.
Responses are `no-store`. A missing identity provider disables the route;
missing or stale tenant grants fail closed.

`POST /operator/api/operating-pilot/{location_id}/demand-signals` uses a
separate exact `operating_pilot:create` location grant. It requires the signed
operator session and same-origin CSRF protection; responses are `no-store`.
The Gateway validates the request ID, ISO dates, bounded period, work type,
hours, priority, description, and allowed fields before opening PostgreSQL.
It sets create-action tenant context on that same transaction and invokes the
bounded migration-552 function. The route can create or replay a draft only;
it cannot submit, approve, fulfill, or otherwise change demand lifecycle.

## Data boundary

Migration 461 exposes an aggregate projection only when an active
`operating_pilot_scope` row has `scope_type='adelphi'`, is active, and points
to an active `farm` whose `location_id` exactly matches the requested
location. This follows the legacy model: the Adelphi pilot scope ID is a farm
ID, while Gateway grants are location-scoped. The internal Kokonut
organization scope is never included in a farm/location response. Work items
are selected by their explicit `location_id`; capacity, demand, learning,
requests, and coaching records must use the same Adelphi farm-scope ID.
Competency summaries are limited to active roles in that pilot's governance
circle.

The response includes `as_of_date` and lifecycle counts for capacity profiles, demand signals,
location work items and claims, competency reviews, learning plans, resource
requests, and aggregate-only coaching sessions. It never returns personnel
identities, party IDs, descriptions, evidence, profile notes, resource request
text, coaching content, or private/limited coaching records. Capacity and
demand figures include only records whose period contains the database's
current date. Capacity hours include only submitted or approved profiles;
demand required-hours include only submitted or approved signals.

For person-linked capacity, work-claim, competency, learning, resource-request,
and aggregate-only coaching measures, the SQL projection counts distinct
participants internally and suppresses all associated counts/hours when the
group contains one or two people. Empty cohorts return zero; groups of at least
three return the aggregate plus `suppressed: false`. This is a baseline
disclosure control for authorized operator reads, not a substitute for
reviewing audience-specific privacy policy or temporal differencing risk.

The endpoint deliberately fails closed when the Adelphi pilot scope does not
map through an active farm row to the requested location. Legacy internal
organization scope IDs are not silently reinterpreted as farm or location
associations. Populated owner/tenant mapping still requires review before
rollout.

## Demand record page

`GET /operator/api/operating-pilot/{location_id}/demand-signals` uses the same
exact OIDC `operating_pilot:read` grant and signed location transaction. It
returns a page of Adelphi demand rows scoped through active pilot scopes and
their active farm-to-location mapping. Default page size is 25; the database
accepts limits from 1 to 50 and offsets from 0 to 10,000. The response exposes
only `work_type`, `period_start`, `period_end`, `required_hours`, `priority`,
and lifecycle `status`, plus pagination metadata. It can list drafts and
historical/future periods so authorized reviewers can see the existing demand
queue, but makes no change to its review state.

Demand IDs, descriptions, source references, source metadata, creator identity,
and internal organization scope never leave the security-definer function.
The non-login reader receives only the additional `work_type` and `priority`
columns needed to render this projection. The Gateway keeps the route disabled when
OIDC is unavailable and sends `no-store` responses.

## Demand draft creation

The POST route accepts `work_type`, `period_start`, `period_end`,
`required_hours`, `priority`, optional private `description`, and a UUID
`request_id`. Migration 552 rechecks the signed operator/location context and
the exact create grant, requires an enabled operator bound to an active human
party, and requires an active Adelphi pilot scope mapped through an active
farm to that same location. The signal is created only with
`source='planning'` and `status='draft'`, with `created_by_party_id` set from
the verified binding.

The private receipt is keyed by operator and request ID and stores location,
signal ID, and a SHA-256 digest of canonical input. An advisory transaction
lock makes retries deterministic: identical input returns the existing signal
ID and current lifecycle status; a different payload or location using that
ID returns conflict. Receipt contents and private description never appear in
the response. The Gateway role can execute the function but cannot read or
write the receipt table directly. The function's non-login owner has only the
table/column access needed to create the draft, record the receipt, and read
minimal retry status. Runtime and Directus lose existing table-level and
column-level direct `INSERT`/`UPDATE`/`DELETE` access to demand signals; direct
receipt access remains revoked.

The console displays the draft form only for locations with an exact
`operating_pilot:create` grant. It retains the request ID and payload after
transport or server failure so retries do not duplicate drafts. The demand
queue remains hidden unless the operator also has `operating_pilot:read`; a
create-only grant does not imply read access. The form offers no lifecycle
review actions.

## Capacity-period page

`GET /operator/api/operating-pilot/{location_id}/capacity-periods` uses the
same exact location read grant, signed tenant context, read-only transaction,
and no-store response. Migration 480 groups submitted and approved capacity
profiles by their exact start/end period under active Adelphi farms mapped to
the requested location. It returns period boundaries and aggregate
available/committed/protected hours. Draft and superseded profiles are omitted.
When fewer than three distinct people contribute to a period, all three hour
totals are null and `suppressed` is true; the exact participant count is never
returned. Pages default to 25 periods and cap at 50 rows and offset 10,000.

Profile IDs, participant IDs, notes, source labels, and individual hours remain
inside PostgreSQL. Migration 461 already grants the reader the period, status,
participant-key, and capacity columns needed by the summary and this aggregate;
it does not grant profile notes. The route cannot verify, approve, or mutate a
capacity profile.

## Work-claim category page

`GET /operator/api/operating-pilot/{location_id}/work-claims` uses the same
exact location read grant, signed tenant context, read-only transaction, and
no-store response. Migration 526 aggregates claims attached to work items with
the requested `location_id`, and only when the active Adelphi farm scope maps
to that location. It normalizes the free-form `work_type` field to a fixed set
of known categories and maps every unrecognized value to `other`; caller text
never appears in the response. The projection returns category, aggregate claim
count, and suppression flag only. It does not expose individual work items,
claim lifecycle states, claim IDs, claimant/reviewer identities, effort,
evidence, notes, titles, descriptions, or review reasons.

Counts are suppressed when fewer than three distinct claimants contribute to
that category. The exact contributor count is not returned. Pages default to
25 categories and cap at 50 rows and offset 10,000. This is an aggregate
activity view; independent human review remains necessary and no claim can be
accepted, rejected, or changed from this route.

## Resource-request category page

`GET /operator/api/operating-pilot/{location_id}/resource-categories` uses
the same exact location grant, signed tenant context, read-only connection,
bounded pagination, and no-store response. Migration 538 scopes requests to
active Adelphi farms mapped to the requested location and normalizes the
legacy free-text `resource_type` value into a fixed category set; unknown
values become `other`. The page returns only category, request count, and a
suppression flag. It omits request IDs, requester identity, descriptions,
urgency, decision/status, dates, and decision reasons. Counts are hidden when
fewer than three distinct requesters contributed to a category. The projection
is an aggregate inventory, not an individual request queue or decision path.

The non-login pilot reader receives the additional `resource_type` column
needed by this function. Migration 461 already grants that role access to
`decision` for the aggregate summary; migration 538 does not broaden that
pre-existing grant or expose decision state in this response. Runtime and
Directus receive no direct request-table access from migration 538.

## Operator console

The operator console exposes the five read routes in a single operating-pilot
panel only when the signed session contains an exact `operating_pilot:read`
location grant, and exposes the demand form separately for exact
`operating_pilot:create` grants. The location selector is populated from the
union of those grants; the browser sends same-origin, no-store requests and discards stale responses when
the selected location changes. Demand and capacity pages are bounded to 25
rows per request and provide explicit load-more controls. Capacity hours,
work-claim counts, and resource-request counts are rendered as suppressed
whenever their groups have fewer than three contributors. Fixed allowlists and
text-only DOM rendering are used.
The console adds demand-draft creation only; it adds no lifecycle review
actions and does not constitute live OIDC/browser acceptance.

## Database boundary

The non-login `kokonut_operating_pilot_reader` role can select only the source
columns needed by these projections and has no identity-table access or
mutation privileges, except the minimal INSERT columns and receipt access
needed by the migration-552 definer function. It cannot select demand
descriptions or receipt digests. Migrations 526 and 538 add only
`work_item.work_type` and `operating_resource_request.resource_type`; titles,
descriptions, and decision reasons remain unavailable to the reader.
`kokonut_runtime` is granted execution of the security-definer functions,
which recheck signed operator location context and the active exact database
grant on every call. Migration 552 removes table-level and per-column direct
write privileges on demand signals from the legacy runtime and Directus
logins. This is a scoped ACL boundary, not universal least privilege or forced
RLS: other tables, inherited memberships, and deployed ACL state still require
review.

## Verification and rollback

The Gateway contract and exact route policy are covered by
`tests/test_gateway_operating_pilot_reads.py` and
`tests/test_operator_route_policy_inventory.py`. The disposable PostgreSQL 16
acceptance runner applies/replays migrations 461, 479, 480, 526, 538, and 552,
exercises active and internal scopes, checks aggregate values,
demand/capacity/claim/resource-category paging, small-cohort suppression,
tenant/grant denials and data redaction, and
inspects runtime, Directus, and reader privileges, including pre-existing
table-level and column-level demand write grants:
`scripts/check-operating-pilot-summary-disposable.py`.

Before migration rollout, disable the capability by removing the route/service
registration and route policy. If migrations 461, 479, 480, 526, 538, or 552
are applied, retain their ordered functions, receipts, roles, and ACLs; disable
only the affected route. Do not delete created demand drafts or edit or reverse
an applied migration. Re-enabling any prior direct-write path requires a
separately reviewed forward migration.

## Remaining gates

These slices do not establish populated Adelphi scope mapping, item-level
capacity/work-claim/competency/learning/resource/coaching workflows, demand
submission/review/fulfillment parity, parity with populated legacy outputs, live
OIDC/browser behavior, operator audience review, production recovery,
universal direct-database ACL/RLS, or MAN-CAP-037 owner acceptance. Those gates
remain open in `docs/refactor/batches.md`.
