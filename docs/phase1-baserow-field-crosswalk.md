# Baserow-to-KI field crosswalk (schema-only draft)

**Source:** owner-confirmed Baserow database `115056`; supplied JSON export.

**Status:** owner-reviewed with Batch 1–27 decisions/allocations recorded, including the owner-approved external grant-tranche model; migrations 359–367 were validated only in isolated scratch rehearsals. The Batch 25 scratch projection used only its previously approved allow-list. No additional source projection/import or live schema change is approved by this inventory.
**Scope:** no source row values are included. Mapping decisions use field definitions, current target DDL, and owner-confirmed semantics.

Every source field receives an explicit proposed mapping, exclusion, manual-curation, provenance, or hold disposition. Target columns are checked against current `schemas/postgres/*.sql`; conditions remain blocking until reviewed. The separate media rule is owner-directed: no bulk files, only individually selected manual intake if later needed.

## Owner-confirmed decisions (through 2026-10-06)

- Locations are in the Dominican Republic; `Province` maps to `location.region`. Use `Dominican Republic` as the country transform, but do not invent coordinates or boundaries.
- Farm and plot areas are in square meters. Preserve numeric values without conversion and set the corresponding `area_unit` to `square_meters`.
- For F001, keep `Activity Name` as a labeled note; map `Actividad` only when a single value matches a canonical activity type. Hold multi-select cases; do not split records.
- Batch 1 — F001 activity types: only `Riego`→`irrigation`, `Harvesting`→`harvesting`, and `Otros`→`other`; all other labels and all 11 multi-selection activity rows remain quarantined.
- Batch 1 — F001 scope/relations: store the source farm in optional `farm_activity.farm_id`, derive required `location_id` through that farm, and reject inconsistent farm/plot/location links. Preserve every plot edge in `farm_activity_plot`; populate legacy `farm_activity.plot_id` only for exactly one linked plot, otherwise leave it NULL. Map the one-per-populated-row Farm Task link to optional `farm_activity.farm_task_id` after stable source-row resolution.
- Batch 1 — F001 elapsed duration maps to `farm_activity.duration_minutes`, not `labor_hours`; source duration seconds convert exactly to whole minutes. Map the end date to `farm_activity.activity_end_date` with date-only semantics.
- Batch 1 — F001 `Responsable` means accountable/assigned staff, not labor allocation; preserve every edge in `farm_activity_responsible_staff` after Staff identity resolution.
- Batch 1 — F003 outputs are a distinct output entity linked through `farm_activity_output_activity`, not impact claims. Map name, description, and only safety-validated proof URLs; keep file attachments under manual curation and F004/Impact links held for later review.
- F002 amounts are actual payments in DOP; set `expense_event.currency = 'DOP'`. The `US$ Rate` is the DOP/USD rate associated with USD grant receipts; preserve the source value in the explicit source-field allowlist, but do not apply it to expense amounts or calculate USD totals without a tranche association and validated direction. `Expense Status` is not `expense_event.status`.
- `Harvest & Sales.Avg Sale Price` is forecast-only, with no realized sales; owner confirms DOP per production unit. Use the reviewed `Production Metric` unit and record currency in `crop_cycle.metadata.expected_price_currency = 'DOP'` because the schema has no typed expected-price currency column. Do not create a `sales_event`.
- Funding rows represent source-keyed received grant-round tranches. Owner confirms `Date` is the grant-round/program date, not a cash-receipt date, and each linked Organization is a funder/source. The approved typed mapping is `external_grant_tranche(program_name, program_date, location_id)` plus the `external_grant_tranche_funder` join; `location_id` is required but needs an owner-supplied per-tranche mapping. Keep Grant Amount and Crowdfunding Amount held, separate, and out of the target/allow-list until an exact accounting rule is supplied. Do not map the program date to `financial_transaction.transaction_date`, create duplicate representations, project Funding source rows, or import.
- Impact rows are work/evidence records, not formal impact claims. Do not create `impact_claim` rows; retain their source relationships for a later evidence/work-record mapping.
- New F004 metric definitions are welcome as reviewed proposals. Do not auto-create definitions from indicator text; each proposal needs a stable key, meaning, unit, data type, and sufficient context. Imported metric values remain `verified = FALSE`.
- Biofactory rows represent production batches. Batch creation remains conditional on required values being available; do not invent batch names, methods, or date semantics.
- 2026-10-06 — Owner approves `organization.org_type = 'other'` for any entity without a source-backed type. The source Organizations table has no type field, so this mapping applies to its 8 rows unless separate source evidence is reviewed; do not infer a type from display names or rely on the schema default `cooperative`. This mapping decision does not authorize canonical entity merges, row creation, or import.
- 2026-10-06 — Owner approves the `external_grant_tranche` and `external_grant_tranche_funder` schema draft for repository-only implementation and synthetic scratch validation. This does not authorize source-row projection or import; required tranche locations and canonical Organization identities remain unresolved.

## Batch 2 technical allocation — Departments, Job roles, and Staff role links (2026-10-05)

- Department names/descriptions map directly to `department.name` / `department.description`; job-role names/descriptions map to `job_role.name` / `job_role.description`.
- The source `Job roles.Department` and inverse `Departments.Job roles` links contain 31 identical edges. Twenty-five roles have one department, three roles have two departments, and one role has none. Because `job_role.department_id` cannot preserve every multi-department edge without choosing a primary department, migration 360 adds `job_role_department(job_role_id, department_id)` as the canonical many-to-many target. The existing scalar column is not used for this source relationship.
- The source `Staff.Job` and inverse `Job roles.Staff` links contain 9 identical edges; each of the 9 staff rows links to exactly one role. Map the canonical edge to `staff.job_role_id` and validate the inverse source links without inserting duplicate relationships. Staff identity and PII decisions remain separate blockers; this allocation does not approve staff-row creation or import.
- These are source-structure/target-model allocations only. Migration 360 passed isolated scratch schema and constraint checks; no source rows were projected or imported, and the migration remains branch-local.

## Batch 3 technical allocation — Farm Tasks (2026-10-05)

- `Title`, `Start`, `Duration in days`, `Actual end date`, and `Description` map to the corresponding `farm_task` columns. Aggregate validation found 66 distinct titles (maximum length 85), 6 parseable start dates, 7 nonnegative integral durations, and 1 parseable actual end date; no end date precedes a populated start date.
- `Project` maps to `farm_task.farm_id`; all 66 task-to-farm edges match the inverse farm links. Derive required `location_id` through the resolved farm and reject scope mismatches.
- Preserve all 56 directed Prerequisites edges in `farm_task_dependency(task_id, prerequisite_task_id)`. The source graph has no self-edges, cycles, or cross-farm edges; revalidate those conditions after stable identity resolution.
- Expenses map to `expense_event.farm_task_id`: 509 reciprocal edges, with at most one task per expense. Framework Steps map to `farm_task_framework_step(task_id, framework_step_id)`: 41 reciprocal edges. Daily Activity Report maps to `farm_activity.farm_task_id`: 182 reciprocal edges. Weekly Planning maps to `farm_task_weekly_plan(task_id, weekly_plan_id)`; the source currently has zero edges on both sides.
- `Quantity` and `Quoted Cost per Unit` map only to `farm_task.metadata.baserow_legacy.quantity` and `.quoted_cost_per_unit`. Preserve the source numbers as provenance; no quantity unit or cost currency is present, so do not treat them as typed yield or USD total cost.
- Owner approves mapping all seven source `Category` options (Agricultural Work, Components & Materials, Construction, Equipment, Infrastructure, Operations, Sustainability) to `farm_task.category = 'other'`, while preserving each exact source label at `farm_task.metadata.baserow_legacy.category_label`. Do not infer a more specific task subtype. `Required equipment` remains held because the target has no generic equipment relation and the source contains zero such edges.
- Formula/rollup fields remain excluded; task attachments remain manual curation. Migration 361 adds typed relations and scope checks; all 353 numbered PostgreSQL schema SQL files applied in the isolated scratch database, and synthetic edge/scope constraints passed in a rollback-only transaction. Scratch rows were rolled back and the container removed. This batch does not authorize source projection or import.

## Batch 4 technical allocation — Staff links and active flag (2026-10-05)

- Staff names are unique within these 9 source rows, but matching them to existing KI people still requires identity resolution. Keep `Name` conditional; do not use display-name equality as canonical identity. `Phone` and `Email` remain conditional PII fields (3 populated values each), and `Photo` remains manual curation. `Password` remains excluded without reading or reproducing values.
- `Active` is a Baserow boolean field serialized as strings in this export. A strict parser recognizes all 9 values (4 true, 5 false, zero null/unrecognized); map only to `staff.is_active`, never to `employment_status` or an inferred employment lifecycle.
- `Projects - Team` and inverse farm `Team` are exactly reciprocal: 10 staff↔farm edges across 9 staff and 4 farms. Migration 362 adds `farm_staff_member(farm_id, staff_id)`; do not infer team role, hire date, or staff location from membership.
- Staff `KKN-F001` and F001 `Responsable` are exactly reciprocal: 267 edges. Map once to the owner-approved `farm_activity_responsible_staff` relation; validate inverse equality and resolve Staff identities by stable source row keys.
- Staff `Ground Expenses` and F002 `Authorized by` are exactly reciprocal: 526 edges, at most one Staff per expense. `expense_event.approved_by` is a workflow UUID alongside `status`/`approved_at`, with no Staff foreign key; keep both source fields `CONDITIONAL` and do not populate that workflow actor from legacy data. If approved later, retain the exact source Staff row ID at `expense_event.source_raw.baserow_legacy.authorized_by_staff_source_row_id`; do not set expense status or claim KI verification/publication.
- Staff links to `F005 -- Resources Inputs` and `Ecosystem Branches` are empty on both sides. Retain explicit held targets at `staff.metadata.baserow_legacy.resource_input_source_row_ids` and `staff.metadata.baserow_legacy.ecosystem_branch_source_row_ids`; do not create unsupported resource/branch records.
- This allocation is structural only. Migration 362 passed an isolated scratch rehearsal after 354 numbered PostgreSQL schema SQL files were applied; a valid membership edge was accepted, duplicate pairs, duplicate source edges, and partial provenance were rejected, and rollback restored the membership, farm, staff, and location counts to zero. The scratch container was removed. No source row is projected or imported.
- Organizations (8 rows): all Name values are populated and unique within the source table (maximum length 28); Notes has zero populated values. Active is strictly parsed and maps true -> `active`, false -> `inactive` (5/3); no source value maps to `dissolved`. `organization.org_type` is required but absent from source; owner approves `other` for all 8 source rows without a source-backed type. Do not use the schema default `cooperative` or infer type from display name. Derive required `org_key` from the composite source identity; canonical identity resolution is still required, and this field mapping does not authorize row creation or import.
- Organization.Funding and Funding.Organization are exact reciprocals with 16 edges across 12 Funding rows and 7 linked Organizations. Keep both relationship fields held because Funding has no resolved canonical target FK/join; reconcile all edges by stable source row ID after target placement.

## Batch 8 technical allocation — impact/reference catalogs (2026-10-06)

- Aggregate-only review covered Impact Frameworks, Impact Dimensions, Forms of Capital, and SDGs: 8 rows and 14 fields. Seven of the eight rows have no source name, so they cannot satisfy the required target `name`; do not manufacture labels or identities. The one named framework row also has its description and URL; the other framework row is missing the required name. Its name has no exact case-insensitive match among the seven framework names in repository seed 023, which does not establish a new canonical identity or authorize a new record.
- The sole populated framework URL passes HTTP(S) URL parsing and fits `impact_framework.url VARCHAR(500)`. This is syntax/shape validation only; no network fetch was performed. The URL maps as a candidate with original text and row provenance, not as evidence that a framework is canonical.
- The two Impact Dimensions rows, two Forms of Capital rows, and two SDG rows have zero populated names; all Notes/Description values in those tables are empty. All six values across their Active fields parse strictly as false. If a record later has a validated name, carry the explicit `FALSE` value rather than using the schema default; currently no target row can be created. No source SDG-number field exists; do not infer `sdg_number` from absent names.
- Impact Dimensions↔Impact Frameworks links are empty on both sides (zero edges). Map both source fields once to the nullable `impact_dimension.framework_id` relation, preserving the empty edge set; do not duplicate the inverse or invent links.
- Seed 023 removes blank-name rows from these canonical reference tables before loading seed entries. Keep the unnamed source rows out of target projection. No schema migration was required; this batch changes only field-level candidate/relationship dispositions and row-level quarantine notes. No import is approved.

## Batch 9 technical allocation — EBF pillar and Ground Analytics references (2026-10-06)

- Aggregate-only review covered EBF and Ground Analytics: 4 rows and 6 fields. Both tables have zero populated Name and Notes values; all four Active values parse strictly as false. Do not invent source labels or create rows from flags alone.
- EBF Active maps as a field candidate to `ebf_pillar.status`: false → `inactive`, explicitly overriding the target's active default. The two EBF rows still cannot create pillars: the source has no names, `pillar_key`, or `sort_order`, while the target requires all three; repository seed 032 already defines seven canonical pillars, and no source identity can resolve to them.
- Ground Analytics remains held. The source only has Name/Notes/Active, with no populated labels/notes or event measurements, location, or date. `026_ground_analytics.sql` models concrete plant, water, disease, and irrigation records—not a generic Ground Analytics catalog—so do not coerce these rows into observation/program events.
- No schema migration was needed. The Active field mapping is candidate-only; all unresolved rows remain quarantined and no import is approved.

## Batch 10 technical allocation — technology hierarchy and provenance (2026-10-06)

- Aggregate-only review covered Digital Legos Tracker (2 rows / 8 fields) and Ecosystem Infra Stack (3 rows / 5 fields). All five source Name values are populated, but none exactly matches the single seeded roadmap, any of its three areas, or any of its three alternatives. Do not attach these records to the seed by resemblance.
- `technology_area.roadmap_id`, `technology_driver.area_id`, and `technology_alternative.driver_id` are required in the target hierarchy. The source has no roadmap/driver identity. Keep names, descriptions, status, and criteria held; the two populated source status values have one distinct label and zero exact matches to the allowed alternative maturity enum. The three Infra Stack Active values parse strictly as false, but false does not distinguish `technology_area.status = 'deprecated'` from another inactive meaning.
- Digital Legos Tracker contains one populated Contract value with 20-byte hexadecimal-address syntax; chain/network and deployment role are unknown. Allocate only to provenance path `technology_alternative.metadata.baserow_legacy.contract_source_value`, held pending hierarchy and semantic review. Its single populated URL parses as HTTP(S); allocate to `technology_alternative.metadata.baserow_legacy.source_url`, also held because no driver-resolved alternative row exists. These are provenance paths, not validated chain or canonical URL fields. Users and Criteria are empty and remain explicitly held without invented semantics.
- Ecosystem Infra Stack has one populated HTTP(S) URL, but `technology_area` has no URL or metadata field; do not copy it to linked child alternatives. The two source link edges are exactly reciprocal, but the target provides only the area→driver→alternative hierarchy and no direct area-to-alternative join. Keep both relationship fields held; do not fabricate drivers or flatten the hierarchy.
- No schema migration or target projection was performed. Unresolved technology records and edges remain quarantined; no import is approved.

## Batch 11 technical allocation — Ecosystem Branches and Kokonut Dependencies (2026-10-06)

- Aggregate-only review covered 4 rows and 7 fields. Ecosystem Branches has one populated Name and one blank Name, no Notes, two strictly parsed false Active values, and zero Owner edges; the inverse Staff relation also has zero edges. `kokonut_guild.name/status` are typed candidates only: no branch-to-guild semantics are approved, the target requires a unique `guild_key`, and it has no Staff foreign key. Keep every field/edge held and do not create a guild or infer an owner.
- Kokonut Dependencies has two rows and zero populated values across Name, Notes, and URL. The canonical schema has no generic dependency entity; task prerequisites and backcast milestone dependencies are domain-specific relations and are not valid substitutes for an ecosystem dependency catalog.
- No schema migration or target projection was performed. No source row is loadable from this batch; no import is approved.

## Batch 12 technical allocation — Equipment and F005 resource inputs (2026-10-06)

- Aggregate-only review covered 3 rows and 19 fields. The single Equipment row has only its table-scoped UUID populated; Name, Description, Category, Quantity, formulas, and all three source relationships are empty. The candidate `infrastructure_asset` requires `location_id`, `name`, and `asset_type`, none supplied here. Preserve Quantity only at `infrastructure_asset.metadata.baserow_legacy.quantity` if a row is later approved; no unit or count semantics support mapping it to capacity.
- Equipment↔Farm Task, Equipment↔Framework Step, and Equipment↔F005 relationships each have zero edges on both sides. Keep them held; do not invent required-equipment or resource joins.
- F005 has two rows with zero Name/Notes values, two strict-false Active values, and zero Expense/Staff/Equipment edges on both sides. The schema has no generic resource-input catalog; scheduler `task_resource` and actual-use models are not interchangeable with this source concept. No F005 target row or relationship is created.
- No schema migration or target projection was performed. Unresolved fields remain held/conditional; no import is approved.

## Batch 13 technical allocation — Funding Milestones and Milestones Outcomes (2026-10-06)

- Aggregate-only review covered 4 rows and 15 fields. Both tables have only table-scoped UUID provenance populated; every title, priority, date, description, URL, file, and relationship field is empty. All four source link fields have zero edges and their inverse fields are also empty.
- No generic external grant milestone entity is defined. `solution_funding_tranche` requires an internal `funding_case_id`, tranche number, and amount and represents conditional releases, not external grant milestones. Keep all Funding Milestones fields/edges held rather than coercing them into that model.
- Milestones Outcomes has no title, description, proof, file, or linked objective/milestone data. `stakeholder_outcome` is a separate impact concept requiring location and stakeholder-group context; do not map these empty source rows to it or to `impact_claim`. Keep proof files under the existing manual-curation policy.
- No schema migration or target projection was performed. No target rows are loadable; no import is approved.

## Disposition totals

- `CANDIDATE`: 68 fields
- `CONDITIONAL`: 29 fields
- `EXCLUDE_DERIVED`: 85 fields
- `EXCLUDE_SENSITIVE`: 3 fields
- `HOLD_FIELD`: 82 fields
- `HOLD_RELATIONSHIP`: 48 fields
- `MANUAL_CURATION`: 10 fields
- `PROVENANCE_ONLY`: 24 fields
- `RELATIONSHIP`: 40 fields

## Field-by-field inventory

### Biofactory (table ID `417033`; 4 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Product` (`3196795`) | `single_select` | `bio_factory_batch.batch_type` | `CONDITIONAL` | Owner confirms these are production batches. All 10 source options are used; only 1 option normalizes to an allowed target `batch_type` (used by 2 rows), while 9 lack an approved map. No option-level owner mapping has been approved. Keep the whole field conditional; the Farm Task `other` decision does not apply here. Target also requires `batch_name`, `production_method`, `production_start_date`, and `batch_summary`; source has no batch-name or production-method field. |
| `Notes` (`3196796`) | `long_text` | `bio_factory_batch.batch_summary` | `CONDITIONAL` | All 16 rows are populated (12 distinct notes; maximum length 53). Schema shape is plausible, but review content for summary suitability and sensitive material before mapping; raw notes were not emitted. Target also requires batch_name, batch_type, production_method, and production_start_date. |
| `Farm` (`3196876`) | `link_row` → `Kokonut Farms` | `bio_factory_batch.farm_id` | `RELATIONSHIP` | 16 forward edges: exactly one linked farm per batch across 2 source farms; all source farm IDs resolve within the 4-row Farm table. No reciprocal Biofactory link field exists on the source Farm table. Resolve the FK through the composite source-key crosswalk; other required batch fields remain incomplete. |
| `Date` (`3196878`) | `date` | `bio_factory_batch.production_start_date` | `CONDITIONAL` | Zero of 16 source rows have a Date value, so the required `production_start_date` cannot be populated. If dates are supplied later, confirm they mean production start; do not infer or fabricate dates. `batch_name` and `production_method` also have no source fields, and all other required batch conditions remain blocking. |

### Departments (table ID `305804`; 7 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2202748`) | `text` | `department.name` | `CANDIDATE` | Direct name mapping. |
| `Description` (`2202749`) | `text` | `department.description` | `CANDIDATE` | Direct description mapping. |
| `Job roles` (`2202750`) | `link_row` → `Job roles` | `job_role_department(job_role_id, department_id)` | `RELATIONSHIP` | Inverse of Job roles.Department; validate exact edge-set equality, then record each canonical pair once in the normalized join table. |
| `Staff count` (`2202751`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total projects count` (`2202752`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Active projects count` (`2202753`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Projects by staff ratio` (`2202754`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |

### Development Phases (table ID `326753`; 5 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2386671`) | `text` | `development_phase.phase_name` | `CANDIDATE` | All 4 names are populated and distinct. Target also requires `phase_order` and `location_id`; `phase_order` is absent from source. Baserow row `order` metadata is unique but is not a crosswalk field and is not approved as phase order. No source UUID field exists; preserve the composite source identity (source system/database/table/row), never display-name match. All 4 rows remain blocked until required order and location scope are resolved. |
| `Description` (`2386678`) | `long_text` | `development_phase.description` | `CANDIDATE` | All 4 descriptions are populated and distinct. This direct text mapping does not clear the required `phase_order`/`location_id` or source-identity blockers on the phase rows. |
| `Plot of Land` (`3136770`) | `link_row` → `Land Lots` | `development_phase.plot_id` | `RELATIONSHIP` | One exact reciprocal edge matches Land Lots.`Development Stage` (`3136769`). The linked plot resolves to one farm/location through the validated plot-farm relation; this is the only phase with a plot edge. Resolve by composite source row identity; the phase still lacks required `phase_order`. |
| `Kokonut Farms` (`3600215`) | `link_row` → `Kokonut Farms` | — | `HOLD_RELATIONSHIP` | Three exact reciprocal edges span 2 phase rows; one phase links to 2 farms in 2 different locations. Scalar `development_phase.farm_id` cannot preserve that relation, and `location_id` is required. Another phase has no Farm or Plot edge. Do not collapse farms, infer a location, or create a multi-scope target schema without review; keep all source edges held. |
| `Development Phase Step` (`3600224`) | `link_row` → `Framework Steps` | — | `HOLD_RELATIONSHIP` | Fourteen exact reciprocal edges: every Framework Step row links to exactly one phase, while each phase links to 3–5 steps. The current `framework_step` schema has no phase FK or join table; no typed target exists. Preserve both source fields; no target relation is approved or added. |

### Digital Legos Tracker (table ID `594502`; 8 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4810194`) | `text` | `technology_alternative.name` | `HOLD_FIELD` | Two names are populated, but neither exactly matches one of the three seeded alternatives. Target requires a `technology_driver`; source has no driver/requirement identity, and the driver depends on an area and roadmap. Do not match by resemblance or create an incomplete alternative. |
| `Notes` (`4810195`) | `long_text` | `technology_alternative.description` | `HOLD_FIELD` | Zero populated values; no canonical alternative can be created without the missing roadmap/area/driver hierarchy. |
| `Status` (`4810196`) | `single_select` | `technology_alternative.maturity_status` | `HOLD_FIELD` | Two populated values have one distinct label and zero exact matches to the target's allowed maturity enum. Keep held; do not infer a maturity state, recommendation, or lifecycle from the source label. |
| `Contract` (`4810203`) | `text` | `technology_alternative.metadata.baserow_legacy.contract_source_value` | `HOLD_FIELD` | One populated value has 20-byte hexadecimal-address syntax, but chain/network and deployment role are unknown. Preserve only at this namespaced provenance path if a driver-resolved alternative is later approved; do not treat it as a validated or typed contract address. |
| `Users` (`4810204`) | `number` | — | `HOLD_FIELD` | Zero populated values and no target user-count field or defined unit/scope. Keep explicitly held; do not infer users, adoption, or usage. |
| `Criteria` (`4810206`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no approved mapping to a measurable `technology_driver` criterion. Do not invent a driver or metric from this field. |
| `URL` (`4810207`) | `url` | `technology_alternative.metadata.baserow_legacy.source_url` | `HOLD_FIELD` | One populated value parses as HTTP(S). Preserve only at this provenance path if a driver-resolved alternative is later approved; it is not a canonical URL field or independent validation of the referenced resource. |
| `Ecosystem Infra Stack` (`4810479`) | `link_row` → `Ecosystem Infra Stack` | — | `HOLD_RELATIONSHIP` | Two edges are exactly reciprocal with the inverse source field. Target offers only area→driver→alternative, with no direct area-to-alternative join or source-backed driver; preserve the edge set in quarantine and do not fabricate hierarchy. |

### EBF (table ID `557322`; 3 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4470196`) | `text` | `ebf_pillar.pillar_name` | `CONDITIONAL` | Zero of two source rows has a name. The target also requires unique `pillar_key` and `sort_order`, neither of which exists in source; repository seed 032 already defines seven canonical pillars, but blank names cannot resolve source identity. No target rows are loadable. |
| `Notes` (`4470197`) | `long_text` | `ebf_pillar.description` | `CONDITIONAL` | Zero of two source rows is populated. A direct description target does not resolve missing pillar identity, required key, or order; do not create a pillar from this field. |
| `Active` (`4470198`) | `boolean` | `ebf_pillar.status` | `CANDIDATE` | Strict Boolean transform: both values are false, mapping to `status = 'inactive'` (the target check permits `active`/`inactive`). Set explicitly rather than inheriting the target's `active` default. This field mapping does not resolve pillar identity/key/order; no target rows are loadable. |

### Ecosystem Branches (table ID `594558`; 4 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4810871`) | `text` | `kokonut_guild.name` | `HOLD_FIELD` | One of two source rows has a name; the other is blank. `kokonut_guild.name` is only a typed candidate: a source “branch” is not approved as a guild, and the target also requires a unique `guild_key`. Do not create either row without a semantic mapping and stable identity rule. |
| `Notes` (`4810872`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no approved branch-to-guild semantics or canonical notes/purpose target. |
| `Active` (`4810873`) | `boolean` | `kokonut_guild.status` | `HOLD_FIELD` | Both values parse strictly as false, but target status is an unconstrained string defaulting to `active`; no source-backed transform to paused, deprecated, inactive, or another status is defined. Branch identity is unresolved. |
| `Owner` (`4810876`) | `link_row` → `Staff` | `kokonut_guild.metadata.baserow_legacy.owner_staff_source_row_ids` | `HOLD_RELATIONSHIP` | Inverse of Staff.Ecosystem Branches; zero edges on both sides. `kokonut_guild` has no Staff foreign key. Preserve source Staff row IDs only at this provenance path if a guild mapping is later approved; do not infer owners. |

### Ecosystem Infra Stack (table ID `594514`; 5 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4810331`) | `text` | `technology_area.name` | `HOLD_FIELD` | Three names are populated; none exactly matches the seeded roadmap or any of its three technology areas. `technology_area.roadmap_id` is required, and the source has no roadmap identity. Do not attach by resemblance or create incomplete areas. |
| `Notes` (`4810332`) | `long_text` | `technology_area.description` | `HOLD_FIELD` | Zero populated values; no canonical technology area can be created without the missing roadmap parent. |
| `Active` (`4810333`) | `boolean` | `technology_area.status` | `HOLD_FIELD` | All three values parse strictly as false, but the target permits only `active`/`deprecated`; false does not establish deprecation. The required roadmap parent is also unresolved. |
| `Digital Legos Tracker` (`4810480`) | `link_row` → `Digital Legos Tracker` | — | `HOLD_RELATIONSHIP` | Two edges are exactly reciprocal with the inverse source field. Target offers only area→driver→alternative, with no direct area-to-alternative join or source-backed driver; preserve the edge set in quarantine and do not fabricate hierarchy. |
| `URL` (`4816328`) | `url` | — | `HOLD_FIELD` | One populated value parses as HTTP(S), but `technology_area` has no URL or metadata field. Do not copy it onto linked alternatives because the source relationship is not a one-to-one URL assignment. |

### Equipment (table ID `305807`; 12 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2202783`) | `text` | `infrastructure_asset.name` | `CONDITIONAL` | Zero populated values. Target requires `name`, `asset_type`, and `location_id`; no source location relation is available, so the sole source row cannot be created. |
| `Description` (`2202784`) | `text` | `infrastructure_asset.description` | `CONDITIONAL` | Zero populated values. The candidate column is optional, but `infrastructure_asset` still requires `name`, `asset_type`, and `location_id`, none of which is supplied by this source row. |
| `Category` (`2202785`) | `single_select` | `infrastructure_asset.asset_type` | `CONDITIONAL` | Zero populated values and no used source options to map. Target `asset_type` and `location_id` are required; neither is supplied. |
| `Quantity` (`2202786`) | `number` | `infrastructure_asset.metadata.baserow_legacy.quantity` | `HOLD_FIELD` | Zero populated values. The target has capacity/capacity_unit, not an equipment-count field; with no defined unit or quantity semantics, retain only at this namespaced provenance path if a row is later approved. Do not map to capacity. |
| `Farm Specific Task` (`2202787`) | `link_row` → `Kokonut Farm Tasks` | — | `HOLD_RELATIONSHIP` | Zero source edges and zero inverse `Kokonut Farm Tasks.Required equipment` edges. The target has no generic equipment-to-task FK/join; do not add a relation or infer required equipment. |
| `Currently in use` (`2202788`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Scheduled start dates` (`2202789`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Currently scheduled` (`2202790`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Currently available` (`2202791`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `UUID` (`2365314`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Framework Steps` (`2437665`) | `link_row` → `Framework Steps` | — | `HOLD_RELATIONSHIP` | Zero source edges and zero inverse `Framework Steps.Required equipment` edges. No approved target association exists; do not create a generic equipment/step join. |
| `Resources Inputs` (`4453003`) | `link_row` → `F005 -- Resources Inputs` | — | `HOLD_RELATIONSHIP` | Zero source edges and zero inverse `F005.Equipment` edges. F005 has no generic resource-input target; preserve the empty relationship field as held. |

### F001 — Activity Report (table ID `322673`; 16 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Activity Name` (`4258323`) | `text` | `farm_activity.notes` | `CANDIDATE` | Owner approves preserving this as a labeled note; do not interpret it as an activity type. |
| `Start Date` (`2350133`) | `date` | `farm_activity.activity_date` | `CANDIDATE` | Date-only event mapping; validate timezone/date semantics. |
| `Actividad` (`2350134`) | `multiple_select` | `farm_activity.activity_type` for explicitly approved options | `CONDITIONAL` | Owner-approved exact option-ID map: `1811741`→`irrigation`, `2427447`→`harvesting`, `2144655`→`other`. All other option IDs remain held; quarantine all 11 multi-selection rows rather than splitting one report or guessing that a product label is a material. Aggregate: 204 populated activity rows (193 single-selection; 11 multi-selection). |
| `Activity Description` (`2350135`) | `long_text` | `farm_activity.description` | `CANDIDATE` | Direct descriptive text. |
| `Responsable` (`2350178`) | `link_row` → `Staff` | `farm_activity_responsible_staff.activity_id` + `staff_id` | `RELATIONSHIP` | Owner confirms this is accountable/assigned staff, not labor participants. Preserve every source edge (207 populated activities: 148 single-staff, 59 multi-staff; 267 total edges) using stable source table/row identity. These match Staff.KKN-F001 exactly; insert each canonical edge once. Quarantine edges until the referenced Staff row is canonically mapped; do not populate `labor_event`. |
| `Project` (`2350182`) | `link_row` → `Kokonut Farms` | `farm_activity.farm_id`; derive required `farm_activity.location_id` from the resolved farm | `RELATIONSHIP` | Owner approves optional activity `farm_id` and required location derived from that farm. Resolve by source row identity; reject missing/ambiguous farms and any farm/plot/location mismatch. |
| `UUID` (`2367977`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Created on` (`2367978`) | `created_on` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Duration` (`3135643`) | `duration` (`h:mm`) | `farm_activity.duration_minutes` | `CANDIDATE` | Owner confirms elapsed activity duration, not labor. Baserow stores duration values as seconds; source review found 228 populated values, all nonnegative integral seconds and exact multiples of 60. Convert exactly with `seconds / 60` to whole minutes; reject invalid/nonintegral-minute values and never map to `labor_hours`. A new typed column is defined in unapplied migration 359. |
| `Farms Individual Tasks` (`3143319`) | `link_row` → `Kokonut Farm Tasks` | `farm_activity.farm_task_id` | `RELATIONSHIP` | Owner confirms the activity is associated with its linked farm task. 182 populated activities have exactly one task link. Resolve by source table/row identity; quarantine until that task has a canonical mapping, and reject task/farm/location mismatches. New optional FK is defined in unapplied migration 359. |
| `Last modified` (`3143343`) | `last_modified` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Last modified by` (`3143344`) | `last_modified_by` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Plot of Land` (`3143346`) | `link_row` → `Land Lots` | `farm_activity_plot` for every source edge; `farm_activity.plot_id` only when exactly one plot is linked | `RELATIONSHIP` | Owner approves preserving all source edges in `farm_activity_plot`; set the legacy `plot_id` convenience column only for exactly one linked plot and leave it NULL for multi-plot activities. Snapshot: 359 edges (46 single-plot, 56 multi-plot, 153 none); all linked plots resolve to the activity's linked farm. Resolve by stable source identity and reject farm/plot/location mismatches. New association and consistency trigger are defined in unapplied migration 359. |
| `Weekly Planning` (`3179887`) | `link_row` → `Weekly Planning` | — | `HOLD_RELATIONSHIP` | No populated links occur in this snapshot (0/255 rows), so there are no current edges to allocate. Keep the schema-level relationship unresolved unless a later snapshot contains values or the owner requests a typed association. |
| `Activity End date` (`4258345`) | `date` | `farm_activity.activity_end_date` | `CANDIDATE` | Owner-approved typed activity end date. Snapshot: 39 populated ISO dates; all parse and none precede the paired start date. Preserve date-only semantics. New nullable column and start/end check are defined in unapplied migration 359. |
| `F003 — Activity Outputs` (`4270927`) | `link_row` → `F003 — Activity Outputs` | `farm_activity_output_activity` association | `RELATIONSHIP` | Owner approves a distinct activity-output association, not an impact claim. Record each edge once from F003 field `4270926`, validate reciprocity against this F001 field, and resolve both rows by stable source identity. Snapshot has 22 reciprocal edges; no name-based matching. Association is defined in unapplied migration 359. |

### F002 — Expenses (table ID `317575`; 22 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2305088`) | `text` | `expense_event.description` | `CANDIDATE` | Direct expense label. |
| `Expense Notes` (`2305089`) | `long_text` | `expense_event.notes` | `CANDIDATE` | Direct note; do not concatenate with Audit Notes without a rule. |
| `Entity` (`2305091`) | `link_row` → `Kokonut Farms` | `expense_event.farm_id` + `expense_event.location_id` | `RELATIONSHIP` | Owner approves typed farm scope. Migration 363 adds `expense_event.farm_id`; resolve the source farm by stable row identity and derive required `location_id` from the canonical farm. Migration 363 rejects farm/location mismatch and blocks farm reparenting while scoped expense or plan rows remain attached. All 533 source expenses have exactly one Entity farm link. |
| `Bank Account` (`2305190`) | `number` | — | `EXCLUDE_SENSITIVE` | Bank account identifier; exclude from batch migration and do not reproduce values in the crosswalk. |
| `Bank` (`2305191`) | `single_select` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Account Name` (`2305193`) | `text` | — | `EXCLUDE_SENSITIVE` | Bank account holder/name field; exclude from batch migration and do not reproduce values in the crosswalk. |
| `Archivos` (`2305208`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Date` (`2330113`) | `date` | `expense_event.expense_date` | `CANDIDATE` | Direct date mapping. |
| `Category` (`2330114`) | `single_select` | `expense_event.category` | `CONDITIONAL` | Technical exact-match candidate: source option ID `1775981` → `labor` (154 rows). The other 12 used options (373 rows) have no exact canonical match; keep them quarantined. Six rows have no Category. This partial match is not approved for projection, and the field remains conditional. |
| `Tasks` (`2330115`) | `link_row` → `Kokonut Farm Tasks` | `expense_event.farm_task_id` | `RELATIONSHIP` | Canonical expense-side FK; 509 reciprocal edges, at most one task per expense. Resolve by source row identity and require matching target location; migration 361 adds the FK and scope trigger. |
| `Authorized by` (`2350403`) | `link_row` → `Staff` | `expense_event.approved_by` (conditional) / provenance `expense_event.source_raw.baserow_legacy.authorized_by_staff_source_row_id` | `CONDITIONAL` | 526 exact reciprocal edges with Staff.Ground Expenses; at most one Staff per expense. `approved_by` is a workflow actor UUID with no Staff FK; keep held until its actor identity domain is confirmed. Do not populate `approved_by`, status, or `approved_at`; preserve only the source Staff row ID through the explicit provenance path if later approved. |
| `Monto a Depositar` (`2356443`) | `number` | `expense_event.amount` | `CANDIDATE` | Owner confirms these are actual payments in DOP; set `expense_event.currency = 'DOP'` and preserve the numeric amount without conversion. |
| `UUID` (`2357579`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Last modified` (`2382819`) | `last_modified` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Created on` (`2383620`) | `created_on` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Weekly Planning` (`3179929`) | `link_row` → `Weekly Planning` | `expense_event.weekly_plan_id` | `RELATIONSHIP` | Owner now directs mapping all 49 exact reciprocal edges: 48 same-farm pairs plus the single different-farm pair at the same Location. Resolve both endpoints and the expense farm by stable source row IDs; preserve the source farm and plan farm without coercion. For that one pair only, set `expense_event.weekly_plan_scope_exception = TRUE` with a nonblank reason. Migration 365 requires the explicit per-expense exception and continues to enforce identical location scope; it does not relax location checks globally. Insert each edge once from this canonical side and validate the inverse. |
| `US$ Rate` (`3932281`) | `number` | `expense_event.source_raw.baserow_legacy.usd_dop_rate` (source-record provenance only) | `PROVENANCE_ONLY` | Owner says this is the DOP/USD rate associated with USD grant receipts. Preserve only at this named JSONB provenance path; do not treat it as a per-expense exchange rate or calculate USD totals without a tranche association and validated direction. |
| `Expense Dollar Conversion` (`3932305`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Expense Status` (`4244464`) | `single_select` | — | `HOLD_FIELD` | No compatible payment-status column is defined on `expense_event`; do not map a payment status to governed `expense_event.status` (`draft/submitted/verified/published/rejected`). Preserve source-only pending a separate payment-status target. |
| `Personas Impactadas` (`4261434`) | `number` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Audit Notes` (`4420023`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Resources Inputs` (`4452998`) | `link_row` → `F005 -- Resources Inputs` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides; no generic resource-input target exists. Keep the relationship explicitly held rather than creating an empty association. |

### F003 — Activity Outputs (table ID `534165`; 9 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Deliverable Name` (`4258577`) | `text` | `farm_activity_output.output_name` | `CANDIDATE` | Owner approves a separate activity-output entity. All 18 rows have nonblank names; 17 distinct labels means source table/row identity, not display-name deduplication, must preserve row identity. Require normalized text within the target length. |
| `Description` (`4258578`) | `long_text` | `farm_activity_output.description` | `CANDIDATE` | 16 of 18 rows are populated and all 16 texts are distinct. Owner approves direct descriptive-text mapping. Do not reinterpret an output as an impact claim or metric. |
| `Proof Media` (`4258584`) | `file` | — | `MANUAL_CURATION` | 14 of 18 rows have file references. Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Proof URL` (`4258585`) | `url` | `farm_activity_output.proof_url` | `CANDIDATE` | Empty in all 18 rows. Owner approves the URL field only; file attachments remain manual curation. Project only absolute HTTPS URLs that pass URL-safety validation (no userinfo, query, fragment, or local/private host); quarantine unsafe/unsupported values and never emit URLs in reports. |
| `F004 - Activity Metrics` (`4258787`) | `link_row` → `F004 — Activity Metrics` | `farm_activity_reported_metric_output (reported_metric_id, output_id)` | `RELATIONSHIP` | Inverse side of the exact 14-edge F004 relation. Insert each edge once from the canonical F004 side, then validate this reciprocal list by stable output/metric source row identities. The association is a typed activity-output link, not an impact claim or a `metric_value.source_record_ids` substitute. Migration 364 defines the association table. |
| `Kokonut Farm Tasks` (`4258792`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `F001 — Activity Report` (`4270926`) | `link_row` → `F001 — Activity Report` | `farm_activity_output_activity` association | `RELATIONSHIP` | Canonical edge source for this reciprocal relation. Emit each source edge once and validate it matches F001 field `4270927`; resolve both endpoints by stable source table/row identity. Snapshot: 22 reciprocal edges across 14 of 18 outputs; four outputs have no activity edge and can remain unlinked output entities. Association is defined in unapplied migration 359. |
| `Impact` (`4455408`) | `link_row` → `Impact` | — | `HOLD_RELATIONSHIP` | Zero edges on this field and the inverse Impact field `4455407`; keep the schema-level relation held and do not attach an output to an `impact_claim`. |
| `UUID` (`4457703`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### F004 — Activity Metrics (table ID `534174`; 8 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Indicator` (`4258662`) | `text` | `farm_activity_reported_metric.indicator_label` | `CANDIDATE` | All 14 populated labels are distinct; none exactly matches a repository-seeded metric key or display name. Preserve each as a source-reported indicator label, not as `metric_definition.metric_key`; do not auto-create governed definitions or infer canonical semantics. Candidate for the dedicated unverified activity-output report record in migration 364 only. |
| `Value` (`4258663`) | `number` | `farm_activity_reported_metric.reported_value` | `CANDIDATE` | All 14 numeric values fit `NUMERIC(15,4)` exactly (source field allows two decimal places; maximum observed precision is four integer digits and two fractional digits). F004 has no unit or measurement-period field; migration 364 leaves `reported_unit`, `period_start`, and `period_end` nullable, with no inferred defaults. Store only as an unverified source-reported value, never as `metric_value` or a verified metric. |
| `F003 - Activity Outputs` (`4258786`) | `link_row` → `F003 — Activity Outputs` | `farm_activity_reported_metric_output (reported_metric_id, output_id)` | `RELATIONSHIP` | Exact reciprocal relation has 14 edges: each metric row links to exactly one output across 12 outputs (one output links to three metrics). Migration 364 defines a normalized many-to-many association, so records are not split if cardinality changes. Resolve both ends by stable source row identity, insert each edge once from this canonical F004 side, and validate the F003 inverse. This relationship does not assert a unique activity/location context or formal impact claim. |
| `Proof URL` (`4258788`) | `url` | — | `HOLD_FIELD` | Empty in all 14 rows; no approved field-level target yet. Keep held rather than inventing a metric-evidence destination. |
| `Proof Media` (`4258789`) | `file` | — | `MANUAL_CURATION` | All 14 rows have file references. Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Description` (`4453489`) | `long_text` | `farm_activity_reported_metric.reported_description` | `CANDIDATE` | All 14 descriptions are populated and distinct. Preserve as source-reported context on the dedicated report record; description is not proof, verification, or a formal impact claim. |
| `Impact` (`4455427`) | `link_row` → `Impact` | — | `HOLD_RELATIONSHIP` | Zero edges on this field and the inverse Impact field `4455426`; preserve the empty source relation and do not create an impact-claim link. |
| `UUID` (`4457707`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### F005 -- Resources Inputs (table ID `555496`; 7 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4452947`) | `text` | — | `HOLD_FIELD` | Zero populated values across both rows; there is no generic resource-input target/catalog, so no target entity can be created. |
| `Notes` (`4452948`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no generic resource-input target/catalog has an approved notes field. |
| `Active` (`4452949`) | `boolean` | — | `HOLD_FIELD` | Both values parse strictly as false, but no generic resource-input target exists to receive a status. Do not reinterpret as metered consumption or scheduler-resource status. |
| `Expenses` (`4452997`) | `link_row` → `F002 — Expenses` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (F005 and F002); no generic resource-input entity or expense join is defined. |
| `Staff` (`4453000`) | `link_row` → `Staff` | `staff.metadata.baserow_legacy.resource_input_source_row_ids` | `HOLD_RELATIONSHIP` | Inverse of Staff.Resources Inputs; zero edges on both sides. No generic resource-input target exists; retain source-row identities at this named path only if a compatible entity is later approved. |
| `Equipment` (`4453002`) | `link_row` → `Equipment` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (F005 and Equipment); no generic resource-input/equipment join is defined. |
| `UUID` (`4457701`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### Forms of Capital (table ID `487995`; 3 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`3844665`) | `text` | `form_of_capital.name` | `CANDIDATE` | Direct label target, but zero of two source rows has a name; target `name` is required, so neither source row can create a target record. |
| `Notes` (`3844666`) | `long_text` | `form_of_capital.description` | `CANDIDATE` | Direct optional description target; zero of two source rows is populated. |
| `Active` (`3844667`) | `boolean` | `form_of_capital.is_active` | `CANDIDATE` | Strict Boolean parse: both source values are false; map explicitly to `is_active = FALSE`, never the target default. No target row can be created without a name. `capital_key` and `sort_order` are optional and are not invented. |

### Framework Steps (table ID `331882`; 9 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Title` (`2437632`) | `text` | `framework_step.step_name` | `CANDIDATE` | All 14 titles are populated and distinct. Target requires `step_order`, `step_type`, and `location_id`; `step_order` is absent from source. Baserow row `order` metadata is unique but is not a crosswalk field and is not approved as step order. No source UUID field exists; preserve the composite source identity (source system/database/table/row), never title-match. All 14 rows are blocked until required order, type, location, and source identity are resolved. |
| `Duration in days` (`2437635`) | `number` | `framework_step.duration_days` | `CANDIDATE` | Empty in all 14 rows; target duration is nullable. Do not infer a duration. |
| `Description` (`2437636`) | `long_text` | `framework_step.description` | `CANDIDATE` | All 14 descriptions are populated and distinct. This direct text mapping does not clear the required order/type/location or source-identity blockers on the step rows. |
| `Required equipment` (`2437645`) | `link_row` → `Equipment` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Prerequisites` (`2437650`) | `link_row` → `Framework Steps` | `framework_step.prerequisites` | `CONDITIONAL` | Four source edges are internal to this table, with no self-links or cycles. The target is a JSONB array, not an FK; resolve every endpoint through the composite source identity before encoding target IDs. Do not match by title or use Baserow row order; no target rows/IDs are created by this mapping review. |
| `Development Phase` (`2729316`) | `link_row` → `Development Phases` | — | `HOLD_RELATIONSHIP` | Fourteen exact reciprocal edges; each of the 14 step rows links to one phase. KI has no `framework_step.development_phase_id` or phase-step join. Keep both source fields held until a typed target relation and phase/step identity are approved. |
| `Type` (`3167697`) | `single_select` | — | `HOLD_FIELD` | Empty in all 14 rows. Target `step_type` is `NOT NULL` with default `implementation`; do not use that default or infer a type from the title. No source value can currently satisfy the required target field. |
| `Farms Individual Tasks` (`2386682`) | `link_row` → `Kokonut Farm Tasks` | `farm_task_framework_step(task_id, framework_step_id)` | `CONDITIONAL` | Forty-one exact reciprocal many-to-many edges match the existing typed join. After deriving phase scope only from explicit Farm/Plot links, 21 edges connect tasks within the phase farm set, 18 connect tasks outside it, and 2 have no derivable phase farm/location. Keep the inverse field CONDITIONAL too; quarantine the 20 scope-unresolved edges and all dependent rows until scope and endpoint identity are resolved. |
| `Plot of Land` (`3918768`) | `link_row` → `Land Lots` | `framework_step.plot_id` | `RELATIONSHIP` | Resolve linked plot; derive location only from validated ownership. |

### Funding (table ID `554709`; 13 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Program` (`4446732`) | `text` | `external_grant_tranche.program_name` | `CANDIDATE` | Owner approved a source-keyed `external_grant_tranche` row for each received grant-round tranche, with a program name. All 12 Program values are distinct; keep each source row distinct and never merge by display name. The required per-tranche `location_id` still has no source mapping, so no tranche row is eligible for projection or import. Candidate is not import approval. |
| `Overview` (`4446733`) | `long_text` | — | `HOLD_FIELD` | Populated in 3/12 rows; text was not emitted. Migration 367 intentionally has no overview/description field. Review content before assigning a canonical destination; otherwise retain source-only. Do not map to `financial_transaction.description` without an approved cash-transaction representation. |
| `Organization` (`4446734`) | `link_row` → `Organizations` | `external_grant_tranche_funder(tranche_id, organization_id)` | `RELATIONSHIP` | Owner confirms linked Organizations are the funder/source of money; 16 exact reciprocal edges span 12 Funding rows and 7 Organizations, with up to 3 funders per tranche. Preserve every reciprocal edge and its composite source-edge identity. The join is typed, but endpoints remain unprojected until per-tranche locations and Organization identities are resolved; this relationship disposition is not import approval. |
| `Blockchain` (`4446791`) | `multiple_select` | — | `HOLD_FIELD` | Zero populated values. Do not map a future value to `payment_method`, currency, or chain by label alone; define the intended domain if values are supplied. |
| `Funding Proposal` (`4446799`) | `url` | — | `HOLD_FIELD` | Zero populated values. If supplied later, distinguish proposal provenance from evidence of a completed receipt; no canonical destination is approved. |
| `Grant Amount` (`4446800`) | `number` | — | `HOLD_FIELD` | Populated in 10/12 rows; all populated values are positive and have at most 2 decimal places. Owner confirms grant receipts are USD. Nine of these rows also contain `Crowdfunding Amount`; one contains Grant Amount only; 2 rows have neither amount, with no Crowdfunding-only rows. Owner directs keeping both amount fields held until an exact accounting rule is supplied; do not sum, choose, duplicate, or project them. Migration 367 intentionally excludes amounts and cash-transaction modeling. |
| `Impact Criteria` (`4447192`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no criteria text or formal impact claim is present to map. Keep the source field held rather than manufacturing a claim or verification record. |
| `Objectives` (`4447364`) | `link_row` → `Objectives` | — | `HOLD_RELATIONSHIP` | Zero source edges; the inverse Objectives.Funding field is also empty, so the reciprocal relationship is exactly empty. No funding-to-objective FK/join is approved for an external tranche; preserve the field definition and keep held until target semantics are defined. |
| `Funding Milestones` (`4447367`) | `link_row` → `Funding Milestones` | — | `HOLD_RELATIONSHIP` | Zero source edges; the inverse Funding Milestones.Source of Funding field is also empty. `solution_funding_tranche` models milestone-conditioned releases for an approved internal solution-funding case, not receipt of an external grant tranche. Do not force-map by label; hold pending an external grant milestone target. |
| `UUID` (`4457708`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | All 12 values are populated and unique within this source table. Retain as a table-scoped alternate provenance key, not as a canonical primary key. |
| `Crowdfunding Amount` (`4638640`) | `number` | — | `HOLD_FIELD` | Populated in 9/12 rows (7 positive, 2 zero); all 9 overlap rows with `Grant Amount`, whose field is also populated. Owner directs keeping both amount fields held until an exact accounting rule is supplied; do not add to Grant Amount, create a second transaction, or project this field. |
| `Date` (`4638641`) | `date` | `external_grant_tranche.program_date` | `CANDIDATE` | Owner confirms all 12 values represent a grant-round/program date, not a cash-receipt date. Store only in `program_date`; never map to `financial_transaction.transaction_date`. The required per-tranche `location_id` has no source location/link, so no row is eligible for projection or import. Candidate is not import approval. |
| `Results` (`4646240`) | `url` | — | `HOLD_FIELD` | Populated in 8/12 rows; URLs were not emitted. A results link is not automatically reviewed evidence or proof of receipt. Keep held pending content/access review and a compatible evidence destination. |

### Funding Milestones (table ID `554723`; 8 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Title` (`4446829`) | `text` | — | `HOLD_FIELD` | Zero populated values across both rows; no generic external grant milestone entity/target exists. Do not force-map the title to an internal funding tranche. |
| `Priority` (`4446830`) | `single_select` | — | `HOLD_FIELD` | Zero populated values and no used source options; no approved external grant milestone priority scale or typed target exists. |
| `Start Date` (`4446831`) | `date` | — | `HOLD_FIELD` | Zero populated values; no external grant milestone target or date semantics are established. |
| `End Date` (`4446833`) | `date` | — | `HOLD_FIELD` | Zero populated values; no external grant milestone target or date semantics are established. |
| `Description` (`4446834`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no generic external grant milestone description target exists. |
| `Source of Funding` (`4447366`) | `link_row` → `Funding` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (Funding Milestones and Funding). `solution_funding_tranche` requires an internal `funding_case_id` and amount, and models conditional releases—not this external grant milestone relationship. |
| `Milestones Updates` (`4447369`) | `link_row` → `Milestones Outcomes` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (Funding Milestones and Milestones Outcomes); no outcome entity or join is approved for this external grant context. |
| `UUID` (`4457711`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### Ground Analytics (table ID `482436`; 3 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`3796736`) | `text` | — | `HOLD_FIELD` | Zero of two source rows is populated and no canonical `ground_analytics` catalog table exists. The concrete observation/program tables in `026_ground_analytics.sql` require event meaning and location/date context absent from this source; do not infer an observation from a blank label. |
| `Notes` (`3796737`) | `long_text` | — | `HOLD_FIELD` | Zero of two source rows is populated. No standalone Ground Analytics description target exists; event-note fields require a resolved plant, water, disease, or irrigation record. |
| `Active` (`3796738`) | `boolean` | — | `HOLD_FIELD` | Both values are false, but there is no canonical entity/status target for this source catalog. Do not map to a measurement-event lifecycle or fabricate an event record. |

### Harvest & Sales (table ID `317638`; 28 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2305706`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Quantity Planted` (`2305707`) | `number` | `crop_cycle.metadata.baserow_legacy.quantity_planted` | `HOLD_FIELD` | Six rows contain a numeric value, but none has a paired `Planting Metric`. This named metadata path is a held preservation candidate only; do not project or interpret as expected yield, area, or plant count without units/semantics. |
| `Crops` (`2305709`) | `link_row` → `Species` | `crop_cycle.crop_id` | `RELATIONSHIP` | Nine exact reciprocal edges with Species.`Harvest Forecast` (`2305710`), exactly one Crop per source row. Resolve endpoints by source row identity and record each FK once. Crop-cycle rows remain outside the allow-list while plot cardinality and cycle identity are unresolved. |
| `Planting Metric` (`2305713`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Actual Production Quantity` (`2305714`) | `number` | `crop_cycle.actual_yield` | `CONDITIONAL` | Two rows contain a value; neither has a `Production Metric` unit. One row links to one Plot and the other to four Plots. Keep the yield conditional until its unit and one-cycle/plot allocation are source-backed. No actual harvest date is supplied; do not create a `harvest_event`. |
| `Production Metric` (`2305715`) | `single_select` | `crop_cycle.actual_yield_unit` only with a supported actual-yield value; `crop_cycle.metadata.baserow_legacy.expected_price_unit` for forecast price | `CONDITIONAL` | Three rows use two distinct unit labels, both within target `VARCHAR(50)`; preserve labels exactly without conversion. None of the two actual-production quantities has a unit. The three price+unit rows have no Plot edge, so zero source rows currently satisfy the required scalar Plot plus price-unit context. Do not populate `expected_yield_unit` from a price denominator or a quantity lacking a paired unit. |
| `Avg Sale Price` (`2305720`) | `number` | `crop_cycle.expected_price_per_unit`; `crop_cycle.metadata.expected_price_currency` | `CONDITIONAL` | Nine values fit target `NUMERIC(12,4)` and are nonnegative. Owner confirms forecast-only pricing in DOP per production unit, with no realized sales. Three rows have a `Production Metric` unit and all three have no Plot edge; the other six lack a unit. Therefore zero rows currently have both the required single Plot and price-unit context. Preserve DOP at `crop_cycle.metadata.expected_price_currency`; do not create a `sales_event` or split/duplicate source rows. |
| `Realized Total Sales` (`2305721`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Harvest Forecast Date` (`2730541`) | `date` | `crop_cycle.expected_harvest_date` | `CONDITIONAL` | Two forecast dates co-occur with Planting Date; both pairs parse and are ordered. Keep forecast-only; never treat as an actual harvest date. |
| `UUID` (`3142258`) | `uuid` | `crop_cycle.metadata.baserow_legacy.source_uuid` | `PROVENANCE_ONLY` | Nine populated values are unique within this source table. Preserve as table-scoped alternate provenance, not as the canonical target ID; resolve links by composite source system/database/table/row identity. |
| `Lots of Land` (`3142259`) | `link_row` → `Land Lots` | — | `HOLD_RELATIONSHIP` | Thirteen exact reciprocal edges with Land Lots.`Harvest Forecast` (`3142260`): among 9 source rows, 3 have no Plot, 4 have one, 1 has four, and 1 has five. `crop_cycle.plot_id` is one required scalar FK. Keep all edges held; do not drop links, select a primary Plot, or split/duplicate a source row without an approved cycle-allocation rule. |
| `Live quantity` (`3191600`) | `number` | `crop_cycle.metadata.baserow_legacy.live_quantity` | `HOLD_FIELD` | Six rows contain a numeric value. This named metadata path is a held preservation candidate only; no compatible typed inventory/live-plant measure or unit is established. Do not project. |
| `Planting Date` (`3196966`) | `date` | `crop_cycle.planting_date` | `CONDITIONAL` | Six of 9 rows are populated. Resolve one crop-cycle record and validate Plot/Crop/Location; the source has no direct one-row/one-Plot mapping for every record. |
| `Status` (`3418061`) | `single_select` | `crop_cycle.metadata.baserow_legacy.status_label` | `HOLD_FIELD` | Eight values use three labels; zero exactly match the schema-documented `crop_cycle.status` values. This named metadata path is a held preservation candidate only; do not project. Do not infer a lifecycle state or inherit the target default `planned`. |
| `Planted Plot of Lands` (`4039637`) | `number` | `crop_cycle.metadata.baserow_legacy.planted_plot_count` | `HOLD_FIELD` | All 9 rows contain a numeric value, with 3 distinct values. This named metadata path is a held preservation candidate only; do not project, treat as plot area, or use it to collapse/replace the linked Plot edges. |
| `Planting Density` (`4039813`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Bed Area` (`4039814`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Weeks to Maturity` (`4039815`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Planting Beds per Plot of Land` (`4040001`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Loss Rate` (`4040191`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Forecast per Bed` (`4040192`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Forecast per Plot of Land` (`4040206`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total based on Planted Plots` (`4040211`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total Forecast with Loss Rate` (`4040213`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Estimated Revenue` (`4040435`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Annual Harvests Capacity` (`4040755`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Annual Revenue Capacity` (`4040757`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Kokonut Farms` (`4042180`) | `link_row` → `Kokonut Farms` | `crop_cycle.metadata.baserow_legacy.farm_source_keys` | `PROVENANCE_ONLY` | Three exact reciprocal Farm edges; the target `crop_cycle` has no `farm_id`. Preserve the composite source Farm keys in metadata and derive required `location_id` from the resolved Farm for those rows. The other six rows have no direct Farm edge; their linked Plots resolve to one Farm each and location derives through that Farm. Direct Farm and Plot links never co-occur, so do not claim a per-row cross-check. All 9 rows resolve to one Farm and one Location through these explicit links. |

### Impact (table ID `554746`; 14 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4447195`) | `text` | — | `HOLD_FIELD` | Owner identifies this table as work/evidence records, not formal impact claims. Keep source-only; do not infer `impact_claim.claim_type` from the label. |
| `Work Description` (`4447196`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Impact Description` (`4447197`) | `long_text` | — | `HOLD_FIELD` | Owner identifies this as work/evidence material, not a formal impact claim; retain source-only pending an approved work/evidence target. |
| `Work Date Start` (`4447341`) | `date` | — | `HOLD_FIELD` | Preserve as source work-period data; no direct work/evidence target is approved. Do not use it to create an impact claim. |
| `Work Date End` (`4447342`) | `date` | — | `HOLD_FIELD` | Preserve as source work-period data; no direct work/evidence target is approved. Do not use it to create an impact claim. |
| `Impact Proof` (`4447352`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Impact URL` (`4447353`) | `url` | — | `HOLD_FIELD` | Preserve source-only until an approved work/evidence target and URL handling rule exist. |
| `Impact Verification` (`4447354`) | `long_text` | — | `HOLD_FIELD` | Preserve source-only; this text is not canonical verification and must not certify a claim or evidence. |
| `Kokonut Farms` (`4447373`) | `link_row` → `Kokonut Farms` | — | `HOLD_RELATIONSHIP` | Preserve the source link; do not create an `impact_claim` relationship. Resolve to a farm only if a work/evidence target is later approved. |
| `Impact Level` (`4453735`) | `single_select` | — | `HOLD_FIELD` | Preserve source-only; do not map to `impact_claim.claim_category` because the owner says these are work/evidence records. |
| `Impact Score` (`4453736`) | `rating` | — | `HOLD_FIELD` | Both source rows contain zero; there is no supported metric definition or unit, period, location, work description, or claim context. Keep held; do not write this rating as a `metric_value` or formal impact claim. |
| `F003 — Activity Outputs` (`4455407`) | `link_row` → `F003 — Activity Outputs` | — | `HOLD_RELATIONSHIP` | Zero edges on this field and the inverse F003 field `4455408`; preserve the empty relation and do not attach it to an `impact_claim`. |
| `F004 — Activity Metrics` (`4455426`) | `link_row` → `F004 — Activity Metrics` | — | `HOLD_RELATIONSHIP` | Zero edges on this field and the inverse F004 field `4455427`; preserve the empty relation and do not attach it to an `impact_claim`. |
| `UUID` (`4457716`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### Impact Dimensions (table ID `555533`; 4 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4453512`) | `text` | `impact_dimension.name` | `CANDIDATE` | Zero of two source rows has a name; target `name` is required, so neither source row can create a target record. |
| `Description` (`4453513`) | `long_text` | `impact_dimension.description` | `CANDIDATE` | Direct optional description target; zero of two source rows is populated. |
| `Active` (`4453514`) | `boolean` | `impact_dimension.is_active` | `CANDIDATE` | Strict Boolean parse: both source values are false; map explicitly to `is_active = FALSE`, not the target default. Both rows remain blocked by missing required names. |
| `Impact Frameworks` (`4453616`) | `link_row` → `Impact Frameworks` | `impact_dimension.framework_id` | `RELATIONSHIP` | Zero source edges on this field and the inverse `Impact Frameworks.Impact Dimensions`; target FK is nullable. Preserve the empty relationship set; never insert the inverse twice. |

### Impact Frameworks (table ID `555534`; 4 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4453515`) | `text` | `impact_framework.name` | `CANDIDATE` | One of two rows has a name, description, and URL together; the other has no name, while target `name` is required. The sole populated name has no exact case-insensitive match among seven repository-seeded framework names; do not merge or infer identity by name alone. No source Active field exists. Since target `status` defaults to `'active'`, explicitly set `status = NULL` for this mapping unless an owner-approved status transform is provided; do not infer lifecycle. |
| `Description` (`4453516`) | `long_text` | `impact_framework.description` | `CANDIDATE` | One of two rows is populated, co-occurring with the sole populated name and URL; the other row lacks the required name and cannot create a target record. |
| `Source` (`4453517`) | `url` | `impact_framework.url` | `CANDIDATE` | One of two rows is populated; the value passed HTTP(S) URL parsing and fits target `VARCHAR(500)`. Preserve the exact source text and row provenance; no network fetch was performed. |
| `Impact Dimensions` (`4453617`) | `link_row` → `Impact Dimensions` | `impact_dimension.framework_id` | `RELATIONSHIP` | Inverse of `Impact Dimensions.Impact Frameworks`; zero source edges on both fields. Record no edges and do not insert this inverse a second time. |

### Job roles (table ID `305803`; 9 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2202739`) | `text` | `job_role.name` | `CANDIDATE` | Direct role label. |
| `Description` (`2202740`) | `text` | `job_role.description` | `CANDIDATE` | Direct description mapping. |
| `Department` (`2202741`) | `link_row` → `Departments` | `job_role_department(job_role_id, department_id)` | `RELATIONSHIP` | Canonical source direction; resolve both endpoints by stable source row identity. Preserve all 31 edges, including three multi-department roles; do not select a primary department or collapse into scalar `job_role.department_id`. |
| `Staff` (`2202742`) | `link_row` → `Staff` | `staff.job_role_id` | `RELATIONSHIP` | Inverse of Staff.Job; validate exact edge-set equality and do not insert a second copy of the same staff-role edge. |
| `Staff count` (`2202743`) | `count` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total projects count` (`2202744`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Department name` (`2202745`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Active projects count` (`2202746`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Projects by staff ratio` (`2202747`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |

### Kokonut Dependencies (table ID `594507`; 3 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4810213`) | `text` | — | `HOLD_FIELD` | Zero populated values across both source rows; no generic dependency entity/target is defined. Do not infer a task prerequisite, funding dependency, or technology requirement from the table label. |
| `Notes` (`4810214`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no generic dependency record or associated target exists. Keep held rather than inventing a description or entity. |
| `URL` (`4810215`) | `url` | — | `HOLD_FIELD` | Zero populated values; no generic dependency target has a canonical URL field. Do not create a target record from an empty URL. |

### Kokonut Farm Tasks (table ID `305801`; 34 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Code` (`2202697`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Title` (`2202698`) | `text` | `farm_task.task_name` | `CANDIDATE` | Direct task label. |
| `Start` (`2202699`) | `date` | `farm_task.start_date` | `CANDIDATE` | Direct date mapping. |
| `Duration in days` (`2202701`) | `number` | `farm_task.duration_days` | `CANDIDATE` | Direct numeric duration. |
| `Project` (`2202703`) | `link_row` → `Kokonut Farms` | `farm_task.farm_id` | `RELATIONSHIP` | Resolve farm through the crosswalk; target location_id derives from validated farm location. |
| `Status` (`2202706`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Estimated end date` (`2202707`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Actual end date` (`2202708`) | `date` | `farm_task.end_date` | `CANDIDATE` | Direct actual-end date; validate completed/cancelled semantics separately. |
| `Autonumber` (`2202710`) | `autonumber` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Required equipment` (`2202711`) | `link_row` → `Equipment` | — | `HOLD_RELATIONSHIP` | No generic equipment target exists; source has zero linked edges. Keep held until Equipment receives a reviewed canonical asset mapping; do not infer `infrastructure_asset`. |
| `Category` (`2202712`) | `single_select` | `farm_task.category`; `farm_task.metadata.baserow_legacy.category_label` | `CANDIDATE` | Owner-approved transform: map every source option to canonical `other` and preserve its exact original label in the namespaced provenance path; do not infer a more specific task subtype. |
| `Is overdue` (`2202713`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Days overdue` (`2202714`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Days until end` (`2202715`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Prerequisites` (`2202716`) | `link_row` → `Kokonut Farm Tasks` | `farm_task_dependency(task_id, prerequisite_task_id)` | `RELATIONSHIP` | Preserve directed edges by stable source-row identity; reject self-edges, cycles, unresolved endpoints, and cross-farm edges. Source profile: 56 edges, no self-edges/cycles/cross-farm edges. |
| `Prerequisites OK` (`2202717`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Today` (`2202720`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Quantity` (`2305701`) | `number` | `farm_task.metadata.baserow_legacy.quantity` | `PROVENANCE_ONLY` | Preserve the source numeric value without interpretation; no quantity unit is supplied, and no typed task-quantity column exists. |
| `Quoted Cost per Unit` (`2305702`) | `number` | `farm_task.metadata.baserow_legacy.quoted_cost_per_unit` | `PROVENANCE_ONLY` | Preserve the source numeric value without conversion; no currency or unit is supplied. Do not map to total `estimated_cost_usd` or calculate a task total. |
| `Forecasted Budget` (`2305705`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Name of Project` (`2311692`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Expenses` (`2330116`) | `link_row` → `F002 — Expenses` | `expense_event.farm_task_id` | `RELATIONSHIP` | Inverse of F002 Expenses.Tasks; validate exact equality of all 509 edges and do not insert a duplicate relationship. Require resolved expense/task identities and matching location. |
| `Framework Steps` (`2386683`) | `link_row` → `Framework Steps` | `farm_task_framework_step(task_id, framework_step_id)` | `CONDITIONAL` | Canonical task-side inverse with the same 41 exact reciprocal many-to-many edges. Twenty edges remain scope-unresolved (18 outside the linked phase farm set; 2 without derivable phase scope). Quarantine those edges and dependent rows; do not insert pairs until both endpoints have stable source identity and scope is validated. |
| `Created by` (`2729976`) | `created_by` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Last modified by` (`2729977`) | `last_modified_by` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Last modified` (`2729978`) | `last_modified` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `UUID` (`2729987`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Daily Activity Report` (`3143320`) | `link_row` → `F001 — Activity Report` | `farm_activity.farm_task_id` | `RELATIONSHIP` | Inverse of F001 Activity Report.Farms Individual Tasks; validate exact equality of all 182 edges, one task per activity, plus farm/location consistency. |
| `Weekly Planning` (`3192504`) | `link_row` → `Weekly Planning` | `farm_task_weekly_plan(task_id, weekly_plan_id)` | `RELATIONSHIP` | Resolve by stable source row identity; the reciprocal Weekly Planning field is also empty in this snapshot. Migration 361 provides the typed join target. |
| `Development Phase` (`3600349`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Description` (`3919095`) | `long_text` | `farm_task.description` | `CANDIDATE` | Direct description mapping. |
| `Attachments` (`3919757`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Expenses Amount Pesos` (`3932246`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Expenses Amount Dollar` (`3932379`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |

### Kokonut Farms (table ID `305805`; 54 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Title` (`2202756`) | `text` | `farm.name` | `CANDIDATE` | Direct identity label; resolve duplicate/entity identity before insert. |
| `Farm Description` (`2202757`) | `long_text` | `farm.description` | `CANDIDATE` | Direct descriptive text. |
| `Start` (`2202759`) | `date` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Actual end date` (`2202761`) | `date` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Departments involved` (`2202763`) | `lookup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Team` (`2202766`) | `link_row` → `Staff` | `farm_staff_member(farm_id, staff_id)` | `RELATIONSHIP` | Inverse of Staff.Projects - Team; validate exact equality of all 10 edges and record each canonical pair once. No role, hire date, or staff location is inferred. Migration 362 defines the join target. |
| `Stage` (`2202767`) | `link_row` → `Development Phases` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Farm Individual Tasks` (`2202768`) | `link_row` → `Kokonut Farm Tasks` | `farm_task.farm_id` | `RELATIONSHIP` | Inverse of Kokonut Farm Tasks.Project; validate exact equality of all 66 edges and derive each task's required location from its resolved farm. |
| `Total Forecasted Budget` (`2202769`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Available budget (US$)` (`2202770`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Budget Spent %` (`2202771`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Active tasks` (`2202772`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Scheduled tasks` (`2202773`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Completed tasks` (`2202774`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total tasks` (`2202775`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Ground Expenses` (`2305092`) | `link_row` → `F002 — Expenses` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Sales Revenue` (`2305722`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Net Profit` (`2305723`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Land Size` (`2305728`) | `number` | `farm.total_area` | `CANDIDATE` | Owner confirms square meters; preserve the numeric value and set `farm.area_unit = 'square_meters'` without conversion. |
| `Forecasted Cost per Square Meter` (`2305729`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Sales Revenue per Square Meter` (`2305730`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Sales Profit per Square Meter` (`2305731`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Project Location` (`2307563`) | `link_row` → `Locations` | `farm.location_id` | `RELATIONSHIP` | Resolve the one linked location through stable source table/row identity. Snapshot profile: all 4 farm rows have exactly one location link; the full link audit found no dangling references. Owner-confirmed country/region transforms apply to the target location. |
| `Species` (`2308567`) | `link_row` → `Species` | `crop.metadata.baserow_legacy.farm_source_row_ids` | `HOLD_RELATIONSHIP` | Inverse of Species.`Projects` (`2308566`), with 32 exact reciprocal edges: 29 Species rows link one Farm, one links three Farms, and 13 have no Farm edge. This is a held source-row-ID path only; `farmer_crop` is keyed to `farmer_profile`, not `farm`, and source Farms cannot be equated with farmer profiles. `crop_cycle` requires plot/cycle context. Do not invent a Farm→crop relation or write the inverse twice. |
| `KKN-GEN-F001` (`2350183`) | `link_row` → `F001 — Activity Report` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Plot of Land` (`3136781`) | `link_row` → `Land Lots` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Weekly Planning` (`3180013`) | `link_row` → `Weekly Planning` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Project Coordinates` (`3790808`) | `long_text` | `farm.center` | `CONDITIONAL` | Parse and validate coordinate format and CRS; do not accept free text as geometry. |
| `Source of Funding` (`3790819`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Governance Mechanism` (`3790827`) | `single_select` | `farm.metadata.legacy_source_fields.governance_mechanism` | `CONDITIONAL` | Per-farm only, per owner direction. Preserve the source option label unchanged; do not infer a network-wide/DAO governance model. This is a namespaced JSONB path, not a typed SQL column. |
| `Token Allocation` (`3790828`) | `long_text` | `farm.metadata.legacy_source_fields.token_allocation` | `CONDITIONAL` | Per-farm only; retain as source text with provenance and do not infer a contract, token, or allocation policy. This is a namespaced JSONB path, not a typed SQL column. |
| `Public Goods Allocation` (`3790829`) | `number` | `farm.metadata.legacy_source_fields.public_goods_allocation` | `CONDITIONAL` | Per-farm only; preserve the numeric value and field label without inferring currency, percentage, denominator, or policy. This is a namespaced JSONB path, not a typed SQL column. |
| `Project Summary` (`3790836`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Local Problem` (`3790838`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Proposed Solution` (`3790843`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Target Market` (`3791643`) | `multiple_select` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Revenue Streams` (`3793659`) | `multiple_select` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Actual Expenses Pesos` (`3932533`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Actual Expenses Dollar` (`3932535`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Actual Cost per Square Meter` (`3932697`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Wiki Farm Page` (`3995099`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Youtube Playlist` (`3995117`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Harvest & Sales Forecast` (`4042181`) | `link_row` → `Harvest & Sales` | `crop_cycle.metadata.baserow_legacy.farm_source_keys` | `PROVENANCE_ONLY` | Exact inverse of Harvest & Sales.`Kokonut Farms` (`4042180`): 3 reciprocal edges. Preserve the composite source Farm keys at the cycle provenance path from the canonical Harvest & Sales direction; validate this inverse and do not write a second relationship. `crop_cycle` has no typed `farm_id`. |
| `Data Hub` (`4310844`) | `boolean` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Resources` (`4445349`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Project Mission` (`4445740`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Main Smart Contract` (`4445801`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `GitHub Repo` (`4445862`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Project Website` (`4445954`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Project Deck` (`4445958`) | `url` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Objectives` (`4447363`) | `link_row` → `Objectives` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Impact` (`4447374`) | `link_row` → `Impact` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `UUID` (`4457681`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Project Logo` (`4470134`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |

### Land Lots (table ID `410138`; 10 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`3136385`) | `text` | `plot.name` | `CANDIDATE` | Direct plot label. |
| `Description` (`3136386`) | `long_text` | `plot.description` | `CANDIDATE` | Direct descriptive text. |
| `Crops` (`3136389`) | `link_row` → `Species` | `crop.metadata.baserow_legacy.plot_source_row_ids` | `HOLD_RELATIONSHIP` | Inverse of Species.`Plot of Land` (`3136390`), with 2 exact reciprocal edges: two Species rows link one Plot each and 41 have no Plot edge. This is a source-row-ID preservation path only, not a typed crop-to-plot relation; `crop_cycle` requires a plot, crop, location, and cycle context. Keep held and do not create cycles from this association. If separately approved for retention, preserve each source edge once and treat this inverse as validation only. |
| `Size of Plot` (`3136681`) | `number` | `plot.area` | `CANDIDATE` | Owner confirms square meters; preserve the numeric value and set `plot.area_unit = 'square_meters'` without conversion. |
| `Development Stage` (`3136769`) | `link_row` → `Development Phases` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Kokonut Farms` (`3136780`) | `link_row` → `Kokonut Farms` | `plot.farm_id` | `RELATIONSHIP` | Resolve the one linked farm through stable source table/row identity. Snapshot profile: all 8 plot rows have exactly one farm link; reject unresolved farm or farm/location mismatches. |
| `UUID` (`3142090`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Harvest Forecast` (`3142260`) | `link_row` → `Harvest & Sales` | — | `HOLD_RELATIONSHIP` | Exact inverse of Harvest & Sales.`Lots of Land` (`3142259`), 13 reciprocal edges. The source side has 3 rows with no Plot, 4 with one, 1 with four, and 1 with five; a scalar required `crop_cycle.plot_id` cannot preserve the set. Keep both fields held until the source-row-to-cycle/plot allocation is approved; never insert the inverse twice. |
| `KKN-F001 — Daily Report` (`3143347`) | `link_row` → `F001 — Activity Report` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |
| `Framework Steps` (`3918767`) | `link_row` → `Framework Steps` | — | `HOLD_RELATIONSHIP` | Source link target is shown; define target FK/join through source row-ID crosswalk before load. |

### Locations (table ID `317635`; 8 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Municipality` (`2305684`) | `text` | `location.name` | `CANDIDATE` | Owner confirms all source locations are in the Dominican Republic; set `location.country = 'Dominican Republic'` as a reviewed transform. Validate place identity/slug uniqueness; do not invent geospatial data. |
| `Description` (`2305685`) | `long_text` | `location.description` | `CANDIDATE` | Direct text mapping. |
| `Projects` (`2307562`) | `link_row` → `Kokonut Farms` | `farm.location_id` | `RELATIONSHIP` | Reverse source link; each linked farm must resolve through the crosswalk. |
| `Location Photo` (`2350443`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Province` (`3255476`) | `text` | `location.region` | `CANDIDATE` | Owner confirms Province maps to KI `location.region`. |
| `Long Description` (`4403637`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `Flora & Fauna` (`4403838`) | `long_text` | — | `HOLD_FIELD` | No approved field-level target yet; explicit review required before load. |
| `UUID` (`4457680`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### Milestones Outcomes (table ID `554745`; 7 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Title` (`4447187`) | `text` | — | `HOLD_FIELD` | Zero populated values; no generic milestone-outcome target exists, and the source does not identify a stakeholder or operational outcome record. |
| `Description` (`4447188`) | `long_text` | — | `HOLD_FIELD` | Zero populated values; no generic milestone-outcome description target exists. Do not reinterpret it as an impact claim or stakeholder outcome. |
| `Output Proof` (`4447189`) | `url` | — | `HOLD_FIELD` | Zero populated values; no proof URL or compatible outcome/evidence destination is supplied by this row. |
| `Output File` (`4447191`) | `file` | — | `MANUAL_CURATION` | Zero file references. Bulk migration is excluded; any owner-selected item remains private, individually reviewed manual curation. |
| `Funding Milestones` (`4447368`) | `link_row` → `Funding Milestones` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (Milestones Outcomes and Funding Milestones); no external grant milestone target/join is approved. |
| `Objectives` (`4447379`) | `link_row` → `Objectives` | — | `HOLD_RELATIONSHIP` | Zero edges on both sides (Milestones Outcomes and Objectives); preserve as held rather than implying objective completion or outcome evidence. |
| `UUID` (`4457712`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### Objectives (table ID `554665`; 6 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Title` (`4446084`) | `text` | `objective.objective_name` | `CANDIDATE` | Zero of 2 source rows has a title; target `objective_name` is required. No Objective row can be created from this snapshot; do not invent a label or completion state. |
| `Description` (`4446085`) | `long_text` | `objective.description` | `CANDIDATE` | Direct description mapping. |
| `Date` (`4446086`) | `date` | `objective.target_date` | `CONDITIONAL` | Confirm source date means target/deadline, not creation/event date. |
| `Kokonut Farms` (`4447362`) | `link_row` → `Kokonut Farms` | `objective.location_id` | `RELATIONSHIP` | Resolve farm, then canonical location; funding/outcome links remain separate. |
| `Funding` (`4447365`) | `link_row` → `Funding` | — | `HOLD_RELATIONSHIP` | Zero edges on this side and Funding.Objectives; the reciprocal relationship is exactly empty. No external-tranche-to-objective FK/join is approved; retain as held. |
| `Milestones Outcomes` (`4447380`) | `link_row` → `Milestones Outcomes` | — | `HOLD_RELATIONSHIP` | Zero edges on this field and the inverse Milestones Outcomes.Objectives field; preserve the empty relation. No target row or join is created. |

### Organizations (table ID `554714`; 5 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`4446750`) | `text` | `organization.name` | `CANDIDATE` | Direct organization label; resolve identity before insert. |
| `Notes` (`4446751`) | `long_text` | `organization.description` | `CANDIDATE` | Direct descriptive text. |
| `Active` (`4446752`) | `boolean` | `organization.status` | `CANDIDATE` | Strict Boolean parse: true -> `active`; false -> `inactive`; null or unrecognized values stay held; never infer `dissolved`. All 8 source values were recognized (5 true, 3 false); source UUID remains provenance only. |
| `Funding` (`4446757`) | `link_row` → `Funding` | `external_grant_tranche_funder(tranche_id, organization_id)` | `RELATIONSHIP` | 16 exact reciprocal edges with Funding.Organization (12 Funding rows, 7 linked Organizations). Map each reciprocal source edge once using its composite source-edge identity. Parent tranche rows remain held until per-record location mapping; Organization identities remain unresolved. Relationship disposition is not import approval. |
| `UUID` (`4457710`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |

### SDGs (table ID `487994`; 3 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`3844662`) | `text` | `sdg.name` | `CANDIDATE` | Zero of two source rows has a name; target `name` is required. The source has no SDG-number field; do not infer a number or canonical identity from blank labels. |
| `Notes` (`3844663`) | `long_text` | `sdg.description` | `CANDIDATE` | Direct optional description target; zero of two source rows is populated. |
| `Active` (`3844664`) | `boolean` | `sdg.is_active` | `CANDIDATE` | Strict Boolean parse: both source values are false; map explicitly to `is_active = FALSE`, not the target default. Both rows remain blocked by missing required names. |

### Species (table ID `317629`; 21 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Name` (`2305620`) | `text` | `crop.name` | `CANDIDATE` | All 43 source names are populated and unique within Species. Two source names match, case-insensitively, names in the five-row static pilot crop seed; that seed insert omits `scientific_name`, so it cannot establish whether either pair is the same taxon. Do not merge or resolve identity by display name alone; keep those two row identities for canonical-catalog review. Runtime database was not queried. |
| `Scientific Name` (`2305621`) | `text` | `crop.scientific_name` | `CANDIDATE` | 20 values are populated and unique within the source table. Preserve exact source text; do not invent missing names or use display-name similarity as canonical identity. |
| `Harvest Forecast` (`2305710`) | `link_row` → `Harvest & Sales` | `crop_cycle.crop_id` | `RELATIONSHIP` | Exact inverse of Harvest & Sales.`Crops` (`2305709`), 9 reciprocal edges with one Crop per source row. The `crop_cycle.crop_id` FK represents this edge once; resolve by source identity and do not insert the inverse twice. Crop-cycle rows remain outside the allow-list pending Plot/cycle allocation. |
| `Image` (`2305724`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Projects` (`2308566`) | `link_row` → `Kokonut Farms` | `crop.metadata.baserow_legacy.farm_source_row_ids` | `HOLD_RELATIONSHIP` | 32 exact reciprocal edges with Kokonut Farms.`Species` (`2308567`): 29 Species rows link one Farm, one links three Farms, and 13 have no Farm edge. This named path holds source row IDs only; the target has no direct Farm→crop relation, and `crop_cycle` would assert a plot/cycle that this edge does not provide. Keep held; if separately approved for retention, preserve each edge once and do not duplicate the Farm-side inverse. |
| `Unit of Metric` (`2729828`) | `single_select` | `crop.metadata.baserow_legacy.unit_of_metric_label` | `HOLD_FIELD` | Six cells use three distinct option IDs, and all six co-occur with `Harvest Units Density in Square Meter`. Owner directed keeping this field and its paired density held. Preserve at this named path only; do not map to `crop.expected_yield_unit` or infer an expected-yield unit. |
| `Created by` (`3136312`) | `created_by` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Created on` (`3136313`) | `created_on` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Last modified` (`3136321`) | `last_modified` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Last modified by` (`3136322`) | `last_modified_by` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Plot of Land` (`3136390`) | `link_row` → `Land Lots` | `crop.metadata.baserow_legacy.plot_source_row_ids` | `HOLD_RELATIONSHIP` | 2 exact reciprocal edges with Land Lots.`Crops` (`3136389`): two Species rows link one Plot each and 41 have no Plot edge. This is a held source-row-ID path only, not a typed crop-to-plot relation. Do not create `crop_cycle` rows without a source-backed cycle allocation, plot, location, and cycle context; the inverse is validation only. |
| `GBIF Database` (`4033391`) | `url` | `crop.metadata.baserow_legacy.gbif_database_url` | `PROVENANCE_ONLY` | 20 populated URLs pass HTTP(S)/hostname syntax checks. Retain only as an external taxonomy-reference URL; no network fetch was performed and no crop identity or scientific name may be inferred from it. |
| `UUID` (`4033810`) | `uuid` | `crop.metadata.baserow_legacy.source_uuid` | `PROVENANCE_ONLY` | All 43 values are unique within Species. Retain as a table-scoped source identifier, not a canonical primary key; resolve links by the composite source identity. |
| `Type` (`4034223`) | `single_select` | `crop.crop_category` | `CANDIDATE` | All four source options have explicit case-normalized mappings that retain each category distinction: `3110859` Fruit → `fruit`; `3110860` Vegetable → `vegetable`; `3110861` Ornamental → `ornamental`; `3110862` Utility → `utility`. The last two are unused in this snapshot. Do not collapse them to `other`; migration 366 documents both as free-text category values on unconstrained `crop.crop_category VARCHAR(100)`. This technical candidate is not import approval, remains outside the projection allow-list, and does not resolve crop identity. |
| `Weeks to Maturity` (`4034419`) | `number` | `crop.growing_season_days` | `CANDIDATE` | Source unit is explicit (weeks): convert days = weeks × 7. All three populated values produce positive integer days; quarantine any invalid/non-integral/overflow value. This field mapping is not import approval and does not resolve crop identity. |
| `Harvest Units Density in Square Meter` (`4039538`) | `number` | `crop.metadata.baserow_legacy.harvest_units_density_per_m2` | `HOLD_FIELD` | 43 explicit numeric values: 40 are zero and 3 nonzero. Six rows have a `Unit of Metric`; two nonzero values have a unit and one nonzero value does not. Owner directed keeping this field and its paired unit held. Preserve only at this named held path; do not project or map to expected yield. The meaning of zero and any per-hectare conversion remain unresolved. |
| `Bed Area in Square Meter` (`4039545`) | `number` | `crop.metadata.baserow_legacy.bed_area_m2` | `HOLD_FIELD` | 43 explicit numeric values, 40 zero. `crop` has no typed bed-area column; `crop_cycle.area_planted` is cycle-specific and must not be populated from a Species catalog value. Preserve only at this named held path; do not project. |
| `Beds per Plot of Land` (`4039547`) | `number` | `crop.metadata.baserow_legacy.beds_per_plot` | `HOLD_FIELD` | 43 explicit numeric values, 40 zero; one value is fractional. KI has no typed `beds_per_plot` field, and the two Plot edges do not establish cycle scope for all Species rows. Preserve only at this named held path; do not project or infer planting density. |
| `Loss Rate %` (`4039670`) | `number` | `crop.metadata.baserow_legacy.loss_rate_percent` | `HOLD_FIELD` | 43 explicit numeric values, 40 zero. KI has no typed crop loss-rate field; retain the source percentage at this named held path pending semantic review. Do not infer a verified metric or project it. |
| `Forecasted Harvests Per Year` (`4040439`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Rollup` (`4042203`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |

### Staff (table ID `305802`; 23 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Code` (`2202721`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Name` (`2202722`) | `text` | `staff.name` | `CONDITIONAL` | Identity resolution required before person-record creation. |
| `Photo` (`2202723`) | `file` | — | `MANUAL_CURATION` | Excluded from batch migration; owner may select an individual item for private, reviewed intake later. |
| `Phone` (`2202724`) | `phone_number` | `staff.phone` | `CONDITIONAL` | PII; import only if explicitly needed and access-controlled. |
| `Email` (`2202725`) | `email` | `staff.email` | `CONDITIONAL` | PII; import only if explicitly needed and access-controlled. |
| `Job` (`2202726`) | `link_row` → `Job roles` | `staff.job_role_id` | `RELATIONSHIP` | Canonical source direction; resolve by stable source row identity and validate exact equality with inverse Job roles.Staff links. Staff identity remains a separate prerequisite. |
| `Department` (`2202727`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Projects - Team` (`2202729`) | `link_row` → `Kokonut Farms` | `farm_staff_member(farm_id, staff_id)` | `RELATIONSHIP` | Canonical source direction; preserve all 10 staff↔farm edges through stable source identities, validate the reciprocal farm.Team field, and record each pair once. No role, hire date, or staff location is inferred. Migration 362 defines the join target. |
| `Active projects` (`2202731`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Scheduled projects` (`2202732`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Completed projects` (`2202733`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Active tasks` (`2202734`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Scheduled tasks` (`2202735`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Completed tasks` (`2202736`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total projects` (`2202737`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Total tasks` (`2202738`) | `formula` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `KKN-F001` (`2350179`) | `link_row` → `F001 — Activity Report` | `farm_activity_responsible_staff.activity_id` + `staff_id` | `RELATIONSHIP` | Inverse of F001.Responsable; validate exact equality of all 267 edges and insert each canonical pair once. Resolve Staff identities by stable source IDs; do not map to labor allocation. |
| `Password` (`2350279`) | `password` | — | `EXCLUDE_SENSITIVE` | Never migrate credential/password field or value. |
| `Ground Expenses` (`2350404`) | `link_row` → `F002 — Expenses` | `expense_event.approved_by` (conditional) / provenance `expense_event.source_raw.baserow_legacy.authorized_by_staff_source_row_id` | `CONDITIONAL` | Inverse of F002.Authorized by; validate the 526-edge set and at most one Staff per expense. `approved_by` is a workflow UUID with no Staff FK. Do not populate workflow fields until the actor identity domain is confirmed; preserve the source Staff row ID only in the named provenance path if separately approved. |
| `Resources Inputs` (`4453001`) | `link_row` → `F005 -- Resources Inputs` | `staff.metadata.baserow_legacy.resource_input_source_row_ids` | `HOLD_RELATIONSHIP` | Source has zero edges on both sides; preserve stable source-row IDs only if later approved. F005 has no canonical resource target. |
| `UUID` (`4457693`) | `uuid` | `source crosswalk.source_uuid` | `PROVENANCE_ONLY` | Retain as table-scoped alternate provenance key, not as canonical primary key. |
| `Ecosystem Branches` (`4810877`) | `link_row` → `Ecosystem Branches` | `staff.metadata.baserow_legacy.ecosystem_branch_source_row_ids` | `HOLD_RELATIONSHIP` | Source has zero edges on both sides; preserve stable source-row IDs only if later approved. No canonical ecosystem-branch model is established. |
| `Active` (`8686938`) | `boolean` | `staff.is_active` | `CANDIDATE` | Strict boolean parse; all 9 serialized values are recognized with no null/unrecognized values. Map only to `is_active`, not `employment_status`. |

### Weekly Planning (table ID `415230`; 10 fields)

| Source field (ID) | Type / linked table | KI target candidate | Disposition | Rule / unresolved condition |
|---|---|---|---|---|
| `Week` (`3179881`) | `text` | `weekly_plan.plan_name` | `CANDIDATE` | All 8 labels are nonblank and within the target length; use only as the plan label. Do not parse or derive dates from the label; map the explicit Date Start/Date End fields separately. |
| `Notes` (`3179882`) | `long_text` | `weekly_plan.notes` | `CANDIDATE` | Direct note mapping. |
| `KKN-F001 — Daily Report` (`3179886`) | `link_row` → `F001 — Activity Report` | — | `HOLD_RELATIONSHIP` | Zero edges on both source sides in this snapshot; no activity↔plan association is allocated. |
| `KKN-F002 - Expenses` (`3179928`) | `link_row` → `F002 — Expenses` | `expense_event.weekly_plan_id` | `RELATIONSHIP` | Inverse of F002.Weekly Planning: validate all 49 reciprocal edges (48 same-farm pairs and one explicit cross-farm exception at the same location), including the single owner-authorized pair. Map once from the Expense side using stable row identities; validate that `expense_event.weekly_plan_scope_exception` and its reason are set only on the mismatched same-location pair. Migration 365 requires explicit per-expense exception metadata and preserves location consistency. |
| `Date Start` (`3179932`) | `date` | `weekly_plan.week_start` | `CANDIDATE` | Direct date mapping. |
| `Date End` (`3179933`) | `date` | `weekly_plan.week_end` | `CANDIDATE` | Direct date mapping. |
| `Kokonut Farms` (`3180012`) | `link_row` → `Kokonut Farms` | `weekly_plan.farm_id` | `RELATIONSHIP` | Resolve farm; target location_id derives from validated farm location. |
| `Budget Forecast` (`3180014`) | `number` | `weekly_plan.budget_forecast_usd` | `CONDITIONAL` | Confirm currency before USD mapping. |
| `Expenses Actuals` (`3180738`) | `rollup` | — | `EXCLUDE_DERIVED` | Baserow-computed/system field; recompute in KI where defined, otherwise retain only in restricted source snapshot. |
| `Farms Individual Tasks` (`3192503`) | `link_row` → `Kokonut Farm Tasks` | `farm_task_weekly_plan(task_id, weekly_plan_id)` | `RELATIONSHIP` | Inverse of Kokonut Farm Tasks.Weekly Planning; both source sides contain zero edges in this snapshot. |

## Use and review rules

- `CANDIDATE` means a plausible one-to-one column mapping, not permission to insert values.
- For required target slugs absent from the source (`location.slug`, `farm.slug`, `plot.slug`), generate a deterministic unique slug from the approved canonical name plus stable source identity; validate collisions before dry-run. Slugs do not replace the composite provenance key.
- Preserve farm-local governance/economic configuration in namespaced `farm.metadata` only; do not normalize across farms or apply it to Kokonut DAO/network policy. Keep the original field label/value and source provenance until a typed domain model is approved.
- `CONDITIONAL` and `RELATIONSHIP` require the stated enum/unit/identity/link validation; unresolved conditions block the affected rows.
- `HOLD_FIELD` / `HOLD_RELATIONSHIP` are explicit non-load dispositions until a target and semantic rule are approved; preserve source provenance and do not silently discard.
- `EXCLUDE_DERIVED`, `EXCLUDE_SENSITIVE`, and `MANUAL_CURATION` are not batch-loaded. Selected files can be provided and reviewed one at a time by the owner.
- The `source crosswalk.source_uuid` label is a proposed provenance attribute for the future crosswalk design, not an existing KI table/column. The source key remains `(baserow, 115056, source_table_id, source_row_id)`.
- Before dry-run, review every `CONDITIONAL`, `RELATIONSHIP`, `HOLD_*`, and any PII/financial data path. Do not infer missing units, dates, locations, currencies, framework order, verification, or lifecycle state.
