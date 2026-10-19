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
or minority reports. It does not create, edit, open, close, approve, reject,
publish, or execute Delphi content. Facilitator-generated recommendations
remain drafts until a separate human review path is implemented.

## Database boundary and limitations

Migration 449 creates a non-login, non-inheriting read-function owner with only
the table reads needed for this projection. The `STABLE SECURITY DEFINER`
function is not executable by `PUBLIC`; this migration grants the Gateway
runtime execute permission for the bounded function without granting it direct
table access. This is a bounded application access path, not a claim that
all legacy database roles, Directus permissions, or every Delphi CLI operation
are tenant-isolated. Universal runtime ACL/RLS and Directus parity remain open.

The consent filter relies on the existing Delphi panel `consent_status` field;
it does not replace the platform's broader consent/retention policy. The
minimum-group suppression is a disclosure guard, not differential privacy.
Published reports, cross-item differencing, populated legacy parity, live OIDC,
and MAN-CAP-027 acceptance remain separate gates.

## Verification and rollback

Focused Gateway, exact route-policy, existing Delphi, and disposable PostgreSQL
16 checks cover scoped access, current-consent filtering, minimum-group
suppression, omitted private fields, bounded paging, authorization denial,
function privilege boundaries, and migration replay. No candidate or legacy
database is modified by these checks.

Before migration 449 is applied, roll back by removing the route, service, route
policy, and migration from the proposed deployment. After application, retain
the additive function and role as an ordered migration; disable the route to
roll back application behavior. No candidate rollout is included in this batch.
