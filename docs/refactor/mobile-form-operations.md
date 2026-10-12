# Field Collector form authoring and review operations

**Status:** Architecture decision, offline validation/preview, and transactional publication through `mobile_form` are implemented and covered by isolated source tests. Disposable-database acceptance and the private review queue remain open.

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

The first implementation should provide read-only list/detail plus audited
review events. Any decision that verifies or publishes content must use the
existing governed lifecycle and independent human boundary. A review event does
not itself publish a record.

## Retention and erasure boundary

This decision does not select a legal basis, jurisdiction, or retention period.
There is no automatic pruning of mobile collections, participant links, consent
events, or review history. A withdrawal blocks new use under the eligibility
view and opens human disposition; it does not silently erase or authorize
continued publication. Any later erase/restrict workflow needs an approved
retention schedule, a recorded request/authority, media cleanup behavior, and a
separate audit trail that preserves only the minimum evidence required by the
approved policy.

## Implementation sequence and acceptance

1. [x] Add manifest validation and preview commands with offline tests; verify
   malformed schemas, external references, policy completeness, and duplicate
   version handling. Keep database and optional-chain imports lazy for offline CLI use.
2. [x] Add explicit transactional publication via `mobile_form`, with
   independent publisher identity, expected-version/absence guards, and offline
   default preview. Twenty-nine focused CLI/schema checks pass using a fake
   transaction adapter.
3. [ ] Verify trigger-created immutable snapshots, retirement of the prior
   active revision, rollback, and preserved history against a disposable
   database before enabling operator use.
4. [ ] Add OIDC-scoped private queue list/detail routes and UI; verify location
   isolation, CSRF, audit attribution, payload minimization, and media privacy.
5. [ ] Add append-only review/disposition events; verify consent-ineligible rows
   cannot be made eligible and no action publishes without the independent
   governed lifecycle.
6. Keep tenant/RLS, legal retention periods, erasure execution, media expiry,
   and real-provider/browser acceptance open until their own evidence and human
   approvals exist.

Rollback for the authoring path is to disable the CLI publication command and
retain the database snapshots. Rollback for the queue is to disable its routes
and UI while preserving review events and the existing eligibility view.
