# Dynamic retention policy and legal holds

Updated: 15 October 2026. This document defines the Kernel's configurable
retention boundary. It intentionally does not choose a retention period or
interpret legal requirements for the United States or Dominican Republic.

## Policy lifecycle

Retention windows are policy data, not application constants. A policy is
scoped by data category, entity type, and optional location, and may have an
unset `retention_days` while it is being drafted. The migration removes the
legacy category default windows and clears those reference values. No missing
period is inferred.

Create an inert draft. The period can be omitted while the accountable owner
reviews the applicable purpose and jurisdiction:

```bash
python3 -m services.analytics.data_governance set-retention \
  --data-category soil --entity-type soil_sample \
  --policy-owner ACCOUNTABLE_OWNER \
  --actor OPERATOR --reason "Drafted for policy review"
```

To prepare a fully configured draft, supply its reviewed window and action.
Approval is a separate action and records the approver, date, reason, and
policy snapshot. `--auto-enforce` is an explicit second choice; it does not
override the independent feature gate.

```bash
python3 -m services.analytics.data_governance set-retention \
  --data-category soil --entity-type soil_sample --retention-days N \
  --action soft_delete --policy-owner ACCOUNTABLE_OWNER \
  --actor OPERATOR --reason "Reviewed proposal"
python3 -m services.analytics.data_governance approve-retention \
  --policy-id UUID --approved-by OPERATOR --reason "Approved schedule" \
  --auto-enforce
```

Replace an active policy by creating its successor, retiring the current
policy, then approving the successor. Overlapping active policies are rejected
or skipped as ambiguous. Retirement disables enforcement and records the
actor, reason, and policy snapshot in append-only history.

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

```bash
python3 -m services.analytics.data_governance place-retention-hold \
  --entity-type platform_event --entity-id UUID \
  --actor OPERATOR --reason "Preserve for active review"
python3 -m services.analytics.data_governance release-retention-hold \
  --hold-id UUID --actor OPERATOR --reason "Review closed"
```

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
protected lifecycle entities, detects overlapping active policy scopes, and
checks active holds. Policy actor fields currently provide attribution, not
authenticated administrative authorization. It is not a general erasure executor. Notification
outbox, handler attempt history, operator-audit records, media, exports,
backups, and Field Collector disposition do not have automatic pruning paths.

No periods have been configured. Migration 401 and the source changes are not
yet applied to the local candidate, and focused migration/hold acceptance has
not run. Keep both `KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP` and
`KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT` disabled. Do not add a recurring
cleanup schedule until an accountable owner configures the applicable policy
data and the target passes acceptance.

## Migration and rollback

Migration 401 is additive for hold/audit structures and changes the retention
model to allow unset periods. It clears the old category-reference periods and
demotes policy rows that lack approval metadata; it does not delete operational
records. Before applying it to a candidate or production database, take and
restore-rehearse a fresh encrypted checkpoint. A code-only revert does not
restore cleared reference values or re-enable demoted policies; restoring the
pre-migration checkpoint is the complete rollback. Never turn on either
enforcement switch as part of migration rollout.
