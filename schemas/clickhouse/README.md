# ClickHouse Schemas

Analytical event store for time-series data. PostgreSQL is the canonical source of truth; ClickHouse is a write-only analytical mirror consumed by the `Exporter` (`--source clickhouse`).

## Application

`scripts/seed.sh` applies all `*.sql` files in filename order via `clickhouse-client --multiquery`. All statements are idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE MATERIALIZED VIEW IF NOT EXISTS`, `ALTER TABLE ADD COLUMN IF NOT EXISTS`).

There is no migration tracker — ClickHouse schemas are stateless and re-applied on every seed run.

## Tables

| Table | TTL | Purpose |
|-------|-----|---------|
| `events_raw` | 2 years | Generic time-series events |
| `wallet_events` | 2 years | On-chain wallet activity |
| `sensor_readings` | 1 year | IoT sensor data |
| `weather_events` | 2 years | Weather observations |
| `financial_events` | 2 years | Financial transaction mirror |
| `dlego_events` | 2 years | Digital Lego protocol usage |
| `remote_sensing_events` | 2 years | NDVI/NDRE/EVI/SAVI satellite observations |
| `attestation_events` | 2 years | EAS attestation records |

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

`events_raw` and `financial_events` are defined but have no Python writers yet.

## Security

Insert methods in `services/ingestion/base.py` validate table/column identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` to prevent SQL injection. Values are never interpolated into SQL.
