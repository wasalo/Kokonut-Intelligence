# CAP-027 bounded Delphi consultation read contract

## Purpose

This is the first native Kernel access path for Real-time Delphi. It gives a
location-authorized operator a privacy-aware view of consultation state while
keeping participant identities, raw explanations, facilitator recommendations,
and minority reports outside the response.

## Route and authorization

`GET /operator/api/delphi/{location_id}/studies?limit=50&offset=0`

- Requires an authenticated OIDC operator and the exact location-scoped
  `delphi:read` grant.
- The Gateway establishes signed tenant context in the same transaction before
  calling `kokonut_security.list_location_delphi_consultations`.
- The database function checks actor type, signed location, and current exact
  grant again. It returns only studies whose `location_id` equals that location;
  null-location and other-location studies are omitted.
- `limit` is 1–50, `offset` is 0–10,000, and the SQL function reads at most one
  extra row to report `has_more`. Responses are `no-store` and vary by cookie.

## Projection and consent

Study rows include their title, description, variation, status, and lifecycle
timestamps. Item rows include the question label/description, type, scale, and
range. Scores are aggregated from contributions whose panel member is currently
marked `consent_status = 'granted'`; pending and withdrawn members are excluded
at query time. Median, mean, interquartile range, population standard deviation,
coefficient of variation, weighted median, consensus flag, participant count,
and latest included submission time are returned only when the eligible group
meets `max(3, ceil(stopping_criteria.min_participants))`. Below that threshold,
the response reports `results_available: false` and returns null statistics and
participant count.

The route never returns panel member IDs, participant references, display
tokens, expert weights, contribution rows or reasoning, arbitrary metadata,
consensus history, recommendations, stopping evaluations, diversity records,
or minority reports.

## Human recommendation review

`GET /operator/api/delphi/{location_id}/recommendations?limit=50&offset=0`
lists bounded draft summaries and text for an authenticated operator with the
exact location-scoped `delphi:review` grant. The review queue returns only
recommendations attached to that location and adds readiness blockers for
self-review, missing diversity assessment, and draft/submitted minority
reports. It never returns participant identifiers, raw reasoning, or arbitrary
study metadata.

`POST /operator/api/delphi/{location_id}/recommendations/{recommendation_id}/decision`
accepts exactly `decision`, `request_id`, and `reason_code`. It supports
approve/reject decisions on draft recommendations only. The creator cannot
decide their own draft. Approval requires an existing diversity assessment and
no draft or submitted minority report; rejection remains available for a draft
even when approval gates are incomplete. Request IDs are bound to the operator,
location, recommendation, decision, and reason code; retries must match exactly.
The private append-only decision ledger contains the reviewer, request key,
decision, and allowlisted reason code, without free-text feedback or review
notes. Neither endpoint is cached.

An approval changes the existing recommendation status to `approved`. Under
the legacy `v_delphi_consensus_public` view, that status can make aggregate
consensus visible when a verified/published farm registry record also exists;
the view does not expose recommendation text. This Kernel route adds no separate
publish action or publication surface. This approval behavior must be included
in human review acceptance.

The operator console shows this panel only when the signed-in session includes
an exact `delphi:review` grant for the selected location. It loads the draft
text through no-store requests, displays database blockers, hides approval when
the queue says review is not ready, and withholds both decisions for the
creator's own draft. Decisions use CSRF protection and only the database's
allowlisted reason codes. A browser-generated request UUID is retained for an
identical retry. Five focused console contract checks pass, including Node.js
parsing of the inline application script. The console has not been accepted
through live OIDC/browser use.

## Study opening readiness

`GET /operator/api/delphi/{location_id}/studies/{study_id}/open-readiness`
requires the exact location-scoped `delphi:open` grant and signed operator
context. Migration 633 checks the selected study, question presence, the
configured minimum rule, and the current consent status of panel members. It
returns only those booleans, the study/location/status, and fixed blocker codes;
it never returns a participant identifier or panel count. Pending and
withdrawn members do not satisfy the current-consent threshold.

The console keeps **Open study** disabled until a fresh matching readiness
response says the study is eligible, refreshes readiness when the selection or
question set changes, and makes another no-store check before asking for the
open confirmation. The migration-631 transition remains authoritative and
rechecks prerequisites in its write transaction, so consent changes between
the projection and the action cannot bypass the gate. The readiness result is
advisory and can become stale immediately; it is not a reservation.

The current repository still has no tenant-safe participant invitation flow,
participant-authenticated consent receipt, or bounded panel-membership write
path. This readiness projection does not grant consent and does not close those
CAP-027 implementation gates.

## Study draft creation

`POST /operator/api/delphi/{location_id}/studies` creates one private Delphi
study in `draft` state. The request accepts exactly `request_id`, `title`,
`description`, `variation`, `facilitator_type`, and `stopping_criteria`;
`request_id` and title are required. Variations and facilitator types use
explicit allowlists, title/description are bounded, and stopping criteria
accept only the four supported fields with bounded numeric values. The
operator identity comes from the authenticated OIDC session, and the route
requires an exact location-scoped `delphi:draft` grant. The service sets signed
tenant context before calling the bounded database function and returns
no-store responses.

Migration 630 rechecks signed operator/location context and the live grant in
the database, inserts only `draft` state, and records an immutable private
request receipt. The receipt stores a SHA-256 digest rather than duplicating
the title or description. Identical retries return the original study;
reusing a request ID with different content, a mismatched location, malformed
criteria, or a read-only grant fails closed. Runtime and Directus cannot read
the receipt table; only the Gateway runtime can execute the function, which is
owned by a dedicated non-login role with column-limited study access. This
route creates a study only; item, panel, open/close, contribution, and stopping
operations remain separate lifecycle work. The operator console does not yet
provide panel, item, open/close, contribution, or stopping controls. Its study
creation panel appears only when the session has an exact location `delphi:draft`
grant. The form uses bounded stopping-criteria inputs and sends CSRF-protected,
no-store requests; an unchanged retry within the active page reuses its request
ID. It confirms the returned location and `draft` lifecycle state and does not
offer any open, review, or publish action.

## Questionnaire item draft creation

`POST /operator/api/delphi/{location_id}/studies/{study_id}/items` adds one
question to a private study draft. The authenticated operator must hold the
exact location-scoped `delphi:draft` grant. The Gateway establishes signed
tenant context on the same transaction before calling the bounded database
function, which rechecks the live grant, exact study/location pair, and `draft`
status under a row lock.

The request accepts only `request_id`, `item_type`, `label`, `description`,
`scale`, `min_value`, and `max_value`; `request_id` and `label` are required.
Types and scales use explicit allowlists, text and numeric bounds are checked in
the Gateway and again in PostgreSQL, and values must fit the legacy
`NUMERIC(8,4)` columns. Item creation never opens a study, enrolls a panel, or
submits a response. The private append-only receipt stores the operator,
request key, location, study and item references, and a content digest. Exact
retries replay; reusing a key with changed content fails. The dedicated
non-login function owner has only eligibility reads and question insert
columns, plus the row-lock privilege on the study. Runtime can execute the
function but cannot read the receipt; Directus can neither execute it nor read
the receipt.

The current contract intentionally omits `target_entity_type` and
`target_entity_id`: the repository does not yet define one generic
location-safe resolver for all supported target entity types. Preserve those
links in the legacy implementation until a typed, per-entity resolver and
cross-location denial contract are implemented. The operator console question
editor appears only where the session has both `delphi:read` and `delphi:draft`
for the same location. Its bounded, paged study read filters the chooser to
`draft` status; the write still relies on the database check, so a concurrent
open makes the request fail closed. The form uses CSRF-protected, same-origin,
no-store requests, reuses a request ID for an unchanged retry, and validates
that the returned item belongs to the selected location and study. It does not
enroll panel members, collect answers, open the study, or attach a target
entity. Panel enrollment, contribution submission, and stopping evaluation
remain separate work. Migration 632 and six grouped disposable PostgreSQL 16
acceptance checks are recorded in the [implementation evidence](builds/2026-10-25-recovery/cap-027-delphi-study-items-disposable.json).

## Facilitator draft creation

`GET /operator/api/delphi/{location_id}/draft-studies?limit=50&offset=0`
lists only open or closed studies at the requested location. It requires the
distinct location-scoped `delphi:draft` grant and signed operator context.
Study list pages are bounded to 50 rows and never include participant data.

`POST
/operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts`
accepts exactly `request_id`, `summary`, and `recommendation_text`. The
request ID and study must be valid UUIDs; the summary is optional and bounded
to 4,000 characters, and recommendation text is non-empty and bounded to
20,000 characters. The database verifies that the study belongs to the signed
location and is open or closed, then creates only a `draft` recommendation.
The unique creator/request key is held in a private append-only ledger, so
exact retries return the same recommendation and reuse with changed study or
content is rejected. The ledger stores request identity and row references,
not duplicate draft text. Creation does not approve, publish, or expose the
draft through the public consensus view.
Review remains a separate exact `delphi:review` grant and rejects creator
self-review.

The operator console lists draftable studies and provides a CSRF-protected,
no-store form. Its retry key remains stable for identical content. On success
the UI says that an independent decision is required and explicitly reports
that nothing was published. The form appears only for a location with the
`delphi:draft` grant; it does not grant review access.

## Database boundary and limitations

Migration 449 creates a non-login, non-inheriting read-function owner with only
the table reads needed for the consultation projection. Migration 450 adds a
separate non-login reviewer function owner, narrow recommendation update
privileges, and a private immutable review ledger. Both migrations grant the
Gateway runtime execute permission for bounded functions; Directus cannot call
the review functions or read the review ledger. Migration 451 adds a separate
non-login draft-function owner with study/grant reads, column-limited draft
inserts, and a private append-only request ledger. Runtime and Directus cannot
read or write that ledger directly; only the Gateway runtime can invoke the
bounded functions, and Directus is explicitly denied. The shared runtime still has broader legacy
DML on Delphi records, so neither route family proves that direct legacy/CLI
access cannot bypass the Kernel contracts. Universal runtime ACL/RLS and
Directus field/row parity remain open.

The consent filter relies on the existing Delphi panel `consent_status` field;
it does not replace the platform's broader consent/retention policy. The
minimum-group suppression is a disclosure guard, not differential privacy.
Published reports, cross-item differencing, populated legacy parity, live OIDC,
and MAN-CAP-027 acceptance remain separate gates.

## Verification and rollback

Focused Gateway, exact route-policy, existing Delphi, and migration metadata
checks pass (119 tests). The study draft route/service selection and route
policy inventory pass 29 tests. Migration 449's disposable PostgreSQL 16
acceptance passed. Migration 450 applies and replays in a fresh disposable PostgreSQL 16
container and passes seven runtime assertions, including review scope, creator
self-review denial, diversity/minority gates, exact retry/collision behavior,
append-only audit, and runtime/Directus direct-table denial. A first run exposed
the PostgreSQL row-lock privilege requirement; migration 450 now grants only
`UPDATE(id)` to the non-login function owner for locking the study row. The
corrected run passes. Candidate and legacy databases remain untouched, and
migration 450 has not been rolled out there.
The five focused reviewer-console contract and inline JavaScript syntax checks
also pass ([console tests](../../tests/test_operator_console_delphi_recommendation_review.py)).
The new draft path passes 33 focused Gateway, exact route-policy, and console
checks; the combined selected Delphi and migration regression set passes 91
tests. Disposable PostgreSQL 16 applies and replays migrations 449–451, then
passes ten assertions for signed location/grant scope, open/closed study
filtering, exact request retries and collision rejection, draft-only state,
request payload bounds, private append-only ledger behavior, read-only grant
denial, runtime/Directus privilege boundaries, and the drafter owner's narrow
`UPDATE(id)` row-lock grant ([draft tests](../../tests/test_gateway_delphi_recommendation_drafts.py), [console tests](../../tests/test_operator_console_delphi_recommendation_drafts.py), [database evidence](builds/2026-10-19-recovery/cap-027-delphi-recommendation-drafts-disposable.json)).
Migration 451 is not rolled out to candidate or legacy. Migration 630 applies
and replays with migrations 449–451 on disposable PostgreSQL 16; six grouped
assertions cover exact location/grant enforcement, draft-only creation, exact
retry and changed-content rejection, malformed criteria, immutable digest-only
receipts, runtime/Directus access denial, and the dedicated function owner
([study draft tests](../../tests/test_gateway_delphi_study_drafts.py),
[disposable check](../../scripts/check-delphi-study-drafts-disposable.py),
[evidence](builds/2026-10-25-recovery/cap-027-delphi-study-drafts-disposable.json)).
No candidate or legacy database was touched; migration 630 is not rolled out.
The study-creation console panel has four focused contract checks and passes
Node.js syntax validation; the three focused Delphi console suites pass 13
tests total ([console tests](../../tests/test_operator_console_delphi_study_drafts.py),
[evidence](builds/2026-10-25-recovery/cap-027-delphi-study-draft-console.json)).
This is source/contract verification; live browser and OIDC acceptance remain
open.
The CAP-027 draft
source slice is implemented and verified, not accepted as a capability.
Live OIDC/browser, broader Delphi parity, universal runtime ACL/RLS, and
MAN-CAP-027 owner acceptance remain open.

Migration 631 adds authenticated `POST /operator/api/delphi/{location_id}/studies/{study_id}/open` and `/close` actions with separate `delphi:open` and `delphi:close` grants. Opening is allowed only from `draft`, and requires at least one question plus the configured minimum number of panel members whose `consent_status` is currently `granted`. Closing is allowed only from `open`; it preserves `opened_at`, stamps `closed_at`, and a closed study cannot be reopened. Each transition uses signed location context, a serialized request ID, and a private append-only receipt. Exact retries return the original transition result; changed action/scope reuse fails closed. The lifecycle function owner has only the required study/item/panel/grant reads and lifecycle-column updates. Runtime can execute the bounded function but cannot read receipts; Directus cannot execute it or access receipts. The focused lifecycle and route-policy selection passes 47 tests, and disposable PostgreSQL 16 applies/replays migrations 449–451, 630, and 631 before six grouped lifecycle assertions. The console lists studies under `delphi:read` and shows open/close controls only when the matching same-location action grant exists; it requires confirmation, CSRF/no-store, retry-stable IDs, and validates the transition response. The four Delphi study/recommendation console suites pass 19 tests including Node.js syntax checks. No candidate or legacy database was touched; migration 631 is not rolled out. Live OIDC/browser acceptance and questionnaire/panel authoring paths remain open.

Before migrations 449–451, 630, or 631 are applied, roll back by removing the routes,
services, route policies, and migrations from the proposed deployment. After
application, retain additive functions, roles, and ledgers as ordered
migrations; disable the routes to roll back application behavior. No candidate
rollout is included in this batch.

The legacy Delphi facilitator and CLI no longer persist, list, approve, or
reject recommendations directly. The agent helper produces an in-memory
suggestion only; the old recommendation command paths fail before database
access. The remaining CLI study and panel commands (create/open/close study,
list studies, add/list panel, add item, submit contribution, check stopping,
and calibrate panel) now also fail before database access because they lack an
authenticated location grant. Use the scoped Gateway study-list and
recommendation workflows where available. The blocked study/panel operations
remain capability gaps until their matching authenticated Gateway contracts
are implemented; this is an access-boundary hardening step, not a claim of full
Delphi lifecycle parity. No candidate or legacy database change is implied.


## Versioned participant consent and single-use invitation boundary

Migration 634 adds an immutable, location-scoped notice for each Delphi study.
An operator submits it only while the study is still in draft under
delphi:consent_draft. A separate operator with delphi:consent_review must
approve or reject using an allowlisted reason code. The author cannot review
their own text. Exact request IDs replay only when all submitted content and
scope match; each decision is recorded in a private append-only ledger. There
can be only one approved version per study. Approving a replacement marks the
previous approved version superseded.

The three protected routes are:

- POST /operator/api/delphi/{location_id}/studies/{study_id}/consent-notices
  submits a version and notice text.
- GET /operator/api/delphi/{location_id}/consent-notices?limit=50&offset=0
  returns a bounded review queue and a fixed self-review blocker.
- POST /operator/api/delphi/{location_id}/consent-notices/{notice_id}/decision
  records an independent approval or rejection.

All three require OIDC, exact location scope, same-transaction signed tenant
context, and no-store responses. Runtime reaches private data through bounded
functions only; Directus cannot read the notice ledger or invoke those
functions. Notice versions are immutable, and invitation issuance must reject
any version whose current state is not approved.

The selected participant model is a study-scoped single-use invite. Migrations
635–636 implement notice-bound token issuance, preview and atomic acceptance,
with no canonical party link. The database stores only cryptographic digests
for invite/session/CSRF credentials, and acceptance records the exact notice
version/digest. Participant-facing state remains pseudonymous. A later
approved notice version prevents both new issuance and redemption against the
superseded version.

Withdrawal prevents future submissions through the member's `withdrawn`
consent state and revokes the participant session. Existing records remain
private until the configured retention/erasure policy determines their
disposition; no fixed period or automatic deletion is introduced here. Human
review of actual notice language and applicable legal requirements remains
necessary. Migration 634 does not itself issue invites or accept participant
consent, and CAP-027 remains prepared.

Migration 634 has passed focused Gateway/route-policy/migration checks (62
tests) and a network-disabled disposable PostgreSQL 16 apply/replay with nine
grouped assertions, including reviewer separation, exact retries, immutable
content, version supersession, and runtime/Directus privilege boundaries.
Candidate and legacy databases were not touched; migration 634 is not rolled
out. To roll back before migration deployment, remove the three routes and
their exact policy entries. After migration application, disable the routes
while retaining immutable notices and audit records.


### One-time invite issuance and revocation

Migration 635 adds two operator-only routes:

- POST /operator/api/delphi/{location_id}/studies/{study_id}/invites
  takes only a request ID and lifetime in seconds.
- POST /operator/api/delphi/{location_id}/invites/{invite_id}/revoke
  takes a request ID and a fixed revoke reason.

Issuance requires exact delphi:invite scope, signed same-transaction location
context, a draft study, and a currently approved notice. The invite binds the
study/location plus the exact notice ID, version, and digest. The database
generates a 32-byte random token, persists only its SHA-256 digest, and returns
the bearer token once with Cache-Control: no-store. Lifetime is bounded to one
hour through thirty days, and each study is capped at 500 simultaneously
pending unexpired invites. Exact request retries replay metadata but omit the
secret; a lost or exposed token must be explicitly revoked and replaced with a
new request. Revocation has its own exact delphi:invite_revoke grant and
append-only reason-coded audit.

No email or other external delivery occurs. Do not distribute invite tokens
until the first-party participant page and live browser acceptance are
implemented; the API primitives alone are not a finished participant
experience.
Operator responses are OIDC/CSRF protected by the enclosing Gateway middleware,
location scoped, and no-store. Runtime and Directus have no direct access to
invite rows or receipts.

The focused Gateway/route-policy/migration tests pass (58); network-disabled
disposable PostgreSQL 16 applies/replays migrations 449–451 and 630–635 and
passes nine grouped assertions. Candidate and legacy databases remain
untouched; migration 635 is not rolled out. Disable the two routes/policies to
roll back application behavior; retain the additive migration and private
invite history if applied.


### Participant notice preview, consent acceptance, and withdrawal

Migration 636 adds three exact public-capability routes. The invite token is
accepted only in a JSON body, never in a URL:

- `POST /api/participation/delphi/preview` accepts exactly `invite_token` and
  returns the study title and exact approved notice text, version, digest, and
  expiry. It succeeds only while the invite is pending and unexpired, the study
  remains draft, and the approved notice still matches the stored location,
  notice ID, version, and digest.
- `POST /api/participation/delphi/accept` accepts the invite token, notice
  digest, request UUID, literal `accepted: true`, and two client-generated
  256-bit random values. These values support exact retries after a lost
  response; only their SHA-256 digests reach the database. The database locks
  and consumes the invite, creates one anonymous `pseudonymous_participant`
  panel member with no party reference, records an immutable acceptance event,
  and creates a 30-day revocable session in one transaction. Exact retries
  replay without creating a second member; changed credentials or request
  content fail closed.
- `POST /api/participation/delphi/withdraw` accepts a request UUID, the
  HttpOnly session cookie, and a CSRF header matching the readable CSRF cookie.
  It marks consent `withdrawn`, revokes the session, and appends the withdrawal
  event atomically. Exact retries replay; a different request or mismatched
  CSRF token is rejected. Existing submissions remain private for disposition
  under the configurable retention/erasure policy and are not deleted here.

These routes are public only at the Gateway authentication layer; their
capability tokens and bounded database functions enforce access. Responses are
no-store and set `Referrer-Policy: no-referrer`. Session cookies are Secure,
HttpOnly, SameSite=Strict, and path-limited. The CSRF cookie is same-origin
readable and is checked with constant-time comparison against the request
header and its database digest. PostgreSQL retains no raw invite, session, or
CSRF token. A dedicated non-login role owns credential and consent ledgers;
runtime and Directus cannot read those ledgers, and Directus cannot execute the
participant functions.

The participant browser page, live browser acceptance, and contribution
submission/update path are not part of migration 636. Do not distribute invites
until the first-party page is implemented and accepted. The 27-test focused
Gateway/policy selection passes within the broader 335-test Delphi, Gateway,
route-policy, and migration-integrity regression. Network-disabled disposable
PostgreSQL 16 applies and replays migrations 449–451 and 630–636 with ten
grouped checks. Candidate
and legacy databases remain untouched; migration 636 is not rolled out. Roll
back by disabling the exact routes and policy entries; retain the additive
migration, consumed invites, consent events, and withdrawal receipts if
applied.
