# Farm activity workflow map

Status: source map and declarative workflow correction complete; native write
and review flow not implemented.

This map selects the current `farm_activity_v1` Field Collector form as the
first Batch 3 vertical slice. It records what the repository does today and
defines the handoffs the native Kernel path must provide. It does not change
runtime behavior or move existing data.

## Current source path

```text
Field Collector (encrypted local queue)
        │ POST /mobile/sync (device token, exact form revision)
        ▼
offline_collection + mobile_media_upload
        │ eligibility view: transport / immutable form / consent policy
        ▼
OIDC location-scoped review queue and append-only reviewer notes
        │  [no farm_activity promotion route exists]
        ▼
farm_activity (canonical governed record; currently populated by other paths)
        │ lifecycle_transition ledger
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
  The current queue is aimed at form/consent review and does not implement the
  `farm_activity` workflow.
* `schemas/postgres/003_operations.sql` defines canonical `farm_activity`
  fields, lineage fields, and lifecycle status. `services/export/
  spreadsheet_bridge.py::import_farm_activity_csv` is one existing importer;
  it creates draft rows. No Field Collector-to-`farm_activity` adapter or
  location-scoped native farm-activity write/review route is present.
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

## Proposed native handoff contract

These are the implementation boundaries for the next Batch 3 slices. Names
below describe the intended contract; routes and services are not yet present.

### Promotion from private capture to canonical draft

1. An OIDC operator with a location-scoped `mobile_collection_review:read_detail`
   grant reads the synced collection. A distinct explicit action (proposed
   grant `farm_activity:create_draft`) promotes it; consent eligibility alone
   never performs this write.
2. In one database transaction, the service locks and rechecks the collection,
   exact form revision, location, sync state, eligibility, and existing source
   mapping. It rejects revoked/ineligible collections and retries safely.
3. The server derives `farm_activity.location_id` from the collection. It maps
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
4. Set `status='draft'`. Preserve source lineage as
   `source_system='field_collector'`, `source_id=<offline_collection.id>`,
   `schema_version='1.2.0'`, and a minimal `source_raw` envelope containing
   form ID/version, collection ID, and payload digest. The original payload
   remains in `offline_collection`; do not duplicate private text or media in
   the lineage envelope.
5. Add an additive partial unique constraint/index for the adapter's stable
   `(source_system, source_id)` identity after a duplicate preflight. On retry,
   return the existing canonical row only if location and source mapping agree;
   otherwise fail closed. Preserve other importers' source-key semantics.
6. Record collection promotion and operator action in an append-only audit
   event. Set transaction-local lifecycle actor context before status changes.
   Do not treat the Field Collector device `user_id`, participant link, or OIDC
   `operator_id` as a `party` identity. Keep operator identity in the operator
   audit/lifecycle actor fields and retain their distinct semantics.

### Lifecycle and authorization

* Draft creation is location-scoped and never directly publishes.
* A submit action moves `draft -> submitted` after required content checks.
  Submission actor is retained so the reviewer can be required to differ.
* A human verifier with location-scoped `farm_activity:verify` authority moves
  `submitted -> verified` or rejects with a reason. The verifier must differ
  from the submitter. A verified row may still be edited only by returning it
  to a reviewable state with an audit entry; silent edits are prohibited.
* Rejection is a reasoned rework/exception state, not an unconditionally
  terminal state. The workflow spec and guards must define an explicit
  `rejected -> draft` correction path while preserving the rejection event.
  A rejected row is never eligible for metric/report publication.
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

The first parity slice should add a bounded, location/period-filtered activity
summary to `generate_farm_summary`, using only published farm activities and
explicit units/counts. `store_snapshot` should persist the result as a draft
report with its canonical report hash. It must not auto-submit, verify, freeze,
or publish the snapshot. A selected activity metric may be computed from the
same published fixture only if its calculation and source IDs are explicit;
the result stays draft and needs a separate human `--verify-value` action.

Do not publish notes, worker identity, private media URLs, or participant data
through the report. The form specifically prohibits worker names and
person-specific evaluations; future text review must retain that restriction.

## Implementation order and acceptance

1. **Done:** source-map this form, canonical model, lifecycle, metric, and report
   path. Checklist and CAP-001 link this map.
2. **Done:** update `services/workflow_specs/farm_activity.py` and its contract
   test so rejection offers explicit rework or exception disposition, the
   submitter and verifier are distinct by contract, and publication requires a
   human action. Runtime enforcement remains open.
3. Add a narrow service under `services/gateway/` for private collection
   promotion and canonical draft creation, with strict scope, exact-revision,
   idempotency, source-lineage, and transaction-local actor handling.
4. Add explicit submit/reject/rework/verify/publish transitions through the
   native Gateway route policy and operator grants; keep reviewer notes
   append-only and preserve state-transition evidence.
5. Add the published-only farm activity summary and one draft report/metric
   fixture with independently checked expected output.
6. Verify with disposable PostgreSQL/PostGIS state and injected failures:
   duplicate promotion, stale/ineligible collection, wrong location, grant
   denial/revocation, actor identity, reviewer independence, rejected rework,
   invalid transition, rollback, published-only projection, draft metric,
   and draft report hashing. Live OIDC/public-route acceptance remains a later
   deployment gate.

Rollback uses additive migration(s), disabled-by-default native write routes,
and preservation of `offline_collection` as the source record. If promotion or
parity fails, disable the new route and leave existing Directus/spreadsheet
paths and all source rows intact; do not delete or rewrite captured records.

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

