# Schema Change Checklist

Every relational schema change must answer these questions before review.

## Model and Vocabulary

- [ ] What entity types and instances are affected?
- [ ] What relationship roles are added, removed, or redefined?
- [ ] What are the minimum and maximum cardinalities on each side?
- [ ] Is the relationship an associative entity because it has evidence, dates, status, confidence, or rationale?
- [ ] What is the candidate key: global, parent-scoped, active-state scoped, version-scoped, or intentionally non-unique?
- [ ] If a new status column is introduced, which of the 16 governing ENUM types from `015_constraints.sql` applies (`lifecycle_status`, `entity_status`, `payment_status_type`, etc.)?
- [ ] If no existing ENUM fits, is the new vocabulary justified and added to `015_constraints.sql` with a CHECK constraint?

## Constraint Enforcement Hierarchy

Apply constraints in layers. Each layer depends on the one before it.

```text
ENUM CHECK → FK + index + ON DELETE → operational triggers (308)
→ reference triggers (313) → partial unique (310) → GiST exclusion (315)
```

- [ ] Are ENUM-backed CHECK constraints applied to all status columns? (`015_constraints.sql`)
- [ ] Are foreign keys present with supporting indexes and an explicit `ON DELETE` policy? (`015_constraints.sql`)
- [ ] If the change touches the farm → plot → crop_cycle → activity/harvest/sales/expense path, does `validate_operational_context()` cover it? (`308_er_integrity_foundations.sql`)
- [ ] If the change introduces a polymorphic `*_type`/`*_id` pair, is it registered in `relationship_reference_policy` with an enforcement status and retirement target? (`311_relationship_reference_policy.sql`)
- [ ] If the polymorphic pair is high-risk (scope or entity references), does a validation trigger verify `*_id` references the correct parent table? (`313_phase2_backfill_phase3_reference_validation.sql`)
- [ ] Does the change require a partial unique index for semantic current-state uniqueness? (`310_cardinality_temporal_integrity.sql`)
- [ ] Can existing rows violate the new rule? If so, is there a backfill before trigger installation? (`308` pattern: validate existing → install trigger)

## Temporal Semantics

- [ ] Are `valid_from`, `valid_until`, and `supersedes_id` needed for historical tracking? (`315_temporal_semantics.sql`)
- [ ] Is an `is_current` boolean field needed for current-state projection?
- [ ] Can active intervals overlap? If not, is a GiST exclusion constraint applied? (`315`: `ex_role_assignment_active_interval`, `ex_consent_active_interval`, `ex_party_relationship_active_interval`)
- [ ] Does the entity have a current-state view separate from history? (`315`: `v_current_location_baseline` pattern)
- [ ] Are lifecycle status, payment status, verification status, and domain status stored in separate columns?

## Polymorphic References

- [ ] Is the polymorphic pair registered in `relationship_reference_policy` with `allowed_type_values`, `enforcement_status`, and `replacement_target`? (`311_relationship_reference_policy.sql`)
- [ ] Is the `enforcement_status` correct: `inventory_only` → `registry_validated` → `typed_table_planned` → `typed_table_complete`?
- [ ] If replacing a polymorphic pair, is the old policy updated (not edited) via a new migration? (`314_reference_policy_correction.sql` pattern)
- [ ] If the polymorphic pair scopes to multiple domain entities (e.g., `scope_type`), does the validation trigger cover all allowed types? (`313`: `validate_party_scope_reference`)

## Migration Discipline

- [ ] Is this a new ordered migration with a unique version number (never edit an applied migration)?
- [ ] Does the version number avoid duplicates with existing schema files? (`python3 -m services.migration validate`)
- [ ] Is the SQL free of `\connect` commands and NUL bytes?
- [ ] Is there a backfill for existing rows, and is it idempotent (`ON CONFLICT` or equivalent)?
- [ ] Are legacy JSON/array fields retained for backward compatibility until all consumers migrate? (`313`: `v_metric_value_provenance`, `v_role_assignment_permissions` compatibility views)
- [ ] Are published or verified records protected from silent mutation?
- [ ] If correcting a prior migration's data, is the fix a new migration (not an edit)? (`314` pattern)
- [ ] If the checksum must be repaired, is it done through the audited `repair` workflow with approved migration ID, operator identity, and audit trail?

## Seed Discipline

- [ ] Are seed files idempotent with `ON CONFLICT` or equivalent guards?
- [ ] Do canonical metadata seeds correct stale source-of-truth rows on conflict (not only `DO NOTHING`)?
- [ ] If the seed applies in a trusted session, is `kokonut.seed_context` used to bypass stricter triggers? (`308`: pilot seed bypass)
- [ ] Do seed scripts use `psql -v ON_ERROR_STOP=1`? Are SQL errors propagated, not hidden with `|| true`?
- [ ] Is the platform setup order followed: `seed.sh` → `seed-pilot.sh` → `compute-metrics.sh` → `verify-platform.sh`?

## Analytics and Views

- [ ] Could a view introduce a fan trap through multiple one-to-many joins combined with a COUNT aggregate? (Check with `python3 -m services.schema_introspection --format markdown`)
- [ ] Could a chasm trap hide records with incomplete relationship paths?
- [ ] Are public views gated on `farm_registry_record` status IN ('verified', 'published')? (`018_public_views.sql`)
- [ ] Are public metric views additionally gated on `metric_value.verified = TRUE`?
- [ ] Are public/private and consent boundaries preserved in view definitions?

## CI Validation Pipeline

Before requesting review, run:

```bash
python3 -m services.migration validate          # source discovery + SQL boundary
bash scripts/verify-clean-bootstrap.sh           # fresh DB, schema-only apply
python3 -m tests.test_seed_idempotency           # seed idempotency
python3 -m services.schema_introspection --fail-on-risk --format markdown  # ER risks
```

- [ ] Does `python3 -m services.migration validate` pass (no duplicate IDs, no NUL bytes)?
- [ ] Does `verify-clean-bootstrap.sh` apply all schema migrations cleanly from scratch?
- [ ] Are source-level ER integrity tests passing? (`test_relational_integrity.py`, `test_cardinality_constraints.py`, `test_polymorphic_references.py`, `test_relationship_reference_policy.py`, `test_temporal_integrity.py`, `test_relationship_entities.py`, `test_evidence_lineage_integrity.py`, `test_migration.py`)
- [ ] Does the schema introspection report no new risk patterns?
- [ ] Are `ruff` and `pip-audit` passing (mandatory CI gates)?
