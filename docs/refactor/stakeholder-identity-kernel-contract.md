# CAP-025 Kernel identity review contract

Status: prepared identity-review and scoped identity-trust slices; not MAN-CAP-025 accepted.

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

Migration `447_location_scoped_identity_trust_projection.sql` adds a read-only
identity-trust projection derived only from those independently approved
location cases. `GET
/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence`
requires an exact `stakeholder_trust:read` grant and the same transaction-local
signed location context. It returns a bounded page of structured identity
evidence code, match method, confidence, and review time. The projection
rechecks the active source profile, latest personal/internal-use consent, and
the canonical party's active/non-private state on every read. Consent
withdrawal, profile deactivation, or a private/inactive canonical party
suppresses the evidence. No participant name or profile ID, reviewer ID,
free-text summary, raw feedback, legacy trust row, or global reputation score
is returned. This is reviewed identity evidence only; it does not claim to be
a complete stakeholder trust profile.

Migration `448_location_scoped_identity_resolution.sql` adds the first
consumer resolver at `GET
/operator/api/stakeholder-identity/{location_id}/resolve/{source_profile_id}`.
It requires a separate exact `stakeholder_identity:resolve` grant; create or
review access alone cannot resolve. The resolver returns only the canonical
party UUID and approval time, and only while the approved case remains in the
requested location, the farmer profile remains active, the latest
personal/internal-use consent remains granted and unexpired, the canonical
party remains active/non-private, and no conflicting verified legacy source
link exists. An unavailable mapping returns the same not-found response for
pending, absent, withdrawn, conflicted, or private mappings; the source UUID
is never echoed in the response.

## Explicit exclusions and next work

This is the first source type and review workflow, not full identity parity.
There is no merge operation, participant feedback access, general
trust-evidence write path, delivery/payment/governance trust evidence, global
trust score, or publication path. The resolver and scoped identity-evidence
read cover only reviewed farmer-profile identity cases; they are not a general
trust profile or cross-location identity lookup. Existing global trust
evidence and profile views are not exposed by the Kernel API. The new tables do not yet have forced RLS;
runtime/directus ACLs and bounded signed functions are the current boundary.
Live OIDC/browser checks, populated fixture parity, consent withdrawal
disposition after a completed review, all remaining source types, and
MAN-CAP-025 acceptance remain open.

## Verification and rollback

The Python services validate identifiers, enums, confidence, and keyset cursors
before opening a connection. They set signed scope and call bounded database
functions in the same transaction; read projections use `STABLE` SQL functions
and fixed parameterized `SELECT` statements. Focused tests cover exact Gateway
policies, request shape, bounded pagination, transaction ordering, and the
absence of raw feedback fields. A disposable PostgreSQL 16 fixture applies
migration 446 and exercises location/grant checks under a synthetic tenant
context, direct-table denial, independent review, decision retries/collisions,
consent withdrawal concealment, and immutable decisions. A separate
PostgreSQL 16 replay applies migrations 446–448, then verifies that the trust
projection returns only approved identity evidence; missing grants and
location mismatch deny access; direct runtime table reads remain denied; and
withdrawn consent or a private canonical identity suppresses evidence. The
resolution acceptance also proves distinct-grant enforcement, stale-consent
and legacy-conflict suppression, and the minimal canonical-party response.
Neither path reads the legacy global trust ledger. The existing
tenant-context checks cover the actual OIDC-session signature path.

To withdraw the feature before migration rollout, remove the Gateway
registrations/policies and routes/services as one unit. Migrations 446–448 are
additive and checksummed; if applied, do not edit or reverse them. Keep
the ledgers, ACLs, and functions in place while removing only API registration.
