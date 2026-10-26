# Dynamic retention policy and legal holds

Updated: 16 October 2026. This document defines the Kernel's configurable
retention boundary. It intentionally does not choose a retention period or
interpret legal requirements for the United States or Dominican Republic.

## Policy lifecycle

Retention windows are policy data, not application constants. A policy is
scoped by data category, entity type, optional location, and optional
owner-defined jurisdiction and purpose codes. It may have an unset
`retention_days` while it is being drafted. The migration removes the legacy
category default windows and clears those reference values. No missing period
is inferred.

Create an inert draft. The period can be omitted while the accountable owner
reviews the applicable purpose and jurisdiction; optional opaque codes can be
recorded without selecting a duration:

```bash
python3 -m services.analytics.cli_data_governance set-retention \
  --data-category soil --entity-type soil_sample \
  --jurisdiction-code us --purpose-code research \
  --policy-owner ACCOUNTABLE_OWNER \
  --actor OPERATOR --reason "Drafted for policy review"
```

These codes are normalized, owner-defined identifiers rather than an
enumerated legal registry. They have no defaults, do not validate a legal
interpretation, and do not imply a retention window. Until a reviewed resolver
maps these scopes to records, the generic sweeper skips policies containing
either code, and approval reports
`jurisdiction_purpose_scope_resolved: false`. Such a policy cannot
enable auto-enforcement. An
unscoped policy cannot be approved alongside an overlapping scoped policy.
Event cleanup also refuses to run when another active policy for `event_bus` /
`platform_event` could make its global scope ambiguous.

To prepare a fully configured draft, supply its reviewed window and action.
Approval is a separate action and records the approver, date, reason, and
policy snapshot. `--auto-enforce` is an explicit second choice; it does not
override the independent feature gate.

```bash
python3 -m services.analytics.data_governance set-retention \
  --data-category soil --entity-type soil_sample --retention-days N \
  --action soft_delete --policy-owner ACCOUNTABLE_OWNER \
  --actor OPERATOR --reason "Reviewed proposal"
python3 -m services.analytics.cli_data_governance approve-retention \
  --policy-id UUID --approved-by OPERATOR --reason "Approved schedule" \
  --auto-enforce
```

Replace an active policy by creating its successor, retiring the current
policy, then approving the successor. Overlapping active policies are rejected
or skipped as ambiguous. Retirement disables enforcement and records the
actor, reason, and policy snapshot in append-only history.

Review the current policy inventory before a change. The bounded read-only
command supports filters for status, category, jurisdiction, purpose, and
location. It returns configured windows and approval state, while omitting
free-text metadata and audit reasons:

```bash
python3 -m services.analytics.cli_data_governance retention-policies \
  --status draft --jurisdiction-code us --purpose-code research --limit 100
```

## Legal holds

Holds target an existing UUID-backed entity. Placement and release each need
an operator identity and a reason. The current hold row cannot be deleted or
rewritten; a hold can be released once, and both actions are kept in immutable
history. Reasons should explain the hold without copying participant payloads
or other unnecessary sensitive data.

The CLI records supplied actor and approver identifiers; it does not
authenticate them or prove that the actor has a retention-administration
grant. Keep these commands inside the protected operator environment until an
authenticated, least-privilege policy-management surface is available.
All policy and hold mutations reject blank or non-string audit reasons and
reject blank, non-string, or over-200-character actor identifiers before
opening a database cursor. This matches the persisted audit columns; it does
not authenticate the supplied identity.

```bash
python3 -m services.analytics.cli_data_governance place-retention-hold \
  --entity-type platform_event --entity-id UUID \
  --actor OPERATOR --reason "Preserve for active review"
python3 -m services.analytics.cli_data_governance release-retention-hold \
  --hold-id UUID --actor OPERATOR --reason "Review closed"
python3 -m services.analytics.cli_data_governance retention-holds \
  --entity-type platform_event
```

The hold inventory is active-only by default, is limited to 500 rows, and
omits hold/release reasons. Add `--include-released` for bounded historical
state, or filter to one entity with both `--entity-type` and `--entity-id`.

Hold placement/release serializes with generic and event cleanup using a
transaction advisory lock. Both cleanup paths exclude active record-level
holds. A hold is not an authorization to disclose or reuse the held record.

## Current enforcement boundary

Event cleanup accepts no caller-supplied period. It requires exactly one
approved, active, auto-enforced, global `event_bus` / `platform_event`
hard-delete policy with a recorded policy owner. It then protects pending dead-letter dispositions,
non-success durable handler deliveries, and active record-level holds. Its
feature flag remains off by default; missing or ambiguous policy fails closed.
Each successful run is recorded with its operator and outcome.

The generic sweeper remains a default-off soft-delete path for explicitly
approved tables with `created_at`, `id`, and `deleted_at` semantics. It excludes
protected lifecycle entities and unresolved jurisdiction/purpose scopes,
detects overlapping active policy scopes, and checks active holds. Policy actor
fields currently provide attribution, not authenticated administrative
authorization. The inventory and mutation commands remain local
protected-operator tools; do not expose them through the Gateway until an
authenticated, least-privilege policy-management contract is implemented. It
is not a general erasure executor. Notification
outbox, handler attempt history, operator-audit records, media, exports,
backups, and Field Collector disposition do not have automatic pruning paths.

The generic sweeper explicitly skips `notification_outbox`,
`notification_outbox_attempt`, and `notification_outbox_operator_audit` in both
preview and enforcement modes until an archive workflow can preserve the
outbox's idempotency tombstone, parent/child relationships, and applicable
legal holds. A skipped policy is logged but does not update
`last_enforced_at`; a dry-run records its preview without marking the policy as
enforced. Focused source tests cover all three targets in both modes
([evidence](builds/2026-10-16-recovery/retention-notification-sweeper-guard.json)).

No periods have been configured. Migrations 401 and 402 are applied to the
local candidate after an encrypted checkpoint and isolated restore/replay;
the rollout left policy and hold tables empty and did not recreate the app.
Keep both
`KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP` and
`KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT` disabled. Do not add a recurring
cleanup schedule until an accountable owner configures the applicable policy
data and the target passes acceptance.

## Migration and rollback

Migration 401 adds hold/audit structures and changes the retention model to
allow unset periods. Migration 402 adds nullable scope-code fields with no
defaults. Migration 401 clears the old category-reference periods and demotes
policy rows that lack approval metadata; neither migration deletes operational
records. Before applying them to a candidate or production database, take and
restore-rehearse a fresh encrypted checkpoint. A code-only revert does not
restore cleared reference values or re-enable demoted policies; restoring the
pre-migration checkpoint is the complete rollback. Never turn on either
enforcement switch as part of migration rollout.
