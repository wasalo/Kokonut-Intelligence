# Deployment Guide

## Local Development

### Prerequisites

- Docker Desktop (with Docker Compose v2)
- 4GB+ RAM available for Docker
- Ports available for base Compose: 80 and 443. PostgreSQL, ClickHouse, Directus, and Metabase are internal Docker services unless a local override exposes additional ports.

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/wasalo/Kokonut-Intelligence.git
cd Kokonut-Intelligence

# 2. Configure environment
cp .env.example .env
# Edit .env with your secrets

# 3. Start all services
docker compose up -d

# 4. Wait for health checks
docker compose ps

# 5. Apply schema, seed data, metrics, and MVP checks
./scripts/seed.sh
./scripts/seed-pilot.sh
./scripts/compute-metrics.sh
./scripts/verify-mvp.sh
```

### Service URLs

| Service | Base Compose URL | Purpose |
|---------|------------------|---------|
| Caddy | `https://localhost` | TLS termination, reverse proxy, security headers |
| Directus | `https://localhost` or `https://localhost/directus` | Schema management, API, admin |
| Directus admin | `https://localhost/admin` | Admin UI route through Caddy |
| Metabase | `https://localhost/metabase` | Internal BI dashboards |
| PostgreSQL | Docker service `database:5432` | Canonical data store |
| ClickHouse HTTP | Docker service `clickhouse:8123` | Analytical queries |
| ClickHouse Native | Docker service `clickhouse:9000` | Native protocol |

Optional local overrides may expose Directus at `http://localhost:8055` and Metabase at `http://localhost:3001`. Use those direct URLs only when your Compose overlay maps the ports.

### Stopping Services

```bash
docker compose down          # Stop containers
docker compose down -v       # Stop and remove volumes (deletes data)
```

## Cloud Deployment

### Docker Compose on a VM

```bash
# On your cloud VM:
git clone https://github.com/wasalo/Kokonut-Intelligence.git
cd Kokonut-Intelligence

# Configure for production
cp .env.example .env
# Edit .env with production secrets
# Set PUBLIC_URL and CADDY_DOMAIN to your domain

# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Reverse Proxy Options

The platform includes a built-in Caddy reverse proxy for TLS termination. For VPS environments that already run Traefik (or another reverse proxy), use the Traefik overlay instead.

**Option A: Built-in Caddy (default)**

Caddy binds to ports 80 and 443 by default. Change them via env vars if needed:

```bash
# .env
CADDY_DOMAIN=kokonut.example.com
CADDY_HTTP_PORT=80
CADDY_HTTPS_PORT=443

# Start with production overlay
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Option B: External Traefik**

If your VPS already runs Traefik on ports 80/443, use the Traefik overlay to disable Caddy and let Traefik route to the internal services:

```bash
# .env
KOKONUT_DOMAIN=kokonut.example.com
KOKONUT_METABASE_DOMAIN=metabase.example.com
KOKONUT_TRAEFIK_NETWORK=traefik
KOKONUT_TLS_RESOLVER=letsencrypt

# Start with production + Traefik overlays
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml up -d
```

Prerequisites for Traefik:
1. An external Traefik container running on the host
2. A shared Docker network named `traefik` (or set `KOKONUT_TRAEFIK_NETWORK`)
3. Traefik `websecure` entrypoint (443) with TLS resolver configured
4. `KOKONUT_DOMAIN` must be set in `.env`

The Traefik overlay creates routes:
- `Host(kokonut.example.com)` → Directus on port 8055
- `Host(metabase.kokonut.example.com)` → Metabase on port 3000

### Worker Container (Optional)

Python ingestion services (weather, market data, EAS indexer, RPC indexer, sensor ingester, anomaly detection, metrics computation) are CLI tools. By default, they run on the host via cron. For production isolation, use the worker container:

```bash
# Build and start the worker container
docker compose -f docker-compose.yml -f docker-compose.worker.yml --profile worker up -d kokonut-worker
```

The worker container runs a cron daemon with all ingestion jobs pre-configured in `config/worker/crontab`. To customize the schedule, edit the crontab file and rebuild.

To run ad-hoc commands inside the worker:

```bash
docker compose exec kokonut-worker python3 -m services.metrics --list
docker compose exec kokonut-worker python3 -m services.analytics --portfolio-summary
docker compose exec kokonut-worker bash scripts/health-check.sh
```

Alternatively, keep the host-based CLI approach (see Ingestion Scheduler below) — both paths are fully supported.

### Monitoring and Alerting

The platform includes `scripts/health-check.sh` for continuous health monitoring. In production, run it as a cron job with alerting:

```bash
# Cron entry — every 5 minutes
*/5 * * * * /opt/Kokonut-Intelligence/scripts/health-alert.sh
```

**What is checked:**
- PostgreSQL connection and key tables
- Directus server ping and health endpoint
- ClickHouse HTTP ping and query
- Metabase health endpoint
- Docker container status (running + no crashed containers)
- Disk usage (alert at 90% by default, configurable via `DISK_THRESHOLD`)
- Memory usage (alert at 90% by default, configurable via `MEM_THRESHOLD`)

**Alert channels (configure in `.env`):**

| Channel | Env vars | Notes |
|---------|----------|-------|
| Webhook | `ALERT_WEBHOOK_URL` | Slack/Discord/Teams incoming webhook |
| Email | `ALERT_SMTP_HOST`, `ALERT_SMTP_USER`, `ALERT_SMTP_PASSWORD`, `ALERT_EMAIL_TO` | SMTP with TLS |

Both channels can be active simultaneously. Alerts are only sent on failure — healthy checks produce no output (quiet cron).

**JSON output mode** for external monitoring integration:

```bash
./scripts/health-check.sh --json
# {"hostname":"vps-01","timestamp":"2026-06-29T12:00:00Z","pass":12,"fail":0,"failures":"","disk_pct":45,"mem_pct":62}
```

### Production Checklist

Before deploying to production:

- [ ] All secrets in `.env` set with strong values (24+ chars for passwords, 32+ chars for tokens)
- [ ] `KOKONUT_ENV=production` set
- [ ] `CADDY_DOMAIN` or `KOKONUT_DOMAIN` set to your domain
- [ ] TLS configured (Caddy auto-provisions or Traefik with cert resolver)
- [ ] `docker-compose.prod.yml` applied (no direct port exposure to host)
- [ ] Worker container or cron scheduler set up for ingestion jobs
- [ ] Health-check cron with alerting configured
- [ ] Backup cron job configured (`scripts/backup.sh`)
- [ ] Resource limits reviewed for your VM size
- [ ] Directus `ADMIN_PASSWORD` changed from default
- [ ] `METABASE_EMBEDDING_SECRET_KEY` set to a strong value

### Recommended VM Specs

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4GB | 8GB |
| Storage | 50GB SSD | 100GB SSD |
| Network | 1Gbps | 1Gbps |

### Ingestion Scheduler

Ingestion services are CLI tools. Two options are available:

1. **Worker container** (recommended for production) — see [Worker Container](#worker-container-optional) section above. All cron jobs are pre-configured in `config/worker/crontab`.

2. **Host-based cron** — schedule directly on the host or VM. Use the entries below as a starting point.

Example cron entries for host-based scheduling (adjust paths and timezone as needed):

```cron
# Weather — every 6 hours
0 */6 * * * cd /opt/Kokonut-Intelligence && python3 -m services.ingestion.weather >> /var/log/kokonut/weather.log 2>&1

# Market data — daily at 06:00 UTC
0 6 * * * cd /opt/Kokonut-Intelligence && python3 -m services.ingestion.market_data >> /var/log/kokonut/market.log 2>&1

# EAS indexer — every 15 minutes
*/15 * * * * cd /opt/Kokonut-Intelligence && python3 -m services.ingestion.eas_indexer >> /var/log/kokonut/eas.log 2>&1

# RPC wallet indexer — every 30 minutes
*/30 * * * * cd /opt/Kokonut-Intelligence && python3 -m services.ingestion.rpc_indexer >> /var/log/kokonut/rpc.log 2>&1

# Sensor ingester — every 5 minutes (when devices are active)
*/5 * * * * cd /opt/Kokonut-Intelligence && python3 -m services.ingestion.sensor_ingester >> /var/log/kokonut/sensors.log 2>&1
```

Ensure `KOKONUT_ENV=production` and all required secrets are set in the environment used by the scheduler. Use `./scripts/health-check.sh` after deploy to verify service connectivity.

### Production Compose

For production deployments, use the production overlay to apply memory limits and keep all services internal to Docker networks:

```bash
# With built-in Caddy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With external Traefik
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml up -d

# With worker container for ingestion
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.worker.yml --profile worker up -d
```

The production overlay does not expose Directus or Metabase directly to the host. All traffic goes through the reverse proxy (Caddy or Traefik). For temporary direct access during troubleshooting, create a local override:

```bash
echo 'services:
  directus:
    ports: ["8055:8055"]
  metabase:
    ports: ["3001:3000"]' > docker-compose.debug.yml

docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.debug.yml up -d
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `KOKONUT_ENV` | Runtime mode: `development` (default) or `production` | No |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes |
| `DIRECTUS_SECRET` | JWT signing secret (32+ chars) | Yes |
| `ADMIN_EMAIL` | Directus admin email | Yes |
| `ADMIN_PASSWORD` | Directus admin password | Yes |
| `PUBLIC_URL` | Public URL for Directus | Yes |
| `CLICKHOUSE_PASSWORD` | ClickHouse password | Yes |
| `OpenWeatherMap_API_KEY` | OpenWeatherMap API key (free tier) | For weather |
| `ETH_RPC_URL` | Ethereum RPC endpoint | For RPC indexer |
| `OPTIMISM_RPC_URL` | Optimism RPC endpoint | For RPC indexer |
| `BASE_RPC_URL` | Base RPC endpoint | For RPC indexer |
| `ARBITRUM_RPC_URL` | Arbitrum RPC endpoint | For RPC indexer |
| `CELO_RPC_URL` | Celo RPC endpoint (default: `https://forno.celo.org`) | For EAS attestation |
| `ATTESTER_PRIVATE_KEY` | Private key for EAS attestation wallet | For EAS attestation |
| `EAS_RESOLVER_ADDRESS` | EAS resolver contract address (`0x7A7390Ceb3E8145EffB81914271DA0ebDaF932Ef`) | For EAS attestation |
| `BASEROW_API_URL` | Baserow API URL | For migration |
| `BASEROW_TOKEN` | Baserow API token | For migration |

### Python Dependencies

Ingestion scripts require Python 3.9+ with:

```bash
pip3 install requests web3 clickhouse-connect psycopg2-binary
```

### Foundry (Solidity Contracts)

```bash
# Install Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Build contracts
cd contracts && forge build

# Run tests
cd contracts && forge test

# Deploy resolver to Celo mainnet (requires ATTESTER_PRIVATE_KEY in .env)
cd contracts && forge script script/DeployKokonutResolver.s.sol \
  --rpc-url https://forno.celo.org \
  --broadcast \
  --verify
```

**Celo EAS Contracts:**

| Contract | Address |
|----------|---------|
| EAS | `0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92` |
| SchemaRegistry | `0x5ece93bE4BDCF293Ed61FA78698B594F2135AF34` |
| KokonutResolver | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` |

### ClickHouse Configuration

ClickHouse listens inside the Docker network for service-to-service access. Query it with `docker compose exec clickhouse ...` or expose its ports only through an intentional local override.

## Database Management

### Backup

```bash
./scripts/backup.sh
```

Backups are saved to `backups/` directory.

### Schema Snapshots

```bash
./scripts/schema-snapshot.sh
```

Snapshots are saved to `schemas/directus/snapshots/`.

### Direct Access

```bash
# PostgreSQL
docker compose exec database psql -U kokonut -d kokonut_intelligence

# ClickHouse
docker compose exec clickhouse clickhouse-client -u kokonut --password YOUR_PASSWORD
```

## Troubleshooting

### Directus won't start

- Check PostgreSQL is healthy: `docker compose ps`
- Check logs: `docker compose logs directus`
- Verify `.env` secrets are set

### Schema changes not appearing

- Restart Directus: `docker compose restart directus`
- Check schema files are in `schemas/postgres/`
- Run `./scripts/seed.sh` to reapply

### Metabase connection refused

- Wait 2-3 minutes for initial setup
- Check logs: `docker compose logs metabase`
- Verify PostgreSQL credentials in `.env`
