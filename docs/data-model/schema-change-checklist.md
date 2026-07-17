# Schema Change Checklist

Every relational schema change must answer these questions before review.

## Model

- What entity types and instances are affected?
- What relationship roles are added, removed, or redefined?
- What are the minimum and maximum cardinalities on each side?
- Is the relationship an associative entity because it has evidence, dates, status, confidence, or rationale?
- What is the candidate key: global, parent-scoped, active-state scoped, version-scoped, or intentionally non-unique?

## Integrity

- Are foreign keys present and indexed?
- What is the `ON DELETE` policy?
- Are cross-parent consistency rules required?
- Are polymorphic references governed by a policy and retirement target?
- Does the change require a partial unique index or exclusion constraint?
- Can existing rows violate the new rule?

## Temporal and lifecycle behavior

- Are `valid_from`, `valid_until`, `recorded_at`, and `supersedes_id` needed?
- Can active intervals overlap?
- Does the entity have a current-state view separate from history?
- Are lifecycle status, payment status, verification status, and domain status separate?

## Migration and data

- Is this a new ordered migration rather than an edit to an applied migration?
- Is the backfill idempotent and source-preserving?
- Are legacy JSON/array fields retained until all consumers migrate?
- Are published or verified records protected from silent mutation?

## Analytics and governance

- Could a view introduce a fan trap through multiple one-to-many joins?
- Could a chasm trap hide records with incomplete relationship paths?
- Are public/private and consent boundaries preserved?
- Are negative database tests included?
- Are migration, ER inventory, platform, and CI checks updated?
