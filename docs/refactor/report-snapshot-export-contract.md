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
| `POST /operator/api/report-exports?location_id=UUID` | `create` | Strict body `{report_snapshot_id, idempotency_key}`; returns opaque request ID and state |
| `GET /operator/api/report-exports?location_id=UUID&limit=N` | `read` | Bounded newest-first status list; never includes report payload |
| `GET /operator/api/report-exports/{request_id}?location_id=UUID` | `read` | One request's status and safe error class |
| `GET /operator/api/report-exports/{request_id}/artifact?location_id=UUID` | `download` | Completed JSON bytes only; rechecks grant and source lifecycle before storage read |

The idempotency key is scoped to the operator. Repeating the same key with the
same location and snapshot returns the existing request. Reusing it for a
different source is a conflict. The service generates the request ID and a
distinct opaque artifact ID for each worker attempt. No API accepts an output
path, storage key, arbitrary table, export format, organization ID, or caller
selected report payload.

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

The first worker uses the owner-only local artifact adapter behind
`PrivateArtifactStore`. The storage directory is dedicated, private, and
mounted only into the worker and Gateway services that need it. No HTTP static
file route is exposed. The worker is default-off and runs under an explicit
Compose profile with its own database DSN and no shared `PG_*` environment.

R2 remains a future adapter. Adding it requires a private bucket contract,
least-privilege credentials, retry/consistency tests, inventory and deletion
acceptance, and backup/retention ownership. It is not required for this local
development slice.

## Rollback

Before migration application, rollback is a source revert. After it has been
applied, do not edit or remove migration history. Disable the export feature and
Compose profile to stop request processing. Keep queue rows and files intact
until a reviewed disposition policy exists. A future rollback migration may
revoke execution and stop new requests, but must not delete request history or
artifacts automatically.
