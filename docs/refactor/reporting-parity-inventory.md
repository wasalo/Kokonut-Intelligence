# Native reporting and projection parity inventory

**Review date:** 15 October 2026
**Status:** source inventory complete; domain, dashboard, and runtime parity remain open.

## Scope and decision

This maps the repository's existing reporting, projection, and named-query
surfaces so that parity work can be split by owned capability. It does not
declare every legacy report or SQL view a product requirement. The capability
owner must decide which outputs remain supported, who may see them, and what
reference fixture defines their behavior before a replacement or provider
retirement is accepted.

## Stakeholder review audience

The owner identified the common cross-lifecycle stakeholder review audience
for farms and natural assets as **liquidity providers, DAO members, guild
members, and the wider community**. Use these groups when organizing report
review and eliciting needs across design, financing, governance, operations,
verification, and stewardship.

This is a review-audience direction, not an access grant or a blanket public
classification. The 94 repository-registered report types remain in the
source inventory; the existing query-scope inventory is a review aid only.
For each report/dashboard, owners must still decide intended distribution,
organization/location scope, lifecycle and verification filters, measures and
time grain, redaction needs, and an accepted reference output. No report should
be exposed to a stakeholder group merely because that group belongs to the
common review audience. Populated reference outputs are deferred until the
owner's planned farm-data ingestion.

When review begins, capture one contract per retained report/dashboard with:
owner; lifecycle stage and decision supported; consulted stakeholder groups;
permitted viewers and tenant/location scope; source lifecycle/verification
filters; measures, units, and time grain; sensitive-field/redaction rules;
fixture identity and expected output; and human verification/publication
boundary. Keep the public curated aggregate API and its explicit allowlist as a
separate contract.

PostgreSQL remains canonical for governed records. The three curated
`kokonut_reporting` views and their three first-party Metabase cards are a
deliberately narrow public aggregate slice. They do not replace internal or
location-scoped reports. Metabase is an optional presentation adapter, not the
owner of calculations, authorization, lifecycle, or evidence.

## Current source surfaces

| Surface | Source of truth | Current scope | Boundary / remaining work |
| --- | --- | --- | --- |
| Public reporting views | [`377_kokonut_reporting_contract.sql`](../../schemas/postgres/377_kokonut_reporting_contract.sql) | Three versioned-by-migration aggregate views: farm summary, human-approved verified metric values, and Celo attestation summary. | Their database role and populated fixture/card outputs have scoped evidence. They are not a general per-user or tenant reporting API; keep the allowlist empty until metrics are explicitly approved. |
| Optional BI presentation | [`kokonut-reporting-cards.json`](metabase/kokonut-reporting-cards.json), [`metabase-reporting-contract.md`](metabase-reporting-contract.md) | Three Kokonut cards on one dashboard, backed only by the curated schema. The archived H2 board is generic demo content. | First-party card SQL matched copied populated fixtures. This is not parity for historical Metabase content, domain dashboards, or every capability report. |
| Native public API | [`services/gateway/router.py`](../../services/gateway/router.py), [`services/gateway/public_models.py`](../../services/gateway/public_models.py) | Versioned public location, metrics, CRISP, and location-summary reads. The metrics handler uses the analytics query port; CRISP and summary use their existing domain/read functions. | These routes are narrow public contracts, not generic report execution. Live payload and provider parity remain separate gates. |
| Typed analytics query port | [`services/analytics/queries.py`](../../services/analytics/queries.py), [`services/analytics/backend.py`](../../services/analytics/backend.py), [`postgres_analytics.py`](../../services/core/adapters/postgres_analytics.py) | The `QueryId` catalog currently contains only `public_metric_summary`, with a typed location request, explicit public context, parameterized SQL, a read-only transaction, and bounded statement/lock timeouts. | This is not yet a catalog for all of `services/analytics/`; domain CLIs/functions continue to own most calculations. Do not add caller-provided SQL or infer access scope from `AnalyticsContext`. |
| Governed report snapshots | [`REPORT_GENERATORS`](../../services/export/reports/__init__.py), [`report_generator.py`](../../services/export/report_generator.py), [`reports/context.py`](../../services/export/reports/context.py) | The registry maps 94 `report_type` keys across core, operations, wellbeing, state, strategy, commons, business-plan, process-health, and value-stream modules. `--type` and `--auto` generate snapshots; stored snapshots start as unfrozen `draft` records with a content hash. | Generation is not verification or publication. Snapshot list/detail in the operator console is a reviewer read path, not report generation, report-output parity, or a replacement for the State of Kokonut export. Each retained type needs an owner, scope, fixture, and acceptance decision. |
| Legacy dashboard datasets | [`dataset_refresh.py`](../../services/export/dataset_refresh.py), [`dashboard_dataset` schema](../../schemas/postgres/007_modeled_outputs.sql), [`017_dashboard_datasets.sql`](../../schemas/seeds/017_dashboard_datasets.sql) | Rows hold a free-form `query_sql`, refresh interval, status, location, and metadata. The seed defines five example datasets with hard-coded pilot UUIDs and `published` status. `--all` selects only rows with `status = 'active'`. | Stored SQL execution is behind `KOKONUT_FEATURE_LEGACY_DATASET_SQL`, default `false`; refresh commands now reject the disabled feature before opening the application connection, while listing remains available. When enabled, saved SQL runs only on the separately verified `kokonut_analytics_ro` login: it has SELECT access to the three curated views, no application-table access or write privileges, and no unreviewed security-definer functions. Execution uses a read-only transaction with 15-second statement and 3-second lock timeouts and returns only a row count. There is no source-level SQL parser/query-ID allowlist, location parameter binding, or durable result materialization; the view-role ACL is an effective relation allowlist, but it does not establish tenant scope for arbitrary saved SQL. The five seeded `published` rows are not selected by `--all`. Treat this as a bounded compatibility runner, not an accepted native dashboard provider. External consumer roles, retained query ownership, and runtime grants still need review. |
| Evidence graph projection | [`services/graph_projection/query.py`](../../services/graph_projection/query.py), [`graph projection README`](../../services/graph_projection/README.md), [`evidence_lineage.py`](../../services/graph_projection/evidence_lineage.py) | A separate bounded lineage graph read with fixed edge types, active generation, public/internal audience, optional location filter, depth cap 5, node cap 500, and statement timeout. | This is evidence navigation, not a report/dashboard engine. Its own projection freshness, completeness, and domain lineage gates remain independent. |
| ClickHouse rollups | [`analytics-read-views-v2.md`](analytics-read-views-v2.md), [`sensor-projection.md`](sensor-projection.md) | Optional analytical event-store rollups and corrected read views have separate source and consumer contracts. | Known multi-block aggregate defects and unverified saved-query adoption mean ClickHouse parity/scale gates remain open. Do not count ordinary PostgreSQL views or graph projections as ClickHouse parity. |

All 94 report calculations run with a session-level read-only default, and the
CLI ends calculation before writing a draft snapshot. A disposable PostgreSQL
probe found a mode-change/autocommit escape; the connection facade now blocks
autocommit changes directly and through `cursor.connection`. Direct DML fails
with SQLSTATE `25006`, rejected calculations leave no rows, and the post-
calculation draft write succeeds. The registry-wide invocation check also
caught and fixed a business-plan signature mismatch; its adapter supports a
single or explicit all-location scope. Nine focused unit tests, Ruff, Python
compilation, and the disposable check pass. The application connection remains
a writer, so this guard is not database-role isolation. Populated report output
parity remains open ([source evidence](builds/2026-10-15-recovery/report-generator-read-only-calculation.json);
[disposable evidence](builds/2026-10-15-recovery/report-generator-readonly-disposable.json)).

The source-only [generator inventory](report-generator-source-inventory.json)
now resolves all 94 registered report keys to their defining callable, source
file/line, and declared input names across 15 modules. All 94 signatures name a
`location_id` parameter and 93 name a period boundary. This is useful for
assigning later report fixtures, but a declared parameter does not prove the
calculation filters every query by that location. The AST-only generator and
its two focused tests pass without importing service modules or loading SOPS
configuration ([evidence](builds/2026-10-15-recovery/report-generator-source-inventory.json)).

A second AST-only [query-scope inventory](report-generator-query-scope-inventory.json)
now maps the direct `execute`/`query` calls in those generators. It finds 177
query sites: 126 show a bound location predicate, a `location.id` lookup, or
one of the recognized indirect location keys. The recognizer includes
attestation rows bound by `subject_type='location'` and a parameterized
`subject_id`, which correctly classifies the farm-summary attestation query.
Across report types, 34 have that signal for every direct query, 3 add it
conditionally when a location is supplied across 5 query sites, 16 mix scoped
and no-scope direct queries, 13
have no bound location scope visible in their direct SQL, and 28 issue no
direct query from the registered function. Twelve queries allow
`location_id IS NULL`, which may intentionally include shared reference rows.
The no-scope and mixed groups include possible network-level
reports, reference-data lookups, conditional fallbacks, and helper-mediated
reads; the scan cannot distinguish intended behavior from a scope defect.
All current direct query sites were resolved by the bounded literal, f-string,
string-join, and augmented-string rules. It records relation names and source
lines without retaining SQL text. Seven query-scope tests and two report-source
inventory tests pass with Ruff and generated-inventory checks, without importing
report services or loading SOPS. This is a review map, not an
authorization or RLS proof; helper call paths, view lineage, audience, and
populated semantic parity still need review against owner-approved contracts
and fixtures ([evidence](builds/2026-10-15-recovery/report-generator-query-scope-inventory.json)).

A third AST-only [helper-scope inventory](report-generator-helper-scope-inventory.json)
follows statically imported and same-module helper functions across the local
`services/` source tree. Across 94 report types, 34 have query sites reachable
through those helpers, producing 167 report-to-helper query-site memberships;
63 memberships show the scanner's location-scope signal. This membership count
is not a count of unique SQL statements because helpers can be reused. The
trace resolves simple import/assignment aliases and records source files,
relations, lines, and call paths without SQL text. It has no unresolved local
helper calls under its bounded resolver, but dynamic dispatch, external calls,
runtime branch selection, database/view lineage, and transitive authorization
are not proven. Several invalid relative imports in the strategy and core
report modules were corrected so their analytics helpers resolve to
`services.analytics` and `services.revenue_multiplier`; this source fix does
not establish report output parity or tenant isolation. The inventory is a
source-review map only ([inventory](report-generator-helper-scope-inventory.json)).

The SQL tree contains hundreds of ordinary view definitions across domain
migrations. A view's existence does not establish that it is a dashboard
contract, that its measures are correct for a capability, or that it is safe
for a broad read role. Inventory and approve candidate views per report owner
instead of exposing the schema wholesale.

## Populated archive metadata snapshot

A read-only transaction inspected aggregate metadata from the existing isolated
legacy PostgreSQL replay through migration 385. The encrypted source archive
checksum matched its retained manifest. No stored query text was returned or
executed, and the temporary network-disabled container was removed afterward.
The pre-existing recovery volume remains retained.

- The clone contains 43 `dashboard_dataset` rows: 41 `published` and 2
  `verified`. All have `query_sql` and an owner metadata field; there are 12
  distinct owner labels, which were not retained in evidence. Only 5 rows have
  a location, and none has refresh timestamp or last-refresh metadata.
- The 43 stored SQL fields have 11 `SELECT` keyword prefixes and 32
  `dashboards` keyword prefixes. Five rows contain a hard-coded UUID literal;
  none contains a recognized `%s` or `$n` bind placeholder. Prefix counts are
  not a SQL parser result: no query was validated or executed. The odd
  `dashboards` prefix needs source-format and owner review before the runner is
  considered usable.
- The repository CLI's `--all` selector targets `active`; it would select zero
  rows from this restored state. A caller can still request a specific dataset
  by ID, and the source code then executes its `query_sql` without status
  filtering. This makes the runtime query path a separate security gate.
- The archive contains three `report_snapshot` rows: two
  `dao_proposal_history` and one `state_of_kokonut`. All are unfrozen `draft`
  records and have no location. They do not demonstrate published-report
  parity or a location-scoped dashboard.

Sanitized aggregate results are retained in
[`reporting-archive-inventory.json`](builds/2026-10-13-recovery/reporting-archive-inventory.json).
No raw identifiers, query text, owner labels, or report payloads were retained.
A follow-up read-only review found no direct location or confirmed-tenant
lineage for the 38 unlocated dashboard definitions or three report snapshots;
they remain unassigned ([lineage review](builds/2026-10-13-recovery/reporting-tenant-lineage-review.json)).

## Report registry map

The current 94-key registry is grouped by implementation module below. This is
a source index only; it does not certify a report's output, schedule, access
policy, or continued product ownership.

| Module | Registered `report_type` keys |
| --- | --- |
| `reports/core.py` | `farm_summary`, `crop_noi`, `environmental`, `revenue_multiplier`, `forecast`, `climate_impact` |
| `reports/operations.py` | `pest_management`, `resource_efficiency`, `training_impact`, `revenue_streams`, `model_validation`, `livestock_feed`, `token_rewards`, `reward_calibration`, `organic_certification_readiness`, `organic_transition_progress`, `organic_input_audit`, `statement_of_work` |
| `reports/wellbeing.py` | `ebf_scorecard`, `holistic_wellbeing`, `financial_sustainability`, `risk_mitigation`, `scaling_roadmap`, `green_paper_publication_status`, `capital_efficiency`, `governance_throughput`, `dao_proposal_history` |
| `reports/state.py` | `capital_provider_utility`, `state_of_kokonut`, `state_of_kokonut_graphs`, `comprehensive_status`, `strategic_reserve` |
| `reports/strategy.py` | `data_stream_summary`, `business_model_canvas`, `pitch_deck`, `capability_dashboard`, `strategy_execution`, `capability_assessment`, `value_stream_formal`, `technology_roadmap`, `stakeholder_landscape`, `stakeholder_engagement`, `stakeholder_grievance`, `stakeholder_representation`, `stakeholder_decision_lineage`, `stakeholder_ecosystem`, `stakeholder_outcomes`, `stakeholder_trust`, `stakeholder_value_streams`, `stakeholder_cockpit`, `coordination_cockpit`, `governance_coordination_health`, `pestel_assessment`, `regional_readiness`, `publics_market_landscape`, `env_scan_report`, `fork_opportunities`, `pin_dependency`, `promotion_ladder`, `tactical_layer`, `simulation_wargame`, `capital_accounting` |
| `reports/commons.py` | `time_liberation`, `capital_alignment`, `governance_inclusion`, `land_stewardship`, `gnh_alignment`, `cultural_preservation`, `renewable_energy`, `vulnerable_access`, `foundational_wellbeing`, `regenerative_outcomes`, `community_governance`, `replication_readiness`, `adaptive_stewardship`, `scaling_economics`, `adoption_barriers`, `perpetual_value_stress`, `open_source_impact`, `anti_capture_governance`, `redistribution_policy`, `federation_mutual_aid`, `algorithmic_redistribution`, `participatory_signal`, `bio_factory_batch`, `bio_input_provenance`, `bio_recipe_library`, `bio_quality_test`, `bio_regional_input`, `ecological_modeling`, `trophic_pyramid` |
| `analytics/value_stream.py`, `analytics/process_health.py`, `business_plan.py` | `value_stream_map`, `process_health`, `business_plan` |

This registry provides one practical parity unit: one report type, a named
owner, one reference input/output fixture, expected lifecycle state, and a
rollback path. The `--auto` command runs all 94 types and is not by itself a
safe parity operation: empty reports can still be stored, expensive outputs
can be generated together, and all snapshots begin as drafts.

## Safe next slices

1. Read-only inventory of the populated archived dashboard/report definitions:
   stable IDs, dataset status, owner metadata, location scope, query fingerprints,
   and referenced relations. Do not execute stored SQL. Preserve private SQL in
   the encrypted evidence channel; publish only sanitized fingerprints and
   counts.
2. Have capability owners identify the report types and dashboards that remain
   required, their intended audience, source lifecycle filters, units, time
   grain, and independent human review boundary.
3. Prioritize small PostgreSQL-native contracts by owner. Compare each against a
   copied populated fixture and independent reference query; include empty,
   unauthorized, wrong-location, and date-boundary cases where applicable.
4. Decide the fate of `dashboard_dataset.query_sql` before enabling its worker:
   either retire it after saved consumers are reconciled, or replace it with a
   fixed query-ID registry and a least-privilege read role. The compatibility
   flag is an explicit temporary escape hatch, not query approval. Do not expose
   or execute arbitrary stored SQL as part of console, Metabase, or SDK requests.
5. Only migrate a saved dashboard or report after output, authorization,
   lineage, refresh ownership, outage behavior, and rollback evidence pass for
   that slice. Keep Metabase optional and do not make it the canonical store.

## Current disposition

The three-card public reporting slice has bounded copied-fixture evidence.
The source inventory distinguishes it from the 94 report types, the single typed
public analytics query, the separate evidence graph, ClickHouse rollups, and
the legacy dynamic-SQL dashboard dataset mechanism. The archive review queried
only aggregate metadata in a read-only transaction. No stored SQL was executed,
report generated, or source database changed for that archive review.
Reporting and projection parity remains open until retained capabilities are
selected by owners and accepted against scoped populated fixtures.
