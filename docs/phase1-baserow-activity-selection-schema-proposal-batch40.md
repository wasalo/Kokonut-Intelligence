# F001 Activity option-preservation schema proposal — Batch 40

**Status: migration 369 is committed and passed an isolated disposable PostgreSQL rehearsal of the ordered schema chain and JSON-array constraint; it has not been applied to any persistent database.** The owner approved using the 13 additional used source option labels as new `farm_activity.activity_type` strings, exactly as written, and using the first selected option in source order as primary for multi-select rows. Migration `schemas/postgres/369_baserow_activity_source_options.sql` adds a nullable JSONB field to preserve all source selections. Batch 45 separately authorizes scratch projection-scope expansion for mappings explicitly decided for this migration; no Baserow source rows have been projected and no persistent import is authorized.

## Owner-approved scope

- Source: F001 `Actividad` (source field ID `2350134`), a Baserow `multiple_select` field.
- The three previously approved option-ID-to-canonical-type mappings remain unchanged.
- The existing three owner-approved option-ID mappings remain unchanged. The owner approves mapping each of the 13 additional used option IDs to its exact source metadata label as a distinct `activity_type` string, without normalization. Twelve occur as single selections across 127 rows; one occurs only in multi-selection rows.
- For each multi-selection row, the first selected option in source order supplies the primary canonical type; preserve all selected IDs/labels/order in migration 369's field and do not split rows. The rule is limited to the manifest-matched, owner-reviewed snapshot; unknown option IDs or a changed snapshot fail closed.
- This document records the design and implementation boundary only; it does not reproduce option labels, option IDs, source row IDs, or raw export values.

## Proposed model

Add a nullable, explicitly source-specific column to `farm_activity`:

```text
activity_type_source_options JSONB
```

For Baserow source records, store an ordered JSON array with one object per selected option. Each object carries the stable source option ID and the exact source label as observed in the approved snapshot. Preserve source selection order; do not normalize labels, merge equivalent-looking options, deduplicate, or split one activity into multiple `farm_activity` rows. A non-Baserow activity leaves the column `NULL`.

The database constraint requires a JSON array when populated. Any future import/preflight validator must additionally require each element to contain a positive integer option ID and a nonempty string label, and reject or quarantine unknown option IDs, malformed elements, or label/option mismatches. Retain the existing row-level source lineage separately; this field is for source activity selections, not a replacement for source identity. The disposable PostgreSQL rehearsal verified the array constraint; it did not load Baserow source rows.

A dedicated column is preferred over burying this business selection in generic `source_raw` JSONB: its purpose and cardinality are explicit, and downstream consumers can distinguish source labels from canonical activity classification.

## Canonical type policy and scope

The current schema defines `farm_activity.activity_type VARCHAR(100) NOT NULL`, with no enum or lookup table. The approved mapping therefore uses strings directly: the existing three option-ID mappings remain as-is; each additional option ID maps to its exact source label; and the first source selection supplies the primary type for multi-select rows. The owner approved these semantics on 2026-10-07. The DDL comment, user-guide examples, and field-collector choices are not fully aligned; this mapping is limited to the reviewed Baserow snapshot and does not create or revise a global activity taxonomy or UI option catalog. Existing analytics code may group only selected activity-type values, so some new strings may not appear in those specific aggregates; this work does not change analytics logic.

Do not map any additional option to `other`; the source label becomes its exact canonical string. The first-option primary rule is deterministic but does not assert that the first selection is more important; all selections remain preserved in order in the JSONB field.

## Implementation and validation gates

The 2026-10-07 owner instruction authorizes repository-only implementation of the source-preservation field and mapping policy. Migration 369, an in-memory mapping validator, and synthetic unit tests are present. The offline validator is scoped to the manifest-matched snapshot, verifies the exact option inventory/labels and selection patterns, and fails closed for changed snapshots, unknown IDs, malformed selections, or target strings over 100 characters. The 2026-10-08 owner instruction authorizes expanding the scratch projection scope to mappings explicitly decided for this migration. The allow-list/projection update and a manifest-matched source rehearsal remain pending; no persistent import is authorized.

Migration 369 is committed and scratch-rehearsed, but has not been applied to any persistent database. The owner-approved mapping policy resolves the populated F001 field-level mapping condition for the exact reviewed snapshot; the 51 blank `Actividad` rows still require evidence-based review or quarantine. Batch 45 authorizes scratch projection-scope expansion, not a persistent import.
