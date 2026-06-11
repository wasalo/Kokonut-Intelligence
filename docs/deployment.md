# Deployment Guide

## Local Development

### Prerequisites

- Docker Desktop (with Docker Compose v2)
- 4GB+ RAM available for Docker
- Ports available: 5432, 8055, 3001, 8123, 9000

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

# 5. Apply schema and seed data
./scripts/seed.sh
```

### Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Directus | http://localhost:8055 | Schema management, API, admin |
| Metabase | http://localhost:3001 | Internal BI dashboards |
| PostgreSQL | localhost:5432 | Canonical data store |
| ClickHouse HTTP | http://localhost:8123 | Analytical queries |
| ClickHouse Native | localhost:9000 | Native protocol |

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
docker compose -f docker-compose.yml up -d

# Set up reverse proxy (nginx/caddy) for HTTPS
```

### Recommended VM Specs

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4GB | 8GB |
| Storage | 50GB SSD | 100GB SSD |
| Network | 1Gbps | 1Gbps |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
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
| `BASEROW_API_URL` | Baserow API URL | For migration |
| `BASEROW_TOKEN` | Baserow API token | For migration |

### Python Dependencies

Ingestion scripts require Python 3.9+ with:

```bash
pip3 install requests web3 clickhouse-connect psycopg2-binary
```

### ClickHouse Configuration

ClickHouse requires `listen_host: 0.0.0.0` to accept HTTP connections from the host. This is configured in `config/clickhouse/config.d/network.xml` and applied automatically by `seed.sh`.

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
docker exec -it kokonut-intelligence-database-1 psql -U kokonut -d kokonut_intelligence

# ClickHouse
docker exec -it kokonut-intelligence-clickhouse-1 clickhouse-client -u kokonut --password YOUR_PASSWORD
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
