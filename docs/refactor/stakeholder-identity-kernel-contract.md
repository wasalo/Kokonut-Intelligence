# CAP-025 Kernel identity review contract

Status: prepared first slice; not MAN-CAP-025 accepted.

## Owner-selected boundary

Canonical `party` records remain network-wide identities. Identity resolution
cases and their decisions are scoped to one farm location. A different OIDC
operator must review each proposal before it is approved. Raw participant
feedback is never accepted by, queried by, or returned from this API.

## Current Kernel surface

Migration `446_location_scoped_stakeholder_identity_review.sql` adds a
location-scoped proposal and immutable decision ledger. The first supported
source is an active `farmer_profile` in the requested location. Proposal and
approval each require the latest location-specific `personal` / `internal_use`
consent to be granted and unexpired. The review projection withholds the
source profile UUID. It returns a participant name only while that consent is
current; it also withholds candidate identity details if consent is absent or
the canonical party is private.
Profiles already carrying a verified legacy global `party_identifier` are
rejected from this Kernel path to avoid conflicting source mappings. An
approved location-scoped case cannot be reopened as a second pending case.

`POST /operator/api/stakeholder-identity/{location_id}/cases` accepts only the
source profile UUID, candidate party UUID, request UUID, a fixed match method,
a fixed evidence code, and a confidence value. Unknown keys, including free
text, are rejected. `GET .../cases` returns only pending cases for the signed
location grant, in pages of at most 50. `POST
.../cases/{case_id}/decision` accepts a request UUID, approve/reject choice,
and controlled reason code. Exact retries return the recorded decision;
reusing a request UUID with different content is rejected. Creator self-review
is rejected, and approval rechecks source, candidate, location, and consent
state.

The API uses exact `stakeholder_identity:create` and
`stakeholder_identity:review` location grants, OIDC sessions, and the
transaction-local signed tenant context. Runtime and Directus roles cannot
read or mutate the new tables directly. Narrow security-definer functions own
all reads and writes; decision history is append-only. Approved mappings stay
in the location-scoped ledger and are not copied into the legacy global
`party_identifier` views.

## Explicit exclusions and next work

This is the first source type and review workflow, not full identity parity.
There is no consumer resolver, merge operation, participant feedback access,
trust evidence write/read path, location-scoped trust profile, global trust
score, or publication path. Existing global trust evidence and profile views
are not exposed by the Kernel API. The new tables do not yet have forced RLS;
runtime/directus ACLs and bounded signed functions are the current boundary.
Live OIDC/browser checks, populated fixture parity, consent withdrawal
disposition after a completed review, all remaining source types, and
MAN-CAP-025 acceptance remain open.

## Verification and rollback

The Python service validates identifiers, enums, confidence, and keyset cursors
before opening a connection. Mutations set signed scope and call one bounded
database function in the same transaction. Focused tests cover exact Gateway
policies, request shape, bounded pagination, transaction ordering, and the
absence of raw feedback fields. A disposable PostgreSQL 16 fixture applies
migration 446 and exercises location/grant checks under a synthetic tenant
context, direct-table denial, independent review, decision retries/collisions,
consent withdrawal concealment, and immutable decisions. The existing
tenant-context checks cover the actual OIDC-session signature path.

To withdraw the feature before migration rollout, remove the Gateway
registration/policies and its route/service as one unit. Migration 446 is
additive and checksummed; if applied, do not edit or reverse it. Keep the
ledger, ACLs, and functions in place while removing only the API registration.
