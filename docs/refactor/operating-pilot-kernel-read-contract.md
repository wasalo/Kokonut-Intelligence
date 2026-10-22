# CAP-037 Operating Pilot Kernel Read Contract

**Status:** Prepared (`P`), not MAN-CAP-037 accepted
**Current slices:** Location-scoped operating-pilot summary, redacted demand page, private demand draft creation and own-draft submission, independent redacted demand review queue, self-reported capacity creation, personal capacity history, own-draft revision and submission, independent capacity review queue and decisions, aggregate capacity-period page, suppressed work-claim category page, and suppressed resource-request category page
**Migrations:** `schemas/postgres/461_location_scoped_operating_pilot_summary.sql`; `schemas/postgres/479_location_operating_pilot_demand_signals.sql`; `schemas/postgres/480_location_operating_pilot_capacity_periods.sql`; `schemas/postgres/526_location_operating_pilot_work_claims.sql`; `schemas/postgres/538_location_operating_pilot_resource_categories.sql`; `schemas/postgres/552_location_operating_pilot_demand_draft.sql`; `schemas/postgres/553_location_operating_pilot_capacity_draft.sql`; `schemas/postgres/554_location_own_operating_pilot_capacity.sql`; `schemas/postgres/555_location_operating_pilot_capacity_draft_revision.sql`; `schemas/postgres/556_location_operating_pilot_capacity_draft_submission.sql`; `schemas/postgres/557_location_operating_pilot_capacity_review_queue.sql`; `schemas/postgres/558_location_operating_pilot_capacity_review_decision.sql`; `schemas/postgres/559_location_operating_pilot_demand_draft_submission.sql`; `schemas/postgres/560_location_operating_pilot_demand_review_queue.sql`

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

`POST /operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/submit`
is a separate one-way action under exact location `operating_pilot:submit_own`.
The Gateway accepts only a UUID request ID, applies the same signed session,
tenant-context, CSRF, and no-store boundaries, and invokes migration 559 on the
same transaction. The function rechecks the active human-party binding, exact
location grant and Adelphi farm mapping, plus ownership and `draft` status of
the private demand row. It atomically changes only `draft` to `submitted` and
records a private idempotency receipt. Exact retries replay the current state;
request-ID reuse with changed inputs, another operator's draft, missing scope,
location mismatch, and repeated submission fail closed. The console exposes
the action only for a draft created in the current session, requires explicit
confirmation, and retains its request ID for transport retries. This action
does not approve or fulfill the request and does not expose demand text or
creator identity.

`GET /operator/api/operating-pilot/{location_id}/demand-review-queue` uses the
separate exact `operating_pilot:review` location grant. Migration 560 requires
signed exact-location context, an active reviewer with exactly one human-party
binding, and an active Adelphi farm mapping. It returns only submitted rows
created through the Kernel draft receipt path and excludes the reviewer's own
human party. Results are bounded and ordered, and include a record ID plus
work type, period, requested hours, priority, status, and update time. Narrative,
source references, scope IDs, and submitter identity remain private. The queue
is read-only and records no decision.

`POST /operator/api/operating-pilot/{location_id}/capacity-profiles` uses the
same separate exact `operating_pilot:create` grant, signed operator context,
and CSRF protection. The Gateway validates the UUID request ID, canonical ISO
period, finite bounded hour values, committed-plus-protected capacity bound,
private note, and allowed fields before connecting to PostgreSQL. Migration
553 attributes the profile to the operator's active human-party binding and
creates only a `self_reported` `draft` under the active Adelphi farm mapped to
the exact location. It cannot submit, approve, supersede, or otherwise change a
profile's lifecycle.

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

The capacity form is also visible only for an exact create grant. It records
available, committed, and protected hours plus an optional private note for
the authenticated operator. It keeps the same request ID for unchanged retries
and resets only after confirmed success. A create-only grant can use either
draft form without exposing the summary or any read queue; read requests still
require the separate read grant.

## Own capacity records

`GET /operator/api/operating-pilot/{location_id}/my-capacity-profiles` uses a
separate exact `operating_pilot:read_own` grant. General `read` does not imply
access to person-linked records or notes, and `create` does not imply read
access. The function rechecks signed operator/location context, the active
grant, enabled operator identity, active human-party binding, and active
Adelphi farm mapping. It returns only profiles whose `party_id` matches the
authenticated operator's bound person; other participants' records and notes
are excluded in PostgreSQL.

The response includes the operator's own period, hours, private note, source,
status, and timestamps while omitting party identity and internal scope IDs.
Rows are ordered by update time and profile ID, newest first, with pages capped
at 50 rows and offset 10,000. Historical superseded profiles remain visible to
their owner. This is a read-only personal history view, not a review or
lifecycle decision surface. Responses are same-origin and `no-store`, and the
console renders fields through text nodes.

## Capacity draft creation

The capacity POST accepts `period_start`, `period_end`, `available_hours`,
`committed_hours`, `protected_hours`, an optional private `notes` value, and a
UUID `request_id`. Dates must form an ordered inclusive period no longer than
367 days. Hours are finite, non-negative decimals with at most two fractional
digits and no value above 100,000; committed and protected hours together may
not exceed available hours. Notes are limited to 2,000 characters and are
never included in the response or a read projection.

Migration 553 rechecks the signed location context and exact create grant,
locks the current operator-to-human-party binding, and maps the location
through the active Adelphi farm scope. The created row is always attributed to
that party, has `source='self_reported'` and `status='draft'`, and cannot select
another party, scope, source, or lifecycle state from client input. Exact
request retries return the same profile ID and current status; changed input
under the same request ID and another non-superseded profile for the same
person and period return conflict. The response includes only location ID,
profile ID, status, and replay indicator.

The Gateway and Directus roles lose existing table-level and column-level
direct `INSERT`/`UPDATE`/`DELETE` on `operating_capacity_profile`. They cannot
read or write capacity receipts. The non-login writer owner receives only the
columns and helper access needed to validate identity/scope, create a draft,
and resolve a retry; it receives no access to notes for reading. The aggregate
capacity route continues to omit draft profiles.

## Capacity draft revision

`PUT /operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}`
uses a separate exact `operating_pilot:edit_own` location grant. The operator
must also be able to read their own capacity history through
`operating_pilot:read_own` to discover and select an editable record. Neither
`create` nor general `read` implies `edit_own`; editing does not grant access to
another person's records.

The Gateway validates the location, profile, and request UUIDs and applies the
same bounded period, decimal-hour, committed-plus-protected, and private-note
rules as draft creation before connecting to PostgreSQL. Migration 555 then
rechecks the signed location context, exact edit-own grant, enabled operator,
unique active human-party binding, and active Adelphi mapping. It accepts only
the caller's own `source='self_reported'`, `status='draft'` profile. It marks
that version `superseded` and inserts a new self-attributed `draft` in the same
transaction; submitted, approved, reviewed, or other-party profiles cannot be
revised. It does not submit, verify, approve, reject, or publish either
version.

The private revision receipt binds the operator/request ID to the location,
original profile, replacement profile, and canonical input digest. An
identical retry returns the same replacement; a changed payload, location, or
original profile under that request ID conflicts. Period collisions and all
validation or authorization errors roll the transaction back, preserving the
original draft. The response contains only the two profile IDs, current draft
status, and replay indicator; private notes and hour values are not returned.

## Capacity draft submission

`POST /operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/submit`
uses a separate exact `operating_pilot:submit_own` location grant. The request
body contains only a UUID `request_id`; callers cannot send a lifecycle status,
identity, hours, notes, or review fields. The Gateway validates the identifiers
before connecting, sets signed submit-own context on the same transaction, and
uses same-origin CSRF protection with `no-store` responses.

Migration 556 rechecks the signed location, active exact submit-own grant,
enabled operator and unique active human binding, and active Adelphi mapping.
It locks and submits only the caller's own `self_reported` draft. The status
change and private request receipt commit atomically. The route cannot revise,
verify, approve, reject, or publish a profile; independent human review remains
a separate capability.

The receipt binds the operator/request ID to the exact location and profile.
Identical retries return the current profile status; reusing the request ID for
a different profile or location conflicts. A different request cannot resubmit
a profile that has already left `draft`, and missing grants, cross-party
profiles, or signed-location mismatch fail closed. The response contains only
profile ID, current status, and replay indicator.

## Capacity review queue

`GET /operator/api/operating-pilot/{location_id}/capacity-review-queue` uses a
separate exact `operating_pilot:review` location grant and signed tenant
context. The Gateway opens a read-only transaction, bounds the page to 1–50
rows and offset 0–10,000, and sends a same-origin `no-store` response.

Migration 557 returns only submitted `self_reported` capacity profiles in the
active Adelphi farm mapped to the requested location. It requires an enabled
operator with exactly one active human-party binding and excludes profiles
belonging to that same party, preventing self-review. Results are ordered by
update time and profile ID, with total count and bounded paging metadata.
Reviewers see the record ID, period, available/committed/protected hours, and
last-update timestamp. Party identity, scope IDs, source metadata, and private
notes remain inside PostgreSQL. This queue endpoint remains read-only; decisions
use a separate action below.

## Capacity review decisions

`POST /operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/review`
uses the same separate exact `operating_pilot:review` location grant, signed
tenant context, same-transaction database connection, CSRF protection, and
no-store response. The request contains a UUID `request_id`, a decision of
`approved` or `rejected`, and an optional reason of at most 2,000 characters.
Rejection requires a non-empty reason. The console requires an explicit review
acknowledgement and preserves the request ID for an exact retry; changing the
decision or reason starts a distinct request.

Migration 558 rechecks the active exact location grant, the active Adelphi farm
mapping, and exactly one enabled operator-to-human-party binding. Binding,
operator, and party rows are locked while the decision runs. The target must be
a submitted, self-reported profile in that farm, and its owner must differ from
the reviewer. Only one terminal decision can be recorded for a profile. The
profile status update and private append-only decision receipt commit in the
same transaction; the response contains only profile ID, decision/status, and
the replay flag. A reviewer cannot set lifecycle state directly, and runtime
and Directus have no direct status update or receipt access. The non-login
function owner has only the required profile status and receipt columns.

Approval changes `submitted` to `approved`. Rejection changes it to `rejected`
and returns the record to the submitter's own-history surface. With the
separate `operating_pilot:edit_own` grant, the submitter can revise a rejected
record into a new draft; the old record becomes `superseded` and the original
decision receipt remains tied to it. Rejection is not deletion or approval.

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

The operator console exposes five aggregate/read routes under exact
`operating_pilot:read` grants and personal capacity history under the separate
exact `operating_pilot:read_own` grant. Demand and capacity draft forms are
separately gated by `operating_pilot:create`. Revision controls appear only
for a caller-owned `self_reported` draft when the location also has the exact
`operating_pilot:edit_own` grant; submit controls require the independent exact
`operating_pilot:submit_own` grant and an explicit confirmation. Own-history
read, revision, and submission remain separate permissions. The location
selector uses the union of read, read-own, create, edit-own, and submit-own
locations without allowing one grant to activate another surface. Requests are same-origin and `no-store`, and stale responses
are discarded when the selected location changes. Pages are bounded and
provide explicit load-more controls. Aggregate capacity hours, work-claim
counts, and resource-request counts remain suppressed below three contributors.
Fixed allowlists and text-only DOM rendering are used. Draft forms add no
review actions; own-capacity submission remains a separate action and does not
provide verification or approval. This does not constitute live
OIDC/browser acceptance.

## Database boundary

The non-login `kokonut_operating_pilot_reader` role can select only the source
columns needed by these projections. Its column-level reads include the small
operator/person-binding allowlist required by the draft and own-record
functions; it has no broad identity-table access or unrelated mutation
privileges. It receives only the minimal INSERT columns and receipt access
needed by the demand- and capacity-draft definer functions. It cannot select
demand descriptions or receipt digests. Migrations 526 and 538 add only
`work_item.work_type` and `operating_resource_request.resource_type`; titles,
descriptions, and decision reasons remain unavailable to the reader.
`kokonut_runtime` is granted execution of the security-definer functions,
which recheck signed operator location context and the active exact database
grant on every call. Migrations 552 and 553 remove table-level and per-column
direct write privileges on demand signals and capacity profiles from the
legacy runtime and Directus logins. Migration 554 grants the non-login reader
only the additional capacity columns required by the own-record function. The
runtime and Directus roles receive no direct SELECT access to private notes;
Directus cannot execute the own-record, revision, or submission function,
and the reader has no login or role memberships. Migration 555 gives the
non-login function owner only `status` UPDATE on capacity profiles and the
bounded receipt columns needed to replay a revision. Migration 556 adds only
SELECT/INSERT access to the submission receipt columns needed by its function.
Runtime can execute the revision and submission functions but has no direct
receipt access or profile write privilege. Capacity receipts remain private.
This is a scoped ACL boundary, not universal least privilege or forced
RLS: other tables, inherited memberships, and deployed ACL state still require
review.

## Verification and rollback

The Gateway contract and exact route policy are covered by
`tests/test_gateway_operating_pilot_reads.py`,
`tests/test_gateway_operating_pilot_writes.py`,
`tests/test_operator_console_operating_pilot.py`, and
`tests/test_operator_route_policy_inventory.py`. The disposable PostgreSQL 16
acceptance runner applies/replays migrations 461, 479, 480, 526, 538, 552, 553,
554, 555, 556, 557, 558, 559, and 560, exercises active and internal scopes, checks aggregate
values, demand/capacity/own-capacity/claim/resource-category paging,
small-cohort suppression, separate read-own/edit-own/submit-own enforcement,
revision and demand/capacity submission replay, demand review-queue paging and redaction, old-version preservation, collision rollback,
submission eligibility, capacity approval/rejection, rejection-reason
validation, reviewer self-denial, exact retry/collision behavior, rejected-record
revision, append-only decision history, and data redaction; it also
inspects runtime, Directus, and reader privileges, including pre-existing
table-level and column-level demand and capacity write grants:
`scripts/check-operating-pilot-summary-disposable.py`. Migration 559 and all 54 grouped assertions pass in the 13-migration network-disabled acceptance on native PostgreSQL 16 and under linux/arm64 Docker/QEMU emulation ([native evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-arm64-disposable.json)). This is emulated software portability evidence, not physical Raspberry Pi acceptance. The migration 461–560 disposable suite and all 56 grouped assertions pass on native PostgreSQL 16 and under linux/arm64 Docker/QEMU emulation ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-arm64-disposable.json)). The ARM64 run demonstrates emulated software portability, not physical Raspberry Pi acceptance. Migrations 559 and 560 are not deployed to the candidate or legacy database.

Before migration rollout, disable the capability by removing the route/service
registration and route policy. If migrations 461, 479, 480, 526, 538, 552, 553,
554, 555, 556, 557, 558, 559, or 560 are applied, retain their ordered functions, receipts,
roles, and ACLs; disable only the affected route. Do not delete created drafts or edit or
reverse an applied migration. Re-enabling any prior direct-write path requires
a separately reviewed forward migration.

## Remaining gates

These slices do not establish populated Adelphi scope mapping, additional
capacity workflows beyond own drafts/revision and independent approve/reject,
work-claim/competency/learning/resource/coaching workflows, demand decisions and
fulfillment parity, parity with populated legacy outputs, live
OIDC/browser behavior, operator audience review, production recovery,
universal direct-database ACL/RLS, or MAN-CAP-037 owner acceptance. Those gates
remain open in `docs/refactor/batches.md`.
