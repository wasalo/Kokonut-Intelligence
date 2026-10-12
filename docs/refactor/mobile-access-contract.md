# Field Collector access and consent contract

This implementation adds an additive consent and immutable-form boundary for
the Field Collector. It records the approved baseline while keeping the five
current form revisions `unclassified` until an authorized reviewer evaluates
each one. It does not imply that the migration has been applied or that mobile
acceptance has passed.

## Existing identity and location boundary

- `POST /api/mobile/locations/{location_id}/enrollments` issues a short-lived,
  single-use enrollment code. The enrolling operator supplies the collector's
  `user_id`; it is never treated as participant identity.
- `POST /api/mobile/register` locks and consumes the enrollment. The device
  token is opaque; only its SHA-256 hash is stored. Device ID, user ID, and
  location ID come from the enrollment row.
- Private-media upload and sync resolve the active device token to the stored
  device/user/location. Sync rejects a mismatching device ID and derives the
  collection location from enrollment. Media references are scoped to that
  device, location, client ID, uploaded state, and expiry.
- Anonymous `GET /api/mobile/forms` returns only active, explicitly public
  global revisions. An enrolled device receives active global revisions and
  revisions assigned to its location. A requested location must match the
  device assignment.
- The browser queue and device credentials remain in the passphrase-encrypted
  IndexedDB vault. Server-side media remains private and provider-selected.

This establishes a device-to-location boundary for these routes. The schema
does not define a general `tenant_id`; location is the mobile scope only. This
does not establish RLS or tenant isolation for other services, Directus, or
external integrations.

## Implemented baseline — migration 381 source

The owner approved separation of collector and participant identity, the
reviewer-created location link, exact form-revision consent policy, immutable
form snapshots, and private review handling for known retired revisions.
Implementation is in source; migration 381 is not applied by this change.

### Form revisions

- Migration 381 backfills `mobile_form_version` from `mobile_form`. A trigger
  snapshots new versions, retires the previous active revision, and prevents
  changes to revision content or reuse of a `(form_id, version)` pair.
- Editing the current `mobile_form` content or consent policy requires a new
  version. The current authoring surface remains the `mobile_form` row; the
  database trigger publishes its immutable snapshot. A policy decision must
  include reviewer, time, and non-empty evidence. There is not yet a dedicated
  form-authoring UI or CLI.
- `GET /api/mobile/forms` reads only active snapshots. It exposes the
  participant-required flag and the reviewed data category, purpose, recipient
  type/name, and consent version needed by the collector UI; it does not expose
  the canonical recipient party ID.
- A new sync record must name an exact known form ID/version and matching
  collection type. Its form must be global or assigned to the device location.
  Unknown revisions and mismatches fail closed. Inactive revisions reject new
  records. A known retired revision can sync only to the private pending queue
  with `retired_review` and `form_review_required`; it is not marked consented
  or eligible for use.

### Participant identity and consent

- `mobile_device.user_id` remains collector/operator identity. A mobile request
  cannot submit a canonical `party_id`.
- `POST /api/mobile/locations/{location_id}/participants` creates a
  reviewer-approved mapping to a canonical party. The API returns a random
  participant reference once and stores only its SHA-256 digest in
  `mobile_participant_link`. The link records location, creator, time, and
  evidence. `POST /api/mobile/locations/{location_id}/participants/revoke`
  revokes a reference without deleting the mapping.
- These routes are protected by location-scoped `mobile_participant:create` or
  `mobile_participant:revoke`. With OIDC enabled, they require a browser session,
  matching operator location grant, and CSRF validation. With OIDC disabled,
  the existing Gateway API key/capability policy applies. Neither route is
  public, and the collector token cannot manage links.
- A form revision has one of three consent classifications: `required`,
  `not_required`, or `unclassified`. The current five forms are deliberately
  `unclassified`; the approved architectural baseline did not decide their
  individual data categories, purposes, recipients, scopes, versions, or whether
  consent is required.
- A `required` form revision asks for the opaque participant reference. Sync
  resolves it within the device location, requires an unrevoked link, then
  checks the latest exact `stakeholder_consent` decision at `collected_at` and
  again at sync. The category, purpose, scope, recipient, and consent version
  must match the immutable form policy. Any intervening withdrawal, denial,
  expiry event, or grant expiry rejects the new sync, including for a known
  retired revision. The mobile operator cannot create a consent grant with a
  checkbox.
- Private-media upload carries the same client, form revision, participant
  reference, and collection timestamp. The Gateway validates the form and any
  required consent before it reads/stores the JPEG bytes; final sync checks
  consent again before attaching those objects to a collection. A retired
  revision with a required-consent policy remains review-only, but must still
  pass the same link and consent checks before its private upload or sync.
- An active `not_required` revision needs reviewer metadata and evidence and
  rejects participant references. An active `unclassified` revision remains
  collectable into the private pending queue, but is marked `unassessed` and
  review-required. It cannot be treated as consent-cleared.
- Existing collection rows receive `unassessed` defaults; the migration does
  not infer identity, consent, or form validity for legacy records.
- The legacy `services.analytics.mobile_offline` CLI is a transport/admin path,
  not a consent-aware admission path. It can stage rows and mark transport as
  synced, but after migration 381 its rows remain unassessed and fail the
  eligibility view. Do not use that transport status as permission to report
  or publish the row.
- `v_mobile_collection_use_eligibility` is the consent/form prerequisite for
  downstream use. It also requires transport status `synced`; unassessed,
  retired, and review-required rows are ineligible. A later
  withdrawal/denial/expiry makes the row ineligible permanently, including if a
  later grant is added; revoking the referenced participant link also makes the
  row ineligible. This view does not replace governed review/publication
  approval. `/api/mobile/sync` is an externally reachable, device-token
  authenticated intake route; it writes only to the private collection queue.
  The source scan found no business, reporting, or publication consumer of
  `offline_collection` outside the Field Collector API and the transport-only
  CLI. Every future downstream consumer must use this view before reporting,
  publication, or other use.

### Withdrawal and retention

A withdrawal blocks new sync for a required form and makes an already accepted
row ineligible for later use through the eligibility view. The system does not
delete append-only consent or collection evidence. There is not yet a human
retention/erasure disposition workflow; that remains a release gate. Do not
describe these records as erased or resolved after a withdrawal.

## Remaining owner decisions and operational work

1. Review and classify each of the five existing forms using the
   [source-grounded worksheet](mobile-form-classification-review.md). Until then
   they stay `unclassified`, private, and ineligible for downstream use. A
   classification change must publish a new form version with reviewer,
   timestamp, and evidence.
2. Specify organization-wide tenant policy. Location is the scope for this
   mobile API only; locations must not be treated as interchangeable tenant IDs.
3. Define the human retention/erasure disposition process after withdrawal.
4. Decide whether a form-authoring CLI/UI and a private review queue are needed
   before local or production operators classify forms and review retired rows.
5. Apply migration 381 only through the ordered, checksummed migration runner.
   This implementation has not changed the candidate database or any running
   container.

## Acceptance and rollback

Still required: anonymous and enrolled form visibility; route policy and OIDC
scope/CSRF behavior; create/revoke mapping authorization; collector/participant
separation; exact consent at collection and sync for active and known-retired
required revisions; missing, expired, denied, and withdrawn consent; form
status/version/type/location mismatch; retired revision review; inactive/unknown
revision rejection; device revocation; cross-location media; idempotent retry
after link revocation/consent withdrawal; eligibility view behavior; and
encrypted media recovery. No mobile test suite, migration, or runtime probe ran
in this implementation pass.

Migration 381 is additive. Rollback deploys the previous API image or disables
the mobile profile while retaining the new columns, revision history, link
audit, collection rows, consent events, encrypted local objects, and their key.
Do not drop migration 381 or prune media as part of application rollback.

## Repository owners

- Mobile routes and sync policy: `services/mobile/api.py`
- Location-scoped route/auth policy: `services/gateway/router.py`,
  `services/gateway/operator_auth.py`, and `services/gateway/app.py`
- Browser queue and participant reference input: `services/mobile/field-collector.html`
- Additive schema and triggers: `schemas/postgres/381_mobile_consent_form_revisions.sql`
- Canonical append-only consent: migrations 215, 320, and 322
- Existing participant privacy/publication guidance: `docs/field-data-collection-guide.md`
