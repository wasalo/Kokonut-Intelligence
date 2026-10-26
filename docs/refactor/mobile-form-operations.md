# Field Collector form authoring and review operations

**Status:** Manifest validation/publication, the OIDC-scoped Field Collector queue, append-only reviewer notes, and a separate-grant read-only disposition inventory are implemented in source. Publication passed trigger-focused disposable PostGIS acceptance; queue/review route and query tests pass; migration 382 and the actual Gateway service functions passed isolated PostGIS checks. The inventory's focused authorization/query/console acceptance is pending. The complete 373-file ordered schema replay through migration 382 passed on a clean disposable PostGIS database; migration 382 is applied to the candidate and its app health/auth gates pass; real-provider/browser acceptance and human disposition remain open.

**Decision date:** 12 October 2026.

## Decision

Kokonut needs a lightweight, Directus-independent authoring path for immutable
Field Collector form revisions. Use a JSON manifest and a local CLI for schema
validation, preview, and explicitly applied publication. Directus may offer an
optional convenience UI, but it is not a runtime or publishing dependency.

Kokonut also needs a private, location-scoped review queue before retired or
otherwise review-required submissions can be handled operationally. The queue
is a separate operator capability; it must not turn consent, transport, or
semantic review into one overloaded status.

This decision keeps form structure configurable while preserving the current
PostgreSQL model as the canonical runtime source. The existing `mobile_form`
row remains the publication input. Its migration 381 trigger creates the
immutable `mobile_form_version` snapshot and retires the previous active
revision. The CLI must publish through that existing boundary rather than write
to `mobile_form_version` directly.

## Authoring CLI contract

The local, manifest-based interface is:

```text
python3 -m services.cli mobile-forms validate --manifest form.json
python3 -m services.cli mobile-forms preview --manifest form.json --current prior.json
python3 -m services.cli mobile-forms publish --manifest form.json
python3 -m services.cli mobile-forms publish --manifest form.json --actor operator-id --expected-current-version 1.0.0 --apply
python3 -m services.cli mobile-forms publish --manifest form.json --actor operator-id --expect-absent --apply
```

`validate`, `preview`, and `publish` without `--apply` are read-only and make no
database connection. The unified CLI can register its command groups without
decrypting database credentials; the optional Baal adapter is loaded only when
a governance query runs. Preview can compare two manifests and rejects content
or review-metadata changes that reuse a version. Apply requires an independent
`--actor` and an optimistic concurrency assertion: `--expected-current-version
VERSION` for an update or `--expect-absent` for a new form. The implementation
must:

- require an immutable `form_id` and a new, unused semantic `version` for every
  content or policy change, and reject a stale expected version;
- validate the exact JSON Schema locally, reject remote `$ref` values, require
  the root schema to reject undeclared properties, and report errors without
  echoing submitted or personal data;
- require a reviewed `consent_policy_status`, reviewer, timestamp, and
  non-empty evidence for every publishable revision; `unclassified` revisions
  cannot become active;
- run publication as one transaction through `mobile_form`, set
  transaction-local `kokonut.actor` for the snapshot trigger, require the
  publisher to differ from the manifest reviewer, and fail closed on duplicate
  versions, location reassignment, invalid policy, or a stale preview;
- retain prior snapshots and let the database trigger retire them; no CLI
  command may edit or delete historical revision content;
- document that the local CLI is a privileged maintenance tool. Operator
  self-service through the browser requires the separate OIDC authorization
  path and location grant.

Versioned seed changes remain appropriate for built-in forms. The CLI is for
reviewable custom revisions and local operations; it must not edit an applied
migration or silently rewrite the built-in seed.

## Private review queue contract

The queue is private and location-scoped. It must derive the operator's
locations from the authenticated OIDC session and active grants; a caller
supplied location is only a filter within those grants, never an authority
source.

The first read-only source slice is implemented at
`GET /operator/api/mobile-collection-review-queue` and
`GET /operator/api/mobile-collection-review-queue/{collection_id}`. List access
uses the `mobile_collection_review:read` location grant; payload detail requires
the separate `mobile_collection_review:read_detail` grant. Both the Gateway
middleware and SQL query check the active grant. List responses omit payload,
participant linkage, device ID, and collector ID. Detail returns only a synced,
review-required/ineligible row, caps JSON payloads at 512 KiB, and exposes the
photo-reference count without bytes, object keys, or download links. The console
renders the payload as text. It also provides a bounded reviewer-note form
through `POST /operator/api/mobile-collection-review-queue/{collection_id}/events`.
That write requires both `mobile_collection_review:review` and
`mobile_collection_review:read_detail`, a valid OIDC session, and CSRF.
Migration 382 stores these notes in `mobile_collection_review_event`, with
authenticated operator, location, collection, decision, reason, evidence, and
timestamp. The table rejects update/delete, invalid evidence shape, unsynced
collections, and rows that are currently eligible and do not require review.
The event never changes collection data, consent eligibility, or lifecycle
status and cannot publish a record.

Provision these grants separately for each approved location:

```bash
python3 -m services.cli operator grant --operator-id OPERATOR_UUID --resource mobile_collection_review --action read --location-id LOCATION_UUID --granted-by PROVISIONER
python3 -m services.cli operator grant --operator-id OPERATOR_UUID --resource mobile_collection_review --action read_detail --location-id LOCATION_UUID --granted-by PROVISIONER
python3 -m services.cli operator grant --operator-id OPERATOR_UUID --resource mobile_collection_review --action review --location-id LOCATION_UUID --granted-by PROVISIONER
```

- Queue only server-synced records. Pending transport records stay in the
  transport queue and are not presented as accepted business records.
- Show the exact form revision, `eligibility_reason`, consent state, collection
  timestamp, and review state. List views should omit participant identity and
  minimize payload exposure; detail access is separately authorized and
  audited.
- Use `v_mobile_collection_use_eligibility` as a hard prerequisite for
  reporting or publication. A reviewer cannot override withdrawn, missing, or
  expired consent through a review action.
- Keep form/schema review, content/semantic review, consent eligibility, and
  governed lifecycle status as separate fields and decisions. Retired records
  remain review-required even when their consent check passed.
- Record each review/disposition as an append-only event with actor, time,
  location, collection, decision, reason, and evidence. Do not mutate the
  eligibility view or delete consent evidence to make a record appear eligible.
- Keep private media behind authenticated, scoped access. A review list must
  never return decrypted media bytes or create a public download route.

The current console slice provides list/detail reads and append-only reviewer
notes with Gateway access audit. Any decision that verifies or publishes
content must use the existing governed lifecycle and independent human
boundary. A review event does not itself publish a record.

## Retention and erasure boundary

This decision does not select a legal basis, jurisdiction, or retention period.
There is no automatic pruning of mobile collections, participant links, consent
events, or review history. A withdrawal blocks new use under the eligibility
view and requires human disposition; it does not silently erase or authorize
continued publication. A separate `mobile_collection_retention:inventory`
grant exposes known direct database lineage counts without payload, participant
IDs, or object keys. This is an assessment aid, not a case decision or proof of
complete lineage. Any later erase/restrict workflow needs an approved retention
schedule, a recorded request/authority, media cleanup behavior, downstream and
backup reconciliation, and a separate audit trail that preserves only the
minimum evidence required by the approved policy.

## Implementation sequence and acceptance

1. [x] Add manifest validation and preview commands with offline tests; verify
   malformed schemas, external references, policy completeness, and duplicate
   version handling. Keep database and optional-chain imports lazy for offline CLI use.
2. [x] Add explicit transactional publication via `mobile_form`, with
   independent publisher identity, expected-version/absence guards, and offline
   default preview. Twenty-nine focused CLI/schema checks pass using a fake
   transaction adapter.
3. [x] Verify trigger-created immutable snapshots, retirement of the prior
   active revision, rollback, duplicate/stale/location rejection, and preserved
   history against a disposable PostGIS fixture. The trigger-focused fixture
   used the migration 381 publication prefix, not the full migration or
   candidate database ([evidence](builds/2026-10-12-recovery/mobile-form-publication-transaction.json)).
4. [x] Add OIDC-scoped queue list/detail routes and console UI. List
   and payload detail use separate `read` / `read_detail` grants; SQL repeats
   location checks, lists omit identities/payloads, and detail is bounded and
   omits media bytes/links. Queue and review route/auth checks pass; Ruff and
   console JavaScript syntax checks pass.
5. [x] Add append-only review events. The separate `review` grant also requires
   `read_detail`; the API sets actor identity from the OIDC session. Migration
   382 validates review eligibility and evidence shape and blocks update/delete.
   Twenty-two focused route/query/auth tests pass; an isolated PostGIS fixture
   verified valid insertion, list/detail reads, event append/history, unchanged
   collection eligibility fields, cross-location denial, and revoked/ungranted
   operator denial for list/detail/write. No unauthorized events persisted. The
   fixture also rejected malformed evidence, unsynced collections, updates, and
   deletes. No candidate database was changed.
6. [ ] Verify real-provider grant
   provisioning, location isolation, audit attribution, browser payload
   minimization, and media privacy before operator rollout.
7. Keep tenant/RLS, legal retention periods, erasure execution, media expiry,
   and real-provider/browser acceptance open until their own evidence and human
   approvals exist.

Rollback for the authoring path is to disable the CLI publication command and
retain the database snapshots. Rollback for the queue is to disable its routes
and UI while preserving review events and the existing eligibility view.
