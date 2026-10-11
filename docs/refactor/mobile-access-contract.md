# Field Collector access and consent contract

This contract records the current native mobile boundary and the gaps that
must close before mobile sync/media is accepted as a tenant- or consent-aware
workflow. It does not authorize a schema migration or change sync behavior.

## Current identity and location boundary

- `POST /api/mobile/locations/{location_id}/enrollments` is protected by the
  gateway's `mobile_device:enroll` policy and location scope. An authorized
  operator supplies the `user_id`; the service stores only the single-use code
  hash and its assigned location.
- `POST /api/mobile/register` locks and consumes the enrollment. The resulting
  device token is opaque; only its SHA-256 hash is stored. Device ID, user ID,
  and location ID come from the enrollment row, not registration fields.
- Every private-media upload and sync request resolves the active device token
  to the stored device/user/location. Sync rejects a mismatching request device
  ID. Collection location is server-derived. A media reference must match the
  same device, location, collection client ID, uploaded state, and unexpired
  window before it can be attached.
- `GET /api/mobile/forms` exposes only active, explicitly public global forms
  anonymously. With a device token it returns active global forms plus forms
  assigned to that device's location. A caller-supplied location must match the
  device assignment.
- The browser stores its offline queue and credentials in a passphrase-encrypted
  IndexedDB vault. Server-side media is private and provider-selected; object
  keys and public URLs are not returned.

These controls establish a **device-to-location boundary for the listed mobile
routes**. The schema has no general `tenant_id`; location is the mobile scope.
The boundary does not prove isolation for unrelated services, database roles,
RLS policies, Directus, or external integrations.

## Consent and form-validation gaps

`offline_collection` stores `device_id`, `user_id`, and `location_id`, but no
`party_id`, consent event ID, consent category, or purpose. The canonical
`stakeholder_consent` stream is party-linked and append-only; the mobile
`user_id` is a string with no enforced mapping to that party. No consent lookup
occurs before collection sync, media upload, attachment, or downstream use.
Therefore the platform must not describe generic Field Collector submissions
as consent-checked or allow a public/research/reporting consumer to infer consent
from device enrollment.

Sync accepts optional `form_id` and `form_version` and persists the submitted
`collection_type`, but current sync code does not verify that a supplied form is
active, belongs to the device's location (or is global), or matches the
collection type/version. Enrollment proves operator authorization to attach a
device to a location; it does not prove the participant's consent to collect,
share, retain, or publish a particular data category.

## Required design before enforcement changes

1. Define the participant identity link from mobile enrollment to the canonical
   `party` record, including how an authorized human confirms that link.
2. Define which mobile collection types require consent, their data category,
   purpose, recipient, scope, consent version, expiry, and withdrawal behavior.
   Device assignment and form visibility must not stand in for participant
   consent.
3. Decide whether consent is captured as an append-only `stakeholder_consent`
   event, a separately reviewed form response linked to that event, or both.
   Preserve evidence and human review for any publication transition.
4. Define form submission rules: required versus optional `form_id`, accepted
   active version, location/global scope, collection-type match, and safe
   handling of offline records collected before a form is retired.
5. Specify tenant policy for database and service access. If location is the
   tenant boundary for a profile, document that mapping; if an organization can
   span locations, do not treat location IDs as interchangeable tenant IDs.
6. Add reversible migrations and guarded runtime checks only after these
   contracts are approved. Keep legacy offline records readable and do not
   silently relabel them with consent or tenant state.

## Acceptance and rollback

Acceptance must cover anonymous/public form visibility, enrolled-device
location filtering, form status/version/type mismatches, missing and withdrawn
consent for required collection types, device revocation, cross-location
uploads/references, idempotent offline retries, and recovery of encrypted media
with the correct key. Compare the effective consent result with the canonical
append-only ledger and verify that no private fields appear in public output.
No test suite or runtime probe was run for this source review.

Until the policy is implemented and verified, retain the current route and schema
behavior behind the existing candidate/mobile opt-in. Roll back by removing the
mobile profile or deploying the preceding API image; preserve local encrypted
objects, their key, and database references. Do not prune media during rollback.

## Repository owners

- Routes and device binding: `services/mobile/api.py`
- Gateway resource/action/location policy: `services/gateway/router.py` and
  `services/gateway/auth.py`
- Browser queue/vault: `services/mobile/field-collector.html` and
  `services/mobile/field-collector-vault.js`
- Device, collection, form and media schema: migrations 139, 357 and 358
- Canonical stakeholder consent: migrations 215, 320 and 322
- Existing collection consent/publication caveats:
  `docs/field-data-collection-guide.md`
