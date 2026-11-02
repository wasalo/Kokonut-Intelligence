# ClickHouse Schemas

Optional analytical event store for time-series data. PostgreSQL is the
canonical source of truth; ClickHouse is a rebuildable analytical projection
used by selected exporters and reports. It is not required by the Kernel base
or standard profile; select the analytics overlay only after its parity and
recovery gates are accepted.

## Application

For the legacy integration stack, `scripts/seed.sh` applies all `*.sql` files
in filename order through `clickhouse-client --database "$CH_DB" --multiquery`
(`CH_DB` defaults to `kokonut_analytics`). All bootstrap statements use
idempotent DDL. The Kernel candidate uses a separately selected analytics
overlay and does not make this seed step part of its base startup.

There is no migration tracker. Bootstrap DDL is re-applied on seed runs; table data and materialized rollups are persistent state. `IF NOT EXISTS` does not reconcile changed definitions. The selected database must already exist; never silently fall back to `default`.

Retention and legal holds are not configured in ClickHouse today. The interim
policy is **no automated pruning**. Fresh table definitions contain no TTL.
`011_retention_policy_no_prune.sql` is a manifest consumed by
`scripts/apply-clickhouse-retention.py`; the helper checks each table and runs
`REMOVE TTL` only where a table-level TTL still exists. This makes fresh
bootstrap and repeat application safe. Removing a TTL does not itself delete
rows; rows removed by an earlier TTL cannot be recovered by this change. The
legacy `scripts/seed.sh` uses this helper automatically. For a Kernel analytics
deployment, apply it to the selected project and database before enabling
ingestion, then verify the table definitions contain no TTL. For example, with
the candidate and analytics overlay selected, provide the matching Compose
project name and loaded secret environment:

```bash
source scripts/load-secrets.sh
python3 scripts/apply-clickhouse-retention.py \
  --compose-file docker-compose.kernel-candidate.yml \
  --compose-file docker-compose.kernel-analytics.yml \
  --project-name kokonut-kernel-dev \
  --service clickhouse --database kokonut_analytics
```

Use the actual project name selected by the profile planner. Do not pipe
`011_retention_policy_no_prune.sql` directly to `clickhouse-client`; ClickHouse
rejects `REMOVE TTL` when the table has no table TTL. Do not enable Analytics on
an older database until the helper has completed and the table definitions
have been verified. Any future retention must be configurable,
jurisdiction-aware, owner-approved, and preserve legal holds.

The network-disabled disposable check applies the full schema on the pinned
25.8 image, verifies fresh-install skip behavior, removes eight synthetic
legacy TTLs, replays the helper, and confirms an old-dated synthetic event
survives a merge ([evidence](../../docs/refactor/builds/2026-10-30-recovery/clickhouse-retention-no-prune-disposable.json)).

## Tables

| Table | Automated expiry | Purpose |
|-------|-------------------|---------|
| `events_raw` | None | Generic time-series events |
| `wallet_events` | None | On-chain wallet activity |
| `sensor_readings` | None | IoT sensor data |
| `weather_events` | None | Weather observations |
| `financial_events` | None | Financial transaction mirror |
| `dlego_events` | None | Digital Lego protocol usage |
| `remote_sensing_events` | None | NDVI/NDRE/EVI/SAVI satellite observations |
| `attestation_events` | None | EAS attestation records |

## Materialized Views

Pre-aggregated rollups for dashboard queries:

| View | Source | Granularity |
|------|--------|-------------|
| `mv_daily_event_counts` | `events_raw` | Daily event totals |
| `mv_hourly_sensor_stats` | `sensor_readings` | Hourly min/max/avg/count |
| `mv_daily_wallet_activity` | `wallet_events` | Daily tx count + value |
| `mv_monthly_financial_summary` | `financial_events` | Monthly financial totals |
| `mv_daily_weather_summary` | `weather_events` | Daily weather stats |
| `mv_monthly_wallet_unique_active` | `wallet_events` | Monthly unique wallets |
| `mv_daily_dlego_protocol_usage` | `dlego_events` | Daily protocol actions |
| `mv_dlego_value_by_location` | `dlego_events` | Monthly DL value |
| `mv_daily_sensor_summary` | `sensor_readings` | Daily sensor stats |
| `mv_sensor_reading_rate` | `sensor_readings` | Hourly reading rates |
| `mv_daily_remote_sensing_summary` | `remote_sensing_events` | Daily NDVI/EVI/SAVI |

## Regular Views

| View | Purpose |
|------|---------|
| `v_portfolio_location_activity` | Aggregated activity per location |
| `v_portfolio_monthly_evaluation` | Monthly revenue/expense/event counts |
| `v_portfolio_evaluation_summary` | Portfolio-level counts |
| `v_remote_sensing_freshness` | Time since last observation per location |

## Ingestion Writers

| Python Module | Target Table |
|---------------|-------------|
| `sensor_ingester` | `sensor_readings` |
| `mqtt_subscriber` | `sensor_readings` |
| `http_sensor_receiver` | `sensor_readings` |
| `weather` | `weather_events` |
| `weather_forecast` | `weather_events` |
| `rpc_indexer` | `wallet_events` |
| `gnosis_indexer` | `wallet_events`, `dlego_events` |
| `eas_indexer` | `attestation_events` |
| `subgraph_indexer` | `attestation_events` |
| `remote_sensing` | `remote_sensing_events` |
| `gee_remote_sensing` | `remote_sensing_events` |
| `copernicus_remote_sensing` | `remote_sensing_events` |

`events_raw` remains a defined sink without a native writer. `financial_events`
is enqueued atomically from PostgreSQL `sales_event` and `expense_event`
inserts by migration 434, then delivered by the optional ClickHouse outbox
worker. This preserves the legacy create-time projection while making outages
durable and keeping ClickHouse optional. Roll out the rebuilt Directus hook
with migration 434 before reopening financial writes to avoid duplicate
delivery from an older installed hook. The projection intentionally does not
pretend non-USD amounts are USD. Source updates/deletes, historical backfill,
and populated report-output parity remain separate gates.

## Security

Insert methods in `services/ingestion/base.py` validate table/column identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` to prevent SQL injection. Values are never interpolated into SQL.

## Corrected sensor read interfaces

Use `v_daily_sensor_summary_v2` and `v_sensor_reading_rate_v2` for finalized
sensor statistics. Legacy SummingMergeTree sensor summaries contain unsafe
non-additive statistics. Schema 007 creates new views without automatically
backfilling existing raw rows. See [migration and rollback](../../docs/refactor/sensor-rollups-v2.md).

Schema 008 adds correctness-first raw read interfaces for wallet distinct counts,
Digital Lego dimensions and remote-sensing statistics. See [interfaces and adoption](../../docs/refactor/analytics-read-views-v2.md).

**Recovery update:** sensor v2 failed crash-replay parity. Prefer `v_daily_sensor_summary_v3` and `v_sensor_reading_rate_v3` over raw rows; see [live recovery](../../docs/refactor/live-outbox-recovery.md).
