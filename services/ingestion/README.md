# ingestion

`services.ingestion`

## CLI Usage

```bash
python3 -m services.ingestion.cli --help
```

## Modules

- `adaptive_sampler` — Adaptive Sensor Sampler — dynamically adjusts polling intervals.
- `anomaly_detector` — Anomaly Detector — Sensor Alert Engine
- `baal_indexer` — Indexer for the Kokonut DAO (Moloch v3 / Baal) on Gnosis Chain.
- `base` — Common Ingestion Utilities
- `cli` — Unified ingestion CLI — lists available ingestion tools and routes to subcommands.
- `climate_data` — Climate data ingestion service.
- `config` — Ingestion Configuration
- `copernicus_remote_sensing` — Copernicus Data Space remote sensing adapter.
- `data_freshness` — Data freshness monitoring service.
- `device_manager` — IoT device manager.
- `eas_indexer` — EAS Attestation Ingestion — Direct EAS API
- `gee_climate` — Google Earth Engine climate data fetching.
- `gee_remote_sensing` — Google Earth Engine remote sensing adapter.
- `gis_import` — GIS Data Ingestion — Spatial Boundaries
- `gnosis_indexer` — Gnosis Chain Ingestion — Kokonut Moloch DAO Events
- `harvest_manager` — General harvesting framework: pull data from external sources.
- `http_sensor_receiver` — HTTP webhook receiver for IoT sensor data.
- `kml_import` — KML/KMZ import: convert KML files to PostGIS geometry.
- `market_data` — Market Data Ingestion — Commodity Prices
- `ml_anomaly_detector` — ML-based anomaly detection for sensor data.
- `mock_sensors` — Mock Sensor Data Generator
- `mqtt_actuator` — MQTT actuator command publisher.
- `mqtt_subscriber` — MQTT subscriber for IoT sensor data.
- `oracle_aggregator` — Multi-source oracle aggregation with median consensus.
- `price_attestation` — On-chain price attestation for audit trail.
- `raster_metadata` — Raster metadata: read GeoTIFF headers and store metadata.
- `remote_sensing` — Remote Sensing Ingestion — CSV Upload
- `remote_sensing_fetcher` — Abstract remote sensing fetcher.
- `rpc_indexer` — RPC Ingestion — Ethereum/L2 Wallet Activity
- `sensor_ingester` — Sensor Ingestion — Batch and HTTP API
- `shapefile_import` — Shapefile import: convert shapefiles to PostGIS geometry.
- `status` — Ingestion Status CLI
- `subgraph_indexer` — Subgraph Ingestion — EAS + Kokonut Contracts
- `weather` — Weather Ingestion — OpenWeatherMap
- `weather_forecast` — Weather Forecast — OpenWeatherMap 5-Day / 3-Hour
- `yahoo_finance` — Yahoo Finance commodity futures ingestion.
- `drivers/` — sub-package

## Files

36 Python modules
