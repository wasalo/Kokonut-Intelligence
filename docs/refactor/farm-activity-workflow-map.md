# Farm activity workflow map

Status: source map, declarative workflow correction, private queue/detail,
canonical draft promotion, governed lifecycle transitions, the published-only
farm summary, and rework-metric provenance are implemented on the feature
branch. Migrations 383–384 and the transition routes pass focused tests and
disposable PostgreSQL acceptance. Eleven report/metric tests and a minimal
synthetic-schema PostGIS check also pass. The feature has not been deployed to
the candidate; full-schema parity and MAN-CAP-001 acceptance remain open.

This map selects the current `farm_activity_v1` Field Collector form as the
first Batch 3 vertical slice. It records existing behavior, the native Kernel
implementation, and remaining acceptance gaps. It does not change runtime
behavior or move existing data.

## Current source path

```text
Field Collector (encrypted local queue)
        │ POST /mobile/sync (device token, exact form revision)
        ▼
offline_collection + mobile_media_upload
        │ eligibility view: transport / immutable form / consent policy
        ▼
OIDC location-scoped review queue and append-only reviewer notes
        │
        ├── private farm-activity intake queue/detail (OIDC, location grants)
        │       └── explicit reviewed promotion → farm_activity draft
        │
        ▼
farm_activity (canonical governed record; currently populated by other paths)
        │ OIDC-scoped submit / verify / reject / rework / publish / close-exception
        │ append-only farm_activity_workflow_event + lifecycle_transition ledger
        ▼
draft metric_value / governed report_snapshot draft
```

### Implemented behavior

* `schemas/seeds/140_mobile_forms.sql` seeds `farm_activity_v1` 1.2.0 as an
  active `farm_activity` collection. The schema requires `activity_type` and
  `activity_date`; allows optional `description`, nonnegative `labor_hours`,
  and `notes`; rejects undeclared fields. Its form copy says not to collect
  worker names or person-specific evaluations.
* `services/mobile/api.py::sync_collections` derives location from the enrolled
  device, resolves the exact immutable form revision, validates its JSON
  Schema, checks any participant policy, and inserts an idempotent
  `offline_collection` row. An active `not_required` form is recorded as
  `consent_validation_status='not_required'` and does not require the
  participant link. The row remains separate from `farm_activity`.
* Migration 381's `v_mobile_collection_use_eligibility` reports this active
  `not_required` row as eligible for use when transport and form checks pass.
  That view evaluates form revision and participant-consent eligibility; it
  does not check whether free text is accurate, safe, or approved for public
  reporting. `eligible_for_use=true` is therefore not a semantic review,
  verification, or publication decision.
* `services/gateway/operator_mobile_review.py` provides location-scoped queue
  and bounded detail reads plus append-only reviewer events. It intentionally
  does not mutate collection eligibility, promote records, or publish content.
  The current queue is aimed at form/consent review; the new farm-activity
  intake path is a separate route and service.
* The current feature branch adds `services/gateway/farm_activity_workflow.py`
  and OIDC routes for `GET /operator/api/farm-activity-intake-queue`, scoped
  detail, and `POST /operator/api/farm-activity-intake-queue/{id}/draft`.
  The queue and detail readers require the active immutable 1.2.0 revision and
  its `not_required` policy; retired captures remain in the private mobile
  review queue rather than this promotion queue. Queue results omit free text;
  detail requires both
  `farm_activity:read_detail` and `mobile_collection_review:read_detail`, is
  capped at 512 KiB, and is sent with `Cache-Control: no-store`. Promotion
  requires CSRF, both `farm_activity:create_draft` and
  `mobile_collection_review:read_detail`, and the exact body
  `{"content_reviewed": true}`. Middleware also requires a valid OIDC session
  and the location-scoped grants.
* Promotion locks and rechecks the source row and exact active form revision,
  then holds locks on any participant link and both active database grants
  through commit. Concurrent participant or grant revocation waits for the
  promotion to finish; a revocation that wins first makes the promotion fail.
  Form validation, consent eligibility, and sync state are also rechecked.
  It validates the stored payload against that immutable form schema, derives
  location from the collection, and maps only `activity_type`, `activity_date`,
  `description`, `labor_hours`, and `notes`. It creates a private canonical
  `draft`, keeps participant/device identity separate from the OIDC operator,
  and stores only form/version, source collection ID, and payload digest in
  `source_raw`. An identical retry returns the same canonical row; a
  source/location/digest mismatch fails closed.
* Additive migration 383 adds a preflighted partial unique source index and an
  append-only `farm_activity_workflow_event` ledger. Its insert trigger checks
  canonical status, location and source identity; a `draft_created` event also
  requires the content-review acknowledgement and matching payload digest.
  Migration 384 scopes these lifecycle guards to `farm_activity_v1` 1.2.0 source
  rows, preserving other historical Field Collector source rows. It requires
  valid source/form lineage and active location grants for draft creation,
  appends an event atomically for every lifecycle action, blocks illegal status
  changes, and prevents edits to submitted, verified, rejected, or published
  content. Rework returns the row to draft before content can change again.
  Existing `lifecycle_transition` rows continue to be written for changed
  status values; `exception_closed` is a separate event because status stays
  rejected. These migrations and routes are not applied to the candidate.
* `schemas/postgres/003_operations.sql` defines canonical `farm_activity`
  fields, lineage fields, and lifecycle status. `services/export/
  spreadsheet_bridge.py::import_farm_activity_csv` is one existing importer;
  it creates draft rows. The feature branch now adds the first
  Field Collector-to-`farm_activity` draft adapter and location-scoped intake
  routes; governed lifecycle routes remain absent.
* Migration 179 records status changes in `lifecycle_transition` for
  `farm_activity`. It reads `kokonut.actor_id` and `kokonut.actor_type`, but
  the trigger observes status changes only; it does not enforce legal state
  transitions or require an independent reviewer. Native writes must set these
  transaction-local values or the ledger actor can be null.
* The source review found `services/workflow_specs/farm_activity.py` modeled
  rejection as terminal and publication as a system action. The declarative
  spec is now corrected: the submitter is separated from the human verifier,
  rejection offers rework or exception disposition, and publication is an
  explicit human action. Runtime authorization and database guards are still
  absent; this spec remains a declaration rather than an API enforcement layer.
* `services/metrics/calculators/{governed_lead_time,first_time_through_yield,
  rework_rate}.py` include farm activity lifecycle traces. The metrics depend
  on truthful status transitions and actor attribution. Per repository policy,
  computation must still create a draft, unverified `metric_value`; a person
  verifies it separately.
* `services/export/reports/core.py::generate_farm_summary` currently summarizes
  location/farms/plots/crop cycles, harvests, finance, expenses, and
  attestations; it does not include farm activities. `store_snapshot` creates
  an unfrozen draft `report_snapshot`; report review and publication are a
  separate lifecycle.

## Native handoff contract and remaining work

The private intake and draft portions below are implemented on the current
feature branch as described above. Lifecycle transitions and analytical
handoffs remain target contracts for the next Batch 3 slices.

### Promotion from private capture to canonical draft

1. **Implemented:** an OIDC operator with both location-scoped
   `farm_activity:read_detail` and `mobile_collection_review:read_detail`
   grants reads the synced collection. A distinct `farm_activity:create_draft`
   action promotes it; consent eligibility alone never performs this write.
2. **Implemented:** in one database transaction, the service locks and rechecks the collection,
   exact form revision, location, sync state, eligibility, and existing source
   mapping. It rejects revoked/ineligible collections and retries safely.
3. **Implemented:** the server derives `farm_activity.location_id` from the collection. It maps
   only the declared v1.2.0 fields:

   | Form payload | Canonical field | Rule |
   |---|---|---|
   | `activity_type` | `activity_type` | Preserve enum value. |
   | `activity_date` | `activity_date` | Parse as ISO date. |
   | `description` | `description` | Copy only on explicit promotion; keep in private review until approved. |
   | `labor_hours` | `labor_hours` | Preserve numeric value; never infer from a person. |
   | `notes` | `notes` | Treat as private free text; require explicit human review before publication. |
   | device-bound collection location | `location_id` | Never accept a client-supplied location. |

   The form does not supply plot, crop-cycle, labor cost, materials, or
   evidence URL fields. The adapter must leave them null/default and must not
   infer them from names or free text. Uploaded photo references remain private
   attachments to the collection until a separately reviewed attachment
   mapping is designed.
4. **Implemented:** set `status='draft'`. Preserve source lineage as
   `source_system='field_collector'`, `source_id=<offline_collection.id>`,
   `schema_version='1.2.0'`, and a minimal `source_raw` envelope containing
   form ID/version, collection ID, and payload digest. The original payload
   remains in `offline_collection`; do not duplicate private text or media in
   the lineage envelope.
5. **Implemented:** add an additive partial unique constraint/index for the adapter's stable
   `(source_system, source_id)` identity after a duplicate preflight. On retry,
   return the existing canonical row only if location and source mapping agree;
   otherwise fail closed. Preserve other importers' source-key semantics.
6. **Implemented in source:** record draft promotion and every later operator
   action in the append-only event ledger. Set the OIDC operator as the
   transaction-local actor; never treat device `user_id`, participant link, or
   OIDC `operator_id` as a `party` identity.

### Lifecycle and authorization

* Draft creation is location-scoped and never directly publishes.
* A submit action moves `draft -> submitted` after required content checks.
  Submission actor is retained so the reviewer can be required to differ.
* The native route `POST /operator/api/farm-activities/{id}/{action}` requires
  an OIDC session, CSRF validation, a location query parameter, and the exact
  action grant: `submit`, `verify`, `reject`, `rework`, `publish`, or
  `close_exception`. Each database transaction locks the canonical row and
  grant, checks the current state, applies one transition, and reads back its
  appended event. Unknown body fields are rejected. Rejection, rework, and
  exception closure require a nonblank reason of at most 2,000 characters.
* A human verifier with location-scoped `farm_activity:verify` authority moves
  `submitted -> verified`; the verifier must differ from the latest submitter.
  Rejection from submitted or verified requires a reviewer distinct from the
  latest submitter and, where present, verifier. A publisher must differ from
  both latest actors. A verified row cannot be silently edited.
* Rejection is a reasoned rework/exception state, not an unconditionally
  terminal state. `rejected -> draft` is an explicit `rework` action that
  preserves the prior rejection event. Draft content can then be corrected;
  submitted or later content is immutable. `close_exception` records a distinct
  reasoned event while leaving lifecycle status rejected. A rejected row is
  never eligible for metric/report publication.
* Publication is a separate, explicit human-controlled action with
  location-scoped `farm_activity:publish` authority. Only published records
  may enter the public farm-activity summary or the selected governed metric
  inputs. This action cannot be performed by an agent or implicit background
  process.
* Native routes use the existing operator identity provider, CSRF checks,
  route default-deny policy, and database-backed per-location grants. Grant
  absence, revocation, cross-location IDs, malformed content, concurrent
  transitions, and invalid status changes must fail closed.

### Metric and report handoff

`services/export/reports/core.py::generate_farm_summary` now adds a bounded,
location/period-filtered activity summary using only published farm activities.
It reports activity counts and reported labor hours by activity type; it omits
free text, media, participant/device identity, source lineage, and canonical
record IDs. `services/export/reports/context.py::store_snapshot` persists the
generated result through the existing SHA-256 hash path as an unfrozen `draft`.
It does not submit, verify, freeze, or publish the snapshot.

`services/metrics/calculators/rework_rate.py` includes `farm_activity` in the
published cohort. The metric counts published-in-period lifecycle entities
that have a rejection transition, uses an inclusive calendar end date, and
returns the published source cohort plus the reworked subset (each capped at
100 IDs with truncation flags). The existing metric engine stores the result
with `verified = FALSE`; human verification remains a separate action.

Do not publish notes, worker identity, private media URLs, or participant data
through the report. The form specifically prohibits worker names and
person-specific evaluations; future text review must retain that restriction.

## Implementation order and acceptance

1. **Done:** source-map this form, canonical model, lifecycle, metric, and report
   path. Checklist and CAP-001 link this map.
2. **Done:** update `services/workflow_specs/farm_activity.py` and its contract
   test so rejection offers explicit rework or exception disposition, the
   submitter and verifier are distinct by contract, and publication requires a
   human action. Runtime enforcement is implemented in source in step 4.
3. **Done for draft promotion:** `services/gateway/farm_activity_workflow.py`
   implements private collection reads and canonical draft creation with
   strict scope, exact-revision, idempotency, source-lineage, and transaction-
   local actor handling. The Gateway route is implemented in
   `services/gateway/operator_auth.py`.
4. **Implemented in source:** add explicit submit/reject/rework/verify/publish/
   exception-close transitions through the native Gateway route policy and
   operator grants; preserve operator-attributed state-transition evidence.
5. **Implemented in source:** add the published-only farm activity summary and
   connect its generated output to the existing hashed draft snapshot path;
   include farm activities in the provenance-bearing `rework_rate_pct` draft
   calculation. Synthetic fixture expectations and privacy exclusions are
   recorded in [report/metric evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json).
6. **Partial verification complete:** 77 tests across migration, workflow,
   lifecycle service, and OIDC suites pass; Ruff passes. Migrations 383–384
   compiled transactionally in a disposable PostgreSQL database. Synthetic
   rows accepted draft creation, submit, independent verify, reject, rework,
   resubmit, publish, and same-status exception closure; guards rejected a
   missing draft event, self-verification, rejection by the submitter or
   verifier, missing reason, revoked grant, invalid transition, post-submit
   content edit, and event update/delete. A legacy Field Collector row using a
   different form version remained outside the new guard. Separately, 11
   focused report/metric tests and Ruff pass, covering synthetic published-only
   aggregates, private-field exclusion, period bounds, report hash/draft state,
   source/rework provenance, array-literal normalization, and the existing
   unverified metric insert rule. A disposable PostGIS 16 run with minimal
   synthetic schema and rows also verified the real report query, report hash /
   draft insert, metric result, both source IDs, reworked source, and unverified
   metric insert. This does not establish parity against the full migration
   chain. The scratch database is removed and the candidate remains unchanged
   ([lifecycle evidence](builds/2026-10-12-recovery/farm-activity-lifecycle-isolated.json),
   [report/metric evidence](builds/2026-10-12-recovery/farm-activity-report-metric-contract.json)). Remaining checks include
   duplicate promotion, stale/ineligible source, wrong-location read/write,
   route-level OIDC against a configured provider, rollback under injected DB
   failure, full-schema report/metric parity, and candidate rollout. These
   migrations and routes are not deployed to the candidate.

Rollback uses additive migrations, the existing OIDC session and default-deny
location grants, and preservation of `offline_collection` as the source record.
The feature is not deployed, so no rollback action is needed now. After
deployment, a route rollback must pause native intake and retain a compatible
transition path for native 1.2.0 rows; migration 384 guards intentionally stay
active and must not be bypassed through Directus. Keep the additive index and
event history. A failed promotion or transition rolls back the canonical write
and its event together. If a draft is incorrect, use the governed rework path;
do not delete it or rewrite the captured source.

## Files in scope for the next implementation slices

* `services/workflow_specs/farm_activity.py` and workflow contract tests.
* `services/gateway/operator_auth.py`, `services/gateway/router.py`,
  `services/gateway/app.py`, plus a focused farm-activity service module and
  auth/route tests.
* Additive `schemas/postgres/` migration for source idempotency and any required
  transition/audit constraints; never edit an applied migration.
* `services/mobile/api.py` only if a reusable transaction contract is needed;
  sync should remain private intake, not silent canonical promotion.
* `services/metrics/calculators/` and `services/export/reports/core.py` for the
  published-only metric/report parity slice.
* `docs/refactor/batches.md`, `docs/refactor/capability-matrix.md`, and
  `docs/refactor/progress.md` at every implementation checkpoint.

