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

## Database boundary and limitations

Migration 449 creates a non-login, non-inheriting read-function owner with only
the table reads needed for the consultation projection. Migration 450 adds a
separate non-login reviewer function owner, narrow recommendation update
privileges, and a private immutable review ledger. Both migrations grant the
Gateway runtime execute permission for bounded functions; Directus cannot call
the review functions or read the review ledger. The existing shared runtime
still has broader legacy DML on Delphi records, so these routes do not prove
that direct legacy/CLI access cannot bypass the new review contract. Universal
runtime ACL/RLS and Directus field/row parity remain open.

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

Before migration 449 or 450 is applied, roll back by removing the routes,
services, route policies, and migrations from the proposed deployment. After
application, retain additive functions, roles, and ledgers as ordered
migrations; disable the routes to roll back application behavior. No candidate
rollout is included in this batch.
