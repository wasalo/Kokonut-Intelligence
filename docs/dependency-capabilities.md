# Dependency Capabilities

This document maps dependencies to capabilities that are actually available in
the repository. It distinguishes infrastructure versions, Python requirement
ranges, direct runtime usage, configured product features, and upstream features
that are not implemented here.

## Evidence Status

| Status | Meaning |
|--------|---------|
| `verified` | Version and repository usage are demonstrated by configuration or code |
| `available-but-unused` | The installed component may provide the feature, but this repository does not use it |
| `unsupported` | The current version or configuration does not support the documented claim |
| `aspirational` | A product direction or external integration is described, but not implemented locally |
| `range-only` | A version range is declared; the exact installed version is not pinned |

Do not describe an upstream library feature as a platform capability unless the
repository uses it or the configuration explicitly enables it. Version headings
for Python packages are therefore expressed as requirement ranges unless a lock
file or image provides an exact version.

## Runtime And Build Matrix

| Component | Repository declaration | Status | Evidence |
|-----------|------------------------|--------|----------|
| Python | 3.11 slim image, digest-pinned | verified | `Dockerfile.worker`, `Dockerfile.grpc` |
| PostgreSQL/PostGIS | `postgis/postgis:16-3.4`, digest-pinned | verified | `docker-compose.yml` |
| ClickHouse | `clickhouse-server:25.8`, digest-pinned | verified | `docker-compose.yml` |
| Directus | `12.1.1`, digest-pinned | verified | `docker-compose.yml` |
| Metabase | `v0.62.4`, digest-pinned | verified | `docker-compose.yml` |
| Node.js | Node 22 in CI; hooks require Node `>=20.19.0` | verified | `.onedev-buildspec.yml`, hooks `package.json` |
| Python packages | Range-based `requirements.txt` | range-only | `requirements.txt` |
| Root Python lock file | No root `requirements.lock` | gap | CI installs from ranges |

Compose keeps PostgreSQL and ClickHouse private in the base deployment. Host
ports are supplied by CI or explicit development overrides. Image digest checks
are enforced by the repository tooling.

## PostgreSQL 16 / PostGIS

PostgreSQL 16 is the canonical transactional database and PostGIS provides
spatial types and indexes.

### Verified Repository Usage

| Capability | Platform use |
|------------|--------------|
| Transactional SQL | Migrations, governed writes, lifecycle transitions, and service operations |
| `date_trunc` | Time-period grouping in analytics and reporting queries |
| `array_agg` and `string_agg` | Aggregation in reports, seed data, and metric queries |
| FULL and outer joins | Dashboard and reporting SQL |
| PostGIS geometry | Farm boundaries, plots, trees, files, spatial clusters, and GeoJSON views |
| GIN indexes | Full-text, evidence URL, and UUID-array search paths |
| GiST indexes | Spatial geometry queries |
| JSONB | Metadata, evidence, source payloads, model inputs, and configuration |
| Database constraints and triggers | Lifecycle, evidence, supply, approval, and audit integrity |

### Available But Not Demonstrated

PostgreSQL 16 may provide features such as SQL/JSON constructors, `pg_stat_io`,
`IS JSON`, `pg_input_is_valid()`, `pg_input_error_info()`, `random_normal()`,
logical-replication standby support, and version-specific parallel join or
aggregate improvements. No repository usage or benchmark was found for these
features. They must not be presented as current platform capabilities.

### PostgreSQL Access

`psycopg2-binary` is the direct PostgreSQL driver and is used throughout
`services/common/database.py`, ingestion, analytics, scoring, governance,
predictions, and threatcasting modules. The repository's database helper
provides a small adapter around psycopg2. SQLAlchemy is not installed or
imported.

## ClickHouse 25.8

ClickHouse is the analytical event store. The repository uses
`clickhouse-connect` for HTTP/native client access and analytical exports.

### Verified Usage

| Capability | Platform use |
|------------|--------------|
| `client.insert(...)` | Event and analytical mirror inserts |
| JSONEachRow HTTP inserts | Validated batch ingestion |
| `MergeTree` | Event storage and analytical tables |
| `SummingMergeTree` | Aggregated event views |
| `AggregatingMergeTree` | Materialized analytical aggregates |
| Materialized views | Sensor, event, and portfolio projections |

Relevant schemas include `schemas/clickhouse/001_events.sql`,
`002_materialized_views.sql`, and `003_sensor_views.sql`.

### Available But Unused

No repository usage was found for ClickHouse PromQL, Iceberg or Delta Lake
writes, the `_table` virtual column, ClickHouse TimeSeries functions, Parquet
v3 ingestion, or CPU slot preemption. These are upstream capabilities, not
implemented platform features.

## Directus 12.1.1

Directus is the canonical API and administration layer. It exposes PostgreSQL
collections, manages metadata, and runs the repository's governance extensions.

### Verified Usage

- REST and GraphQL access to canonical collections.
- Lifecycle and role checks in `extensions/kokonut-hooks`.
- Governed collection validation and agent-safety hooks.
- Schema metadata tests and Directus health checks.
- JavaScript SDK access through `@directus/sdk`.
- Public/private collection policies and workflow transitions.

The repository's governance behavior is implemented jointly by database
constraints, Directus hooks, and service-level safety code. It should not be
attributed solely to a Directus product feature.

### Compatibility Note

The server image is Directus `12.1.1`, while
`extensions/kokonut-hooks/package.json` declares a host compatibility range of
`^11.0.0`. Review this before upgrading the server or extension runtime.

### MCP And Product UI Claims

MCP is mentioned in surrounding documentation, but no local MCP package,
configuration, server, endpoint, or test was found for Directus. MCP server
improvements, an interactive schema viewer, sub-collections, alerts-management
enhancements, and programmatic filters should be treated as upstream or
aspirational unless separately verified against the deployed Directus instance.

## Metabase 0.62.4

Metabase is used for embedded analytics, dashboards, and SQL-backed review
surfaces.

### Verified Usage

- Dashboards under `dashboards/metabase/`.
- SQL cards and dashboard queries under `dashboards/metabase/sql/`.
- Dashboard metadata and refresh configuration in repository JSON and seeds.
- Embedded analytics configuration in deployment files.

The repository does not demonstrate a Metabase MCP server, “charts in AI”
integration, version-specific custom visualization behavior, sub-collection
usage, or an interactive schema-viewer workflow. Those claims are upstream or
aspirational, not verified local capabilities.

## Python Dependency Inventory

Python dependencies are declared in `requirements.txt` with ranges. Unless
otherwise stated, the exact resolved version is not tracked by a root lock file.

| Package | Requirement | Runtime role | Status |
|---------|-------------|--------------|--------|
| `fastapi` | `>=0.139.0,<1.0.0` | Gateway, metadata API, HTTP sensor receiver | range-only / verified usage |
| `pydantic` | FastAPI/transitive; used directly | Request, response, Delphi, and threatcasting models | direct import not separately declared |
| `uvicorn` | `>=0.51,<1` | FastAPI server process | range-only / verified usage |
| `psycopg2-binary` | `>=2.9.12,<3` | PostgreSQL driver | range-only / verified usage |
| `clickhouse-connect` | `>=1.4.1,<2` | ClickHouse client | range-only / verified usage |
| `prefect` | `>=3.0,<4.0` | Flow and task orchestration | range-only / verified usage |
| `numpy` | `>=1.26,<2.0` | Numerical computing, simulations, geostatistics | range-only / verified usage |
| `pandas` | `>=2.0,<4.0` | Time-series preparation and tabular analysis | range-only / verified usage |
| `scikit-learn` | `>=1.9,<2.0` | Isolation Forest, scaling, validation, regression | range-only / verified usage |
| `prophet` | `>=1.3.0,<2.0` | Sensor anomaly and time-series modeling | range-only / verified usage |
| `yfinance` | `>=1.0.0,<2.0.0` | Yahoo Finance market-price ingestion | range-only / verified usage |
| `scipy` | not directly declared | Statistical and geostatistical routines | dependency gap |
| `rasterio` | not directly declared | Raster metadata and raster processing | dependency gap |
| `gstools` | `>=1.6,<2` | Variograms, kriging, simulation | range-only / verified usage |
| `fiona` | `>=1.10,<2` | Shapefile and GIS import | range-only / verified usage |
| `requests` | `>=2.34.2,<3` | HTTP clients and external ingestion | range-only / verified usage |
| `typer` | `>=0.15,<1` | Unified and service CLIs | range-only / verified usage |
| `web3` | `>=7.16,<8` | RPC, EAS, DAO, and governance integration | range-only / verified usage |
| `eth-abi` | `>=5.2,<6` | ABI encoding and decoding | range-only / verified usage |
| `earthengine-api` | `>=1.7,<2` | Remote-sensing integrations | range-only / verified usage |
| `paho-mqtt` | `>=2,<3` | MQTT ingestion and actuation | range-only / verified usage |
| `openpyxl` | `>=3.1.5,<4` | Spreadsheet bridge | range-only / verified usage |
| `grpcio` family | `>=1.68,<2` | gRPC server and client | range-only / verified usage |
| `protobuf` | `>=5.29,<7` | gRPC/protobuf messages | range-only / verified usage |
| `defusedxml` | `>=0.7.1,<2` | Safe XML parsing | range-only / verified usage |

### Missing Direct Declarations

`pydantic`, `scipy`, and `rasterio` are imported or relied upon but are not
declared as direct requirements in the audited manifest. Transitive availability
is fragile: add a direct requirement when application code imports a package
directly, then regenerate and commit the approved lock artifact when the
repository adopts one.

No imports were found for SQLAlchemy, GeoPandas, or Shapely. Do not describe
those libraries as platform dependencies without adding and using them.

## API And Orchestration Capabilities

### FastAPI, Pydantic, And Uvicorn

FastAPI is verified in:

- `services/ingestion/http_sensor_receiver.py`
- `services/gateway/app.py`
- `services/gateway/router.py`
- `services/metadata_api/app.py`

Implemented capabilities include JSON request validation, HMAC-authenticated
sensor ingestion, batch JSON ingestion, JSON API responses, and Uvicorn serving.

The repository does not use Server-Sent Events, `StreamingResponse`, EventSource
responses, or streaming JSON Lines. “Native SSE,” “streaming JSON Lines,” and
“2x JSON via Pydantic/Rust” are not verified capabilities here.

### Prefect 3.x

Prefect is used by `services/flows/`, deployment configuration, and
`tests/test_prefect_workflow.py`:

- `@flow` and `@task` definitions
- submitted task futures
- dependency/result handling
- retries and scheduled deployments

No Prefect MCP server was found. No local benchmark verifies a 90% overhead
reduction, and no repository usage was found for a `CANCELLING` timeout feature.
Event-driven automation may be an operational direction, but inspected flows
are primarily scheduled and dependency-driven.

### gRPC

`grpcio` and `protobuf` support the repository's gRPC server and client under
`services/grpc/`. Generated message contracts and health checks are covered by
the gRPC test suite.

## Analytics And Machine Learning

| Dependency | Verified usage | Not demonstrated |
|------------|----------------|------------------|
| NumPy | Geostatistics, simulations, soil-carbon prediction | StringDType, GPU/alternative Array API backend |
| pandas | Sensor time-series preparation and tabular transformations | Arrow PyCapsule integration, anti-joins |
| scikit-learn | Isolation Forest, scaling, model validation, regression metrics | Callback API, GPU Array API acceleration |
| Prophet | Univariate sensor anomaly detection with standard seasonality/interval parameters | `scaling='minmax'`, custom CV metrics, special NaN-date handling |
| SciPy | Statistical/geostatistical support where imported | Direct requirement declaration is missing |
| gstools | Variograms, kriging, simulation, spatial validation | — |

Primary evidence includes `services/ingestion/ml_anomaly_detector.py`,
`services/analytics/soc_prediction.py`, `services/geostatistics/`, and
`services/simulation/`.

## Market, GIS, Remote Sensing, And Messaging

| Dependency | Capability used |
|------------|------------------|
| `yfinance` | Lazy Yahoo Finance import for market-price ingestion and price attestation |
| `fiona` | GIS/shapefile import |
| `rasterio` | Raster metadata and processing; direct declaration should be added |
| `earthengine-api` | Remote-sensing provider integration |
| `paho-mqtt` | MQTT sensor ingestion and actuator integration |
| `requests` | External API and data-provider requests |
| `openpyxl` | Spreadsheet bridge and workbook handling |

The repository does not configure authenticated Yahoo Finance login, an explicit
`curl_cffi` fallback, or parallel yfinance downloads. Those should not be
documented as guaranteed capabilities.

## Blockchain And Attestation Tooling

`web3` and `eth-abi` are actively used for EVM RPC and ABI workflows, including:

- Gnosis and Baal event indexers
- Governance adapter reads
- EAS attestation configuration and encoding
- Guild and Colony-related integration
- Transaction and contract metadata handling

This document intentionally does not claim transaction submission, autonomous
governance, or autonomous attestation. Repository governance boundaries require
human approval for high-risk and on-chain actions.

## JavaScript And TypeScript Dependencies

The repository includes a JavaScript SDK and Directus hook package.

| Area | Capability | Evidence |
|------|------------|----------|
| Directus SDK | Typed REST/GraphQL client integration | `sdk/javascript/package.json` |
| Directus hooks | Lifecycle, validation, role, and agent-safety enforcement | `extensions/kokonut-hooks/src/` |
| TypeScript | Compiled hook and SDK source | package manifests and build scripts |
| Node.js | Hook build/test runtime | CI Node 22; hooks require `>=20.19.0` |

The hook package's declared Directus host compatibility should be reconciled
with the server image before a production upgrade.

## Feature Verification Matrix

| Documented capability | Version availability | Repository usage | Status |
|-----------------------|----------------------|------------------|--------|
| PostgreSQL JSON constructors | Available in PostgreSQL 16 | No usage found | available-but-unused |
| PostgreSQL `pg_stat_io` | Available in PostgreSQL 16 | No monitoring query found | available-but-unused |
| ClickHouse PromQL | Available upstream | No query or configuration found | available-but-unused |
| ClickHouse Iceberg/Delta writes | Available upstream depending on deployment | No writer found | aspirational |
| Directus MCP | Mentioned in docs | No server/package/config/test found | aspirational |
| Metabase MCP | Mentioned in docs | No server/package/config/test found | aspirational |
| FastAPI SSE | Framework capability | No SSE endpoint found | available-but-unused |
| FastAPI JSON Lines streaming | Framework capability | No streaming endpoint found | available-but-unused |
| Prefect MCP | Mentioned as product capability | No local MCP implementation | aspirational |
| NumPy GPU Array API | Upstream ecosystem capability | No GPU backend use found | available-but-unused |
| pandas anti-join | Version-dependent upstream capability | No anti-join use found | available-but-unused |
| scikit-learn callbacks | Version-dependent upstream capability | No callback use found | available-but-unused |
| Prophet min-max scaling | Version-dependent upstream capability | Not passed by code | available-but-unused |
| Yahoo authenticated access | External/provider capability | No login configuration found | unsupported locally |
| EAS encoding | `web3`/`eth-abi` capability | Schema encoding and attestation services use it | verified |
| PostGIS geometry | PostgreSQL image capability | Spatial schemas, indexes, and exports use it | verified |
| ClickHouse MergeTree | ClickHouse capability | Core analytical schemas use it | verified |

## Dependency Risks And Maintenance

### Range-Based Resolution

The Python manifest uses compatible ranges rather than exact pins. A clean
environment can therefore resolve different minor or patch versions over time.
Record the tested environment in CI and adopt a hash-pinned lock file if
reproducible application installs become a requirement.

### Direct Versus Transitive Dependencies

Application imports should be direct requirements. In particular, review
`pydantic`, `scipy`, and `rasterio`. Relying on another package to bring an
imported dependency transitively can produce build-only failures.

### Compatibility Checks

When upgrading:

1. Compare the requested range with Python 3.11 support.
2. Resolve the full environment in CI, not only the base image.
3. Run the focused platform-integrity, data, analytics, and hook tests.
4. Run `pip-audit` and Ruff security checks.
5. Rebuild images and verify all `FROM` and Compose image references remain
   digest-pinned.
6. Recheck the Directus hook host range against the server image.
7. Update this document only after confirming repository usage or explicit
   configuration.

## Source References

- `requirements.txt` — Python requirement ranges
- `pyproject.toml` — Python tooling and test configuration
- `docker-compose.yml` — database, Directus, Metabase, and image pins
- `Dockerfile.worker` / `Dockerfile.grpc` — Python runtime images
- `.onedev-buildspec.yml` — CI runtime and verification gates
- `extensions/kokonut-hooks/package.json` — Node and Directus extension constraints
- `sdk/javascript/package.json` — JavaScript SDK dependencies
- `services/common/database.py` — PostgreSQL access adapter
- `services/ingestion/base.py` — PostgreSQL and ClickHouse ingestion clients
- `services/gateway/` and `services/metadata_api/` — FastAPI usage
- `services/flows/` — Prefect usage
- `services/attestation/`, `services/governance/`, and `services/ingestion/*indexer.py` — EVM tooling
- `dashboards/metabase/` — Metabase dashboard assets

## Maintenance Rule

Keep this document factual. When a dependency is upgraded, update the version
matrix and feature verification matrix together. When a new capability is
implemented, cite the source file or configuration that proves its use. Do not
turn upstream release notes, product marketing, or roadmap intentions into
claims about the current Kokonut Intelligence deployment.
