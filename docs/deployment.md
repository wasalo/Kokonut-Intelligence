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
# Set PUBLIC_URL to your domain

# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Set up reverse proxy (nginx/caddy) for HTTPS
```

### Recommended VM Specs

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4GB | 8GB |
| Storage | 50GB SSD | 100GB SSD |
| Network | 1Gbps | 1Gbps |

### Ingestion Scheduler

Ingestion services are CLI tools and are not started by Docker Compose. Schedule them with cron, systemd timers, or a job runner on the host or VM.

Example cron entries (adjust paths and timezone as needed):

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

For production deployments, use the production overlay to apply memory limits and keep database services internal:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Place Directus and Metabase behind Caddy or another reverse proxy with TLS termination.

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
| `EAS_RESOLVER_ADDRESS` | EAS resolver contract address (`0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad`) | For EAS attestation |
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
