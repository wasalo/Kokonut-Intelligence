# Field Collector access and consent contract

This implementation adds an additive consent and immutable-form boundary for
the Field Collector. The repository owner delegated form-policy decisions to
the implementation agent; all five built-in operational forms have source
definitions at version `1.2.0` classified `not_required`, with strict schema
allowlists. The local candidate now serves five active `1.2.0` revisions; the
immutable `1.1.0` revisions remain retired for review of known offline records.
See the
[policy decision record](mobile-form-classification-review.md) and
[candidate rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json).

## Existing identity and location boundary

- `POST /api/mobile/locations/{location_id}/enrollments` issues a short-lived,
  single-use enrollment code. With OIDC enabled, authorized operators issue it
  through the same-origin `/operator/api/mobile/locations/{location_id}/enrollments`
  action, which requires `mobile_device:enroll` for that location and CSRF.
  The operator supplies the collector attribution `user_id`; it is never
  treated as participant identity. The original `/api/mobile` route remains
  available to location-scoped Gateway capabilities and API keys.
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
external integrations. The target organization/tenant distinction, treatment
of nullable `location.organization_id`, and fail-closed RLS rollout gates are
recorded in the [tenant isolation contract](mobile-tenant-isolation.md).

## Implemented baseline — migration 381 source

The owner approved separation of collector and participant identity, the
reviewer-created location link, exact form-revision consent policy, immutable
form snapshots, and private review handling for known retired revisions.
Implementation is in source and migration 381 is applied to the local candidate.
Other deployments must use the ordered, checksummed migration workflow.

### Form revisions

- Migration 381 backfills `mobile_form_version` from `mobile_form`. A trigger
  snapshots new versions, retires the previous active revision, and prevents
  changes to revision content or reuse of a `(form_id, version)` pair.
- Editing the current `mobile_form` content or consent policy requires a new
  version. The current authoring surface remains the `mobile_form` row; the
  database trigger publishes its immutable snapshot. A policy decision must
  include reviewer, time, and non-empty evidence. The Directus-independent
  JSON-manifest CLI validates and previews revisions offline, and explicit
  publication updates only `mobile_form` so migration 381 creates its immutable
  snapshot. The OIDC console now provides source-level read-only queue and detail
  routes for synced review-required/ineligible rows. See the
  [form operations contract](mobile-form-operations.md).
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
  `not_required`, or `unclassified`. The five built-in operational forms are
  classified `not_required` at source and local candidate version `1.2.0`,
  with immutable `1.1.0` revisions retained retired; each has an explicit
  operational category, purpose, dynamic location scope, intended operator
  recipient, owner-delegated review evidence, and no participant reference.
  This decision is limited to farm operations, production, business expenses,
  ecological/operational observations, and soil measurements. It is not a legal
  determination or a general exemption for personal data.
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
- `/api/mobile/sync` validates new payloads against the exact immutable form
  revision's JSON Schema. Built-in `1.2.0` schemas reject undeclared fields and
  validate required fields, types, enums, numeric bounds, and date formats;
  error responses do not echo submitted values. Structural validation cannot
  detect sensitive content inside free text and does not inspect photo contents.
  Person-centered or sensitive records require a separate consent-required
  form and workflow.
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
  CLI. Migration 386 adds
  `farm_activity_source_eligible_for_use(source_system, source_id, source_raw,
  location_id)`, which fails closed for Field Collector lineage unless the
  exact collection, active immutable form revision, and current eligibility
  view all agree. Canonical reports, metrics, analytics, process traces, data
  quality, repository-owned dashboard queries, and exports apply this
  predicate. The repository's seeded dashboards and optional Directus weekly
  snapshot hook were updated; operator-edited dashboard SQL is not rewritten
  unless it matches the exact repository seed template and requires separate
  inventory/review. Retirement or inactivation moves
  linked collections into the existing private review queue. Ineligible
  canonical activities remain visible only through authorized operator
  lifecycle reads with an eligibility reason; edits and forward workflow
  transitions are blocked. Existing rejection/exception actions remain
  available only where their governed status preconditions allow them; this is
  not the formal retention-disposition workflow. Directus cannot express this
  cross-table predicate in its permission DSL, so its farm-activity read
  policies retain their existing location/status scopes while excluding
  Field Collector rows; those records use the scoped Gateway reads instead.
  The migration passed focused PostgreSQL 16 synthetic acceptance both with
  and without Directus installed, and the focused application/query/console
  suite passed (56 passed, 18 skipped). Migration 386 also passed the ordered,
  checksummed runner on a fresh clone of the populated archived database with
  zero pending schemas and no checksum drift. It is not deployed to the
  candidate.

### Withdrawal and retention

A withdrawal blocks new sync for a required form and makes an already accepted
row ineligible for later use through the eligibility view. The system does not
delete append-only consent or collection evidence. There is not yet a human
retention/erasure disposition workflow; that remains a release gate. Do not
describe these records as erased or resolved after a withdrawal.

The interim operating policy now treats affected records as restricted pending
human disposition and prohibits automatic purge without an accountable,
jurisdiction-aware retention owner. The generic retention sweeper explicitly
rejects/skips protected consent, collection, media, and governed activity
tables. This guard does not implement erasure; see the
[retention and disposition contract](mobile-retention-disposition.md).
An OIDC route now exposes a content-free known-lineage inventory under a
separate `mobile_collection_retention:inventory` location grant. It is read-only
and does not close a disposition case; downstream reports, exports, and backups
still need reconciliation.

## Remaining policy and operational gates

1. Candidate migrations 380 and 381 and the curated form seed are applied; five
   active `1.2.0` revisions now reject undeclared fields. The immutable `1.1.0`
   revisions remain retired. The pre-rollout candidate had no form or
   collection rows; on other populated databases, backfilled `1.0.0` revisions
   remain unclassified and legacy collection rows remain unassessed. Isolated
   HTTP checks now cover trusted enrollment, form listing, private media upload,
   and sync. A service worker adds an offline app shell while keeping form/API
   responses and writes network-only. Still complete real-browser offline
   capture/reconnection, retired and consent-required withdrawal cases, and
   downstream human disposition before treating CAP-053 as accepted.
2. Implement the documented organization-wide tenant model and database RLS.
   Location is the scope for this mobile API only; locations must not be treated
   as interchangeable tenant IDs. Reconcile nullable/conflicting ownership
   before tenant enforcement, and do not infer owner access from
   `organization_member` relationships ([tenant contract](mobile-tenant-isolation.md)).
3. Implement a human disposition case workflow for participant-linked records
   after withdrawal and for operational records generally. The interim decision,
   evidence, dual-control, and lineage requirements are defined in the
   [retention contract](mobile-retention-disposition.md); accountable retention
   periods and the reviewed executor remain open.
4. Manifest validation/publication and the OIDC-scoped queue/detail routes are
   implemented in source under the [form operations contract](mobile-form-operations.md).
   Disposable publication and migration-trigger checks and focused source tests
   passed. Real-provider, browser, full migration, and live grant acceptance remain open.
5. Append-only reviewer notes are implemented in migration 382 and the OIDC console.
   The `review` action also requires `read_detail`; notes cannot override consent
   eligibility or publish records. Isolated PostGIS and focused route/auth checks passed.
6. Schema validation is implemented, focused-tested, and deployed on the local
   candidate. The rollout changed five form revisions and recreated only the
   app container after a fresh encrypted checkpoint and isolated restore
   rehearsal. The legacy project remains stopped and unchanged.

## OIDC operator enrollment surface

The OIDC operator console includes a source-level enrollment form for operators
with a location-specific `mobile_device:enroll` grant. It asks for a collector
attribution ID and a bounded code lifetime, then calls the same enrollment
handler through `/operator/api/mobile/locations/{location_id}/enrollments`.
The response is `no-store`; the plaintext code is displayed once for handoff.
The handler records the authenticated operator as `created_by`. The existing
`/api/mobile` endpoint remains available to scoped Gateway capabilities and
API keys.

The session and CSRF cookies remain scoped to `/operator`, so these browser
routes are under that path and retain same-origin double-submit CSRF checks.
Equivalent location-scoped OIDC wrappers exist for revoking unused codes and
active devices. The routes and console are source implementation only; no real
OIDC provider has been configured and no live operator-to-device workflow has
been accepted.

## OIDC Field Collector review queue

The optional console provides location-scoped read-only routes for synced
Field Collector rows that have `form_review_required` or fail
`v_mobile_collection_use_eligibility`. `mobile_collection_review:read` lists
bounded summaries; those rows omit payload, participant link, device ID, and
collector ID. The selected payload route requires a separate
`mobile_collection_review:read_detail` grant, repeats the grant check in SQL,
and refuses payloads larger than 512 KiB. It returns the immutable form
revision, consent state, eligibility reason, timestamps, and JSON payload, but
only a count for private photo references. It has no media download action.
The console also appends bounded reviewer notes through a separate `review` grant plus `read_detail`, with CSRF and the
OIDC operator identity taken from the session. Migration 382 enforces location,
current review eligibility, evidence shape, and append-only storage. Notes
cannot alter the eligibility view or governed lifecycle. Gateway audit records
identify the operator and canonical location for each request; the UI renders
returned values with `textContent`.

These routes are source implementation only. A real OIDC provider is not
configured; live grant provisioning, audit storage, location isolation against
PostgreSQL, browser payload privacy, and media privacy acceptance remain open.

## Acceptance and rollback

Focused mobile/schema checks passed (60 tests); four targeted Gateway CORS
checks passed in the previous rollout slice. The candidate now has 373 applied schema migrations through 382 with zero pending; migration 382's review-event table and two triggers are present with no events recorded. The app, database, and Metabase are healthy after an app-only rebuild ([rollout evidence](builds/2026-10-12-recovery/candidate-mobile-review-rollout.json)).
Five `1.2.0` revisions are active with `additionalProperties: false`; five
immutable `1.1.0` revisions remain retired, and no mobile collection rows were
present. The live `/api/mobile/app` route returned HTTP 200 and served all five
`1.2.0` fallback definitions. Anonymous `GET /api/mobile/forms` returned HTTP
200 with an empty list; a location query without a token and an invalid-token
request both returned HTTP 401. A separate current-image HTTP check on an
isolated database clone used a synthetic active device: an undeclared field
returned HTTP 422 without echoing its value or creating a row, and a valid
`1.2.0` field note returned HTTP 200. Follow-up checks used a scoped enrollment
route to create the device, retrieved all five forms, and synced a valid field
note; the stored record remained `transport_pending` and ineligible. A synthetic
JPEG was then uploaded through the encrypted local adapter and attached during
sync. These fixtures were removed. Source route/auth checks cover OIDC console
route policy, but no real provider or operator browser session is configured.
Still required: real-browser offline capture/reconnect, live OIDC
scope/CSRF and enrollment/revocation; exact consent at collection and sync for
active and known-retired required revisions; missing, expired, denied, and
withdrawn consent; form status/version/type/location mismatch; retired revision
review; inactive/unknown revision rejection; cross-location media; idempotent
retry after link revocation/consent withdrawal; eligibility view behavior; and
encrypted media recovery.

The offline app-shell implementation adds explicit public Gateway routes for
the worker alongside each supported mobile entry point. On secure origins, the
worker stores only the static app HTML and vault helper, updates those resources
network-first, and falls back to the cached shell for offline navigation. A
dependency-free Node worker harness verifies offline navigation, valid paired
shell caching, and rejection of unpaired/cross-origin cache requests; it also
confirms that forms and sync requests are not intercepted. The focused mobile
API and Gateway authorization suites passed 51 tests with a private temporary
audit spool. The Field Collector queue, detail, and append-only note routes pass
22 focused route/query/auth tests; Ruff and console JavaScript syntax checks
pass. Migration 382 also passed isolated PostGIS assertions; no candidate app or
database was rebuilt or changed for this source slice. These checks do not replace an actual browser airplane-mode
capture and reconnection sync run, which remains open.

The prior app image is retained as
`kokonut-kernel-candidate-app:pre-form-schema-20261012`. Do not point that older
app at the 1.2.0 database while accepting mobile sync: it predates payload
validation. Form revisions are immutable, and a retired revision cannot simply
be reactivated by reseeding. If rollback is required, pause mobile intake and
restore the encrypted pre-rollout checkpoint into a fresh database volume;
verify it before any reviewed cutover. The checkpoint is
`backups/kernel-candidate-pre-form-schema-20261012`; it covers one PostgreSQL
database only and excludes roles/grants, other databases, volumes, external
media, and provider state. Do not drop migration 381 or delete form revisions.
See the [rollout evidence](builds/2026-10-12-recovery/candidate-mobile-consent-rollout.json).

## Repository owners

- Mobile routes and sync policy: `services/mobile/api.py`
- Location-scoped route/auth policy: `services/gateway/router.py`,
  `services/gateway/operator_auth.py`, and `services/gateway/app.py`
- OIDC review reads/events: `services/gateway/operator_mobile_review.py`,
  `schemas/postgres/382_mobile_collection_review_events.sql`, and
  `apps/operator-console/index.html`
- Browser queue and participant reference input: `services/mobile/field-collector.html`
- Additive schema and triggers: `schemas/postgres/381_mobile_consent_form_revisions.sql`
- Canonical append-only consent: migrations 215, 320, and 322
- Existing participant privacy/publication guidance: `docs/field-data-collection-guide.md`
