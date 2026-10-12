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

## Proposed implementation baseline — review required

This proposal is deliberately not enforced yet. It follows the existing
append-only consent ledger and preserves the offline queue, while leaving
participant identity and consent decisions under human control.

1. Treat `mobile_device.user_id` only as the collector/operator identity. Never
   infer the participant from enrollment or accept a participant `party_id`
   directly from the mobile request. Add a location-scoped opaque
   `participant_ref` mapped to a canonical `party_id` in a restricted
   `mobile_participant_link` table. An authorized reviewer creates or revokes
   that mapping and the record retains reviewer, time, scope, and evidence.
2. Keep consent events in `stakeholder_consent`; the mobile collector must not
   mint a grant from an operator checkbox. A form revision declares its
   collection type, data category, purpose, consent version, scope, recipient,
   and whether a participant grant is required. A required policy fails closed
   if the participant reference, verified mapping, or exact effective grant is
   absent. Check both that consent covered `collected_at` and that it has not
   since been withdrawn, denied, or expired when the server receives the sync.
3. Keep immutable `mobile_form_version` records keyed by `(form_id, version)`;
   `/forms` lists only active revisions. Sync requires the exact known form
   revision and matching collection type and location/global scope. Known
   retired revisions remain acceptable into the private, pending queue so an
   offline device does not lose work; mark them for review, and never treat a
   retired revision as active or consented. Unknown revisions and mismatches
   fail closed. Legacy rows remain unvalidated and receive no inferred consent.
4. A withdrawal after server acceptance blocks new use and publication. Do not
   automatically erase an append-only consent event or collected evidence;
   require an explicit human disposition for retention or erasure. The
   governing retention rule for that disposition still needs owner approval.
5. Implement this as an additive migration and explicit mobile API policy. Keep
   `sync_status` for delivery state; store form and consent validation separately
   so domain review state is not overloaded into transport status. Rollback
   disables the new policy and restores the previous API image without deleting
   historical forms, collections, consent events, or media.

The first implementation slice would add the version and participant-link
tables, nullable references/status fields on new collections, and a policy
lookup in `services/mobile/api.py`. It would preserve the current `mobile_form`
row as the active-form listing surface during migration. No migration, route,
form, consent, or sync behavior has changed; approval is required before that
slice is implemented. The exact retention/erasure disposition after withdrawal
also needs confirmation.

## Owner decisions before enforcement changes

1. Approve or revise the separation between collector `user_id` and the
   participant link, plus who can verify/revoke that location-scoped mapping.
2. Classify each current form's collection type, data category, purpose,
   recipient, scope, consent version, expiry, and whether a participant grant is
   required. Device assignment and form visibility never substitute for consent.
3. Confirm that grants continue to come from the append-only
   `stakeholder_consent` process, not a collector checkbox; approve the check at
   collection and sync time and the human retention/erasure disposition after
   withdrawal.
4. Approve immutable form revisions and the proposed handling of unknown,
   mismatched, retired, and missing form/version references in offline sync.
5. Specify tenant policy for database and service access. If location is the
   tenant boundary for a profile, document that mapping; if an organization can
   span locations, do not treat location IDs as interchangeable tenant IDs.
6. Authorize an additive migration and guarded runtime checks after the policy
   is approved. Keep legacy offline records readable and do not silently relabel
   them with consent or tenant state.

## Acceptance and rollback

Acceptance must cover anonymous/public form visibility, enrolled-device
location filtering, collector/participant mismatch, unauthorized party-link
creation, form status/version/type/location mismatches, historical revisions,
missing and withdrawn consent for required collection types, consent that was
not effective at collection time, device revocation, cross-location
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
