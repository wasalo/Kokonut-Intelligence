# Traceability Kernel read contract

## Scope

The Kernel exposes two read-only operator routes for location-owned produce
batches:

- `GET /operator/api/traceability/{location_id}/batches`
- `GET /operator/api/traceability/{location_id}/batches/{batch_id}`

Both require an authenticated OIDC operator with an exact `traceability:read`
grant for the requested location. The Gateway establishes signed tenant
context on the same PostgreSQL connection before reading data. Every query is
read-only, uses a five-second statement timeout and a two-second lock timeout,
and closes by rollback/connection cleanup.

The batch page accepts only the existing lifecycle statuses. Page size is
1–50, offset is 0–10,000, and the response signals whether another page exists.
Batch detail returns at most 100 records from each related collection and
reports truncation per collection.

## Returned data

The list contains stable batch identifiers, batch number, crop/variety,
quantity/unit, harvest date, organic flag, lifecycle status, and creation
time. Detail adds:

- Custody sequence, actor types, transfer/receipt times, quantity/unit, method,
  temperature, and status.
- Quality inspection point/time, grade, scores, measurements, pass/fail, and
  review status.
- Certification type/category, issue/expiry dates, verification and chain
  flags, and status.
- Food-safety type/time, bounded measurements and checks, pass/fail, and
  review status.
- Provenance event type/time, chain-verification flag, and status.

Actor names and IDs, inspector/recorder identity, free text, GPS, vehicle IDs,
source references, evidence/document URLs, arbitrary JSON metadata, and raw
payloads are omitted. Unknown and cross-location batch IDs both return 404.
The route does not create, edit, approve, publish, verify, or attest records.

## Verification limits

Focused source tests verify exact location context, parameterized location
filters on all collections, pagination bounds, fail-closed authorization,
private-field omission, and cleanup. No migration was needed. This establishes
the initial operator read surface only; it does not establish populated-data
parity, public/community access, direct-database RLS, live OIDC acceptance, or
MAN-CAP-003 acceptance. Those remain separate review and deployment gates.
