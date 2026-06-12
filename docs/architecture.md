# Architecture

## System Overview

The Kokonut Intelligence Platform is a governed, open-source data operating system for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Core Principles

1. **The schema is the product** — Dashboards, spreadsheets, agents, and blockchain views are interfaces. The durable asset is the canonical schema, metric dictionary, verification logic, and API contract.

2. **Web3 is a proof layer, not source of truth** — Canonical operational and financial data lives in PostgreSQL. Blockchain provides proofs, coordination, and public verifiability.

3. **Humans and AI agents use the same governed objects** — Different interfaces over the same canonical objects, permissions, and audit trails.

4. **Private evidence stays off-chain by default** — Public surfaces store hashes, CIDs, attestation UIDs, chain labels, and transaction hashes. Raw private MRV payloads remain in controlled off-chain storage.

## Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    INTERFACES                           │
│  Directus Studio │ Metabase │ API │ Agents             │
└────────┬────────┴─────┬─────┴──┬──┴────┬───────────────┘
         │              │        │       │
┌────────▼──────────────▼────────▼───────▼───────────────┐
│                    DIRECTUS                             │
│          REST API │ GraphQL │ SDK │ Flows              │
│          Permissions │ Automations │ Webhooks           │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                 POSTGRESQL + POSTGIS                     │
│                                                         │
│  Master Data    Operational Facts    Financial Facts    │
│  ──────────     ────────────────     ──────────────    │
│  locations      farm_activity        financial_txn      │
│  farms          harvest_event        expense_event      │
│  plots          sales_event          crop_cost_alloc    │
│  crops          loss_event           noi_snapshot       │
│  crop_cycle     labor_event          cash_flow_snap     │
│  partners       field_note           value_flow_event   │
│  farm_registry  inventory_event      revenue_event      │
│                 maintenance_event                       │
│                                                         │
│  Environmental    Web3/Attestation    Modeled Outputs   │
│  ─────────────    ────────────────    ──────────────    │
│  soil_sample      wallet_profile      forecast_scenario  │
│  species_obs      attestation_record  forecast_output    │
│  remote_sensing   digital_lego_usage  metric_definition  │
│  weather_obs      attestation_schema  report_snapshot    │
│  sensor_reading   mrv_event           ai_summary         │
│  attestation_req  governance_event    agent_task         │
│  price_observation                    ingestion_log      │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│              PYTHON INGESTION LAYER                     │
│                                                         │
│  weather.py       → OpenWeatherMap API                  │
│  rpc_indexer.py   → Ethereum/L2 public RPC              │
│  market_data.py   → World Bank Pink Sheet               │
│  remote_sensing.py → CSV upload (NDVI/NDRE)            │
│  eas_indexer.py   → EAS GraphQL API                     │
│                                                         │
│  All scripts: services/ingestion/                       │
│  Common framework: base.py (DB, logging, retry)         │
└────────┬───────────────────────────────────────────────┘
         │
┌────────▼───────────────────────────────────────────────┐
│                   CLICKHOUSE                            │
│                                                         │
│  events_raw │ wallet_events │ sensor_readings           │
│  weather_events │ financial_events │ dlego_events       │
│                                                         │
│  Materialized Views:                                     │
│  daily_event_counts │ hourly_sensor_stats               │
│  daily_wallet_activity │ monthly_financial_summary      │
│  daily_weather_summary │ daily_sensor_summary           │
│  sensor_reading_rate                                    │
└─────────────────────────────────────────────────────────┘
```

## Data Lifecycle

Every important record follows four states:

```
Draft → Submitted → Verified → Published
 │        │           │          │
 │        │           │          └─ Available to dashboards, APIs, attestations
 │        │           └─ Reviewed, validated, linked to evidence
 │        └─ Mapped to Kokonut canonical schema and submitted for review
 └─ Record created; source payload preserved where available
```

## Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state.

- `schemas/postgres/` — Source of truth for database schema
- `schemas/directus/` — Directus snapshot exports
- `schemas/clickhouse/` — Analytical event schemas

## API Layers

| Layer | Protocol | Auth | Use Case |
|-------|----------|------|----------|
| Directus REST | HTTP REST | Bearer token | CRUD, admin, integrations |
| Directus GraphQL | GraphQL | Bearer token | Complex queries, frontend |
| Directus SDK | JavaScript | Session | Application integration |
| ClickHouse HTTP | HTTP | Basic auth | Analytical queries |
| Directus MCP | MCP | Scoped token | AI agent access |
| Helper CLIs | Python modules | Local process auth | Registry validation, local CID prep, attestation request prep, agent manifest prep |

## Security Model

- **Roles:** Administrator, Field Worker, Supervisor, Manager, Finance, Analyst
- **Policies:** Per-collection, per-action, per-field permissions (84 rules across 5 policies)
- **Field-level:** Sensitive fields hidden per role
- **Row-level:** Filter rules restrict record visibility
- **Audit:** All mutations logged to `audit_log`
- **Evidence:** Raw evidence stored off-chain; hashes/CIDs on-chain
- **Agent scope:** This repository stores agent metadata and tasks only; marketplace identity, payment, escrow, and reputation logic are external to `Kokonut-Agentic-Marketplace`

## Data Ingestion

External data flows through Python scripts in `services/ingestion/`:

| Source | Script | Frequency | Target |
|--------|--------|-----------|--------|
| OpenWeatherMap | `weather.py` | On demand | `weather_observation` + ClickHouse |
| Ethereum/L2 RPC | `rpc_indexer.py` | On demand | `wallet_activity_event` + ClickHouse |
| World Bank | `market_data.py` | On demand | `price_observation` |
| CSV upload | `remote_sensing.py` | On demand | `remote_sensing_observation` |
| EAS API | `eas_indexer.py` | On demand | `attestation_record` |

DApp session ingestion and metrics are deferred. Current Web3 ingestion remains focused on wallet activity, protocol interactions, EAS attestations, and governed value-flow records.

All ingestion is logged to `ingestion_log` with source, status, and timing. Chain indexer health tracked in `chain_indexer_status`.
