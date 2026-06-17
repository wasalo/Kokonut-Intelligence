# Developer Sandbox

A pre-configured local environment with sample farm data, dashboards, and API keys for testing and development.

## Quick Start

```bash
# 1. Start the stack with sandbox profile
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox up -d

# 2. Wait ~60 seconds for services to initialize, then run seed
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox run --rm sandbox-seed

# 3. Open the UIs through Caddy
open https://localhost/admin      # Directus admin
open https://localhost/metabase   # Metabase dashboards
```

## What's Included

| Component | Base Compose URL | Purpose |
|-----------|------------------|---------|
| Directus | `https://localhost` or `https://localhost/directus` | Admin UI, REST/GraphQL API, permissions |
| Directus admin | `https://localhost/admin` | Admin UI route through Caddy |
| Metabase | `https://localhost/metabase` | Embedded BI dashboards |
| PostgreSQL | Docker service `database:5432` | Canonical data store |
| ClickHouse | Docker service `clickhouse:8123` | Analytical event store |

Optional local overrides may expose Directus at `http://localhost:8055` and Metabase at `http://localhost:3001`. The sandbox overlay does not expose PostgreSQL or ClickHouse to the host by default.

### Pre-seeded Data

- **Location**: Kokonut Demo Farm — Costa Rica (Guanacaste)
- **Farm**: Finca El Naranjo (45 ha agroforestry)
- **Plots**: 3 plots (Coffee, Cacao, Timber)
- **Crops**: Arabica Coffee, Trinitario Cacao, Plantain
- **Crop Cycles**: 3 active cycles with expected yields
- **Harvest Events**: 3 verified harvests
- **Expenses**: 6 months of recurring expense events
- **Cost Allocations**: Direct allocations to crop cycles
- **Attestation Schema**: Harvest MRV Claim
- **Attestation Record**: 1 published sample record with an on-chain attestation UID
- **Metric Definitions**: Governed metrics with version records
- **Expense Categories**: 9 standard categories

### Dashboard Templates

Metabase dashboard JSON templates are in `dashboards/`. Import them via the Metabase UI or API after setup.

## Getting Your API Key

The sandbox seed script prints an admin API token. You can also generate one manually:

```bash
# Login and get access token
DIRECTUS_URL=${DIRECTUS_URL:-https://localhost/directus}
TOKEN=$(curl -sk -X POST "$DIRECTUS_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kokonut.network","password":"KokonutDev2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# Use it
curl -sk -H "Authorization: Bearer $TOKEN" "$DIRECTUS_URL/items/location"
```

## Hello World: 5 API Calls

### 1. List all locations

```bash
curl -sk -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/location?fields[]=id&fields[]=name&fields[]=slug" \
  | python3 -m json.tool
```

### 2. Get a specific farm with its plots

```bash
curl -sk -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/farm?filter[slug][eq]=finca-el-naranjo&fields[]=*&fields[]=plots.*" \
  | python3 -m json.tool
```

### 3. Query crop cycles with status

```bash
curl -sk -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/crop_cycle?fields[]=cycle_name&fields[]=status&fields[]=expected_yield&filter[status][eq]=active" \
  | python3 -m json.tool
```

### 4. List verified harvest events

```bash
curl -sk -H "Authorization: Bearer $TOKEN" \
  "$DIRECTUS_URL/items/harvest_event?filter[status][eq]=verified&fields[]=harvest_date&fields[]=quantity&fields[]=unit&fields[]=quality_grade&sort[]=-harvest_date" \
  | python3 -m json.tool
```

### 5. Create a new field note (POST)

```bash
curl -sk -X POST "$DIRECTUS_URL/items/field_note" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "note_date": "2026-06-10",
    "note_type": "observation",
    "title": "First sandbox note",
    "content": "Created from the developer sandbox hello world tutorial.",
    "status": "draft"
  }' | python3 -m json.tool
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `dev-kokonut-postgres-2026` | PostgreSQL password |
| `DIRECTUS_SECRET` | `dev-directus-secret-at-least-32-chars!!` | Directus JWT secret |
| `ADMIN_EMAIL` | `admin@kokonut.network` | Directus admin email |
| `ADMIN_PASSWORD` | `KokonutDev2026!` | Directus admin password |
| `METABASE_EMBEDDING_SECRET_KEY` | `sandbox-dev-secret-key-change-in-production` | Metabase embedding secret |
| `CLICKHOUSE_PASSWORD` | `dev-clickhouse-kokonut-2026` | ClickHouse password |
| `PG_HOST` | `localhost` | PostgreSQL host (use `database` inside Docker) |
| `PG_PORT` | `5432` | PostgreSQL port |
| `PG_DB` | `kokonut_intelligence` | PostgreSQL database name |
| `PG_USER` | `kokonut` | PostgreSQL user |

## Stopping the Sandbox

```bash
# Stop containers (preserves data)
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox stop

# Full teardown (destroys data volumes)
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox down -v
```

## Troubleshooting

### Directus route is unavailable

Directus is still starting or Caddy is not ready. Wait 30 seconds and retry. Check logs:

```bash
docker compose logs directus | tail -20
```

### "relation does not exist" during seed

The schema hasn't been applied yet. Run the base seed first:

```bash
./scripts/seed.sh
```

### Metabase shows "Database not found"

Metabase needs the `kokonut` database to exist. Ensure PostgreSQL is healthy:

```bash
docker compose ps database
docker compose logs database | tail -10
```

### Sandbox seed container exits immediately

The seed container runs once and exits — this is expected. Check output:

```bash
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox logs sandbox-seed
```

### Port conflict on 80 or 443

Another service is using the host HTTP/HTTPS ports. Stop it or change the Caddy port mapping in a local Compose override:

```yaml
ports:
  - "8443:443"  # Use a different host HTTPS port
```
