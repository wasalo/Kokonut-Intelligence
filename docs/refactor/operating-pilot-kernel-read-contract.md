# CAP-037 Operating Pilot Kernel Read Contract

**Status:** Prepared (`P`), not MAN-CAP-037 accepted
**Current slices:** Location-scoped operating-pilot summary, redacted demand page, private demand draft creation, own-demand history, revision and submission, independent redacted demand review queue and decisions, self-reported capacity creation, personal capacity history, own-draft revision and submission, independent capacity review queue and decisions, aggregate capacity-period page, suppressed work-claim category page, bounded work-opportunity queue and self-claim proposal, independent work-claim review and explicit allocation, suppressed resource-request category page, private resource-request draft creation/history/revision/submission, independent resource-request review queue and approve/reject decisions, competency self-assessment draft and own-history read
**Migrations:** `schemas/postgres/461_location_scoped_operating_pilot_summary.sql`; `schemas/postgres/479_location_operating_pilot_demand_signals.sql`; `schemas/postgres/480_location_operating_pilot_capacity_periods.sql`; `schemas/postgres/526_location_operating_pilot_work_claims.sql`; `schemas/postgres/538_location_operating_pilot_resource_categories.sql`; `schemas/postgres/552_location_operating_pilot_demand_draft.sql`; `schemas/postgres/553_location_operating_pilot_capacity_draft.sql`; `schemas/postgres/554_location_own_operating_pilot_capacity.sql`; `schemas/postgres/555_location_operating_pilot_capacity_draft_revision.sql`; `schemas/postgres/556_location_operating_pilot_capacity_draft_submission.sql`; `schemas/postgres/557_location_operating_pilot_capacity_review_queue.sql`; `schemas/postgres/558_location_operating_pilot_capacity_review_decision.sql`; `schemas/postgres/559_location_operating_pilot_demand_draft_submission.sql`; `schemas/postgres/560_location_operating_pilot_demand_review_queue.sql`; `schemas/postgres/561_location_own_operating_pilot_demand.sql`; `schemas/postgres/562_location_operating_pilot_demand_draft_revision.sql`; `schemas/postgres/563_location_operating_pilot_demand_review_decision.sql`; `schemas/postgres/564_location_operating_pilot_work_opportunities.sql`; `schemas/postgres/565_location_operating_pilot_work_claim_review.sql`; `schemas/postgres/566_location_operating_pilot_work_claim_allocation.sql`; `schemas/postgres/567_location_operating_pilot_resource_request_draft.sql`; `schemas/postgres/568_location_own_operating_pilot_resource_requests.sql`; `schemas/postgres/569_location_operating_pilot_resource_draft_revision.sql`; `schemas/postgres/570_location_operating_pilot_resource_draft_submission.sql`; `schemas/postgres/571_location_operating_pilot_resource_review_queue.sql`; `schemas/postgres/572_location_operating_pilot_resource_review_decision.sql`; `schemas/postgres/574_location_operating_pilot_competency_draft.sql`; `schemas/postgres/575_location_own_operating_pilot_competency_drafts.sql`

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

## Own demand history

`GET /operator/api/operating-pilot/{location_id}/my-demand-signals` uses the
same separate exact `operating_pilot:read_own` grant. Migration 561 requires
the signed operator/location context, enabled operator identity, exactly one
active human-party binding, active Adelphi farm mapping, and the original
private demand-draft receipt for that operator and location. A record without
the Kernel receipt is excluded even when its creator party happens to match.
The page includes only that operator's own drafts and later lifecycle records;
another operator's receipt, another farm, and an ambiguous identity binding
fail closed.

This owner-only response includes the private planning description alongside
the work type, period, hours, priority, lifecycle status, and timestamps. The
non-login function owner receives only the required demand columns, including
`description`; it has no table-wide SELECT and cannot read source metadata.
Runtime can execute the bounded function but cannot select descriptions or
source fields directly, and Directus cannot execute the function or read those
columns. The Gateway uses a read-only transaction and `no-store` responses;
the console renders notes as text, supports bounded paging, and exposes no
review or fulfillment action here.


## Own demand draft revision

`PUT /operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}`
uses the separate exact `operating_pilot:edit_own` grant. The Gateway applies
signed operator/location context on the same transaction, validates the
request ID and the same bounded work/period/hours/priority/description contract
as draft creation, and sends a no-store, CSRF-protected request. Migration 562
requires one active human-party binding, the active Adelphi mapping, and a
matching receipt for the original signal, operator, and location. Only an owned
`draft` or `rejected` planning record is eligible. The transaction supersedes
that version, inserts a new private `planning`/`draft` signal, writes its normal
draft receipt for own-history continuity, and appends an idempotent revision
receipt. Exact retries return the same replacement; request-ID reuse with
changed input, submitted records, receiptless legacy rows, foreign owners, and
other-location records fail closed. Review, approval, and fulfillment remain
separate actions.

The own-demand table shows edit controls only on draft or rejected rows and
only when both `read_own` and `edit_own` are present. The previous version stays
visible as `superseded`; its private description remains available only through
the owner history. Runtime and Directus cannot write demand rows or access
revision receipts. The non-login function owner receives only the needed
revision-receipt columns and `status` update on demand rows.

## Independent demand review decision

`POST /operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/review`
uses the exact location `operating_pilot:review` grant already required by the
independent queue. Migration 563 accepts only a receipt-backed Kernel demand
that is still `submitted` at the active Adelphi location. It rechecks signed
location context, one enabled operator and active human-party binding, current
review authorization, and that the reviewer is not the submitter. `approved`
and `rejected` decisions update only lifecycle status; rejection requires a
bounded reason. The status update and private append-only decision receipt are
atomic. Exact retries replay; changed request reuse and duplicate decisions
fail closed. The API response omits reviewer identity and the private reason.

The console decision form requires explicit authorization acknowledgement,
CSRF/no-store requests, and stable request IDs for unchanged retries. Rejection
returns the signal to its owner for a separate revision; approval does not
fulfill work. Runtime can call the bounded function but cannot read/write the
decision ledger or mutate demand rows directly. Directus cannot call the
function or access its decision records.

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
Migration 562 follows the same limited pattern for demand revision receipts;
the runtime can execute the function but cannot read or write either demand
receipt directly, and it cannot mutate demand rows outside the function.
Migration 563 adds the separate demand review decision function and private
append-only ledger; migration 564 adds only the selected work-item projection,
claim/event insert columns, and allocation marker to the same non-login owner; only the non-login function owner can update signal status
and access decision reasons, while runtime and Directus cannot access the
ledger directly.
This is a scoped ACL boundary, not universal least privilege or forced
RLS: other tables, inherited memberships, and deployed ACL state still require
review.

## Work opportunity page and self-claim proposal

`GET /operator/api/operating-pilot/{location_id}/work-opportunities` and
`POST /operator/api/operating-pilot/{location_id}/work-opportunities/{work_item_id}/claims`
require a separate exact location `operating_pilot:claim_own` grant and the
signed operator/location context on the same database transaction. Both paths
require one active human-party binding and the active Adelphi farm-to-location
mapping. The GET page is bounded to limits 1–50 and offsets 0–10,000, sorted by
priority, due date, and ID. It returns the current location's eligible
non-assigned opportunities, fixed display fields, and only whether the caller
has a claim plus that claim's lifecycle status; claim IDs, claimant identity,
descriptions, capability evidence, and other people's claims are excluded.

The POST accepts a UUID `request_id` and optional finite, non-negative
`proposed_effort_hours` bounded to two decimal places and 100,000. Migration 564
locks and revalidates the work item, inserts only a self-attributed `proposed`
claim, writes the existing selection event, marks the opportunity as claimed,
and stores a private append-only request receipt in one transaction. Exact
retries replay; changed request-ID reuse and an existing claim by the same human
party fail closed. It does not assign the work or approve the claim. Independent
review and assignment remain separate actions.

The non-login reader/function owner has only the columns needed for the bounded
queue, claim insert, selection event, receipt, and allocation marker. Runtime
can execute the functions but has no direct claim, selection-event, or receipt
access; Directus has neither function execution nor ledger access. The console
gates the queue/action on the exact `claim_own` scope, uses CSRF and no-store,
reuses request IDs for transport retries, and renders all values as text.

## Independent work-claim review

`GET /operator/api/operating-pilot/{location_id}/work-claim-review-queue` and
`POST /operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/review`
use the separate exact location `operating_pilot:review` grant. Migration 565
requires signed location context, an active Adelphi mapping, one active
human-party binding, a proposed claim for that location, and an independent
reviewer. Queue pages are bounded and omit claimant identity, evidence, and
decision reasons. Review accepts only `accepted` or `rejected`; rejection
requires a reason. Acceptance records review eligibility but does not allocate
or assign the opportunity. Rejection reopens the opportunity only when no
proposed or accepted claims remain. An append-only private receipt provides
exact-request replay and collision rejection.

The reviewer panel is gated by `operating_pilot:review`, confirms the decision,
uses CSRF-protected no-store requests and stable retry IDs, and renders values
as text. Runtime can execute the bounded queue/decision functions but cannot
read or mutate the private receipt or claim rows directly; Directus cannot
execute these functions. Migration 565 also removes row locks from the
migration 564 opportunity projection so its read-only Gateway transaction
remains valid.

## Explicit work-claim allocation

`GET /operator/api/operating-pilot/{location_id}/work-claim-allocation-queue`
and `POST /operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/allocate`
use a separate exact location `operating_pilot:allocate` grant. Migration 566
requires signed operator location context, an active Adelphi mapping, and
exactly one active human-party binding for the allocator. The bounded queue
exposes claimant names only to allocate-scoped operators, omits private claim
evidence and review reasons, and suppresses opportunities while another claim
is proposed or accepted. Allocation requires one independently accepted,
non-self claim and no unresolved competitors; it changes only the work item's
`allocation_status` and `assignee_party_id`, leaving both work lifecycle status
and accepted review status unchanged. A private append-only receipt replays an
identical request and rejects changed request reuse or a second allocation.
Runtime has only bounded function execution and no direct receipt or assignee
column access; Directus cannot execute these functions or mutate assignment
columns. The console separately gates the queue and action on `allocate`, uses
bounded paging, text-only rendering, CSRF/no-store requests, explicit
acknowledgement, and a stable request ID after uncertain responses. Allocation
does not start, verify, or complete work.

## Private resource-request drafts

`POST /operator/api/operating-pilot/{location_id}/resource-requests` requires
the exact location `operating_pilot:create` grant, signed operator/location
context, one active human-party binding, and one active Adelphi farm mapping.
The request is validated to a bounded resource type, description, urgency, and
needed-by date. Migration 567 stores it in the separate
`operating_resource_request_draft` table with a private request receipt; it does
not create or mutate a row in the submitted `operating_resource_request` table.
Therefore draft content does not enter the existing aggregate or category
projections before submission.

Identical retries return the original draft; reusing the request ID with changed
input fails closed. The response contains only a draft identifier, lifecycle
label, replay flag, and location. The operator console shows the form only under
the create grant, uses CSRF-protected same-origin no-store requests, and keeps
the same request ID while retrying unchanged values. Migration 567 alone did not
provide history, revision, submission, review, or fulfillment; migration 568 adds
the own-history read described below.

The create function returns only the generated draft ID and lifecycle label.
The non-login function owner has bounded insert access and the column-level
read access needed by create-retry validation and the subsequent own-history
projection; it cannot update or delete receipts. Runtime can execute only the
bounded functions, while runtime and Directus have no direct draft or receipt
table access. This is not a complete resource-request workflow or a universal
least-privilege/RLS claim.

## Private resource-request history

Migration 568 adds `GET /operator/api/operating-pilot/{location_id}/my-resource-requests` under the exact location `operating_pilot:read_own` grant. The bounded page is receipt-backed and restricted to the signed operator, the active location, exactly one active person binding, and the active Adelphi farm scope. It returns only the operator’s own resource type, private description, urgency, needed-by date, lifecycle label, and timestamps, in deterministic newest-first order. Receipt digests and operator, party, and scope identifiers are never returned.

The create function continues to return only its draft ID and lifecycle label. Its non-login function owner shares the required narrow `SELECT` grants with the own-history function; it retains receipt-digest read access internally because exact create retries must validate the stored input digest. The own-history SQL projection never selects or serializes that digest. Runtime and Directus have no direct draft or receipt access, and Directus cannot execute the history function. The console gates the panel on `read_own`, uses no-store same-origin requests and text-only rendering, and caps pages at 50.

## Own resource draft revision

`PUT /operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}`
uses the exact location `operating_pilot:edit_own` grant. Migration 569
requires signed operator/location context, one active human-party binding, an
active Adelphi farm mapping, and the original operator/location creation
receipt. Only the caller's current `draft` version is eligible; submitted,
superseded, receiptless, foreign-owner, other-farm, mismatched-location, and
missing-grant cases fail closed. One transaction marks the old version
`superseded`, creates a new private draft, adds the normal receipt needed by
own-history, and appends a separate revision receipt. Exact retries replay the
same replacement; changed inputs and reuse of a create request ID fail closed.
Revision does not submit, review, approve, or fulfill the request.

The console adds edit controls only to own-history rows with `draft` status and
the exact `edit_own` scope. The editor also requires `read_own` so it can load
and bind the private version being edited. It preserves the same request ID for
unchanged retries, sends a CSRF-protected same-origin `no-store` request, and
uses text-only rendering. The non-login function owner can update only draft
status and update time and can read/write the append-only revision receipt;
runtime and Directus cannot execute it or access those receipts directly.

## Verification and rollback

The Gateway contract and exact route policy are covered by
`tests/test_gateway_operating_pilot_reads.py`,
`tests/test_gateway_operating_pilot_writes.py`,
`tests/test_gateway_operating_pilot_work_claims.py`,
`tests/test_gateway_operating_pilot_work_claim_reviews.py`,
`tests/test_gateway_operating_pilot_work_claim_allocations.py`,
`tests/test_operator_console_operating_pilot.py`, and
`tests/test_operator_route_policy_inventory.py`. The disposable PostgreSQL 16
acceptance runner applies/replays migrations 461, 479, 480, 526, 538, 552, 553,
554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568,
569, 570, and 571, exercises active and internal scopes, checks aggregate
values, demand/capacity/own-capacity/claim/resource-category paging,
small-cohort suppression, separate read-own/edit-own/submit-own enforcement,
demand/capacity/resource revision and submission replay, resource review-queue scope and redaction, demand review-queue paging and redaction, independent demand approve/reject, location-scoped work opportunity paging and self-claim proposals, independent work-claim review paging and decisions, self-review denial, exact retry replay and collision rollback, old-version preservation,
submission eligibility, capacity approval/rejection, rejection-reason
validation, reviewer self-denial, exact retry/collision behavior, rejected-record
revision, append-only decision history, private resource-draft replay/scope, own-resource exact paging/ownership/redaction and ACLs, and data redaction; it also
inspects runtime, Directus, and reader privileges, including pre-existing
table-level and column-level demand and capacity write grants:
`scripts/check-operating-pilot-summary-disposable.py`. Migration 559 and all 54 grouped assertions pass in the 13-migration network-disabled acceptance on native PostgreSQL 16 and under linux/arm64 Docker/QEMU emulation ([native evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-draft-submission-arm64-disposable.json)). This is emulated software portability evidence, not physical Raspberry Pi acceptance. The migration 461–560 disposable suite and all 56 grouped assertions pass on native PostgreSQL 16 and under linux/arm64 Docker/QEMU emulation ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-queue-arm64-disposable.json)). Migration 561 applies/replays in the 15-migration suite with all 58 grouped assertions passing on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-own-demand-read-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-own-demand-read-arm64-disposable.json)). Those QEMU checks establish software portability only, not physical Raspberry Pi acceptance. Migration 562 also applies/replays with 61 grouped assertions on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-own-demand-revision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-own-demand-revision-arm64-disposable.json)). The migration 461–563 acceptance passes 65 grouped assertions on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-demand-review-decision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-demand-review-decision-arm64-disposable.json)). QEMU is software emulation only, not physical Raspberry Pi acceptance. Migration 564 and all 67 grouped assertions pass on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-work-opportunities-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-opportunities-arm64-disposable.json)). Migration 565 and all 74 grouped assertions pass on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-work-claim-review-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-claim-review-arm64-disposable.json)). Migration 566 and all 82 grouped assertions pass on native PostgreSQL 16 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-work-claim-allocation-arm64-disposable.json)). The focused Gateway, route-policy, and console selection passes 39 tests; Ruff, Python compilation, and inline JavaScript syntax pass. QEMU establishes software portability only, not Raspberry Pi hardware, performance, power-loss, or recovery acceptance. Migrations 559–566 are not deployed to candidate or legacy databases. Roll back by disabling the review/allocation routes, exact policies, and console panels; preserve the additive migration and private receipts if it is later applied.

Migration 567 and all 88 grouped assertions pass on native PostgreSQL 16
([native evidence](builds/2026-10-22-recovery/cap-037-resource-request-draft-disposable.json))
and linux/arm64 Docker/QEMU
([ARM64 evidence](builds/2026-10-22-recovery/cap-037-resource-request-draft-arm64-disposable.json)).
The focused Gateway, policy, and console selection passes 114 tests with Ruff,
Python compilation, and inline JavaScript syntax checks. Candidate and legacy
databases remain untouched, and migration 567 has not been rolled out.

Migration 568 and all 96 grouped assertions pass on native PostgreSQL 16
([native evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-read-disposable.json))
and linux/arm64 Docker/QEMU
([ARM64 evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-read-arm64-disposable.json)).
The focused Gateway, policy, console, and migration selection passes 170 tests;
Ruff and Python compilation pass. Candidate and legacy remain untouched, and
migrations 567–571 have not been rolled out.

Migration 569 and all 107 grouped assertions pass on native PostgreSQL 16
([native evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-revision-disposable.json))
and linux/arm64 Docker/QEMU
([ARM64 evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-revision-arm64-disposable.json)).
The focused Gateway, route-policy, console, and migration selection passes 161
tests; Ruff, Python compilation, and inline JavaScript syntax pass. QEMU is
software portability evidence only, not physical Raspberry Pi acceptance.
Candidate and legacy remain untouched, and migration 569 is not rolled out.

Before migration rollout, disable the capability by removing the route/service
registration and route policy. If migrations 461, 479, 480, 526, 538, 552, 553,
554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568,
569, 570, or 571 are applied, retain their ordered functions, receipts,
roles, and ACLs; disable only the affected route. Do not delete created drafts or edit or
reverse an applied migration. Re-enabling any prior direct-write path requires
a separately reviewed forward migration.

## Remaining gates

These slices do not establish populated Adelphi scope mapping, additional
capacity workflows beyond own drafts/revision and independent approve/reject,
post-allocation work execution, competency submission/revision/review, learning,
or coaching workflows, demand fulfillment parity, parity with populated legacy outputs, live
OIDC/browser behavior, operator audience review, production recovery,
universal direct-database ACL/RLS, or MAN-CAP-037 owner acceptance. Those gates
remain open in `docs/refactor/batches.md`.


## Private resource-request submission

`POST /operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}/submit` accepts only a stable `request_id` under the exact location `operating_pilot:submit_own` grant. Migration 570 rechecks signed context, one active person binding, active Adelphi scope, and the operator's original draft receipt. It copies the private draft's bounded values into the canonical legacy resource-request table with `status = submitted` and `decision = pending`, updates the private draft's link/status, and appends the submission receipt atomically. Exact retry returns the same draft status without creating another canonical row. Reuse for a different draft, create/revision receipt collisions, repeat submission, wrong location, and missing grant fail closed. The response omits the canonical request ID. Independent review and fulfillment remain separate actions.

The non-login reader role can insert only the required request columns and update only draft status, canonical-link ID, and update time. Runtime and Directus cannot read or mutate the canonical resource-request table or submission receipt directly; the Gateway invokes only the bounded function. The former unscoped management create and decision helpers fail before opening a cursor. The operator console requires both `read_own` and `submit_own`, asks for confirmation, sends a same-origin CSRF-protected no-store request, preserves one request ID across retries, and removes editing once the row is submitted.

Migration 570 and all 123 grouped assertions pass on network-disabled disposable PostgreSQL 16 ([native evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-submission-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-own-resource-request-submission-arm64-disposable.json)). The focused Gateway, route-policy, console, management-helper, and migration selection passes 171 tests with one database-backed test skipped; Ruff, Python compilation, inline JavaScript syntax, and diff checks pass. QEMU is software emulation only. Candidate and legacy remain untouched, and migration 570 is not rolled out. Before rollout, disable the route, exact policy, and console button; if applied, retain the additive function, receipt, roles, and ACLs. Resource review decisions and fulfillment, populated parity, live OIDC/browser, universal ACL/RLS, production recovery, and MAN-CAP-037 owner acceptance remain open.


## Independent resource-request review queue

`GET /operator/api/operating-pilot/{location_id}/resource-review-queue` is a read-only, no-store OIDC route under the exact location `operating_pilot:review` grant. Migration 571 rechecks signed tenant context and the grant in the same read-only transaction, requires one active human-party binding and the active Adelphi farm mapping, and returns only receipt-backed Kernel submissions that remain `submitted` / `pending` with a linked submitted draft. It excludes the reviewer's own submissions, legacy receiptless requests, unrelated farms, and internal pilot scope. The response includes only the request ID, resource type, description, urgency, and needed-by date needed by the authorized reviewer; requester identity and internal lifecycle metadata are omitted. Limit is capped at 50 and offset at 10,000.

Runtime and Directus cannot directly query the canonical request or submission-receipt tables. The non-login reader function owner receives only column-scoped request access needed to evaluate and return this projection; the Gateway invokes only the bounded function. The console shows the queue only when the exact review grant is present and renders request content as text. This slice does not approve, reject, or fulfill a request.

Migration 571 and all 130 grouped assertions pass on network-disabled disposable PostgreSQL 16 ([native evidence](builds/2026-10-22-recovery/cap-037-resource-request-review-queue-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-resource-request-review-queue-arm64-disposable.json)). The focused Gateway, route-policy, and console checks pass 146 tests. QEMU is software emulation only. Candidate and legacy remain untouched, and migration 571 is not rolled out. Disable the route, exact policy, and console panel to roll back; retain the additive migration and its ACLs if applied. At this queue-only stage, decisions were still open; the subsequent decision slice is documented below. Fulfillment, populated parity, live OIDC/browser, universal ACL/RLS, production recovery, and MAN-CAP-037 owner acceptance remain open.


## Independent resource-request review decisions

`POST /operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/review` requires the exact location `operating_pilot:review` grant and a same-transaction signed tenant context. Migration 572 also rechecks the active Adelphi farm mapping, exactly one active human-party binding, a distinct reviewer, and an immutable Kernel draft-submission receipt linked to a currently submitted/pending request. It accepts only `approved` or `rejected`; rejection requires a trimmed reason of at most 2,000 characters. Approval moves the canonical request to `approved` / `reviewed`; rejection moves it to `declined` / `reviewed`. Neither action partially allocates or fulfills resources.

An append-only private receipt stores reviewer attribution, decision, reason, and the input digest. Repeating the same request ID and input replays the result; changed input, request-ID collision, and a second decision fail closed. The response excludes the reason. Migration 572 adds the missing reviewer-attribution columns to older request-table shapes only when absent and does not backfill historic rows. Runtime and Directus cannot directly update canonical request fields or access the receipt; only runtime may execute the bounded function, and Directus cannot execute it. The console requires explicit acknowledgement, keeps one retry ID for exact retries, and uses same-origin CSRF-protected no-store requests.

The focused Gateway, read, route-policy, and console selection passes 254 tests. Network-disabled PostgreSQL 16 applies/replays migrations 461–572 with 146 grouped assertions on native AMD64 and linux/arm64 Docker/QEMU ([native evidence](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-disposable.json); [ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-resource-request-review-decision-arm64-disposable.json)). QEMU is software portability evidence, not Raspberry Pi hardware acceptance. Candidate and legacy remain untouched; migration 572 is not rolled out. Disable the decision route, exact policy, and console controls to roll back; retain the additive migration and audit receipts if applied. Fulfillment, populated parity, live OIDC/browser, universal ACL/RLS, production recovery, and MAN-CAP-037 owner acceptance remain open.

## Independent resource-request fulfillment confirmation

`GET /operator/api/operating-pilot/{location_id}/resource-fulfillment-queue` and `POST /operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/fulfill` require the exact location `operating_pilot:fulfill` grant. Migration 573 checks signed tenant context, one active human-party binding, the current grant, active Adelphi mapping, and a receipt-backed Kernel submission with an approved review receipt. The read-only, bounded queue omits requester identity and approval reason and excludes rejected, legacy, already fulfilled, and self-requested rows.

The write function locks the approved request and active fulfiller binding, then changes only the request decision/status and appends a private fulfillment receipt in the same transaction. It preserves the independent review attribution; exact retries replay, while changed request reuse and second fulfillment fail closed. Requester self-confirmation is prohibited. This records a human confirmation only and does not assert inventory receipt, expense recognition, or payment. The console requires the separate grant and an explicit acknowledgement, with CSRF/no-store requests and a stable retry ID.

Migration 573 passes apply/replay and 165 grouped assertions on disposable PostgreSQL 16 in native AMD64 and ARM64/QEMU. Focused Gateway, route-policy, console, and migration checks pass 308 tests. QEMU is software portability evidence only. Candidate and legacy remain untouched; migration 573 is not rolled out. Roll back by disabling the routes, exact policy, and console section; retain the additive migration and receipts if it has been applied. Broader ACL/RLS, populated parity, live OIDC/browser behavior, production recovery, and MAN-CAP-037 owner acceptance remain open.

## Private competency self-assessment draft

`POST /operator/api/operating-pilot/{location_id}/competency-assessments` creates
a private self-reported draft under the exact location `operating_pilot:create`
grant. Migration 574 rechecks signed tenant context, one active human-party
binding, the active Adelphi farm mapping, a normalized competency key, and
0–5 self-assessed and target levels. It stores a bounded private evidence note
and uses a stable request ID for exact retry replay. Changed payload reuse,
duplicate open drafts, missing grants, invalid levels, and location mismatches
fail closed. Responses include only the draft ID, draft status, and replay flag.
The function writes neither `operating_competency_profile` nor verified
competency state; submission and independent review remain separate future
actions. Runtime and Directus have no direct access to the private draft or its
receipt, and the non-login function owner cannot read the evidence note or
mutate receipts.

Migration 574 applies and replays with 176 grouped assertions on network-disabled
disposable PostgreSQL 16 on native AMD64 and linux/arm64 Docker/QEMU
([native evidence](builds/2026-10-22-recovery/cap-037-competency-draft-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-037-competency-draft-arm64-disposable.json)).
Focused Gateway validation and route-policy checks pass 10 tests; Ruff and
Python compilation pass. QEMU is software portability evidence only. Candidate
and legacy databases are untouched; migration 574 is not rolled out. Disable
the route and exact policy to roll back; retain the additive migration and
private receipts if applied. Competency submission, own-history/revision,
independent review, populated parity, live OIDC/browser behavior, broader
ACL/RLS, production recovery, and MAN-CAP-037 owner acceptance remain open.
## Private own competency-assessment history

`GET /operator/api/operating-pilot/{location_id}/my-competency-assessments`
requires the separate exact location `operating_pilot:read_own` grant and a
same-transaction signed tenant context. Migration 575 rechecks the current
grant, exactly one active human-party binding, and active Adelphi mapping. It
returns only receipt-backed drafts for the requesting operator's bound person
at that location and active scope. Pages are bounded to 1–50 rows and offsets
0–10,000, ordered by creation time and ID. The operator can see their own
self-assessed levels and evidence note; the response omits operator, person,
scope, receipt, and digest identifiers and never includes another party's
rows. Aggregate `read` and draft `create` grants do not imply own-history
access.

Only the runtime role can execute the bounded function. Directus cannot execute
it; neither runtime role has direct draft or receipt table access. The reader
function owner has only the column reads needed for the projection and cannot
mutate data. Migration 575 and 184 grouped assertions pass on disposable,
network-disabled PostgreSQL 16; the focused Gateway read and route-policy
selection passes 10 tests. Candidate and legacy databases remain untouched,
and migration 575 is not rolled out. This establishes code and disposable-DB
evidence only; real OIDC, browser behavior, populated data parity, production
ACL/RLS, recovery, and MAN-CAP-037 acceptance remain open.
