# ER Integrity Foundations

Kokonut Intelligence uses PostgreSQL as the canonical relational model. Entity
and relationship changes must preserve explicit ownership, cardinality,
provenance, lifecycle, and temporal semantics.

## Operational Ownership

Operational records must not combine unrelated context identifiers. Migration
`308_er_integrity_foundations.sql` enforces this through deferred constraint
triggers and validates existing rows before installing the triggers.

The canonical ownership path:

```text
location -> farm -> plot -> crop_cycle
                           -> harvest_event -> sales_event
```

Deferred constraint triggers enforce consistency across these tables:

| Trigger | Enforced On | Guards Against |
|---------|-------------|----------------|
| `trg_farm_operational_context` | `farm.location_id` update | Farm move breaking crop_cycle/farm_activity location |
| `trg_plot_operational_context` | `plot.farm_id` insert/update | Plot re-parenting breaking crop_cycle/farm_activity |
| `trg_crop_cycle_operational_context` | `crop_cycle.plot_id`, `location_id` | Cycle location mismatch with plot → farm → location |
| `trg_farm_activity_operational_context` | `farm_activity.plot_id`, `crop_cycle_id`, `location_id` | Activity context disagrees with plot or crop cycle |
| `trg_harvest_event_operational_context` | `harvest_event.plot_id`, `crop_cycle_id`, `location_id` | Harvest context disagrees with crop cycle |
| `trg_sales_event_operational_context` | `sales_event.harvest_id`, `crop_cycle_id`, `location_id` | Sale context disagrees with harvest or crop cycle |
| `trg_expense_event_operational_context` | `expense_event.plot_id`, `crop_cycle_id`, `location_id` | Expense context disagrees with plot or crop cycle |

All triggers are `DEFERRABLE INITIALLY IMMEDIATE` and invoke
`validate_operational_context()`. The function skips validation when
`kokonut.seed_context = 'pilot'` to allow trusted seed reconciliation.

Before installing triggers, migration 308 backfills `harvest_event` rows
whose `plot_id`/`location_id` disagree with their `crop_cycle` parent, then
validates all existing rows to ensure a clean baseline.

## Polymorphic Reference Governance

Polymorphic `*_type`/`*_id` pairs cannot use direct foreign keys. Migration
`311_relationship_reference_policy.sql` creates
`relationship_reference_policy` to govern these relationships:

| Table | Type Column | ID Column | Allowed Types | Enforcement |
|-------|-------------|-----------|---------------|-------------|
| `party_relationship` | `scope_type` | `scope_id` | `network`, `organization`, `location`, `farm`, `cooperative`, `value_stream`, `initiative`, `decision` | `registry_validated` |
| `strategy_advantage_link` | `entity_type` | `entity_id` | `capability`, `market_segment`, `stakeholder`, `metric` | `typed_table_planned` |
| `strategy_evidence_link` | `source_type` | `source_id` | `pestel_factor`, `swot_factor`, `competitive_signal`, `stakeholder_outcome`, `metric_value`, ... | `registry_validated` |

Enforcement statuses:

- `inventory_only` — cataloged but no runtime check.
- `registry_validated` — allowed type values enforced by constraint trigger.
- `typed_table_planned` — replacement typed table is designed but not yet applied.
- `typed_table_complete` — polymorphic pair has been fully replaced.

High-risk polymorphic pairs receive database-level validation triggers
(`313_phase2_backfill_phase3_reference_validation.sql`):

- `validate_party_scope_reference` — verifies `scope_id` references the
  correct parent table for each `scope_type` value. Installed on
  `party_relationship` and `stakeholder_interest`.
- `validate_strategy_advantage_link_target` — verifies `entity_id` references
  the correct parent table for each `entity_type` value. Installed on
  `strategy_advantage_link`.

## Cardinality and Temporal Integrity

Migration `310_cardinality_temporal_integrity.sql` enforces semantic
uniqueness and temporal ordering:

**Semantic uniqueness (partial unique indexes):**

| Index | Table | Scope |
|-------|-------|-------|
| `uq_kyc_current_approved_method` | `kyc_verification` | One approved KYC per farmer + method |
| `uq_role_assignment_active_scope` | `role_assignment` | One active role per farmer + scope |
| `uq_metric_value_semantic_current` | `metric_value` | One verified metric per metric/location/period/method |

**Temporal ordering (CHECK constraints):**

| Constraint | Table | Rule |
|------------|-------|------|
| `chk_kyc_expiry_after_creation` | `kyc_verification` | `expires_at >= created_at` |
| `chk_board_term_order` | `cooperative_board_member` | `term_end >= term_start` |
| `chk_forecast_version_positive` | `forecast_scenario` | `version > 0` |

## Reference Validation

Migration `313_phase2_backfill_phase3_reference_validation.sql` normalizes
legacy JSON/UUID-array columns into proper relationship entities and validates
high-risk polymorphic links:

- `metric_value.source_record_ids` → `metric_value_source` rows with
  `v_metric_value_provenance` view for backward-compatible access.
- `forecast_scenario.assumptions` / `price_assumptions` / etc. →
  `forecast_assumption` rows.
- `role_assignment.permissions` → `role_permission` rows with
  `v_role_assignment_permissions` view.
- `farmer_profile.primary_crops` → `farmer_crop` rows.

## Schema Inventory

The read-only introspection package exposes physical-model risks:

```bash
python3 -m services.schema_introspection --format json
python3 -m services.schema_introspection --format markdown
python3 -m services.schema_introspection --fail-on-risk --format markdown
./scripts/check-er-model.sh
```

The report detects:

- Tables without primary keys
- Foreign keys without supporting indexes
- Lifecycle tables missing `created_at`/`updated_at` timestamps
- Temporal tables without exclusion constraint overlap protection
- Polymorphic `*_type`/`*_id` column pairs
- Relationship-shaped columns (`_uuid[]`, `_text[]`, `jsonb`)
- Views with fan-trap or chasm-trap risk (multi-JOIN + aggregate)

For controlled CI adoption, `--fail-on-risk` exits non-zero when any ER risk
pattern is found. It should be enabled only after each existing risk is either
normalized or recorded in `relationship_reference_policy`.

## Relationship Review

Before adding a relationship, document:

- The subject and object entity types.
- The role name on each side.
- Minimum and maximum cardinality.
- Whether participation is optional or mandatory.
- The relationship's semantic uniqueness key.
- Delete and retirement behavior.
- Evidence, consent, and lifecycle requirements.
- Whether the relationship is temporal.

Relationships with their own evidence, confidence, dates, rationale, status, or
ordering should be represented as associative entities rather than arrays or
unstructured JSON.

If the relationship must be polymorphic, add a row to
`relationship_reference_policy` with `enforcement_status` and a retirement
target. Prefer typed link tables over polymorphic pairs.

## Change Workflow

Schema changes must:

1. Add a new ordered migration; never edit an applied migration.
2. Describe affected entities and relationship cardinalities.
3. Add negative tests for invalid relationships.
4. Add a backfill and compatibility strategy for existing data.
5. Check analytical views for fan traps and chasm traps.
6. Run migration, relational-integrity, and platform verification before review.
7. Update `relationship_reference_policy` if introducing a polymorphic pair.

## Tests

Source-level tests validate migration integrity:

| Test File | What It Checks |
|-----------|---------------|
| `tests/test_relational_integrity.py` | Migration 308 covers all context tables, uses deferred triggers, reconciles pilot seeds |
| `tests/test_cardinality_constraints.py` | Migration 310 includes semantic uniqueness indexes and temporal CHECK constraints |
| `tests/test_polymorphic_references.py` | Migration 311 has retirement metadata; migration 313 validates high-risk polymorphic links |
| `tests/test_relationship_reference_policy.py` | Policy table exists with required columns; seeded relationships are idempotent |

Run ER integrity tests:

```bash
PYTHONPATH=. uv run pytest tests/test_relational_integrity.py tests/test_cardinality_constraints.py tests/test_polymorphic_references.py tests/test_relationship_reference_policy.py -v
```
