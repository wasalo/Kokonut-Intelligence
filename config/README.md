# Configuration Directory

Service-specific configuration files for the Kokonut Intelligence platform. Each subdirectory holds configuration for a service or infrastructure adapter. These files are shared by the legacy Compose stack and selected Kernel overlays; they are not all loaded by every deployment profile.

> The root `docker-compose.yml` is the legacy integration stack. The Kernel
> candidate uses the explicit `docker-compose.kernel-*` manifests and keeps
> Directus, ClickHouse, Prefect, Mosquitto, gRPC, and Caddy selectable or
> replaceable. See the [current architecture and deployment status](../docs/refactor/current-state-and-implementation.md).

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
| **Legacy Compose volume mount (read-only)** | `caddy/`, `clickhouse/`, `mosquitto/` | The root and legacy overlays bind-mount the service-specific files. Kernel proxy, analytics, and MQTT overlays select their own mounts. |
| **Image build copy** | `config/` and `worker/crontab` | `Dockerfile.gateway`, `Dockerfile.worker`, `Dockerfile.grpc`, and `Dockerfile.kernel` copy configuration into their respective images; only a subset is used by each image. |
| **Explicit seed command** | `postgres/init.sql`, `postgres/extensions.sql`, `directus/permissions.sql` | `scripts/seed.sh` applies PostgreSQL bootstrap SQL and migrations, optionally seeds ClickHouse when it is available, and applies Directus permissions only when the Directus catalog exists. The Kernel candidate uses its own bootstrap and rollout procedure. |

## Security Notes

- **Private keys are never committed.** Credential files under `config/keys/` are ignored; this README is tracked. Mosquitto cert/key files are ignored with only the provisioning README tracked.
- **TLS certificates** are provisioned externally before the relevant service starts (Mosquitto fails without them).
- **`directus/permissions.sql`** is the canonical RBAC seed — roles, policies, and per-collection access rules for 6 human roles and 3 agent roles.

## Gateway (Kernel Profiles)

The FastAPI gateway (`services/gateway/`) runs in the selected Kernel Compose
profile. The legacy host command remains available for local development:

```bash
python3 -m services.gateway.cli --serve --port 8099
```

It provides the REST API, authentication, rate limits, and audit logging. Public
location reads use the bounded native PostgreSQL projection; they do not proxy
Directus. Identity, database, optional-provider, and transport settings are
configured through environment variables. Kernel Caddy ingress is an optional
overlay and proxies to the Gateway; Caddy is not required for the local
loopback candidate.

## Modifying Configs

1. **Legacy Caddy routes** — Edit `config/caddy/Caddyfile` or `Caddyfile.production` for the legacy stack. Kernel ingress uses `Caddyfile.kernel` (or `Caddyfile.kernel.zitadel` with the identity overlay); the Gateway owns API routing and CORS.
2. **ClickHouse tuning** — Add `.xml` files to `config/clickhouse/config.d/`. They are mounted by the legacy stack and optional Kernel analytics overlay; restart the selected ClickHouse service to reload them.
3. **Legacy worker cron** — Edit `config/worker/crontab` and rebuild the legacy worker image. The active crontab currently contains only the health-alert job; database scheduling is handled separately. Kernel uses its native worker runtime.
4. **MQTT access** — Edit `config/mosquitto/acl` and restart the selected legacy or Kernel MQTT service. New device certificates must be provisioned separately.
5. **Legacy PostgreSQL bootstrap** — `config/postgres/init.sql` and `extensions.sql` are applied explicitly by `./scripts/seed.sh`; they are not mounted into the PostgreSQL image's automatic entrypoint directory. Use ordered migrations for schema changes.
6. **Directus RBAC rules** — Edit `config/directus/permissions.sql` only for the optional Directus compatibility adapter. Apply through the seed script when Directus is configured; these permissions do not define Kernel Gateway authorization.
