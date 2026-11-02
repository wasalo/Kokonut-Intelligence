# Report Snapshot Export Contract

**Status:** implementation contract for the first C2 export slice
**Audience:** operators with explicit, tenant-qualified location grants
**Scope:** private JSON export of an existing verified or published report snapshot

This contract connects the private artifact store and report-snapshot serializer
to a durable request lifecycle. It does not define general-purpose table export,
public downloads, stakeholder sharing, PDF rendering, or R2 delivery. Those
remain separate capability and access decisions.

## Authorization and scope

The first delivery audience is the signed-in operator who requested the export.
The operator must have a current, organization-qualified grant at the exact
location. The three actions are independent:

| Action | Use |
| --- | --- |
| `report_snapshot_export:create` | Request an export of one report snapshot |
| `report_snapshot_export:read` | Read request status and bounded history |
| `report_snapshot_export:download` | Fetch completed artifact bytes |

The operator console preserves this split. A read grant lists eligible
snapshots and request status. Create controls appear only when the same
location has a create grant; download controls appear only for completed
requests when the location has a download grant. One action does not imply
another through the UI or Gateway. Eligible source snapshots are shared among
operators with the location read grant, while request status, detail, and
artifact access are restricted to the operator who created each request.

Gateway handlers establish `set_operator_tenant_context()` on the same database
connection and transaction as the bounded database function. Legacy
location-only grants fail closed. The database rechecks the exact grant,
organization membership, current owner/share state, exact location, and source
lifecycle. The browser does not provide tenant or organization identifiers.

The tenant-context setter locks the current session, identity, location,
ownership, membership, and grant rows with `FOR SHARE` so authorization changes
serialize with an active request. PostgreSQL rejects those row locks in a
read-only transaction, so the Gateway keeps a normal transaction for these
reads and calls only the fixed, bounded `SECURITY DEFINER` read functions after
the signed context is established. The export request and attempt tables deny
direct access to both the runtime and Directus roles; the routes do not issue
table writes.

The worker has a dedicated database login and may call only its bounded claim,
source-read, and finish functions. It processes a request only while the
requester's current create grant and the source's verified/published lifecycle
remain valid. It cannot read `file_url`, access arbitrary tables through its
login, or return storage paths or URLs.

## HTTP contract

All routes are private, cookie-authenticated, CSRF-protected for writes, and
return `Cache-Control: no-store` and `Vary: Cookie` where applicable.

| Method and path | Grant | Contract |
| --- | --- | --- |
| `GET /operator/api/report-export-snapshots?location_id=UUID&limit=N&offset=N` | `read` | Bounded page of exact-location verified/published snapshots with a valid SHA-256 digest and export-size-compatible JSON object; omits report payload and storage metadata |
| `POST /operator/api/report-exports?location_id=UUID` | `create` | Strict body `{report_snapshot_id, idempotency_key}`; returns opaque request ID and state |
| `GET /operator/api/report-exports?location_id=UUID&limit=N` | `read` | Bounded newest-first status list for the signed-in requester; never includes report payload |
| `GET /operator/api/report-exports/{request_id}?location_id=UUID` | `read` | The requester's status and safe error class only |
| `GET /operator/api/report-exports/{request_id}/artifact?location_id=UUID` | `download` | Completed JSON bytes only; requires the original requester and rechecks grants and source lifecycle before storage read |

The idempotency key is scoped to the operator. Repeating the same key with the
same location and snapshot returns the existing request. Reusing it for a
different source is a conflict. The service generates the request ID and a
distinct opaque artifact ID for each worker attempt. No API accepts an output
path, storage key, arbitrary table, export format, organization ID, or caller
selected report payload.

The console uses a per-location/per-snapshot `sessionStorage` idempotency key
and retains it when a POST response is uncertain, so retrying cannot create a
second request. It polls pending, processing, and retryable requests at a
bounded interval, renders only fixed metadata with text nodes, and downloads
private bytes only for completed requests. Candidate pages stop at offset
5,000; report payloads are never rendered into the page.

The serializer exports only `report_data`, verifies the canonical snapshot
hash, requires exact non-null location scope and `verified` or `published`
status, and enforces the 512 KiB payload limit. `file_url` is ignored.

## Durable worker lifecycle

```text
pending -> processing -> completed
                     \-> retryable -> processing
                     \-> dead_letter
```

Claims use `FOR UPDATE SKIP LOCKED`, a bounded batch, a worker ID, a random
lease token, and an expiry. A stale or expired worker cannot complete a newer
lease. Attempts are bounded at eight; retries use a bounded delay and retain a
safe error class rather than exception text or report contents. Dead letters
remain private for explicit review. No request, attempt, or artifact is
automatically pruned while retention and legal-hold policy is being designed.

The worker creates an attempt-specific UUID artifact, writes it atomically to
the private store, then records its digest and size through the finish
function. If finish definitively reports a lost lease, that attempt's unlinked
artifact may be removed. If the database outcome is ambiguous, the worker must
not delete the artifact because the completion may have committed; it remains
an inaccessible orphan for later reconciliation.

## Storage and deployment boundary

The worker and Gateway use the provider-neutral `PrivateArtifactStore` port.
Local storage remains the default and uses an owner-only directory mounted
read/write for the worker and read-only for the Gateway. An optional S3
compatible adapter supports private R2 buckets under
`private/report-snapshot-exports/`; only UUID-derived keys are accepted, reads
are streamed under the database-authorized size limit, and no public ACL or
URL is created. The adapter is lazy-loaded from the optional exports
dependency group.

The S3 adapter uses separate credentials: the Gateway reader needs only
`GetObject`, and the worker needs `PutObject` plus `DeleteObject` for an
explicitly rejected lease. Neither role needs `ListBucket`. HTTPS, a private
bucket, explicit bucket selection, and encrypted secret provisioning are
required. The worker remains default-off under its explicit Compose profile,
with its own database DSN and no shared `PG_*` environment. This code-level
adapter and mock coverage do not establish live R2 connectivity, access-policy
correctness, listing, deletion, backup, or retention acceptance.

## Rollback

Before migration application, rollback is a source revert. After it has been
applied, do not edit or remove migration history. Disable the export feature and
Compose profile to stop request processing. Keep queue rows and files intact
until a reviewed disposition policy exists. A future rollback migration may
revoke execution and stop new requests, but must not delete request history or
artifacts automatically.

Migration 684 adds only the bounded eligible-snapshot projection used by the
console. It is additive and runs after migration 683. Disposable PostgreSQL 16
acceptance covers apply/replay, location and read-grant separation, lifecycle,
hash/size filtering, pagination, and role boundaries. The candidate and legacy
databases remain untouched; live OIDC, browser acceptance, populated-data
review, and candidate rollout are still separate gates.
