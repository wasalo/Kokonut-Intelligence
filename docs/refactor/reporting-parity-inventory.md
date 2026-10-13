# Native reporting and projection parity inventory

**Review date:** 13 October 2026  
**Status:** source inventory complete; domain, dashboard, and runtime parity remain open.

## Scope and decision

This maps the repository's existing reporting, projection, and named-query
surfaces so that parity work can be split by owned capability. It does not
declare every legacy report or SQL view a product requirement. The capability
owner must decide which outputs remain supported, who may see them, and what
reference fixture defines their behavior before a replacement or provider
retirement is accepted.

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
| Legacy dashboard datasets | [`dataset_refresh.py`](../../services/export/dataset_refresh.py), [`dashboard_dataset` schema](../../schemas/postgres/007_modeled_outputs.sql), [`017_dashboard_datasets.sql`](../../schemas/seeds/017_dashboard_datasets.sql) | Rows hold a free-form `query_sql`, refresh interval, status, location, and metadata. The seed defines five example datasets with hard-coded pilot UUIDs and `published` status. `--all` selects only rows with `status = 'active'`. | A refresh executes the stored SQL through `get_db()` without a source-level SELECT-only/schema allowlist or location parameter binding. It fetches every result row into memory, then discards the rows and stores only count, duration, status, error, and timestamp in metadata. It does not materialize a dashboard result. The five seeded `published` rows are not selected by `--all`. Treat this as an unresolved legacy execution surface, not as an accepted native dashboard provider. Review actual write permissions and runtime DB role before any refresh acceptance. |
| Evidence graph projection | [`services/graph_projection/query.py`](../../services/graph_projection/query.py), [`graph projection README`](../../services/graph_projection/README.md), [`evidence_lineage.py`](../../services/graph_projection/evidence_lineage.py) | A separate bounded lineage graph read with fixed edge types, active generation, public/internal audience, optional location filter, depth cap 5, node cap 500, and statement timeout. | This is evidence navigation, not a report/dashboard engine. Its own projection freshness, completeness, and domain lineage gates remain independent. |
| ClickHouse rollups | [`analytics-read-views-v2.md`](analytics-read-views-v2.md), [`sensor-projection.md`](sensor-projection.md) | Optional analytical event-store rollups and corrected read views have separate source and consumer contracts. | Known multi-block aggregate defects and unverified saved-query adoption mean ClickHouse parity/scale gates remain open. Do not count ordinary PostgreSQL views or graph projections as ClickHouse parity. |

The SQL tree contains hundreds of ordinary view definitions across domain
migrations. A view's existence does not establish that it is a dashboard
contract, that its measures are correct for a capability, or that it is safe
for a broad read role. Inventory and approve candidate views per report owner
instead of exposing the schema wholesale.

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
   fixed query-ID registry and a least-privilege read role. Do not expose or
   execute arbitrary stored SQL as part of console, Metabase, or SDK requests.
5. Only migrate a saved dashboard or report after output, authorization,
   lineage, refresh ownership, outage behavior, and rollback evidence pass for
   that slice. Keep Metabase optional and do not make it the canonical store.

## Current disposition

The three-card public reporting slice has bounded copied-fixture evidence.
Source mapping now distinguishes it from the 94 report snapshots, the single
typed public analytics query, the separate evidence graph, ClickHouse rollups,
and the legacy dynamic-SQL dashboard dataset mechanism. No test suite, stored
dashboard SQL, database, or runtime service was queried or changed for this
source review. Reporting and projection parity remains open until retained
capabilities are selected by owners and accepted against scoped populated
fixtures.
