# Field Collector downstream source audit

**Reviewed:** 13 October 2026
**Scope:** Repository-owned consumers of canonical `farm_activity` records and
Field Collector `offline_collection` rows. This is a static source audit; it is
not populated-runtime, external dashboard, or database-boundary acceptance.

## Eligibility contract

Migration 381 defines `v_mobile_collection_use_eligibility`, which evaluates
current form, participant-link, consent, and sync state for each collected
record. Migration 386 adds
`farm_activity_source_eligible_for_use(source_system, source_id, source_raw,
location_id)`: non-mobile farm activity retains its prior governance path,
while Field Collector activity fails closed unless its canonical source matches
an eligible collection. The trigger and lifecycle guards prevent ineligible
Field Collector drafts from being promoted or edited and prevent productive
lifecycle transitions while a record is ineligible. Private review paths may
still expose an ineligible record with its disposition reason.

## Repository-owned consumers

| Consumer | Source path | Gate |
| --- | --- | --- |
| Farm activity report aggregate | `services/export/reports/core.py` | Calls `farm_activity_source_eligible_for_use` and includes only published rows. |
| Generic exports and farm activity CSV export | `services/export/exporter.py`; `services/export/spreadsheet_bridge.py` | Add the shared predicate to farm activity reads. CSV import is a separate human import path. |
| Ecological and operating analytics | `services/analytics/ecology.py`; `services/revenue_multiplier/dimensions/value_added.py`; `services/fortune500/calculator.py` | Each farm activity query uses the shared predicate. |
| Data quality and lifecycle metrics | `services/analytics/data_quality.py`; `services/metrics/calculators/first_time_through_yield.py`; `services/metrics/calculators/governed_lead_time.py`; `services/metrics/calculators/rework_rate.py` | Filter farm activity samples/entities through the shared predicate. |
| Value-stream and process-trace analysis | `services/analytics/value_stream.py`; `services/analytics/process_mining.py` | Filter activity rows while building the entity set or traces. `process_gap.py`, `process_costing.py`, and `process_simulation.py` consume those traces. |
| Process-interface elapsed-time lookup | `services/analytics/process_interfaces.py` | The audit found a direct `farm_activity` lookup by ID without the predicate. It now adds the predicate when `source_type == 'farm_activity'`; other whitelisted entity types retain their existing lookup. |
| Gateway human review and lifecycle | `services/gateway/operator_mobile_review.py`; `services/gateway/farm_activity_workflow.py`; `services/gateway/farm_activity_lifecycle.py` | Collection queries join the eligibility view; canonical activity reads/writes use the shared predicate and retain reasoned private disposition access. |
| Directus hook aggregate and repository dashboards | `extensions/kokonut-hooks/src/index.ts`; `schemas/seeds/017_dashboard_datasets.sql`; `schemas/seeds/104_flow_dashboard_datasets.sql`; migration 386 | Repository-owned farm activity aggregates use the shared predicate; migration 386 repairs the two known dashboard queries and excludes Field Collector rows from Directus `farm_activity` reads. |
| Mobile transport and private collection operations | `services/analytics/mobile_offline.py`; `services/mobile/api.py` | These paths sync or privately inspect their own collection records; they do not publish or aggregate collected content as farm activity. The migration-381 eligibility view remains the downstream use authority. |

## Remaining boundary

This audit covers source-controlled consumers only. Migration 386 deliberately
does not rewrite unknown or operator-edited dashboard SQL. Migration 389 adds
tenant-aware checks to the database write triggers, but has not been replayed
or accepted. The archive review
found no direct location lineage for 38 dashboards and three report snapshots;
their business ownership, audience, and output parity remain open. Direct SQL
roles also do not receive universal row-level isolation from this predicate;
tenant context, least-privilege worker roles, and RLS remain separate gates.
No live provider, populated runtime, or external dashboard was exercised for
this source audit. See the [reporting parity inventory](reporting-parity-inventory.md),
[tenant boundary](mobile-tenant-isolation.md), and [execution checklist](batches.md).
