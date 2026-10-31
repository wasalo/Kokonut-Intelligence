# Directus polymorphic audit lineage preflight

This source-only tool measures whether legacy `workflow_history` and `approval`
rows can be traced to a location. It does not change permissions, hooks, data,
or lifecycle behavior, and it does not close C3 by itself.

## Run only against an explicitly selected read-only target

Set `DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN` to a database role with read-only
access, after selecting the intended copied/populated target yourself:

```sh
DIRECTUS_POLYMORPHIC_PREFLIGHT_DSN='postgresql://…' \
  python3 scripts/directus-polymorphic-lineage-preflight.py
```

There is no default target. The DSN, database errors, record identifiers,
location identifiers, and row contents are not printed. The script starts one
`REPEATABLE READ READ ONLY` transaction for both aggregate queries and rolls it
back on completion. It uses a connection timeout and an application name for
operator visibility. It must not be pointed at the candidate, legacy, or any
production database as part of unattended checks.

Output contains counts grouped only by recognized static collection names,
recognized approval action (`approve`) or the `other` bucket, and one of these
lineage classes:

- `resolved`: the source record exists, has a non-null location, and that
  location exists.
- `unresolved`: the collection is mapped but its source record or location
  cannot be resolved.
- `unsupported`: the collection is outside the allowlist. Its actual value is
  replaced with the literal `unsupported` in output.

Unexpected result labels are also sanitized to `unsupported` / `other` before
serialization. The tool does not emit one row per source record.

## Current source-to-location allowlist

The direct `location_id` mapping is limited to:

`farm_activity`, `harvest_event`, `expense_event`, `sales_event`, `loss_event`,
`labor_event`, `field_note`, `forecast_scenario`, `report_snapshot`,
`dashboard_dataset`, `farm_registry_record`, `inventory_event`,
`maintenance_event`, `revenue_event`, `stakeholder_outcome`,
`stakeholder_feedback`, `credit_batch`, `project_credit_class_enrollment`,
`retirement_certificate`, `metric_proposal`, `mrv_claim`, `metric_value`,
`impact_claim`, and `mrv_event`.

`protocol_execution_intent` has one explicit relational mapping:
`protocol_execution_intent.mapping_id` → `protocol_project_location.id` →
`protocol_project_location.location_id`.

These are schema-level location lineage mappings, not proof of tenant ownership,
sharing grants, or authorization. In particular, a non-null `location_id`
does not establish which organization owns the location. The preflight treats
all other sources—including subject/polymorphic records without an explicit
contract—as unsupported. It deliberately does not guess through names, IDs,
metadata, or narrative columns.

## Schema-only disposable validation

`python3 scripts/check-directus-polymorphic-lineage-schema-disposable.py`
starts a uniquely named disposable PostgreSQL/PostGIS Compose project with
networking disabled and no host ports, replays all discovered schema migrations
through the ordered migration runner with seeds excluded, checks the allowlist
relations/columns, and executes both generated aggregate queries inside a
read-only repeatable-read transaction. It cleans up that project's container
and volume and writes schema-only evidence to
`docs/refactor/builds/2026-10-28-recovery/directus-polymorphic-lineage-schema-disposable.json`.
The corrected disposable replay applied all 671 schema migrations through
`schema:680_runtime_yield_benchmark_read_only.sql`, with no seeds. All 29
allowlisted source relations and 60 required columns were present, and both
generated aggregate queries executed in the read-only repeatable-read
transaction. The isolated container, volume, and network were removed and
cleanup was verified. The evidence is schema-only: the empty database returned
zero workflow-history and approval groups, so it does not establish populated-
row resolution or live Directus permissions
([evidence](builds/2026-10-28-recovery/directus-polymorphic-lineage-schema-disposable.json)).

## Limitations and next gate

`workflow_history` and `approval` store `collection` plus `record_id`, but have
no source foreign key or `location_id`. The preflight can therefore classify
only the allowlisted lineage above; it cannot prove full historical coverage,
operator access, Directus API behavior, or effective role/field/row permissions.
The synthetic tests validate query construction, aggregation, read-only
transaction setup, missing-target blocking, and output sanitization; they are
not populated-data or live-Directus acceptance.

After an operator explicitly selects a read-only populated copy, review only
the aggregate unresolved/unsupported totals and source categories. Any new
lineage must be added as a reviewed static contract and covered by fixtures.
Only after every retained source class has an accepted rule should the team
design row-filter hooks and field allowlists, then verify those against the
pinned Directus runtime. Do not use these counts alone to narrow the broad
`Field Worker`, `Supervisor`, `Manager`, `Finance`, `Analyst`, `Auditor`, or
`Agent Full` policies in `config/directus/permissions.sql`.
