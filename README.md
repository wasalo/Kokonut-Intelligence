# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Canonical core | PostgreSQL 14 + PostGIS 3.4 + Directus 11.17 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.3 | Time-series, events, high-volume analytical queries |
| BI | Metabase | Internal dashboards, aggregate reporting |
| Intelligence | Python services | Fortune 500 scoring, forecasting, partner dashboards |
| Verification | EAS + evidence storage | Attestations, claims, proof |
| Blockchain | RPC + Subgraphs | On-chain data ingestion |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your secrets

# 2. Start infrastructure
docker compose up -d

# 3. Verify health
docker compose ps

# 4. Access Directus (admin UI + data entry)
open http://localhost:8055

# 5. Access Metabase (BI dashboards)
open http://localhost:3001
```

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Directus | http://localhost:8055 | Schema management, API, admin UI, primary data entry |
| Metabase | http://localhost:3001 | Internal BI dashboards |
| ClickHouse HTTP | http://localhost:8123 | Analytical queries |
| PostgreSQL | localhost:5432 | Canonical data store |

## Roles

| Role | Access | Description |
|------|--------|-------------|
| Administrator | Full | Platform admin, all permissions |
| Field Worker | Create/read own location | Field data entry: activities, harvests, expenses, sales, losses, notes |
| Supervisor | Read all, submit | Can submit records for approval, read all locations |
| Manager | Approve all | Can approve/verify all operational records |
| Finance | Approve expenses, verify sales | Approves expense claims, verifies sales transactions |
| Analyst | Read verified/published | Read-only access to verified data for analysis |

## Workflow

Every operational record follows: **Draft → Submitted → Verified → Published**

```
Field Worker creates record (draft)
    ↓
Supervisor submits for review (submitted)
    ↓
Manager/Finance approves or rejects (verified/rejected)
    ↓
Published — available to dashboards and analysts
```

Expense-specific flow: Draft → Submitted → Approved → Paid

## Data Entry

Directus Studio at `http://localhost:8055` is the primary data entry interface.

**Supported entry types:**
- Farm activities (planting, weeding, irrigation, spraying, harvesting)
- Harvest events with quantity, quality, and loss tracking
- Expenses with category auto-suggestion and amount validation
- Sales with automatic net amount calculation
- Loss/incident records with severity and mitigation
- Labor events with automatic cost calculation
- Field notes with photo capture and auto-summarization

**AI-assisted features (rule-based):**
- Expense auto-categorization from description text
- Amount validation with suspicious-value flagging
- Harvest quantity validation against expected yield
- Date validation (no future dates, no >1yr old expenses)
- Field note summarization for long content
- Automatic cost calculations (labor, loss value)

## Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state.

```bash
# Apply all schemas and seed data
./scripts/seed.sh

# Apply a single schema file
docker compose exec database psql -U kokonut -d kokonut_intelligence -f /path/to/schema.sql

# Snapshot Directus schema
./scripts/schema-snapshot.sh
```

## Directory Structure

```
├── config/
│   ├── postgres/       # PostgreSQL init scripts
│   ├── clickhouse/     # ClickHouse config
│   └── directus/       # Directus permissions SQL
├── schemas/
│   ├── postgres/       # 11 schema files, 60 tables
│   ├── seeds/          # Pilot farm seed data (5 files)
│   ├── directus/       # Directus snapshots
│   └── clickhouse/     # Analytical schemas (6 tables + 8 views)
├── sdk/
│   ├── javascript/     # JS/TS SDK wrapper + examples
│   └── python/         # Python SDK wrapper + examples
├── services/
│   ├── ingestion/      # External data ingestion scripts
│   │   ├── base.py     # Common utilities (DB, logging, retry)
│   │   ├── config.py   # API keys and connection config
│   │   ├── weather.py  # OpenWeatherMap ingestion
│   │   ├── rpc_indexer.py    # Ethereum/L2 wallet activity
│   │   ├── market_data.py    # Commodity prices
│   │   ├── remote_sensing.py # NDVI/NDRE CSV upload
│   │   ├── eas_indexer.py    # EAS attestation ingestion
│   │   ├── sensor_ingester.py # Sensor CSV + single reading
│   │   ├── mock_sensors.py   # Mock sensor data generator
│   │   └── anomaly_detector.py # Threshold-based alert engine
│   ├── analytics/      # Intelligence services
│   │   ├── forecast.py       # Revenue forecasting engine
│   │   └── fortune500/
│   │       ├── calculator.py # Farm scoring engine
│   │       └── cli.py        # CLI for scoring + ranking
│   └── export/         # Data export and report generation
│       ├── exporter.py       # CSV/JSON/Parquet export
│       └── report_generator.py # Report snapshots with hash verification
├── extensions/
│   └── kokonut-hooks/  # Directus lifecycle hooks
│       └── src/
│           ├── index.ts              # Hook registration
│           ├── workflow.ts           # State machine + role routing
│           ├── metrics-calculator.ts # NOI, loss rate, operating margin
│           └── ai-helpers.ts         # Auto-categorization, validation
├── migrations/         # Baserow migration scripts
├── scripts/            # Setup, seed, backup, snapshot
├── docs/               # Architecture, data dictionary, API reference
└── dashboards/
    ├── metabase/       # Metabase dashboard definitions
    └── directus/       # Partner dashboard templates (buyer, funder, vendor, operator)
```

## External Data Ingestion

Python scripts in `services/ingestion/` fetch data from external APIs and insert into the canonical schema.

| Script | Source | Target Tables | Status |
|--------|--------|---------------|--------|
| `weather.py` | OpenWeatherMap API | `weather_observation` + ClickHouse `weather_events` | Working |
| `rpc_indexer.py` | Ethereum/L2 public RPC | `wallet_activity_event` + ClickHouse `wallet_events` | Working |
| `market_data.py` | World Bank Pink Sheet (seed data) | `price_observation` | Working |
| `remote_sensing.py` | Manual CSV upload | `remote_sensing_observation` | Working |
| `eas_indexer.py` | EAS GraphQL API (Optimism/Base) | `attestation_record` + `attestation_schema` | Working |
| `sensor_ingester.py` | CSV / single reading | `sensor_reading` + ClickHouse `sensor_readings` | Working |
| `mock_sensors.py` | Internal (test data) | `sensor_device` + `sensor_reading` + ClickHouse | Working |
| `anomaly_detector.py` | Threshold rules | `sensor_alert` + auto MRV claims | Working |

```bash
# Run weather ingestion
python3 -m services.ingestion.weather

# Run RPC indexer for specific chain
python3 -m services.ingestion.rpc_indexer --chain ethereum

# Upload remote sensing CSV
python3 -m services.ingestion.remote_sensing --file data/sample_remote_sensing.csv

# Seed commodity prices
python3 -m services.ingestion.market_data

# Index EAS attestations
python3 -m services.ingestion.eas_indexer --chain optimism

# Sensor ingestion (batch CSV)
python3 -m services.ingestion.sensor_ingester --file data/sensors.csv

# Generate mock sensor data (for testing)
python3 -m services.ingestion.mock_sensors --setup
python3 -m services.ingestion.mock_sensors --generate --count 96 --anomalies

# Run anomaly detection
python3 -m services.ingestion.anomaly_detector
```

## Data Lifecycle

Every important record follows: **Raw → Normalized → Verified → Published**

- **Raw:** Unmodified source payload
- **Normalized:** Mapped to Kokonut canonical schema
- **Verified:** Reviewed, validated, linked to evidence
- **Published:** Available to dashboards, APIs, attestations

## Metrics

The platform auto-calculates governed metrics on data changes:

| Metric | Trigger | Description |
|--------|---------|-------------|
| Crop NOI | harvest/sales/expense create | Net revenue minus direct costs minus allocated shared costs |
| Loss Rate | harvest create | Loss amount as percentage of total harvest |
| Operating Margin | NOI recalculation | NOI as percentage of net revenue |
| Net Amount | sales create/update | Total minus returns minus discounts |
| Labor Cost | labor event create | Hours worked times hourly rate |

## Developer SDK

JavaScript/TypeScript and Python SDKs for programmatic access to the platform.

```bash
# JavaScript/TypeScript
cd sdk/javascript && npm install && npm run build
# See sdk/javascript/examples/ for usage

# Python
cd sdk/python && pip install -e .
# See sdk/python/examples/ for usage
```

## Developer Sandbox

Full local Docker environment with pre-seeded data and API keys.

```bash
# Start sandbox
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml up -d

# Setup API keys and sample data
./scripts/sandbox-setup.sh

# Follow the hello-world tutorial
open docs/sandbox.md
```

## Data Export

Export data to CSV, JSON, or Parquet from PostgreSQL or ClickHouse.

```bash
# Export expenses to CSV
python3 -m services.export.exporter --collection expense_event --format csv --output exports/

# Export sensor readings from ClickHouse
python3 -m services.export.exporter --collection sensor_readings --format json --source clickhouse --output exports/

# Generate a farm summary report
python3 -m services.export.report_generator --type farm_summary --location-id UUID
```

## Pilot Farm Seed Data

Pre-seeded data for the Kokonut Demo Farm (Kisumu, Kenya) across 5 seed files:

| File | Content |
|------|---------|
| `001_pilot_farm.sql` | Location, farm, plots, crops, crop cycles, partners, staff, infrastructure |
| `003_pilot_farm_environmental.sql` | Soil samples, weather, remote sensing, sensors, alerts |
| `004_pilot_farm_web3.sql` | Wallet activity, digital lego usage, attestations, chain indexer status |
| `005_pilot_farm_operations.sql` | Activities, harvests, sales, expenses, losses, labor, field notes |
| `006_pilot_farm_dao.sql` | Governance events, metric definitions, treasury events |

```bash
# Seed all pilot farm data
./scripts/seed-pilot.sh

# Or run individual files
docker compose exec database psql -U kokonut -d kokonut_intelligence \
  -f schemas/seeds/001_pilot_farm.sql
```

## Fortune 500 Farm Scoring

Weighted 4-pillar ranking system for regenerative farms:

| Pillar | Weight | Metrics |
|--------|--------|---------|
| Financial | 45% | NOI, operating margin, revenue/ha, loss rate, cost/ha |
| Ecological | 25% | NDVI, soil organic matter, data completeness, remote sensing |
| Governance | 15% | Attestations, governance events, treasury events, metric definitions |
| Growth | 15% | Yield improvement, revenue growth, data completeness |

**Tiers:** Platinum (800+), Gold (600+), Silver (400+), Bronze (200+), Developing

```bash
# Score a specific farm
python3 -m services.fortune500.cli --farm <farm-id>

# Rank all farms
python3 -m services.fortune500.cli --all
```

## Revenue Forecasting

Time-series projection engine with Monte Carlo simulation:

```bash
# Run forecast for a location (3, 6, 12 months)
python3 -m services.analytics.forecast --location <location-id>

# Custom horizon and simulations
python3 -m services.analytics.forecast --location <location-id> \
  --months 12 --simulations 2000
```

**Output:**
- Monthly revenue projections with confidence intervals
- Bootstrap simulation for uncertainty estimation
- Historical trend analysis from harvest and sales data

## Partner Dashboards

Directus dashboard templates for different partner roles in `dashboards/directus/`:

| Partner | Dashboard | Key Views |
|---------|-----------|-----------|
| Buyer | `partner-buyer.md` | Production summary, upcoming harvests, quality grades, revenue trends |
| Funder | `partner-funder.md` | NOI trends, cost breakdown, forecasts, impact attestations, ecological outcomes |
| Vendor | `partner-vendor.md` | Purchase history, payment status, demand forecasts |
| Operator | `partner-operator.md` | Operations overview, sensors, weather, crop cycles, alerts |

Row-level security ensures partners see only their own data.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System overview, data flow, security model |
| [API Reference](docs/api-reference.md) | REST/GraphQL/ClickHouse API docs |
| [OpenAPI Spec](docs/openapi.yaml) | Full OpenAPI 3.0 specification |
| [Data Dictionary](docs/data-dictionary.md) | All collections, fields, and governed metrics |
| [Deployment](docs/deployment.md) | Docker setup, environment variables, backup |
| [Sandbox](docs/sandbox.md) | Developer quickstart with hello-world tutorial |
| [Subgraph Guide](docs/subgraph-guide.md) | Subgraph indexer configuration and usage |
| [Attestation Guide](docs/attestation-guide.md) | EAS attestation workflow |
| [Partner Dashboards](docs/partner-dashboards.md) | Dashboard flexibility (Directus/Metabase/Custom) |
| [Agent Access](docs/agent-access.md) | MCP, agent-scoped tokens, audit logging |
| [Export Guide](docs/export-guide.md) | Data export and report snapshots |

## License

Open source — see LICENSE file.
