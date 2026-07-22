# Telemetry Infrastructure

Telemetry covers data collection, freshness monitoring, anomaly detection, and
analytics feeds for Kokonut Intelligence. PostgreSQL/Directus is canonical.
ClickHouse is an analytical mirror for selected streams, not an atomic second
database.

## Runtime Status

The repository contains several ingestion paths with different maturity and
storage semantics:

| Domain | Current implementation | Status |
|---|---|---|
| Weather | `services/ingestion/weather.py`, `weather_forecast.py` | Implemented API ingestion; PostgreSQL first, best-effort ClickHouse mirror |
| Sensors | CSV/CLI `sensor_ingester.py`, HTTP, MQTT | Implemented routes with separate write paths and lineage limitations |
| Remote sensing | `remote_sensing_fetcher.py`, GEE/Copernicus adapters | Job-based; one selected provider per job, no automatic provider fallback |
| Market data | `market_data.py` | Primarily PostgreSQL; source frequency is monthly for World Bank data |
| Direct EAS | `eas_indexer.py` | Chain-specific EAS Scan API path, separate from the legacy subgraph adapter |
| RPC governance | `gnosis_indexer.py`, `baal_indexer.py` | RPC-based governance/event indexing |
| Climate covariates | `climate_data.py` and GEE integrations | Implemented mixed sources; WorldClim values are currently approximations |
| Price oracle | Yahoo Finance, aggregator, attestation modules | Components exist, but production consensus and EAS submission are not fully wired |

Most ingestion jobs write PostgreSQL first and then attempt analytical writes.
ClickHouse errors are commonly logged as warnings, so PostgreSQL and ClickHouse
can diverge until a later reconciliation or refresh.

## Scheduling And Topology

The default worker remains cron-based through `config/worker/crontab`.
Prefect flows are an available orchestration layer, not a complete replacement
for cron. Do not run both schedulers for the same jobs during migration; the
worker Compose configuration explicitly warns about duplicate scheduling.

Base Compose keeps PostgreSQL and ClickHouse private. Inside worker containers,
use Compose service names such as `database` and `clickhouse`. Host execution
requires configured credentials and explicitly published ports; do not assume
that `localhost` database access works in the base development Compose setup.

## Ingestion And Storage

The ingestion layer records operational outcomes in `ingestion_log`. Relevant
canonical and analytical targets vary by source:

- Weather observations are stored in PostgreSQL and mirrored to ClickHouse on a
  best-effort basis.
- Sensor readings use PostgreSQL as the source of truth and may be mirrored to
  ClickHouse by CSV/API, HTTP, or MQTT paths.
- Climate and market data are primarily PostgreSQL-backed.
- Remote-sensing observations are stored in PostgreSQL and projected into
  ClickHouse freshness/summary structures.
- EAS and governance indexers write their own canonical event tables and may
  have separate ClickHouse projections.

This is not a transactional dual-write system. A successful PostgreSQL commit
does not guarantee a successful ClickHouse insert, and source implementations
do not all write to both stores.

## Freshness Monitoring

Freshness configurations are stored in `data_freshness_config`; each check is
persisted in `data_freshness_check` and summarized by
`v_data_freshness_summary`.

Run checks with:

```bash
python3 -m services.ingestion.data_freshness --check
python3 -m services.ingestion.data_freshness --check --source weather
python3 -m services.ingestion.data_freshness --summary
```

Statuses are determined from the configured stale and critical thresholds:

- `fresh`: gap is at or below the stale threshold.
- `stale`: gap is above stale and at or below critical.
- `critical`: gap is above critical.
- `no_data`: neither source data nor a successful ingestion-log timestamp is available.

The current source-to-table mapping uses these timestamp semantics:

| Logical source | Table | Timestamp used |
|---|---|---|
| `weather` | `weather_observation` | `observation_date` |
| `sensors` | `sensor_reading` | `created_at`, not necessarily the sensor reading timestamp |
| `remote_sensing` | `remote_sensing_observation` | `observation_date` |
| `market_data` | `price_observation` | Current code requests `observation_date`, although the canonical table uses `price_date`; failures fall back to ingestion logs |
| `eas_indexer` | `attestation_record` | `attested_at` |
| `rpc_indexer` | `wallet_activity_event` | `block_timestamp` |
| `gnosis_indexer` | `governance_event` | `block_timestamp` |

The configured source name must match `data_freshness_config`; it does not
always match the `ingestion_log.source_system` emitted by individual jobs. For
example, weather may log as `openweathermap`, direct EAS as `eas_api`, and
remote-sensing adapters as provider-specific names.

Although configurations include `location_scoped`, current freshness queries
are source-wide and insert check results with `location_id = NULL`. They do not
perform per-location freshness checks.

Stale and critical checks attempt alerts through:

- Webhook: `ALERT_WEBHOOK_URL`.
- Email: `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT`, `ALERT_EMAIL_FROM`, and `ALERT_EMAIL_TO`.

Inspect results with:

```bash
python3 -m services.ingestion.status log --source freshness
python3 -m services.ingestion.status indexers
python3 -m services.ingestion.status summary
```

## Sensors And Device Health

Supported collection routes include:

```bash
python3 -m services.ingestion.sensor_ingester --file readings.csv
python3 -m services.ingestion.sensor_ingester --sensor SENSOR_UUID --value 25.3
python3 -m services.ingestion.http_sensor_receiver --host 0.0.0.0 --port 8056
python3 -m services.ingestion.mqtt_subscriber --broker BROKER --port 1883
python3 -m services.ingestion.device_manager --list
python3 -m services.ingestion.device_manager --health --device-id DEVICE_ID
```

`v_sensor_device_health_summary` exposes device fields such as
`last_seen_at`, battery, signal strength, firmware, and reading rate. Device
health is derived from observed activity; the device manager does not actively
probe hardware. Current connectivity classification is approximately:

- Online when seen within one hour.
- Stale when seen within 24 hours.
- Offline after 24 hours without a sighting.

HTTP, MQTT, and mobile/offline paths do not all populate complete source
lineage or transform payloads into canonical field records. See
`docs/field-data-collection-guide.md` for implemented, partial, recommended,
and unimplemented field protocols.

## Remote Sensing

Create and run fetch jobs with:

```bash
python3 -m services.ingestion.remote_sensing_fetcher --location-id LOCATION_UUID --provider gee
python3 -m services.ingestion.remote_sensing_fetcher --list-jobs
python3 -m services.ingestion.remote_sensing_fetcher --run-jobs
```

Jobs select one provider and cadence. Supported job providers include `gee`,
`copernicus`, and schema-level `manual`; the CLI exposes the automated GEE and
Copernicus paths. A failed GEE job is not automatically retried through
Copernicus. Provider credentials and geometry prerequisites must be configured
for the selected adapter.

Providers:

- GEE: Google Earth Engine/Sentinel-2 server-side processing.
- Copernicus: Copernicus Data Space/Sentinel-2 direct download.
- Manual: a schema-supported job mode for externally supplied observations.

ClickHouse migration `schemas/clickhouse/006_telemetry_sync.sql` adds the
remote-sensing spectral indices, tasseled-cap values, raw bands, and
`source_system` fields. It also defines `v_remote_sensing_freshness` and
`mv_daily_remote_sensing_summary`. Sensor views are defined separately in
`schemas/clickhouse/003_sensor_views.sql`. Materialized views process inserted
rows and may require explicit backfill or refresh for historical data.

## Climate Data

Run climate ingestion with:

```bash
python3 -m services.ingestion.climate_data --worldclim --location-id LOCATION_UUID
python3 -m services.ingestion.climate_data --all --location-id LOCATION_UUID
```

The current data model includes:

| Table | Intended source | Purpose |
|---|---|---|
| `worldclim_climate` | WorldClim v2 model | Bioclimatic covariates; current implementation uses latitude-based approximations rather than fetched raster values |
| `ncep_weather_summary` | GEE climate product | Short-term climate covariates |
| `modis_lst_summary` | MODIS | Land-surface temperature |
| `smap_soil_moisture` | SMAP | Surface soil moisture |
| `sentinel1_sar_summary` | Sentinel-1 | All-weather SAR backscatter |

Do not represent the WorldClim path as a validated remote raster retrieval
until the implementation is replaced or independently verified.

## Anomaly Detection

Rule-based detection and ML detection are separate paths.

Rule and baseline checks:

```bash
python3 -m services.ingestion.anomaly_detector
python3 -m services.ingestion.anomaly_detector --sensor SENSOR_UUID
python3 -m services.ingestion.anomaly_detector --baseline-check
python3 -m services.ingestion.anomaly_detector --list-rules
```

Rules can cover values, rate of change, gaps, minimums, maximums, cooldowns,
baselines, notifications, and optional actuation. Critical actuation requires
approval according to the rule and safety configuration.

ML checks and training:

```bash
python3 -m services.ingestion.anomaly_detector --ml-check --location-id LOCATION_UUID
python3 -m services.ingestion.anomaly_detector --ml-train --location-id LOCATION_UUID
```

The ML path uses Prophet for eligible univariate sensor series and Isolation
Forest for eligible multivariate series. It requires sufficient recent data.
When dependencies are unavailable, `--ml-check` returns an error result; it does
not automatically fall back to rule-based detection. `--ml-train` saves models
under `models/ml_anomaly/`, but `--ml-check` currently fits models in memory and
does not load those saved pickle files.

## Prefect Flows

Run the full flow with:

```bash
python3 -m services.flows.pipelines full_pipeline
```

The implemented flow structure is:

1. Ingestion: weather, sensors, market data, direct EAS, RPC, and Gnosis flows
   run in parallel.
2. Monitoring: anomaly detection and freshness checks run after ingestion.
3. Analytics: metrics, dashboard refresh, and credit adjustment run after
   monitoring.
4. Remote sensing runs afterward as an independent longer-running flow.

The scheduled flows are:

- `scheduled-hourly`: sensors, anomaly detection, freshness.
- `scheduled-every-6h`: weather, dashboards, remote sensing.
- `scheduled-daily`: market data, metrics, credit adjustment.
- `scheduled-weekly`: climate refresh. The function description mentions ML
  retraining, but the current implementation only invokes climate ingestion.

These flows do not include every standalone ingestion module, including all
climate, Yahoo Finance, and remote-sensing variants. Deployment schedules live
in `config/prefect/deployment.yaml`; the worker cron remains the default
operational scheduler.

## Oracle Infrastructure

Oracle components are not a fully wired production price pipeline. The
available pieces include:

```bash
python3 -m services.ingestion.yahoo_finance
python3 -m services.ingestion.price_attestation --run-daily
```

The Python library provides multi-source aggregation helpers such as:

```python
from services.ingestion.oracle_aggregator import median_consensus, PriceReading
```

Current boundaries:

- `oracle_aggregator.py` provides reusable consensus functions; production
  wiring across all sources is not complete.
- Yahoo Finance supports the configured agricultural instruments, logs
  ingestion, and does not currently guarantee `price_observation` persistence.
- Price attestation prepares an audit path but does not currently submit a live
  EAS transaction; `attestation_uid` may remain unset.
- MQTT actuation remains subject to human-approval safety guardrails.

## Carbon Credits

Carbon-credit records are governed PostgreSQL records, not automatic token
minting. On-chain token fields are optional pointers and this service does not
perform minting.

Issuance requires verified/published climate-impact evidence and creates a
`draft` credit:

```bash
python3 -m services.analytics.carbon_credits \
  --issue --location-id LOCATION_UUID \
  --vintage-year 2026 --methodology "IPCC 2006 Tier 2"
```

Adjustment is conditional and only changes eligible verified/published credits
within configured margins:

```bash
python3 -m services.analytics.carbon_credits --adjust --location-id LOCATION_UUID
```

Retirement is a two-step human-reviewed flow. The first command reserves supply
and creates a draft retirement; `--requested-by` is required:

```bash
python3 -m services.analytics.carbon_credits \
  --retire --credit-id CREDIT_UUID --tonnes 5.0 \
  --reason voluntary_retirement \
  --requested-by REVIEWER_UUID --idempotency-key REQUEST_KEY

python3 -m services.analytics.carbon_credits \
  --confirm-retirement --retirement-id RETIREMENT_UUID \
  --reviewer-id REVIEWER_UUID
```

List and inspect balances with:

```bash
python3 -m services.analytics.carbon_credits --list --location-id LOCATION_UUID
python3 -m services.analytics.carbon_credits --balance --location-id LOCATION_UUID
python3 -m services.analytics.carbon_credits --check-adjustments --location-id LOCATION_UUID
```

Neither issuance, adjustment, nor retirement should be described as automatic
verification or autonomous on-chain settlement.

## Database And ClickHouse Objects

Important telemetry objects include:

| Object | Purpose |
|---|---|
| `data_freshness_config` | Source SLA thresholds and scope configuration |
| `data_freshness_check` | Persisted freshness outcomes and alert details |
| `v_data_freshness_summary` | Current freshness projection |
| `remote_sensing_job` | Provider, cadence, and fetch-job configuration |
| `sensor_device_health` | Device health observations |
| `v_sensor_device_health_summary` | Derived device-health view |
| `v_remote_sensing_freshness` | ClickHouse remote-sensing freshness projection |
| `mv_daily_remote_sensing_summary` | ClickHouse daily remote-sensing aggregate |
| `ingestion_log` | Operational source-to-target ingestion history |

The exact schema and materialized-view definitions are authoritative over this
summary. ClickHouse mirror failures and historical materialized-view backfills
must be handled operationally; they are not automatically repaired by the
canonical PostgreSQL write.

## Field Data Collection

See `docs/field-data-collection-guide.md` for field protocols, equipment,
sampling, QA/QC, and MRV reconciliation. That guide distinguishes implemented,
partial, recommended, and unimplemented workflows. In particular, do not infer
that every listed field protocol is fully canonicalized by the HTTP, MQTT, or
mobile/offline ingestion paths.

## Verification And References

- Freshness: `services/ingestion/data_freshness.py`
- Sensors and devices: `services/ingestion/sensor_ingester.py`, `http_sensor_receiver.py`, `mqtt_subscriber.py`, `device_manager.py`
- Remote sensing: `services/ingestion/remote_sensing_fetcher.py`, `gee_remote_sensing.py`, `copernicus_remote_sensing.py`
- Climate: `services/ingestion/climate_data.py`
- Anomaly detection: `services/ingestion/anomaly_detector.py`, `ml_anomaly_detector.py`
- Orchestration: `services/flows/pipelines.py`, `config/prefect/deployment.yaml`, `config/worker/crontab`
- Oracle: `services/ingestion/oracle_aggregator.py`, `yahoo_finance.py`, `price_attestation.py`
- Credits: `services/analytics/carbon_credits.py`
- Focused tests: `tests/test_telemetry_freshness.py`, `tests/test_prefect_workflow.py`, `tests/test_oracle_infrastructure.py`, `tests/test_carbon_credits.py`

These tests primarily validate structure, library behavior, thresholds, and
schema expectations. They are not a substitute for end-to-end validation of
external APIs, worker schedules, ClickHouse mirroring, EAS transactions, or
provider credentials.
