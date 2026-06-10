# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Canonical core | PostgreSQL + PostGIS + Directus | Schema, API, permissions, workflows |
| Human workbench | Baserow / Grist | Staff data entry (interfaces, not source of truth) |
| Analytics | ClickHouse | Time-series, events, high-volume analytical queries |
| BI | Metabase | Internal dashboards, aggregate reporting |
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

# 4. Access Directus
open http://localhost:8055

# 5. Access Metabase
open http://localhost:3001
```

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Directus | http://localhost:8055 | Schema management, API, admin UI |
| Metabase | http://localhost:3001 | Internal BI dashboards |
| ClickHouse HTTP | http://localhost:8123 | Analytical queries |
| PostgreSQL | localhost:5432 | Canonical data store |

## Schema Management

Schemas are version-controlled as SQL files in `schemas/postgres/`. Directus snapshots capture the API-layer state.

```bash
# Apply schema changes
docker compose exec database psql -U kokonut -d kokonut_intelligence -f /path/to/schema.sql

# Snapshot Directus schema
./scripts/schema-snapshot.sh
```

## Directory Structure

```
├── config/           # Service configurations
├── schemas/          # Database schemas (Postgres, ClickHouse)
├── migrations/       # Data migration scripts
├── extensions/       # Directus extensions
├── scripts/          # Operational scripts
├── dashboards/       # Dashboard definitions
└── docs/             # Architecture documentation
```

## Data Lifecycle

Every important record follows: **Raw → Normalized → Verified → Published**

## License

Open source — see LICENSE file.
