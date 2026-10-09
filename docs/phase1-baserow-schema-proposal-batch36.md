# KI-21 schema draft — Baserow Batches 36–37

**Status: repository-only SQL draft.** The owner approved a draft for the expense fields and Farm↔Crop table; `docs/schema-drafts/368_baserow_expense_and_farm_crop_schema_draft.sql` contains it outside the active migration discovery path. The migration has not been applied to any database. The projection allow-list, row projection/import, live, Staging, and production remain unchanged. No source values or row identifiers are reproduced here.

## 1. Expense settlement status

**Owner-approved source meaning:** F002 `Expense Status` describes payment settlement, not KI expense workflow.

**Proposal:** Add a nullable `expense_event.payment_status` field, separate from the existing workflow `expense_event.status`. Use no default. Batch 38 approves preserving each selected source option label exactly by stable option ID, without normalization. Do not copy `sales_event.payment_status` defaults, populate workflow status, or infer paid/verified states.

**Draft boundary:** the SQL chooses nullable `VARCHAR(50)` with no default or state constraint. Batch 38 approved exact option-label preservation by stable option ID; offline validation found 533 populated selections across five used options, all with nonempty labels of at most 14 characters. This resolves the field mapping candidate only; it does not authorize projection/import or change workflow status.

## 2. People count per expense

**Owner-approved source meaning:** F002 `Personas Impactadas` is a count of people associated with an expense.

**Proposal:** Add nullable `expense_event.people_impacted_count INTEGER` with `CHECK (people_impacted_count IS NULL OR people_impacted_count >= 0)` and no default. Preserve `0` distinctly from `NULL`; do not convert it to a governed metric, infer unique persons, or aggregate it across expenses.

**Validation outcome:** Offline checks found 512 populated values, all positive integers, plus 21 blank cells; no fractional, negative, or nonnumeric values occurred. Preserve the integers unchanged and map blank cells to `NULL`. The reported values remain unverified, non-unique-person counts—not governed impact metrics or claims.

## 3. Farm-to-crop relationship

**Owner-approved source meaning:** Kokonut Farms `Species` / Species `Projects` expresses crops cultivated by a farm. The owner authorized a typed relationship proposal.

**SQL draft:** Migration 368 adds a dedicated `farm_crop` association between existing `farm(id)` and `crop(id)` records. It enforces one canonical relation per `(farm_id, crop_id)`, and optional all-or-none composite source-edge identity (`source_system`, source database/table/field/row, and related table/row IDs) with uniqueness enforcement. Validate reciprocal source edges, endpoint existence, and duplicate canonical pairs; quarantine conflicts rather than deduplicating by display name.

**Critical scope gate:** the existing projection allow-list retains the approved candidate Species field mapping unchanged. That mapping does not authorize projecting/importing Species rows in this migration. The owner keeps legacy Species rows and Farm↔Crop edges held until each source Species row resolves through a separately approved, stable identity mapping to an existing canonical `crop` record. Do not match by name.

## 4. Historical reusable development-phase/framework-step proposal — superseded

**Superseded by Batch 37:** the owner drops the entire Development Phases and Framework Steps source tables and every linked edge from this migration. No phase/step catalog or join DDL is included in migration 368; preserve these source rows and links in the controlled archive.

**Owner-approved domain direction:** treat phases and steps as reusable across farms/locations; the owner authorized a repository-only catalog/join proposal. Source-backed order/type/scope mapping is still pending.

**Proposal:** Separate reusable definitions from location-scoped operational instances rather than weakening existing constraints:

- Add reusable `development_phase_catalog` and `framework_step_catalog` definitions with stable source-row identity.
- Add `farm_development_phase(farm_id, phase_catalog_id)` for the source Farm↔Stage membership, and `development_phase_catalog_step(phase_catalog_id, step_catalog_id)` for the reusable phase↔step template edges. These record association only; they do not imply a farm's current lifecycle status.
- Add `farm_task_framework_step_catalog(task_id, step_catalog_id)` for task-to-reusable-step links and `framework_step_catalog_prerequisite(step_catalog_id, prerequisite_step_catalog_id)` for typed prerequisite edges. Keep source-edge provenance on each join and reject duplicate, unresolved, self, or cyclic edges. Do not encode the same edges in both a join and JSONB.
- Retain existing `development_phase` and `framework_step` as location-scoped operational instances. Do not create source-derived instances until a source-backed mapping supplies each required location and sequence/type; these instances remain distinct from reusable catalog rows.
- The source `Plot of Land` links point to physical, location-scoped plots. Keep those links held until an owner-backed mapping identifies a specific phase/step instance; never attach them directly to a reusable catalog record.

**Blocking facts remain unresolved:** source rows do not provide approved `phase_order` or `step_order`; source `Type` is empty for the reviewed step rows, so do not use the existing `step_type='implementation'` default. `Development Phases` currently link across farms in different locations, while current phase/step instances require one location. Do not infer location, order, step type, or per-location instances, and do not split a source row. The source-to-catalog and source-edge crosswalk must use stable source IDs. Owner input and technical review must determine any ordering/type values and any instance/plot mapping before migration implementation.

## Decisions still held

- The existing explicit projection allow-list is unchanged. None of these proposed fields or relationships is import-approved.
- Project Coordinates is owner-dropped from this migration; the source remains archived and no coordinate extraction/geocoding is authorized.
- F001/F002 residual option mappings and Species Unit of Metric remain held. `Staff.Name` and F001.Responsable identity resolution remain held; F002 Authorized by / Staff Ground Expenses edges are now owner-excluded. The Land Lots-to-F001 Daily Report inverse is resolved against the approved `farm_activity_plot` mapping and must not be emitted twice.
- Migration 368 is a repository-only draft; it has not been applied. No source projection/import, database write, allow-list update, or operational environment change was made.
