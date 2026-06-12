# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Canonical core | PostgreSQL 14 + PostGIS 3.4 + Directus 11.17 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.3 | Time-series, events, high-volume analytical queries |
| BI | Metabase | Internal dashboards, aggregate reporting |
| Intelligence | Python services | Fortune 500 scoring, forecasting, partner dashboards |
| Verification | EAS on Celo + evidence storage | Onchain attestations, offchain signed claims, MRV proof |
| Blockchain | RPC + Subgraphs + Foundry | On-chain data ingestion, smart contracts |

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

Expenses use the same lifecycle; payment is tracked separately with `payment_status`.

## Registry, MRV, And Agents

The PRD completion layer adds Kokonut farm registry, MRV, attestation request, and agent metadata support while keeping PostgreSQL and Directus as the canonical secure API layer.

| Area | Tables / Services | Scope |
|------|-------------------|-------|
| Farm Registry | `farm_registry_record`, `services.registry` | Kokonut Common Data Schema onboarding and validation |
| MRV | `mrv_event`, environmental lineage fields | Ground, remote, and community evidence metadata |
| EAS Requests | `attestation_request`, `services.attestation` | Public payload hashes/CIDs and private payload hashes only |
| Agent Metadata | `agent_identity`, `agent_capability_manifest`, `agent_task`, `agent_action_log`, `services.agents` | Metadata and task records; marketplace contract/payment logic stays external |
| Local CID | `services.storage` | Development-only `local://sha256/<hash>` content addressing |

```bash
# Print a Common Data Schema example
python3 -m services.registry --example-farm-record

# Prepare local EAS request metadata from JSON
python3 -m services.attestation --subject-type mrv_event --subject-id UUID --event-type mrv_submission --payload-file payload.json

# Print an agent capability manifest example
python3 -m services.agents --example kokonut-mrv-reporter
```

See `docs/prd-completion.md`, `docs/attestation-guide.md`, and `docs/agent-access.md` for scope and privacy boundaries.

### EAS on Celo

Celo is the primary chain for Kokonut attestations. EAS v1.3.0 is deployed on Celo mainnet.

**Deployed Contracts:**

| Contract | Address | Explorer |
|----------|---------|----------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` | [celoscan.io](https://celoscan.io/address/0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92) |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` | [celoscan.io](https://celoscan.io/address/0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34) |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` | [celoscan.io](https://celoscan.io/address/0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad) |

**Registered Schemas:**

| Schema | UID | Use Case |
|--------|-----|----------|
| `kokonut-mrv` | `0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54` | MRV claims (location, crop, quantity, evidence) |
| `kokonut-impact` | `0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe` | Environmental impact (soil carbon, biodiversity, NDVI) |
| `kokonut-financial` | `0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b` | Financial summaries (NOI, revenue, costs) |
| `kokonut-harvest` | `0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff` | Harvest verification (quantity, quality, date) |
| `kokonut-compliance` | `0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5` | Partner compliance and audit trails |

**Attester wallets:** Deployer `0x3394C45b5938127EB56603A6051dF26CFAF08C26` + Kokonut multisig `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5`

**Resolver ownership:** Transferred to Kokonut multisig.

```bash
# Show chain config and attester info
python3 -m services.attestation.cli info --chain celo

# List available schema definitions
python3 -m services.attestation.cli schema list

# Create an onchain attestation on Celo
python3 -m services.attestation.cli attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT \
  --data '[{"name":"locationId","type":"string","value":"..."}]' \
  --chain celo

# Create a gasless offchain attestation (EIP-712 signed)
python3 -m services.attestation.cli offchain-attest \
  --schema 0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54 \
  --recipient 0xRECIPIENT \
  --data '[{"name":"locationId","type":"string","value":"..."}]' \
  --chain celo

# Query an attestation from onchain
python3 -m services.attestation.cli query --uid 0xATTESTATION_UID --chain celo
```

**Smart contracts** are under `contracts/` (Foundry project). The `KokonutResolver` gates attestation to allowed attesters. Build and test with `forge build` and `forge test`.

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
├── contracts/          # Foundry project (Solidity)
│   ├── src/
│   │   └── KokonutResolver.sol   # EAS resolver (attester gating)
│   ├── script/
│   │   └── DeployKokonutResolver.s.sol
│   ├── test/
│   │   └── KokonutResolver.t.sol
│   └── lib/            # OpenZeppelin, EAS contracts
├── schemas/
│   ├── postgres/       # 14 schema files, 50+ tables
│   ├── seeds/          # Base and pilot seed data (16 files)
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
│   │   ├── eas_indexer.py    # EAS attestation ingestion (Celo/Optimism/Base)
│   │   ├── sensor_ingester.py # Sensor CSV + single reading
│   │   ├── mock_sensors.py   # Mock sensor data generator
│   │   └── anomaly_detector.py # Threshold-based alert engine
│   ├── attestation/    # EAS attestation service
│   │   ├── cli.py            # CLI: schema, attest, offchain-attest, revoke, query, info
│   │   ├── eas_client.py     # EASClient (web3.py contract wrapper)
│   │   ├── schema_encoder.py # SchemaEncoder (ABI encode/decode)
│   │   ├── signer.py         # Wallet/signer management
│   │   ├── offchain.py       # Offchain EIP-712 signed attestations
│   │   ├── publisher.py      # Onchain attestation orchestration
│   │   ├── schemas.py        # 5 Kokonut schema definitions
│   │   ├── payload.py        # Privacy-preserving request metadata
│   │   ├── config.py         # EAS chain config + contract addresses
│   │   └── contracts/        # EAS + SchemaRegistry ABIs
│   ├── analytics/      # Intelligence services
│   │   ├── cli.py            # CLI for ecology analytics
│   │   ├── ecology.py        # Soil carbon, biodiversity, scenario comparison
│   │   └── fortune500/
│   │       ├── calculator.py # Farm scoring engine
│   │       └── cli.py        # CLI for scoring + ranking
│   ├── revenue_multiplier/ # Module C: Revenue Multiplier Opportunity Map
│   │   ├── models.py         # OpportunityDimension, RevenueMultiplierMap
│   │   ├── analyzer.py       # Main orchestrator
│   │   ├── cli.py            # CLI for opportunity analysis
│   │   └── dimensions/       # 10 dimension analyzers
│   │       ├── crop_mix.py
│   │       ├── loss_reduction.py
│   │       ├── buyer_channel.py
│   │       ├── value_added.py
│   │       ├── web3_replication.py
│   │       ├── bioinput.py
│   │       ├── public_goods.py
│   │       ├── ecological_verification.py
│   │       ├── partner_sponsorship.py
│   │       └── regional_clusters.py
│   ├── forecast/       # Forecast engine
│   │   ├── engine.py         # Scenario-based NOI, revenue, yield forecasting
│   │   ├── cli.py            # CLI for forecasts, comparisons, sensitivity
│   │   ├── config.py         # Forecast configuration
│   │   ├── models.py         # Data models
│   │   ├── pricing.py        # Price projections
│   │   ├── yield_forecast.py # Yield projections
│   │   ├── cost_forecast.py  # Cost projections
│   │   ├── ecology.py        # Ecological score projections
│   │   └── risk.py           # Risk adjustment + confidence intervals
│   ├── export/         # Data export and report generation
│   │   ├── exporter.py       # CSV/JSON/Parquet export
│   │   └── report_generator.py # Report snapshots with hash verification
│   ├── registry/       # Common Data Schema + MRV payload helpers
│   ├── agents/         # Agent capability manifest helpers
│   └── storage/        # Local development CID adapter
├── extensions/
│   └── kokonut-hooks/  # Directus lifecycle hooks
│       └── src/
│           ├── index.ts              # Hook registration
│           ├── workflow.ts           # State machine + role routing
│           ├── metrics-calculator.ts # NOI, loss rate, operating margin
│           └── ai-helpers.ts         # Auto-categorization, validation
├── migrations/         # Baserow migration scripts
├── scripts/            # Setup, seed, backup, snapshot
├── tests/              # Smoke, CLI, seed idempotency, attestation, metadata tests
├── docs/               # Architecture, data dictionary, API reference, attestation guide
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
| `eas_indexer.py` | EAS GraphQL API (Celo/Optimism/Base) | `attestation_record` + `attestation_schema` | Working |
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

Every important record follows: **Draft → Submitted → Verified → Published**

- **Draft:** Record created; source payload preserved where available
- **Submitted:** Mapped to Kokonut canonical schema and submitted for review
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

Pre-seeded data for the Kokonut Demo Farm (Kisumu, Kenya) across 12 pilot seed files, plus 2 base seed files:

| File | Content |
|------|---------|
| `001_pilot_farm.sql` | Location, farm, plots, crops, crop cycles, partners, staff, infrastructure |
| `002_pilot_operations.sql` | Activities, harvests, sales, expenses, losses, labor, field notes |
| `003_pilot_environmental.sql` | Soil samples, weather, remote sensing, sensors, alerts |
| `004_pilot_web3.sql` | Wallet activity, digital lego usage, attestations, chain indexer status |
| `005_pilot_forecasts.sql` | Forecast scenarios, forecast outputs, NOI snapshots |
| `006_pilot_farm_dao.sql` | Governance events, metric definitions, treasury events |
| `007_pilot_prices.sql` | Crop and commodity price observations |
| `008_pilot_capital_flows.sql` | Capital sources, value flows, cash-flow snapshots |
| `009_pilot_carbon_biodiversity.sql` | Soil carbon measurements, species observations, environmental baselines |
| `010_pilot_mrv_claims.sql` | MRV claims and verification reviews |
| `011_pilot_partners_extended.sql` | Additional buyers and cross-buyer sales |
| `012_pilot_bioinputs.sql` | Bioinput expenses and biofactory infrastructure |
| `013_pilot_registry_mrv_agents.sql` | Farm registry, inventory, maintenance, revenue, MRV events, attestation requests, agent metadata |
| `014_pilot_celo_eas.sql` | Celo chain indexer status and EAS schema registrations |

```bash
# Seed all pilot farm data
./scripts/seed-pilot.sh

# Or run individual files
docker compose exec -T database psql -U kokonut -d kokonut_intelligence \
  < schemas/seeds/001_pilot_farm.sql
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
python3 -m services.fortune500.cli --location-id <location-id>

# Rank all farms
python3 -m services.fortune500.cli --all
```

## Revenue Forecasting

Time-series projection engine with Monte Carlo simulation:

```bash
# Run forecast for a location (3, 6, 12 months)
python3 -m services.forecast.cli --location-id <location-id>

# Custom horizon and simulations
python3 -m services.forecast.cli --location-id <location-id> \
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
| [Attestation Guide](docs/attestation-guide.md) | EAS on Celo: schemas, onchain/offchain attestation, private data, CLI |
| [Partner Dashboards](docs/partner-dashboards.md) | Dashboard flexibility (Directus/Metabase/Custom) |
| [Agent Access](docs/agent-access.md) | MCP, agent-scoped tokens, audit logging |
| [Export Guide](docs/export-guide.md) | Data export and report snapshots |

## License

Open source — see LICENSE file.
