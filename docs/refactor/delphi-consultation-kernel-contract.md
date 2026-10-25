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
checks pass (119 tests). Migration 449's disposable PostgreSQL 16 acceptance
passed. Migration 450 applies and replays in a fresh disposable PostgreSQL 16
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
Migration 451 is not rolled out to candidate or legacy. The CAP-027 draft
source slice is implemented and verified, not accepted as a capability.
Live OIDC/browser, broader Delphi parity, universal runtime ACL/RLS, and
MAN-CAP-027 owner acceptance remain open.

Before migrations 449–451 are applied, roll back by removing the routes,
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
