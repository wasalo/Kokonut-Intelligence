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
object in a private S3-compatible bucket and returns an opaque media UUID.
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

- Gateway (preferred): `/mobile` or `/api/mobile/app`
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
| Preferred (gateway via Caddy) | `https://<lan-ip>/mobile` | HTML + `/api/mobile` same origin |
| Static HTML via Caddy | `https://<lan-ip>/field/field-collector.html` | API also same-origin via `/api/mobile/*` proxy |
| Loopback gateway | `http://127.0.0.1:8099/mobile` | Host-only; not reachable from phones |
| Direct file | `file://.../field-collector.html` | Set Settings → API URL to `https://<lan-ip>` or `http://<lan-ip>:8099` |

Start the stack with `docker compose up -d` (includes `gateway`). Host-only
fallback: `python3 -m services.gateway.cli --serve --port 8099`.

When opened directly as a file, configure the API origin in Settings before
syncing. The app does not require a connection to record data.

## API

The browser loads `field-collector-vault.js` from the same origin as its entry
point (`/field-collector-vault.js`, `/mobile/field-collector-vault.js`,
`/api/mobile/field-collector-vault.js`, or the Caddy static `/field/` route).

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
  sync rejects expired references. Automated deletion of expired object bytes
  is not yet implemented; storage cleanup/retention verification is a
  production gate. No bucket or other Cloudflare resource was created in this
  repository-only work.
- Gateway request bodies are capped at 2 MB for media uploads and 8 MB for
  other write requests. CORS is closed by default: set `CORS_ORIGIN` to an
  explicit comma-separated list of trusted browser origins; wildcard origins
  are ignored. Same-origin `/mobile` deployments need no CORS entry. Gateway
  rate-limit denials and handler outcomes use the existing audit service; the
  device token itself is not logged.

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
- Browser encryption is not a substitute for request authorization or
  encryption against a compromised active session. Avoid shared/untrusted
  devices and lock the vault before handing the device to someone else.

The trusted-device flow uses schema migration `357_field_collector_enrollment_hardening.sql` (not applied to any live database in this work):

- `POST /api/mobile/locations/{location_id}/enrollments` issues a short-lived, single-use enrollment code. It requires a Gateway capability or API key scoped to `mobile_device:enroll` and that location. The plaintext code is returned once; only its SHA-256 hash is stored.
- `POST /api/mobile/register` requires `device_id` and `enrollment_code`. The server derives `user_id` and `location_id` from the locked enrollment claim. A conflicting `device_id` is rejected with `409`; registration cannot reassign an existing device.
- `DELETE /api/mobile/locations/{location_id}/enrollments/{enrollment_id}` revokes an unused claim. `POST /api/mobile/locations/{location_id}/devices/{device_id}/revoke` revokes an active device and clears its token hash; both require location-scoped Gateway authorization.
- `GET /api/mobile/forms` returns only explicitly public global forms to anonymous clients (`location_id IS NULL AND is_public = TRUE`). A device may send `X-Device-Token` for global and its server-assigned location forms; caller-supplied location queries are rejected when they do not match the device.
- `POST /api/mobile/sync` accepts up to 50 idempotent records per request. Device identity and location are derived from the active device token.
- `GET /api/mobile/sync/status` returns device queue status.

Private-media upload/reference flow, request-size policy, stricter CORS, and
route-level security acceptance tests are implemented in source and locally
tested. Migrations `357_field_collector_enrollment_hardening.sql` and
`358_mobile_private_media.sql` are not applied to any live database. No live
database, Staging environment, or Cloudflare resource was changed; expired
object-byte cleanup remains open before production use.
