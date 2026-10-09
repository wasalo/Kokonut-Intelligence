# Value Stream Mapping (VSM)

Value-stream mapping analyzes the flow of value through the
**data → analytics → governance → publication** pipeline, identifying
waste (waiting, excess inventory, defects, conveyance) and the constraint
stage.

## How it works

- A generic `lifecycle_transition` ledger (`schemas/postgres/179_lifecycle_transition.sql`)
  records every 5-state lifecycle transition (`draft → submitted → verified →
  published → rejected`) via database triggers on the governed pipeline tables.
  Actor is optionally captured from the `kokonut.actor_id` / `kokonut.actor_type`
  session variables when the application or a Directus hook sets them.
- `services/analytics/value_stream.py` reads the ledger plus live status
  columns to produce the **current-state map**: WIP by stage (excess-inventory
  waste), draft→published lead time, first-time-through yield (defect waste),
  and a bottleneck ranking (constraint identification).
- Flow metrics (`governed_lead_time_days`, `first_time_through_yield_pct`,
  `rework_rate_pct`) are governed `metric_definition` rows computed by the
  metric engine as **draft** values; a human must verify them.
- Pipeline-wide KPIs (WIP by stage, event-bus delivery latency, dead-letter
  rate, ingestion first-time yield) are refreshable `dashboard_dataset` rows
  (`schemas/seeds/104_flow_dashboard_datasets.sql`).

## Usage

```bash
python3 -m services.analytics.value_stream current-state [--location-id UUID]
python3 -m services.analytics.value_stream wip [--location-id UUID]
python3 -m services.analytics.value_stream lead-times [--location-id UUID]
python3 -m services.analytics.value_stream fty [--location-id UUID]
python3 -m services.analytics.value_stream bottleneck [--location-id UUID]
python3 -m services.export.report_generator --type value_stream_map [--location-id UUID]
```

## Notes

- VSM stages are classified VA / NNVA / NVA in `value_stream.STAGES`.
- New governed tables that use the 5-state lifecycle should have a trigger
  added in `179_lifecycle_transition.sql` to keep lead-time analytics complete.
- The ledger is append-only and never updated by agents; `safety.py` still
  forbids agents from setting `verified`/`published`.
