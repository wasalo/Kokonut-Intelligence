# Developer Sandbox

The developer sandbox runs the normal Compose stack with a one-shot seed container and sample farm data. It is for local development only. It does not create a separate static API key or provide production-safe credentials.

## Quick Start

```bash
# 1. Create local configuration and replace every placeholder with a strong value.
cp .env.example .env

# Alternatively load encrypted secrets into the environment:
# source scripts/load-secrets.sh

# 2. Start the stack with the sandbox profile. The sandbox-seed service runs once
#    after PostgreSQL and Directus become healthy, then exits successfully.
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox up -d

# 3. Inspect the one-shot seed output
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox logs sandbox-seed

# 4. Open the UIs through Caddy. The local certificate is self-signed.
open https://localhost/admin       # Directus admin
open https://localhost/directus    # Directus API
open https://localhost/metabase    # Metabase
```

The seed container waits up to two minutes for Directus, authenticates using
`ADMIN_EMAIL` and `ADMIN_PASSWORD`, prints the admin access token, lists dashboard
templates, and seeds sample data. To rerun the idempotent seed manually:

```bash
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox run --rm sandbox-seed
```

Do not commit `.env`, printed tokens, or other local secrets.

## What's Included

| Component | Access | Purpose |
|-----------|--------|---------|
| Directus API | `https://localhost/directus` through Caddy, or `http://localhost:8055` from the base Compose port | REST/GraphQL API and permissions |
| Directus admin | `https://localhost/admin` through Caddy | Admin UI |
| Metabase | `https://localhost/metabase` through Caddy | BI dashboards |
| PostgreSQL | Docker service `database:5432` | Canonical data store |
| ClickHouse | Docker service `clickhouse:8123` | Analytical event store |

The base Compose file publishes Directus on `127.0.0.1:8055`; Metabase is only exposed to the Compose networks and should normally be accessed through Caddy. A local override may publish Metabase on `localhost:3001`. PostgreSQL and ClickHouse are not published to the host by default; use the Compose service names from containers.

### Pre-seeded Data

- **Location**: Kokonut Demo Farm — Costa Rica (Guanacaste)
- **Farm**: Finca El Naranjo (45 ha agroforestry)
- **Plots**: 3 plots (Coffee, Cacao, Timber)
- **Crops**: Arabica Coffee, Trinitario Cacao, Plantain
- **Crop Cycles**: 3 sample cycles with expected yields; two are `active` and one is `harvesting`
- **Harvest Events**: 3 verified harvests
- **Expenses**: Sample verified expenses generated across January-June 2026 for five seeded categories
- **Cost Allocations**: Up to 20 direct allocations to randomly selected crop cycles
- **Attestation Schema**: `Harvest MRV Claim` sample schema on Optimism
- **Attestation Record**: 1 published sample record with an Optimism attestation UID
- **Base-seeded metadata**: Governed metric definitions, metric versions, and standard expense categories

The sample location is `costa-rica-demo` and the farm is `finca-el-naranjo`. Seed statements use conflict guards, but generated expense and allocation rows can vary across reruns.

### Dashboard Templates

Metabase dashboard JSON templates are mounted read-only at `/dashboards` inside the seed container and are listed by the setup script. The script does not import dashboards into Metabase. Templates are stored in `dashboards/` and must be imported through the Metabase UI or API after setup.

## Getting An API Token

The sandbox seed script prints the Directus admin access token after a successful login. It does not create a static sandbox token: the `SANDBOX_TOKEN` shell variable is generated but unused, and the script falls back to the admin token if it cannot create/find the optional `sandbox` role. Treat the printed token as a secret and use it only locally.

You can also generate a short-lived admin access token manually. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `DIRECTUS_URL` from your local configuration first:

```bash
# Use the direct host port or the Caddy API route.
DIRECTUS_URL=${DIRECTUS_URL:-https://localhost/directus}
TOKEN=$(curl -sk -X POST "$DIRECTUS_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
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
    "content": "Created from the developer sandbox hello world tutorial."
  }' | python3 -m json.tool
```

`field_note.status` defaults to `draft`. Directus create permissions do not allow clients to set lifecycle status; verification and publication are separate governed actions.

## Environment Variables

| Variable | Required | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password used by database, Directus, and Metabase |
| `DIRECTUS_SECRET` | Yes | Directus JWT secret; use a random value of at least 32 characters |
| `ADMIN_EMAIL` | Yes | Directus admin email used by the seed login |
| `ADMIN_PASSWORD` | Yes | Directus admin password used by the seed login |
| `CLICKHOUSE_PASSWORD` | Yes | ClickHouse password |
| `REDIS_PASSWORD` | Yes | Redis password required by the base stack |
| `METABASE_EMBEDDING_SECRET_KEY` | Yes | Metabase embedding secret |
| `PG_HOST` | Host-dependent | Use `database` inside Docker; `localhost` requires a host-published database port |
| `PG_PORT` | `5432` | PostgreSQL port |
| `PG_DB` | `kokonut_intelligence` | PostgreSQL database name |
| `PG_USER` | `kokonut` | PostgreSQL user |

The sandbox overlay passes `PGHOST=database`, `PGDATABASE=kokonut_intelligence`, and `PGUSER=kokonut` to the seed container. Do not use host database settings inside the container.

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

The seed container is a one-shot job and exits after setup — this is expected. Check output:

```bash
docker compose -f docker-compose.yml -f docker-compose.sandbox.yml --profile sandbox logs sandbox-seed
```

### Port conflict on 80 or 443

Another service is using the host HTTP/HTTPS ports. Stop it or change the Caddy port mapping in a local Compose override:

```yaml
ports:
  - "8443:443"  # Use a different host HTTPS port
```

## Analysis Sandbox Records

The platform also stores isolated analysis-environment state in PostgreSQL. These records are separate from the Docker sandbox profile:

| Table | Purpose |
|---|---|
| `analysis_environment` | Location-scoped environment with type and lifecycle status |
| `analysis_run` | Module execution, inputs, outputs, status, timing, resource usage, and errors |
| `analysis_sandbox` | Table allow/deny lists, query-row limit, execution timeout, and network-access flag |

`analysis_environment.env_type` accepts `metric_computation`, `crisp_scoring`, `agent_execution`, or `sandbox`. Environment status is `active`, `paused`, or `destroyed`; runs are `running`, `completed`, `failed`, `timeout`, or `cancelled`. Sandbox records default to 10,000 query rows, 300 seconds, and no network access. Runs are deleted with their environment, and sandbox configuration is deleted with its environment.

These database records describe analysis policy and execution history; they do not replace operating-system or container isolation.

## Source References

- Compose overlay: `docker-compose.sandbox.yml`
- Seed/bootstrap script: `scripts/sandbox-setup.sh`
- Analysis environment schema: `schemas/postgres/123_analysis_environments.sql`
- Field-note permissions: `config/directus/permissions.sql`
- Dashboard templates: `dashboards/`
