# KI-21 Baserow blocker decision register

**Snapshot:** manifest-matched owner-provided export; offline preflight on 2026-10-06. Owner field-scope decisions received 2026-10-07.
**Status:** The original blocker inventory contains 84 populated fields. The owner initially marked 38 DROP and 46 PURSUE; follow-up decisions now total 66 DROP and 18 PURSUE after Batch 39. Batch 40 authorizes a repository-only F001 source-option preservation proposal without changing scope totals. The latest active blocker count is recorded in the reconciliation report; import remains blocked. This is a field list, not 84 records.

## How to decide

- Set each row’s **Decision** to `DROP` or `PURSUE`.
- `DROP` means exclude this field from KI projection/import and retain it only in the controlled source archive; it does **not** delete source data.
- `PURSUE` means continue resolving the documented semantic, identity, unit, target, or relationship condition. It does **not** authorize projection or import.
- You may decide a whole field group uniformly only when the same decision genuinely applies to every listed field. Otherwise decide row by row.
- No source row values or source table/field IDs are included. Use the crosswalk for the full rationale: `docs/phase1-baserow-field-crosswalk.md`.

## Summary

| Source table | Blocking fields |
|---|---:|
| Biofactory | 2 |
| Development Phases | 2 |
| Digital Legos Tracker | 5 |
| Ecosystem Branches | 2 |
| Ecosystem Infra Stack | 4 |
| F001 — Activity Report | 1 |
| F002 — Expenses | 6 |
| F005 -- Resources Inputs | 1 |
| Framework Steps | 3 |
| Funding | 4 |
| Ground Analytics | 1 |
| Harvest & Sales | 10 |
| Impact | 1 |
| Kokonut Farm Tasks | 1 |
| Kokonut Farms | 23 |
| Land Lots | 4 |
| Locations | 2 |
| Species | 7 |
| Staff | 4 |
| Weekly Planning | 1 |

Table counts and disposition counts above describe the original 84-field blocker inventory; follow-up owner scope changes are recorded below.

| Initial disposition (at blocker registration) | Blocking fields |
|---|---:|
| `CONDITIONAL` | 22 |
| `HOLD_FIELD` | 44 |
| `HOLD_RELATIONSHIP` | 18 |

## Field-by-field decisions

| # | Source table | Source field | Disposition at blocker registration | Populated cells | KI target candidate | Current decision |
|---:|---|---|---|---:|---|---|
| 1 | Biofactory | Notes | ` CONDITIONAL ` | 16 | `bio_factory_batch.batch_summary` | **DROP** |
| 2 | Biofactory | Product | ` CONDITIONAL ` | 16 | `bio_factory_batch.batch_type` | **DROP** |
| 3 | Development Phases | Development Phase Step | ` HOLD_RELATIONSHIP ` | 4 | — | **DROP** |
| 4 | Development Phases | Kokonut Farms | ` HOLD_RELATIONSHIP ` | 2 | — | **DROP** |
| 5 | Digital Legos Tracker | Contract | ` HOLD_FIELD ` | 1 | `technology_alternative.metadata.baserow_legacy.contract_source_value` | **DROP** |
| 6 | Digital Legos Tracker | Ecosystem Infra Stack | ` HOLD_RELATIONSHIP ` | 2 | — | **DROP** |
| 7 | Digital Legos Tracker | Name | ` HOLD_FIELD ` | 2 | `technology_alternative.name` | **DROP** |
| 8 | Digital Legos Tracker | Status | ` HOLD_FIELD ` | 2 | `technology_alternative.maturity_status` | **DROP** |
| 9 | Digital Legos Tracker | URL | ` HOLD_FIELD ` | 1 | `technology_alternative.metadata.baserow_legacy.source_url` | **DROP** |
| 10 | Ecosystem Branches | Active | ` HOLD_FIELD ` | 2 | `kokonut_guild.status` | **DROP** |
| 11 | Ecosystem Branches | Name | ` HOLD_FIELD ` | 1 | `kokonut_guild.name` | **DROP** |
| 12 | Ecosystem Infra Stack | Active | ` HOLD_FIELD ` | 3 | `technology_area.status` | **DROP** |
| 13 | Ecosystem Infra Stack | Digital Legos Tracker | ` HOLD_RELATIONSHIP ` | 2 | — | **DROP** |
| 14 | Ecosystem Infra Stack | Name | ` HOLD_FIELD ` | 3 | `technology_area.name` | **DROP** |
| 15 | Ecosystem Infra Stack | URL | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 16 | F001 — Activity Report | Actividad | ` CANDIDATE ` | 204 | `farm_activity.activity_type`; preserve selections in `farm_activity.activity_type_source_options` | **PURSUE** |
| 17 | F002 — Expenses | Audit Notes | ` HOLD_FIELD ` | 37 | — | **DROP** |
| 18 | F002 — Expenses | Authorized by | ` CONDITIONAL ` | 526 | — | **DROP** |
| 19 | F002 — Expenses | Bank | ` HOLD_FIELD ` | 516 | — | **DROP** |
| 20 | F002 — Expenses | Category | ` CONDITIONAL ` | 527 | — | **DROP** |
| 21 | F002 — Expenses | Expense Status | ` HOLD_FIELD ` | 533 | `expense_event.payment_status` | **PURSUE** |
| 22 | F002 — Expenses | Personas Impactadas | ` HOLD_FIELD ` | 512 | `expense_event.people_impacted_count` | **PURSUE** |
| 23 | F005 -- Resources Inputs | Active | ` HOLD_FIELD ` | 2 | — | **DROP** |
| 24 | Framework Steps | Development Phase | ` HOLD_RELATIONSHIP ` | 14 | — | **DROP** |
| 25 | Framework Steps | Farms Individual Tasks | ` CONDITIONAL ` | 12 | — | **DROP** |
| 26 | Framework Steps | Prerequisites | ` CONDITIONAL ` | 4 | — | **DROP** |
| 27 | Funding | Crowdfunding Amount | ` HOLD_FIELD ` | 9 | — | **DROP** |
| 28 | Funding | Grant Amount | ` HOLD_FIELD ` | 10 | — | **DROP** |
| 29 | Funding | Overview | ` HOLD_FIELD ` | 3 | — | **DROP** |
| 30 | Funding | Results | ` HOLD_FIELD ` | 8 | — | **DROP** |
| 31 | Ground Analytics | Active | ` HOLD_FIELD ` | 2 | — | **DROP** |
| 32 | Harvest & Sales | Actual Production Quantity | ` CONDITIONAL ` | 2 | `crop_cycle.actual_yield` | **DROP** |
| 33 | Harvest & Sales | Avg Sale Price | ` CONDITIONAL ` | 9 | `crop_cycle.expected_price_per_unit`; `crop_cycle.metadata.expected_price_currency` | **DROP** |
| 34 | Harvest & Sales | Harvest Forecast Date | ` CONDITIONAL ` | 2 | `crop_cycle.expected_harvest_date` | **DROP** |
| 35 | Harvest & Sales | Live quantity | ` HOLD_FIELD ` | 6 | `crop_cycle.metadata.baserow_legacy.live_quantity` | **DROP** |
| 36 | Harvest & Sales | Lots of Land | ` HOLD_RELATIONSHIP ` | 6 | — | **DROP** |
| 37 | Harvest & Sales | Planted Plot of Lands | ` HOLD_FIELD ` | 9 | `crop_cycle.metadata.baserow_legacy.planted_plot_count` | **DROP** |
| 38 | Harvest & Sales | Planting Date | ` CONDITIONAL ` | 6 | `crop_cycle.planting_date` | **DROP** |
| 39 | Harvest & Sales | Production Metric | ` CONDITIONAL ` | 3 | `crop_cycle.actual_yield_unit` only with a supported actual-yield value; `crop_cycle.metadata.baserow_legacy.expected_price_unit` for forecast price | **DROP** |
| 40 | Harvest & Sales | Quantity Planted | ` HOLD_FIELD ` | 6 | `crop_cycle.metadata.baserow_legacy.quantity_planted` | **DROP** |
| 41 | Harvest & Sales | Status | ` HOLD_FIELD ` | 8 | `crop_cycle.metadata.baserow_legacy.status_label` | **DROP** |
| 42 | Impact | Impact Score | ` HOLD_FIELD ` | 2 | — | **DROP** |
| 43 | Kokonut Farm Tasks | Framework Steps | ` CONDITIONAL ` | 31 | — | **DROP** |
| 44 | Kokonut Farms | Actual end date | ` HOLD_FIELD ` | 2 | — | **DROP** |
| 45 | Kokonut Farms | Data Hub | ` HOLD_FIELD ` | 4 | — | **DROP** |
| 46 | Kokonut Farms | Governance Mechanism | ` CONDITIONAL ` | 4 | `farm.metadata.legacy_source_fields.governance_mechanism` | **PURSUE** |
| 47 | Kokonut Farms | Ground Expenses | ` HOLD_RELATIONSHIP ` | 4 | — | **PURSUE** |
| 48 | Kokonut Farms | KKN-GEN-F001 | ` HOLD_RELATIONSHIP ` | 3 | — | **PURSUE** |
| 49 | Kokonut Farms | Local Problem | ` HOLD_FIELD ` | 1 | `farm.metadata.legacy_source_fields.local_problem` | **PURSUE** |
| 50 | Kokonut Farms | Plot of Land | ` HOLD_RELATIONSHIP ` | 2 | — | **PURSUE** |
| 51 | Kokonut Farms | Project Coordinates | ` CONDITIONAL ` | 1 | — | **DROP** |
| 52 | Kokonut Farms | Project Mission | ` HOLD_FIELD ` | 1 | `farm.metadata.legacy_source_fields.project_mission` | **PURSUE** |
| 53 | Kokonut Farms | Project Summary | ` HOLD_FIELD ` | 1 | `farm.metadata.legacy_source_fields.project_summary` | **PURSUE** |
| 54 | Kokonut Farms | Proposed Solution | ` HOLD_FIELD ` | 1 | `farm.metadata.legacy_source_fields.proposed_solution` | **PURSUE** |
| 55 | Kokonut Farms | Public Goods Allocation | ` CONDITIONAL ` | 4 | `farm.metadata.legacy_source_fields.public_goods_allocation` | **PURSUE** |
| 56 | Kokonut Farms | Resources | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 57 | Kokonut Farms | Revenue Streams | ` HOLD_FIELD ` | 1 | — | **PURSUE** |
| 58 | Kokonut Farms | Source of Funding | ` HOLD_FIELD ` | 4 | `farm.metadata.legacy_source_fields.source_of_funding` | **PURSUE** |
| 59 | Kokonut Farms | Species | ` HOLD_RELATIONSHIP ` | 3 | — | **DROP** |
| 60 | Kokonut Farms | Stage | ` HOLD_RELATIONSHIP ` | 3 | — | **DROP** |
| 61 | Kokonut Farms | Start | ` HOLD_FIELD ` | 3 | `farm.metadata.legacy_source_fields.start` | **PURSUE** |
| 62 | Kokonut Farms | Target Market | ` HOLD_FIELD ` | 2 | — | **PURSUE** |
| 63 | Kokonut Farms | Token Allocation | ` CONDITIONAL ` | 1 | `farm.metadata.legacy_source_fields.token_allocation` | **PURSUE** |
| 64 | Kokonut Farms | Weekly Planning | ` HOLD_RELATIONSHIP ` | 2 | — | **DROP** |
| 65 | Kokonut Farms | Wiki Farm Page | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 66 | Kokonut Farms | Youtube Playlist | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 67 | Land Lots | Crops | ` HOLD_RELATIONSHIP ` | 1 | `crop.metadata.baserow_legacy.plot_source_row_ids` | **DROP** |
| 68 | Land Lots | Development Stage | ` HOLD_RELATIONSHIP ` | 1 | — | **DROP** |
| 69 | Land Lots | Harvest Forecast | ` HOLD_RELATIONSHIP ` | 7 | — | **DROP** |
| 70 | Land Lots | KKN-F001 — Daily Report | ` HOLD_RELATIONSHIP ` | 7 | — | **PURSUE** |
| 71 | Locations | Flora & Fauna | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 72 | Locations | Long Description | ` HOLD_FIELD ` | 1 | — | **DROP** |
| 73 | Species | Bed Area in Square Meter | ` HOLD_FIELD ` | 43 | `crop.metadata.baserow_legacy.bed_area_m2` | **DROP** |
| 74 | Species | Beds per Plot of Land | ` HOLD_FIELD ` | 43 | `crop.metadata.baserow_legacy.beds_per_plot` | **DROP** |
| 75 | Species | Harvest Units Density in Square Meter | ` HOLD_FIELD ` | 43 | `crop.metadata.baserow_legacy.harvest_units_density_per_m2` | **DROP** |
| 76 | Species | Loss Rate % | ` HOLD_FIELD ` | 43 | `crop.metadata.baserow_legacy.loss_rate_percent` | **DROP** |
| 77 | Species | Plot of Land | ` HOLD_RELATIONSHIP ` | 2 | `crop.metadata.baserow_legacy.plot_source_row_ids` | **DROP** |
| 78 | Species | Projects | ` HOLD_RELATIONSHIP ` | 30 | — | **DROP** |
| 79 | Species | Unit of Metric | ` HOLD_FIELD ` | 6 | — | **DROP** |
| 80 | Staff | Email | ` CONDITIONAL ` | 3 | `staff.email` | **DROP** |
| 81 | Staff | Ground Expenses | ` CONDITIONAL ` | 4 | — | **DROP** |
| 82 | Staff | Name | ` CONDITIONAL ` | 9 | — | **DROP** |
| 83 | Staff | Phone | ` CONDITIONAL ` | 3 | `staff.phone` | **DROP** |
| 84 | Weekly Planning | Budget Forecast | ` CONDITIONAL ` | 8 | `weekly_plan.budget_forecast_usd` | **DROP** |

## Decision totals

- `DROP`: 66 fields, excluded from KI projection/import scope; source snapshot is not modified or deleted.
- `PURSUE`: 18 fields remain in investigation scope. Follow-up decisions may clear a field blocker, but do not authorize projection/import.
- Neither choice authorizes projection, import, or a live/Staging/production change.

## Safety status

The report is an owner decision aid only. Current source rows remain quarantined where required, and no import, live database change, Staging operation, or production operation is authorized by decisions in this document.

## Follow-up owner decisions — F001/F002 (2026-10-07)

These semantic decisions supplement the original 84 scope dispositions; later table-level exclusions are recorded separately below.

- F001 `Actividad`: keep all 13 additional used options held: 12 occur in single-selection rows across 127 records, and one occurs only in multi-selection rows; keep all 11 multi-select rows held and unsplit. The three previously approved exact mappings remain unchanged.
- F002 `Category` (2026-10-07): the then-current decision approved a partial source-to-canonical `labor` mapping (154 source rows); the other 12 used options (373 rows) and six blanks remained held. At that time F002 remained outside the projection allow-list. The 2026-10-08 exact source-label clarification and scoped allow-list decision are recorded below.
- F002 `Expense Status`: Batch 38 approves exact preservation of each populated source option label by stable option ID in `expense_event.payment_status`, without normalization or workflow-status changes. This is a candidate field mapping, not import approval.
- F002 `Personas Impactadas`: Batch 37 approves repository-only schema preparation for `expense_event.people_impacted_count`; migration 370 is the active additive implementation, while draft 368 remains outside active migration discovery. Aggregate-only validation found 512 positive integers and 21 blanks. Map blanks to NULL and preserve counts as reported/unverified; no governed metric or import is authorized.
- F002 `Authorized by` / Staff `Ground Expenses`: the earlier hold pending Staff identity resolution is superseded by the Batch 37 `DROP` decision. Preserve both reciprocal links in the source archive; do not map them to `expense_event.approved_by`.

These 2026-10-07 follow-up decisions authorized no source projection/import, allow-list change, or live/Staging/production operation. The separate 2026-10-08 F002 expense decision below authorizes only repository-local scope expansion and offline/scratch validation.

## Follow-up owner decision — F002 Category case clarification (2026-10-08)

- Owner approves the exact source option label `Labor`, resolved by stable option ID, mapped to canonical `expense_event.category = 'labor'`. This explicitly authorizes that one exact-label mapping; it does not authorize case-folding or normalizing any other label.
- Hold every other Category option/label and every blank Category value. This supersedes the Batch 39 full-field Category DROP only for exact source label `Labor`; required-field and relationship validation still apply to each expense row.
- Repository-only allow-list/projection changes and offline/scratch validation are in scope. No persistent import, database connection/write, Staging change, or deployment is authorized.

## Follow-up owner decision — Kokonut Farms (2026-10-07)

- Owner approves exact, unchanged per-farm metadata preservation for `Governance Mechanism`, `Token Allocation`, `Public Goods Allocation`, `Target Market`, and `Revenue Streams`, with one namespaced `farm.metadata.legacy_source_fields` key per source field. Resolve select values by stable source option ID and preserve the exact option label; retain each multi-select label array intact, without normalization, taxonomy inference, or splitting.
- These five mappings remain outside the projection allow-list. The decision authorizes neither source projection/import nor a live, Staging, or production change.

## Follow-up owner scope decision — Harvest & Sales (2026-10-07)

- Owner excludes all rows in the Harvest & Sales table from KI projection/import because there have not yet been officially commercially viable harvest or sales records. Manual population may be considered later if needed; it is not authorized by this decision.
- This table-level exclusion supersedes the eight original PURSUE choices (register rows 32, 33, 34, 37, 38, 39, 40, and 41); the two prior DROP choices remain DROP. Exclude all related Harvest & Sales record edges from KI scope while leaving other Farm, Species, and Plot records in scope under their independent decisions.
- Preserve the source snapshot in the controlled archive. Do not delete or modify source data. No allow-list change, projection, import, live/Staging/production operation, or manual KI entry is authorized.

## Follow-up owner scope decision — Funding (2026-10-07)

- Owner excludes the entire Funding table from this migration and will handle it manually later. The four Funding blocker decisions (register rows 27–30) are now `DROP`; every Funding field and every edge to/from Funding is `EXCLUDE_OWNER` for this scope.
- Preserve Funding rows and original reciprocal links in the controlled archive. This does not delete source data, authorize manual KI entry now, or change the projection allow-list. The repository-only `external_grant_tranche` schema draft and its tests remain; the earlier program-date/funder technical mappings are non-operative for this migration.
- Organizations remain independently in scope; excluding Funding edges does not waive canonical Organization identity resolution for any future Organization row creation.

## Follow-up owner mapping decisions — Kokonut Farms (2026-10-07)

- Owner approves exact, unchanged preservation of `Project Summary`, `Local Problem`, `Proposed Solution`, and `Project Mission` in four separate `farm.metadata.legacy_source_fields` keys; do not merge them into `farm.description` or into one another.
- Owner approves exact, unchanged `Source of Funding` text in its own per-farm metadata key; it is descriptive text, not a Funding-record link. Owner defines `Start` as the farm operational start and approves exact source date-string preservation in a separate per-farm metadata key, not `farm.created_at`.
- These six mappings are `CANDIDATE` only. They do not add fields to the explicit allow-list or authorize projection/import.

## Follow-up owner semantic/schema proposal decision — Kokonut Farms.Species (2026-10-07)

- Owner confirms the relationship means species cultivated by a Farm and authorizes a repository-only typed Farm↔Crop relation proposal.
- Keep Farm.Species / Species.Projects held. The existing candidate Species field mapping in the projection allow-list remains unchanged, but it is not row import authorization; no name-based matching or Species-row import is authorized.

## Follow-up owner scope decision — Weekly Planning (2026-10-07)

- Owner excludes the entire Weekly Planning table from this migration because the legacy data is not robust. The original Budget Forecast blocker (register row 84) changed from `PURSUE` to `DROP`; the historical totals after that and Project Coordinates were 52 `DROP` / 32 `PURSUE`. Batch 37 later changes nine additional blocker decisions; current totals are 61 `DROP` / 23 `PURSUE`.
- Apply `EXCLUDE_OWNER` to all nine non-derived Weekly Planning fields and to every reciprocal edge to/from Weekly Planning, including links in F001, F002, Kokonut Farms, and Kokonut Farm Tasks. Keep the Baserow-computed Expenses Actuals field `EXCLUDE_DERIVED`.
- Preserve all Weekly Planning source rows and links in the controlled archive; do not delete source data, manually populate KI, or modify the allow-list. Other in-scope F001, F002, Farm, and Farm Task records remain independently scoped without their Weekly Planning edges.

## Batch 36 owner decisions — schema proposals and coordinates scope (2026-10-07)

- F002 `Expense Status`: owner confirms payment-settlement meaning and authorizes a repository-only proposal for a separate `expense_event.payment_status`; it must not map to workflow `expense_event.status`. Exact source option-ID mappings and final constraints remain unresolved.
- F002 `Personas Impactadas`: owner confirms a count of people per expense and authorizes a repository-only proposal for nullable nonnegative `expense_event.people_impacted_count`. Source-value validation remains unresolved; do not create person rows or governed metrics.
- Kokonut Farms `Species` / Species `Projects`: owner authorizes a repository-only typed Farm↔Crop relation proposal. Keep edges held until schema review and stable source Species→canonical crop identity resolution; Species-table import remains unauthorized.
- Kokonut Farms `Project Coordinates`: owner chooses `DROP`; exclude the field from KI projection/import and preserve only in the controlled source archive. Do not extract, geocode, or populate `farm.center`.
- Development Phases / Framework Steps: owner directs phases/steps to be reusable across farms/locations and authorizes a repository-only catalog/join proposal. Required ordering, step type, and any location-scoped instance/plot mappings remain unresolved; keep all affected source rows/edges held.
- These decisions do not implement SQL, alter the allow-list, authorize projection/import, or permit live, Staging, or production changes. See `docs/phase1-baserow-schema-proposal-batch36.md`.

## Batch 37 owner decisions — schema draft and scope (2026-10-07)

- Owner approves repository-only SQL draft migration 368 for the distinct expense payment-settlement field and nullable nonnegative people-count field. Exact Expense Status option mapping remains unresolved. Offline validation found 512 positive-integer people counts and 21 blank cells; the count field is a `CANDIDATE` with blanks mapped to `NULL`, still not import authorization.
- Owner approves the repository-only `farm_crop` SQL draft. Keep legacy Species rows and Farm↔Crop edges held until approved canonical crop identities are supplied; the existing candidate Species field mapping in the allow-list remains unchanged and does not authorize row import. No name matching or edge projection.
- Owner drops the entire Development Phases and Framework Steps source tables and every linked edge from this migration. Apply `DROP`/`EXCLUDE_OWNER` to all fields and reciprocal links, preserving the original source archive; farms, plots, tasks, equipment, and other endpoints remain independently scoped.
- Owner drops F002 `Authorized by` and Staff `Ground Expenses` edges from this migration. F002 expenses and Staff records remain independently scoped; do not populate workflow `approved_by`.
- This batch supersedes the earlier Phase/Framework reusable-catalog proposal and the earlier hold on the F002/Staff actor edges. No SQL is applied, no data is imported, and no Staging/production/allow-list changes are authorized.

## Batch 38 owner decisions — status preservation and Staff.Name scope (2026-10-07)

- Owner approves preserving each populated F002 Expense Status option label exactly in `expense_event.payment_status`, using stable source option IDs without normalization. Aggregate-only validation confirmed all 533 populated values resolve to five used option IDs and fit the draft column. This maps payment settlement only; it does not set workflow status or authorize import.
- Owner keeps Farm↔Crop edges held pending stable source Species-row → existing KI crop identity mapping; the existing candidate Species field mapping in the allow-list remains unchanged and is not row-import authorization.
- Owner drops Staff.Name from this migration and retains source content only in the controlled archive. Other Staff fields/records and F001 responsibility identity remain separately scoped; no display-name matching or PII import is authorized.
- No allow-list change, import, persistent database write, Staging/production action, or volume operation is authorized.

## Batch 39 owner scope decisions — residual blockers (2026-10-07)

- F001 `Actividad`: owner keeps the 13 extra single-select options and 11 multi-select rows held. The three previously approved exact mappings remain unchanged.
- F002 `Category`: the Batch 39 full-field DROP was the then-current decision and prohibited all Category projection at that time. It is superseded only for the exact source label `Labor` by the 2026-10-08 owner decision recorded above; all other labels and blanks remain held.
- Kokonut Farms `Species` and Species `Projects`: owner drops both reciprocal Farm↔Crop fields from this migration. Preserve all source rows and edges in the controlled archive; Species rows and their other fields remain independently scoped. Do not emit `farm_crop` edges.
- Species `Unit of Metric`: owner drops this field from this migration. This supersedes the earlier held metadata-path candidate; do not preserve it as a KI mapping or map it to an expected-yield unit. The paired density field remains excluded.
- These four field decisions changed the original blocker-register totals to 66 `DROP` / 18 `PURSUE` at that time. Batch 39 did not change the projection allow-list; subsequent expense-only repository changes are limited to the 2026-10-08 owner decision recorded above. No import or live/Staging/production operation is authorized.

## Batch 40 owner decision — F001 source-option schema proposal (2026-10-07)

- Owner authorizes a repository-only design proposal for a dedicated field to preserve exact F001 `Actividad` option IDs and labels, including multi-selections, in source order and without splitting activity rows.
- This proposal does not change the required canonical `farm_activity.activity_type`, approve an `other` fallback, implement SQL, alter the allow-list, or authorize projection/import. Keep the 13 additional options and 11 multi-selection rows held until a separate canonical-type policy is approved; the three existing exact mappings remain unchanged.
- The decision-register scope totals remain 66 `DROP` / 18 `PURSUE`. See `docs/phase1-baserow-activity-selection-schema-proposal-batch40.md`.

## Batch 42 owner decision — F001 multi-selection handling strategy (2026-10-07; historical)

- Owner selected the primary-type-per-pattern approach for the 11 F001 `Actividad` multi-selection rows: assign one primary canonical `farm_activity.activity_type` per each of the 10 distinct source-selection patterns and preserve every exact selected option ID/label/order in the proposed source-options field. Do not split activity rows.
- At that stage, specific primary values were pending. Batch 44 later assigns them deterministically by first selection in source order. No `other` fallback, allow-list change, projection, or import was authorized.

## Batch 43 owner decision — F001 source-preservation field (2026-10-07; historical)

- Owner directs creating a separate source-preservation field in the repository schema for F001 `Actividad`. Draft migration `schemas/postgres/369_baserow_activity_source_options.sql` adds nullable `farm_activity.activity_type_source_options JSONB` and constrains populated values to JSON arrays.
- The migration preserves source option IDs/labels/order as source-selection data. At that stage it did not assign primary types or clear the blocker; Batch 44 later resolved the mapping policy. No `other` fallback is approved.
- Migration 369 has not been PostgreSQL-rehearsed or applied. No allow-list change, source projection/import, persistent database, Staging, production, deployment, or volume operation is authorized. Scope remains 66 `DROP` / 18 `PURSUE`.

## Batch 44 owner decision — F001 canonical string mapping (2026-10-07)

- Owner approves mapping the 13 additional used Activity option IDs to their exact source metadata labels as new `farm_activity.activity_type` strings, without normalization. The three existing exact option-ID mappings remain unchanged.
- For multi-selection rows, owner approves the first selected option in source order as the primary canonical `activity_type` for each pattern. Preserve every selected option ID/label/order in `farm_activity.activity_type_source_options`; do not split rows.
- This resolves the F001 populated field-level mapping condition for the exact manifest-matched snapshot only. Unknown option IDs, changed snapshot/inventory, malformed selections, or target values over 100 characters remain fail-closed. Migration 369 passed an isolated disposable PostgreSQL rehearsal and is committed, but remains unapplied to persistent databases. The scope decision is recorded in Batch 45 below.

## Batch 45 owner decision — projection scope and F001 Staff edge exclusion (2026-10-08)

- Owner authorizes expanding the scratch projection allow-list to source fields/records already mapped and explicitly decided for this migration, including F001 activities. This is not blanket authorization for every `CANDIDATE`: unresolved, `PURSUE`, `CONDITIONAL`, `HOLD_*`, `EXCLUDE_OWNER`, sensitive, derived, and manual-curation fields remain excluded or quarantined.
- Owner excludes F001 `Responsable` and reciprocal Staff `KKN-F001` from this migration. Preserve the 267 reciprocal source edges in the controlled archive; do not resolve Staff identities or write `farm_activity_responsible_staff` rows. This does not exclude Staff records or unrelated Staff links by itself.
- Owner requests evidence-based review of the 51 F001 rows with blank `Actividad`; infer a type only where source-context evidence supports a deterministic mapping, and leave ambiguous rows quarantined rather than inventing a fallback. The referenced export is currently unavailable in the local workspace, so this review and any allow-list validation against that snapshot remain pending reattachment.
- This authorizes repository-local allow-list/projection work and isolated scratch rehearsal. The owner separately delegated backup/restore verification; it remains pending target/access review and has not been run. No Staging/production change, persistent schema/data write, or live import has been authorized. Original blocker-register totals remain 66 `DROP` / 18 `PURSUE`.

## Batch 36 technical resolution — Land Lots activity inverse (2026-10-07)

- Verified Baserow metadata pairs `F001.Plot of Land` with `Land Lots.KKN-F001 — Daily Report`; compared both linked-row edge sets in memory. Each side has 359 edges, with exact set equality and zero differences.
- The Land Lots field is an inverse validation of the existing owner-approved `farm_activity_plot` mapping. Emit each canonical edge once from F001; do not duplicate the relationship. Register row 70 remains `PURSUE` as the original scope choice, but its mapping blocker is resolved. No allow-list or import authorization was added.
