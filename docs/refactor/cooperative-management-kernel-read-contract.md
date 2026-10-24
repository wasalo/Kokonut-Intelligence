# Cooperative management Kernel read contract

**Status:** First read-only slice implemented; capability remains prepared.
**Updated:** 24 October 2026

## Route and authorization

`GET /operator/api/cooperatives/{location_id}/summary` requires the exact
OIDC operator grant `cooperative_management:read` for the selected location.
The Gateway opens one repeatable-read, read-only transaction, applies bounded
statement and lock timeouts, establishes database-signed tenant context, then
runs the summary queries. Invalid operator/location identifiers fail before
the connection is opened. Responses are `no-store` and vary by cookie.

## Returned projection

The route returns grouped counts only:

- Cooperatives by the fixed cooperative-type allowlist (unknown values are
  grouped as `other`) and lifecycle status, with active membership counts.
- Shared assets by asset type and status.
- Asset bookings by lifecycle status.

Every query is anchored to `cooperative.location_id`. Membership counts
require an exact matching `cooperative_membership.location_id`. Asset rows
must belong to an exactly scoped cooperative and either match the requested
asset location or have no asset location recorded. Booking counts additionally
require the asset and membership to resolve to the same cooperative and the
membership to carry the exact requested location. This intentionally excludes
bookings whose legacy membership scope is missing or inconsistent.

The projection does not return cooperative, member, asset, membership, or
booking IDs or names. It omits personal identity/contact fields, credentials,
KYC, booking times/purpose, asset identifiers/serials, financial values, GPS,
notes, evidence, and arbitrary metadata. The operator console renders only
fixed response fields as text and appears only when the exact location grant is
present.

## Boundaries and remaining work

This first slice does not implement profile or credential review, cooperative
CRUD, individual membership history, asset booking workflows, or financial
reconciliation. It is not populated-output parity: aggregate definitions and
historical scope still need review against owner-selected fixtures. The query
uses the current shared runtime database identity, so signed tenant context
does not establish least-privilege table ACLs or row-level security. Live
ZITADEL/browser behavior, scoped database roles/RLS, populated parity,
audience/privacy review, and `MAN-CAP-005` remain open.

## Verification and rollback

Focused route, SQL-shape, authorization, console-contract, and JavaScript
syntax checks run against fakes. No migration, seed, candidate/legacy database,
provider, or external service is used. Rollback is a source revert of the
Gateway reader/route registration/policy and console panel, followed by
regenerating `runtime-sql-inventory.json`; no persistent data has been written.
