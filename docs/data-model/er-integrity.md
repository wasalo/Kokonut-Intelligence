# ER Integrity Foundations

Kokonut Intelligence uses PostgreSQL as the canonical relational model. Entity
and relationship changes must preserve explicit ownership, cardinality,
provenance, lifecycle, and temporal semantics.

## Operational Ownership

Operational records must not combine unrelated context identifiers:

```text
location -> farm -> plot -> crop_cycle
                           -> harvest_event -> sales_event
```

`farm_activity`, `harvest_event`, `sales_event`, and `expense_event` may carry
denormalized context keys for query performance, but those keys must agree with
the canonical ownership path. Migration `308_er_integrity_foundations.sql`
enforces this through deferred constraint triggers and validates existing rows
before installing the triggers.

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

## Schema Inventory

The read-only inventory command exposes physical-model risks:

```bash
python3 -m services.schema_introspection --format json
python3 -m services.schema_introspection --format markdown
./scripts/check-er-model.sh
```

The report detects tables, keys, foreign keys, delete actions, polymorphic
`*_type`/`*_id` pairs, and relationship-shaped arrays or JSON columns. It is a
review aid, not a replacement for the canonical migrations.

For controlled CI adoption, `--fail-on-risk` is available. It should be enabled
only after each existing risk is either normalized or recorded in an explicit
retirement inventory.

## Change Workflow

Schema changes must:

1. Add a new ordered migration; never edit an applied migration.
2. Describe affected entities and relationship cardinalities.
3. Add negative tests for invalid relationships.
4. Add a backfill and compatibility strategy for existing data.
5. Check analytical views for fan traps and chasm traps.
6. Run migration, relational-integrity, and platform verification before review.
