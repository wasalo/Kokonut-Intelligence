# Configuration Directory

Service-specific configuration files for the Kokonut Intelligence platform. Each subdirectory holds configs for a single Docker service or infrastructure component.

## Directory Layout

```
config/
├── caddy/          Reverse proxy (TLS termination, routing)
├── clickhouse/     Analytical database engine tuning
├── directus/       RBAC permission seed (roles, policies, access rules)
├── keys/           Service account credentials (gitignored)
├── mosquitto/      MQTT broker config, ACL, and TLS certificates
├── postgres/       Database initialization and extensions
├── prefect/        Workflow deployment schedules
└── worker/         Cron schedule for the worker container
```

## How Configs Are Loaded

| Mechanism | Configs | How It Works |
|---|---|---|
| **Docker volume mount (ro)** | `caddy/`, `clickhouse/`, `mosquitto/` | `docker-compose.yml` bind-mounts files into the container at read-only paths |
| **Docker COPY** | `worker/crontab`, `keys/`, all of `config/` | `Dockerfile.worker` and `Dockerfile.grpc` copy `config/` into `/app/config/` at build time |
| **Seed script (cat pipe)** | `postgres/init.sql`, `postgres/extensions.sql`, `directus/permissions.sql` | `scripts/seed.sh` reads these files and pipes them to PostgreSQL via `docker exec psql` |

## Security Notes

- **Private keys are never committed.** `config/keys/` is fully gitignored. Mosquitto cert/key files are gitignored with only the README tracked.
- **TLS certificates** are provisioned externally before the relevant service starts (Mosquitto fails without them).
- **`directus/permissions.sql`** is the canonical RBAC seed — roles, policies, and per-collection access rules for 6 human roles and 3 agent roles.

## Gateway (Host-Only)

The FastAPI API gateway (`services/gateway/`) is **not containerized** and **not routed through Caddy**. It runs as a host-only process:

```bash
python3 -m services.gateway.cli --serve --port 8099
```

It provides a public REST API (`/api/locations`, `/api/metrics/{id}`, `/api/crisp/{id}`, etc.) with API key auth, rate limiting, and audit logging. It reads `DIRECTUS_URL` and `DIRECTUS_ADMIN_TOKEN` from the environment to proxy Directus requests. No config file exists for it — it is configured entirely via environment variables.

## Modifying Configs

1. **Caddy routes** — Edit `config/caddy/Caddyfile` (dev) or `Caddyfile.production` (prod). The production overlay in `docker-compose.prod.yml` swaps the mount. Both files must be kept in sync for route parity.
2. **ClickHouse tuning** — Add `.xml` files to `config/clickhouse/config.d/`. The entire directory is mounted read-only; new files are picked up on restart.
3. **Cron jobs** — Edit `config/worker/crontab`. Changes require rebuilding the worker image (`docker compose build kokonut-worker`).
4. **MQTT access** — Edit `config/mosquitto/acl` and restart Mosquitto. New device certificates must be added by the provisioning workflow.
5. **Database extensions** — Edit `config/postgres/init.sql` (standard) or `extensions.sql` (superuser). Apply via `./scripts/seed.sh`.
6. **RBAC rules** — Edit `config/directus/permissions.sql`. Apply via `./scripts/seed.sh`. Idempotent with `ON CONFLICT` guards.
