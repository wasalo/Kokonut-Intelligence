# Telemetry Infrastructure

Data collection, freshness monitoring, and ingestion pipeline for the Kokonut Intelligence platform.

## Architecture

```
External Sources
├── Weather (OpenWeatherMap API)
├── Sensors (CSV / MQTT / HTTP push)
├── Remote Sensing (GEE / Copernicus / CSV)
├── Market Data (World Bank)
├── Climate Data (WorldClim / NCEP / MODIS / SMAP / Sentinel-1)
├── Blockchain (Ethereum RPC / Gnosis / EAS)
└── GIS (GeoJSON / KML)

Ingestion Layer (services/ingestion/)
├── Dual-write: PostgreSQL (canonical) + ClickHouse (analytics)
├── Ingestion logging (ingestion_log)
├── Data freshness monitoring (data_freshness_config + data_freshness_check)
└── Anomaly detection (alert_rule + sensor_alert)

Analytics Layer
├── Materialized views (ClickHouse)
├── CRISP risk scoring (services/crisp/)
├── SOC prediction (services/analytics/)
└── Portfolio views
```

## Data Sources

| Source | Script | Frequency | Automation |
|--------|--------|-----------|------------|
| Weather | `weather.py` | 6 hours | Automatic |
| Sensors | `sensor_ingester.py` | 5 minutes | Semi-automatic |
| Remote Sensing | `remote_sensing.py` | On-demand | Manual CSV / GEE automated |
| Market Data | `market_data.py` | Daily | Automatic |
| EAS Attestations | `eas_indexer.py` | 15 minutes | Automatic |
| RPC Indexer | `rpc_indexer.py` | 30 minutes | Automatic |
| Gnosis Indexer | `gnosis_indexer.py` | 2 hours | Automatic |
| Climate Data | `climate_data.py` | Weekly | Automatic (placeholder) |

## Data Freshness Monitoring

SLAs per data source with automated alerting when data goes stale.

### Configuration

| Source | Expected | Stale | Critical |
|--------|----------|-------|----------|
| Weather | 6 hours | 12 hours | 24 hours |
| Sensors | 5 minutes | 30 minutes | 2 hours |
| Remote Sensing | 7 days | 14 days | 30 days |
| Market Data | 24 hours | 48 hours | 7 days |
| EAS Indexer | 15 minutes | 30 minutes | 1 hour |
| RPC Indexer | 30 minutes | 1 hour | 4 hours |
| Gnosis Indexer | 2 hours | 4 hours | 12 hours |

### Commands

```bash
# Run freshness check
python3 -m services.ingestion.data_freshness --check

# Check specific source
python3 -m services.ingestion.data_freshness --check --source weather

# View freshness summary
python3 -m services.ingestion.data_freshness --summary
```

### Alert Channels

- **Webhook**: `ALERT_WEBHOOK_URL` (Slack/Discord/Teams)
- **Email**: `ALERT_SMTP_HOST` + `ALERT_EMAIL_TO`

## ClickHouse Sync

Schema `006_telemetry_sync.sql` adds 17 missing columns to `remote_sensing_events`:

- Spectral indices: `msavi`, `satvi`, `bsi`, `nbr2`, `ndti`, `lswi`, `brightness_index`
- Tasseled cap: `tc_brightness`, `tc_greenness`, `tc_wetness`
- Raw bands: `band_blue`, `band_green`, `band_red`, `band_nir`, `band_swir1`, `band_swir2`
- Provenance: `source_system`

Materialized view: `mv_daily_remote_sensing_summary` (daily NDVI/NDRE/EVI per location)

## Climate Data Ingestion

Fetches climate covariates for SOC prediction and risk scoring:

```bash
# WorldClim bioclimatic variables
python3 -m services.ingestion.climate_data --worldclim --location-id UUID

# All climate data
python3 -m services.ingestion.climate_data --all --location-id UUID
```

### Tables Populated

| Table | Source | Purpose |
|-------|--------|---------|
| `worldclim_climate` | WorldClim v2 | 19 bioclimatic variables (1970-2000 baseline) |
| `ncep_weather_summary` | NCEP CFS | Short-term climate covariates |
| `modis_lst_summary` | MODIS MOD11A2 | Land surface temperature |
| `smap_soil_moisture` | SMAP L3 | Surface soil moisture |
| `sentinel1_sar_summary` | Sentinel-1 GRD | SAR backscatter (all-weather) |

## Remote Sensing Automation

```bash
# Configure a fetch job
INSERT INTO remote_sensing_job (location_id, provider, cadence_days, cloud_max_pct)
VALUES ('UUID', 'gee', 7, 20.0);
```

### Providers

- **GEE**: Google Earth Engine (Sentinel-2 L2A, server-side composites)
- **Copernicus**: Copernicus Data Space (Sentinel-2, direct download)

## Device Health Tracking

```bash
# View device health summary
SELECT * FROM v_sensor_device_health_summary;
```

Tracks: last_seen_at, battery_pct, signal_strength_dbm, firmware_version, reading_rate_per_hour.

## Database Tables

| Table | Purpose |
|-------|---------|
| `data_freshness_config` | SLA definitions per source |
| `data_freshness_check` | Freshness check results |
| `remote_sensing_job` | Automated RS fetch configurations |
| `sensor_device_health` | Device health tracking |
| `v_data_freshness_summary` | Current freshness status |
| `v_sensor_device_health_summary` | Device health overview |
| `v_remote_sensing_freshness` | ClickHouse RS freshness |
| `mv_daily_remote_sensing_summary` | ClickHouse daily RS aggregates |

## ML Anomaly Detection

Prophet (univariate seasonal) + Isolation Forest (multivariate) anomaly detection.

```bash
# Run ML detection
python3 -m services.ingestion.anomaly_detector --ml-check --location-id UUID

# Train and save models
python3 -m services.ingestion.anomaly_detector --ml-train --location-id UUID
```

Models stored in `models/ml_anomaly/`. Graceful fallback to rule-based detection when ML deps unavailable.

## Carbon Credits

Tokenized carbon credits with auto-adjustment.

```bash
# Issue credit
python3 -m services.analytics.carbon_credits --issue --location-id UUID --vintage-year 2026

# Auto-adjust credits
python3 -m services.analytics.carbon_credits --adjust --location-id UUID

# Retire credits
python3 -m services.analytics.carbon_credits --retire --credit-id UUID --tonnes 5.0 --reason voluntary_retirement

# List/balance
python3 -m services.analytics.carbon_credits --list --location-id UUID
python3 -m services.analytics.carbon_credits --balance --location-id UUID
```

## Workflow Orchestration (Prefect)

Replaces cron-based scheduling with Prefect workflows.

```bash
# Run full pipeline
python3 -m services.flows.pipelines full_pipeline

# Deploy scheduled workflows
prefect deploy --name scheduled-hourly
prefect deploy --name scheduled-every-6h
prefect deploy --name scheduled-daily
prefect deploy --name scheduled-weekly
```

Pipeline dependency chain: ingestion -> monitoring -> analytics

Full architecture: `docs/dmrv-architecture.md`

## Field Data Collection

For detailed protocols on on-ground data collection, see `docs/field-data-collection-guide.md`.

The field guide covers:
- **Equipment catalog** with specifications for all 7 collection types
- **Soil sampling** protocol (depth, composite method, lab submission, chain of custody)
- **Tree measurement** protocol (DBH at 1.3m, height estimation, canopy, health scoring)
- **Biodiversity surveys** (quadrat, transect, point count, camera trap, pitfall trap)
- **Water sampling** protocol (collection, field measurements, preservation, lab submission)
- **Weather observation** (on-site station placement, manual readings, API reconciliation)
- **Harvest measurement** (weighing, grading, loss measurement, post-harvest handling)
- **Pest monitoring** (visual scouting, sticky traps, pheromone traps, soil coring)
- **Measurement cadence matrix** (what/when/who/how for all data types)
- **Data quality & QA/QC** (range validation, duplicate detection, observer calibration)
- **Sample plot design** (plot dimensions, layout, GPS tagging, re-measurement)
- **MRV ground-truthing** (field-to-digital pipeline, reconciliation with remote sensing)
- **Equipment maintenance** (calibration schedules, battery management, cleaning)
