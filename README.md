# Kokonut Intelligence Platform

Open-source intelligence layer for regenerative farm operations, financial performance, ecological outcomes, and Web3 verification.

## Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Canonical core | PostgreSQL 14 + PostGIS 3.4 + Directus 11.17 | Schema, API, permissions, workflows, data entry UI |
| Analytics | ClickHouse 25.3 | Time-series, events, high-volume analytical queries |
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
│   ├── postgres/       # 9 schema files, 55 tables
│   ├── directus/       # Directus snapshots
│   └── clickhouse/     # Analytical schemas
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
└── dashboards/         # Metabase dashboard definitions
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

## License

Open source — see LICENSE file.
