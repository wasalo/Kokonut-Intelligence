# Field Collector retention and withdrawal disposition

Updated: 13 October 2026. This document sets the Kernel's interim operating
policy and the implementation boundary for participant-linked collection data.
It does not set a jurisdiction-specific retention period or claim that a record
has been erased.

## Policy decision

When required consent is withdrawn after capture, the collection becomes
restricted immediately: the existing consent and eligibility checks block new
sync or later use. The record remains private and reviewable by separately
authorized operators so its dependencies can be assessed. Withdrawal alone
does not automatically delete, publish, anonymize, or otherwise change the
record.

Until an accountable owner records the applicable purpose, legal basis,
retention period, and review date for each relevant data category, the platform
must not run an automatic purge against Field Collector data. A record retained
under another basis stays ineligible for the withdrawn purpose. Retention and
permission to use are separate decisions.

Any decision that destroys or de-identifies participant-linked data requires a
documented dependency review and two distinct authorized people: one records
the proposed disposition and evidence; another approves execution. The executor
must reconcile the database, canonical records, private media, downstream
exports, and backup expiry before marking the case complete. No operator note
or consent withdrawal by itself is evidence that erasure completed.

## Data and lineage that a disposition must cover

The review must trace the collection's participant link and consent event,
payload, location/GPS fields, metadata, attached private-media objects, and any
canonical records created from the collection. For a promoted farm activity,
review `farm_activity.source_raw`, source references, lifecycle/edit events,
report snapshots, and any exported or externally anchored representation.
Follow media references into the configured local or S3-compatible provider and
record the applicable backup expiration. Never remove an on-chain proof as an
implicit side effect of a database disposition.

The current schema deliberately uses restrictive foreign keys and append-only
review/workflow evidence. In particular, `offline_collection` references its
participant link and consent events, review events reference the collection,
and promoted farm activities preserve source lineage. There is no complete
domain-specific erasure executor today. A request therefore remains open until
a future reviewed executor can remove or de-identify all in-scope data while
preserving the minimum non-identifying audit evidence and respecting governed
publication history.

## Operator outcomes

Each disposition record must name the collection and location, requester or
trigger, decision owner, second approver when needed, reason, evidence
references, effective date, and next review date. Do not copy participant
payload or direct identifiers into the audit explanation.

Allowed outcomes for the future workflow:

- **Restricted pending review:** default immediately after an applicable
  withdrawal or verified erasure request. No downstream use or publication.
- **Retain under a recorded basis:** identify the purpose, legal basis,
  accountable owner, and review/expiry date. This does not restore consent or
  unlock use for the withdrawn purpose.
- **De-identify:** execute only after lineage and re-identification review;
  verify that direct identifiers, location precision, media, derivatives, and
  recoverable copies are covered.
- **Erase:** execute only after the same lineage review and separate approval;
  record what was removed, what evidence must remain, any lawful hold, and when
  encrypted backups age out. If a hold or immutable publication prevents full
  erasure, keep the case open and record the limitation and review date.

## Enforcement boundary

The generic `data_retention_policy` sweeper is suitable only for tables whose
`deleted_at` semantics were designed for that workflow. It is not an erasure
engine for consent, private intake, participant links, media, or governed farm
activity. Those entities are now rejected by policy creation and skipped by
legacy configured sweeps with an explicit reason. No data is changed by this
guard.

The existing `v_mobile_collection_use_eligibility` remains the collection
gate. Migration 386 adds a canonical farm-activity predicate that rechecks
source lineage, the current form revision, and this view at each downstream
use. Reports, metrics, analytics, process traces, repository-owned dashboards,
and exports exclude ineligible Field Collector activities. The optional
Directus weekly snapshot hook also applies the gate. Custom or operator-edited
saved SQL needs a separate inventory and review. Operators can still see them through
authorized lifecycle reads, marked with an eligibility reason; edits and
forward transitions stop. Existing rejection/exception actions remain
available only where their governed status preconditions allow them; they do
not implement the retention-disposition case. Directus cannot express the
cross-table predicate, so its farm-activity read policies preserve their
existing scopes while excluding Field Collector rows; authorized Gateway
review reads remain available. Focused PostgreSQL 16 synthetic acceptance
passed with Directus installed and absent, and 56 focused application/query/
console tests passed (18 skipped). The full ordered migration replay passed on
a fresh populated archive clone. Migration 386 is now applied to the local
candidate after encrypted checkpoint restore parity; the app is healthy and
anonymous activity/review routes remain protected ([rollout evidence](builds/2026-10-13-recovery/candidate-farm-activity-use-gate-rollout.json)). The OIDC review queue can expose ineligible rows to a
location-scoped operator, but it is not a retention case manager and its
append-only notes do not approve destruction. A read-only inventory is now available at
`GET /operator/api/mobile-collection-review-queue/{collection_id}/disposition-inventory`
with the separate `mobile_collection_retention:inventory` location grant. It
also requires the location-scoped review-queue read grant. The inventory returns
eligibility, collection field/attachment counts, private-media
counts/bytes/statuses, canonical farm-activity counts/statuses, and review and
workflow event counts. It does not return payload values, participant IDs,
object keys, or media hashes. The scope is explicitly limited to known direct
database lineage; reports, external exports, on-chain references, and backups
still require separate reconciliation. The inventory is not a case manager and
cannot approve or execute a disposition.

Focused acceptance on 13 October 2026 passed (49 operator auth/review/console
tests; Ruff clean): service/query scope and read-only checks, both-grant route
authorization including denial when either grant is missing, no-store/audit
behavior, and console permission/rendering checks. This validates the known
direct-lineage inventory contract only; it does not establish complete lineage
or authorize retention, de-identification, or erasure.

Keep the capability partial until a disposition case, dual-control execution,
complete downstream/media/backup reconciliation, and jurisdiction-approved
retention ownership are implemented and accepted.

## Rollback

The code change only blocks new generic policies for the protected entities and
skips a pre-existing matching policy before it can inspect or update candidate
rows. It creates no retention policy and performs no deletion. Rollback is a
code revert; inspect any pre-existing policy logs before re-enabling a generic
sweep.
