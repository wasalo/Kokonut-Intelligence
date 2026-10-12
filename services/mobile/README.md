# Kokonut Field Collector

The Field Collector is a dependency-free HTML companion tool for field workers.
It encrypts device credentials, settings, form cache, and offline records in
IndexedDB with a passphrase-derived AES-GCM key. Create or unlock the vault on
each browser session, and use the header lock button to clear decrypted state
from the app's active runtime. The passphrase is not stored. Legacy
`localStorage` values are removed only after their encrypted migration has been
written and verified; unreadable or failed migrations preserve the original
values.

Selected photos are resized to JPEG and kept only inside the encrypted local
queue while offline. Before collection sync, the browser uploads each photo
with its active device token and collection client ID; the server stores the
object through its configured private media provider (S3-compatible by default,
with a local encrypted provider available in the edge profile) and returns an
opaque media UUID.
`offline_collection.payload` contains form data only, while `photo_refs` stores
those UUIDs. Legacy data URLs are moved out of the payload during encrypted
queue migration. Legacy filename-only references with no image bytes remain
encrypted and are not synced automatically. Existing queue entries with more
than five photo references are marked for review before any upload begins;
they remain encrypted and are shown with remove-and-recollect guidance,
avoiding partial media uploads followed by a server-side photo-limit reject.

The vault protects stored data at rest against casual inspection of browser
storage; it does not protect decrypted data while unlocked or defend against
same-origin script compromise, malware, or a compromised browser/OS. Keep the
browser profile and synced records sensitive.

## Entry points

- Gateway (preferred): `/mobile/` or `/api/mobile/app`; `/mobile` redirects to
  `/mobile/` so relative HTML, vault, and service-worker assets stay under the
  configured proxy route.
- Caddy static route: `/field/field-collector.html`
- Directus endpoint: `/field-collector/` (redirects to the Caddy route)
- Direct file: open `field-collector.html` directly in a browser

Base Compose runs the gateway service and Caddy proxies `/mobile*` and
`/api/mobile/*` to it, so phones on the LAN can use same-origin sync without
manual Settings.

## Local network access

Replace `<lan-ip>` with the host machine's LAN address (for example
`192.168.1.42`). Dev Caddy uses an internal CA, so phones may need to accept a
self-signed certificate warning for HTTPS.

| Path | URL | Notes |
|------|-----|-------|
| Preferred (gateway via Caddy) | `https://<lan-ip>/mobile/` | HTML + `/api/mobile` same origin |
| Static HTML via Caddy | `https://<lan-ip>/field/field-collector.html` | API also same-origin via `/api/mobile/*` proxy |
| Loopback gateway | `http://127.0.0.1:8099/mobile` | Host-only; not reachable from phones |
| Direct file | `file://.../field-collector.html` | Set Settings → API URL to `https://<lan-ip>` or `http://<lan-ip>:8099` |

Start the stack with `docker compose up -d` (includes `gateway`). Host-only
fallback: `python3 -m services.gateway.cli --serve --port 8099`.

When opened directly as a file, configure the API origin in Settings before
syncing. The app does not require a connection to record data.

### Reopen the app offline

On HTTPS or localhost, the Field Collector registers a small service worker and
caches only the static HTML shell and its encryption helper for the exact app
URL. Visit the app once while online to seed that shell; the same URL can then
reopen while offline. The encrypted IndexedDB vault still requires its
passphrase after a browser restart.

The worker never caches forms, enrollment responses, sync responses, media, or
any write request. Forms remain in the encrypted vault after an online fetch,
with the built-in form definitions as a fallback. Collection records and local
photos remain encrypted in IndexedDB until sync succeeds. When connectivity
returns, the app refreshes forms and retries the queue. Browsers that cannot use
service workers (including direct `file://` use) can continue collecting while
the page stays open, but cannot use the cached app shell to reopen it offline.

## API

The browser loads `field-collector-vault.js` from the same origin as its entry
point (`/field-collector-vault.js`, `/mobile/field-collector-vault.js`,
`/api/mobile/field-collector-vault.js`, or the Caddy static `/field/` route).
The matching `field-collector-service-worker.js` aliases are served from the
same routes. The worker caches the app shell only; all `/api/mobile/*` data
requests remain network-only.

The built-in `1.2.0` farm activity, harvest, expense, field note, and soil
sample forms are classified `not_required` for participant-linked consent
because their defined purpose is location-scoped farm operations and ecological
data. This is a form-purpose decision, not a legal determination or permission
to collect personal data. Sync validates payload structure against the exact
immutable form schema; the built-in `1.2.0` schemas reject undeclared fields
and invalid values. This does not detect sensitive content inside free text or
inspect photos. Do not enter worker
identifiers, personal receipts/account details, or person-centered/sensitive
notes; use a separate consent-required workflow for participant-focused data.
The local candidate now serves the five `1.2.0` revisions and matching app.
Other environments must follow the same checksummed migration and seed
workflow. See the [policy decision record](../../docs/refactor/mobile-form-classification-review.md)
and [candidate rollout evidence](../../docs/refactor/builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json).

### Custom form manifest validation

Directus is optional. Validate a reviewed custom JSON manifest and preview its
version against a prior manifest without connecting to PostgreSQL:

```bash
python3 -m services.cli mobile-forms validate --manifest form.json
python3 -m services.cli mobile-forms preview --manifest form.json --current prior.json
python3 -m services.cli mobile-forms publish --manifest form.json
python3 -m services.cli mobile-forms publish --manifest form.json --actor operator-id --expected-current-version 1.0.0 --apply
python3 -m services.cli mobile-forms publish --manifest form.json --actor operator-id --expect-absent --apply
```

The commands reject incomplete consent review metadata, external schema
references, root schemas that accept undeclared properties, and edits that reuse
a version. Validation, preview, and `publish` without `--apply` do not connect to
PostgreSQL. Publication requires an explicit independent operator and either an
expected current version or `--expect-absent`; it updates only the mutable
`mobile_form` row so migration 381 creates the immutable snapshot and retires
the prior active revision in the same transaction. The publisher must differ
from the manifest reviewer. The CLI is a privileged local maintenance tool;
browser self-service and the OIDC-scoped private review queue remain in
progress. See the [form operations contract](../../docs/refactor/mobile-form-operations.md).

### Private media and request protections

- `POST /api/mobile/media/uploads` requires an active `X-Device-Token` and a
  `X-Collection-Client-ID`. It accepts JPEG only (signature checked, at most
  2,000,000 bytes); the app limits each record to five photos. The response
  contains only the media UUID, content type, and byte count—never an object
  key or public URL.
- `POST /api/mobile/sync` rejects inline `payload.photos`. Each UUID in
  `photo_refs` must be an unexpired upload owned by that device, location, and
  collection client ID; the API verifies object type/size before attaching it
  in the same database transaction as the collection. Retries with the same
  client ID and matching references are idempotent.
- Configure a private S3-compatible bucket through
  `MOBILE_MEDIA_S3_ENDPOINT`, `MOBILE_MEDIA_S3_BUCKET`,
  `MOBILE_MEDIA_S3_ACCESS_KEY_ID`, `MOBILE_MEDIA_S3_SECRET_ACCESS_KEY`, and
  `MOBILE_MEDIA_S3_REGION`. Leave credentials unset to fail closed and disable
  uploads. For R2, use its S3 API endpoint and the `auto` region. Do not enable
  public bucket access or expose object keys.
- The media metadata migration gives unattached uploads a 30-day expiry, and
  sync rejects expired references. Operators can preview eligible rows with
  `python3 -m services.cli mobile-media-cleanup`; deleting bytes and marking
  expired rows requires explicit `--apply` and is limited to unattached uploads.
  Attached media remains for governed retention/erasure review. Operators can
  also inventory aged, unregistered objects with
  `python3 -m services.cli mobile-media-reconcile`; this command is dry-run by
  default, has a 24-hour minimum age and a 500-object maximum batch, and reports
  counts without object keys. Add `--apply` to delete eligible objects after a
  fresh database/provider recheck. S3-compatible apply requires scoped
  `s3:ListBucket` and prefix-scoped `s3:DeleteObject`; local storage needs no
  external credentials. Apply creates no per-object restore journal, so
  configure provider versioning/backups when recovery is required. The CLI never
  mutates upload rows. Live S3/R2 inventory/deletion acceptance and production retention
  ownership remain open. No bucket or other Cloudflare resource was created in
  this repository-only work.
- Gateway request bodies are capped at 2 MB for media uploads and 8 MB for
  other write requests. CORS is closed by default: set `CORS_ORIGIN` to an
  explicit comma-separated list of trusted browser origins; wildcard origins
  are ignored. Same-origin `/mobile` deployments need no CORS entry. Gateway
  preflight allows the Field Collector's device, collection, form, participant,
  and timestamp headers, plus API-key/capability and CSRF headers. Credentialed
  browser requests are enabled only when the optional OIDC provider is active.
  Gateway rate-limit denials and handler outcomes use the existing audit
  service; the device token itself is not logged.

## Browser vault

- The vault uses PBKDF2-HMAC-SHA-256 (310,000 iterations) to derive a
  non-extractable AES-256-GCM key. Each state write is serialized, encrypted,
  persisted, read back, and verified before the in-memory state is advanced.
- Initial unlock imports the legacy device token, queue, forms, and settings
  keys. Legacy keys are removed only after successful encrypted persistence and
  read-back verification. A failed migration leaves legacy values untouched.
- If legacy keys appear beside an already-created encrypted vault, the app
  preserves them and warns rather than silently discarding or merging data
  across possibly different device/location identities. Arrange verified
  recovery and cleanup before sensitive reuse; the app does not import that
  second set automatically.
- Locking clears the app's decrypted state, key references, enrollment code,
  and current unsaved photo/location state. Unlocking again requires the
  passphrase. There is no server-side passphrase recovery.
- When an existing vault is locked, **Delete local vault** offers a browser
  confirmation before deleting the encrypted IndexedDB database and known
  legacy keys. If another Field Collector tab still holds the database, open
  app tabs are asked to lock and release it; close a stale tab if the browser
  continues to report deletion as blocked. This
  erases only this browser's local data and does not revoke its server-side
  device enrollment, which must be revoked separately by an authorized
  operator. Do not use local deletion as a retention or erasure decision for
  already-synced server records.
- Browser encryption is not a substitute for request authorization or
  encryption against a compromised active session. Avoid shared/untrusted
  devices and lock the vault before handing the device to someone else.

The trusted-device flow uses schema migration `357_field_collector_enrollment_hardening.sql`:

- `POST /api/mobile/locations/{location_id}/enrollments` issues a short-lived, single-use enrollment code. It requires a Gateway capability or API key scoped to `mobile_device:enroll` and that location. With OIDC enabled, the same-origin operator console provides `/operator/api/mobile/locations/{location_id}/enrollments`, which requires an OIDC session, the same location grant, and CSRF validation. The plaintext code is returned once with `Cache-Control: no-store`; only its SHA-256 hash is stored.
- `POST /api/mobile/register` requires `device_id` and `enrollment_code`. The server derives `user_id` and `location_id` from the locked enrollment claim. A conflicting `device_id` is rejected with `409`; registration cannot reassign an existing device.
- `DELETE /api/mobile/locations/{location_id}/enrollments/{enrollment_id}` revokes an unused claim. `POST /api/mobile/locations/{location_id}/devices/{device_id}/revoke` revokes an active device and clears its token hash; both require location-scoped Gateway authorization. OIDC operators use matching same-origin `/operator/api/mobile/...` routes with `mobile_device:revoke` and CSRF.
- `GET /api/mobile/forms` returns only explicitly public global forms to anonymous clients (`location_id IS NULL AND is_public = TRUE`). A device may send `X-Device-Token` for global and its server-assigned location forms; caller-supplied location queries are rejected when they do not match the device.
- `POST /api/mobile/locations/{location_id}/participants` creates a reviewer-approved opaque participant reference; `/participants/revoke` revokes it. With OIDC enabled, both routes require a location grant and CSRF validation. Otherwise they require a location-scoped Gateway capability or API key. The raw reference is returned only once; only its SHA-256 digest is stored.
- `POST /api/mobile/sync` accepts up to 50 idempotent records per request. Device identity and location are derived from the active device token. New records must match an immutable known form revision and collection type. Every `required` revision, active or known-retired, needs a matching unrevoked participant link and exact consent grant at collection and sync. Retired revisions enter private review and remain unassessed/ineligible even when consent checks pass.
- Private photo uploads carry the collection's form/version/reference/timestamp and check required consent before the Gateway reads or stores JPEG bytes. Sync checks consent again before attaching uploaded objects, including for known retired revisions.
- `GET /api/mobile/sync/status` returns device queue status.

Migration 381 adds immutable form revisions, reviewer-created participant
links, consent validation metadata, and the downstream
`v_mobile_collection_use_eligibility` gate. Migration 381 and the curated form
seed are applied to the local candidate; it has 372 applied schemas, zero
pending migrations, five active `1.2.0` forms, five retired `1.1.0` revisions,
and no mobile collection rows. The new validator is deployed in the candidate
app. A fresh encrypted checkpoint restored successfully into an isolated
template0-derived database before the seed and app rollout.
Other populated deployments must apply 381 and the curated seed in order;
legacy rows remain unassessed. The older
`services.analytics.mobile_offline` CLI stages transport rows without consent
validation; after migration 381 those rows remain unassessed and cannot pass the
eligibility view. Sixty focused mobile/schema tests passed; four targeted CORS
checks passed in the previous rollout slice. An isolated current-image HTTP
sync check returned 422 without echoing or storing an undeclared field and
accepted a valid `1.2.0` payload; its synthetic fixture was removed from the
database clone. The test bypassed the enrollment route, so the trusted
enrollment/OIDC and full mobile workflow acceptance remain open. The legacy project,
staging/production databases, and Cloudflare resources were not changed.
Registered-upload expiry cleanup passed an isolated PostgreSQL/local-media
acceptance. Provider-neutral orphan reconciliation is implemented with a
dry-run default; live S3/R2 acceptance and production retention remain open, as
does full live mobile workflow acceptance before production use.

See the implemented [`mobile access contract`](../../docs/refactor/mobile-access-contract.md)
for the full policy, review gates, and rollback. Enrollment and location binding
do not imply participant consent; the collector's string `user_id` remains
separate from the canonical participant party.
