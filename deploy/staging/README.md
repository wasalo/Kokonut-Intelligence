# Legacy Compose staging runbook (deployment workflow paused)

This is an operational runbook for the legacy Compose integration stack, not a
Kernel candidate or Standard profile deployment. The GitHub Actions workflow
is currently paused in source (`DEPLOY_STAGING_ENABLED=no`) and intentionally
fails before deployment. A configured runner label and Compose files do not
mean staging is deployed or accepted. See the [current architecture and
implementation guide](../../docs/refactor/current-state-and-implementation.md).

When deliberately re-enabled through a reviewed change, the workflow targets
the dedicated self-hosted runner and the legacy `ki-staging` Compose project.
CI and pull-request jobs run on GitHub-hosted workers.

**Never point staging tooling at CI or production, or vice versa.**

## Layout

| What | Where |
|---|---|
| Git checkout | `/opt/ki-staging` (branch `main`) |
| Compose project | `ki-staging` |
| Env (encrypted) | `/opt/ki-staging/deploy/staging/.env.staging.sops` |
| age private key | `/opt/ki-staging/.age-key` (0600) |
| Backups | `/opt/ki-staging/backups` (nightly 03:30, keep 7) |
| Logs | `docker compose -p ki-staging logs -f [service]` |

## Host ports (loopback only)

| Service | Port |
|---|---|
| Directus | 18056 |
| Metabase | 13001 |
| Gateway | 18098 |
| gRPC | 50053 |

Database and ClickHouse are not published — access via
`docker compose -p ki-staging exec database psql ...` or an SSH tunnel.

## Bootstrap from scratch

```bash
# 1. Checkout
sudo mkdir -p /opt/ki-staging && sudo chown $USER /opt/ki-staging
git clone https://github.com/wasalo/Kokonut-Intelligence.git /opt/ki-staging && cd /opt/ki-staging

# 2. Tools (if not already installed)
sudo apt-get install -y sops age   # or download releases

# 3. Secrets — decrypt the committed staging env
export SOPS_AGE_KEY_FILE=/opt/ki-staging/.age-key
sops -d --input-type dotenv --output-type dotenv \
  deploy/staging/.env.staging.sops > .env
chmod 600 .env

# 4. Deploy
./deploy/scripts/deploy-staging.sh

# 5. Verify
./scripts/health-check.sh
curl -fsS http://127.0.0.1:18056/server/health
```

## Day-2 operations

| Task | Command |
|---|---|
| Redeploy latest main | `./deploy/scripts/deploy-staging.sh` |
| Tail logs | `docker compose -p ki-staging logs -f gateway` |
| psql | `docker compose -p ki-staging exec database psql -U kokonut -d kokonut_intelligence` |
| Backup now | `./deploy/scripts/staging-backup.sh` |
| Full teardown | `docker compose -p ki-staging -f docker-compose.yml -f deploy/staging/docker-compose.staging.yml down -v` (destructive: deletes staging data) |

## GitHub runner requirements

Register a repository-scoped self-hosted Linux x64 runner on the staging
host, label it `ki-staging`, and keep it updated for Node 24 compatible
actions (runner 2.327.1 or newer). Run the service under an unprivileged
account that can access Docker, and restrict the runner to this repository.
The workflow runs only by manual dispatch from `main`, requires the explicit
`yes` input, and uses the protected `staging` environment. Keep it paused until
the architecture and legacy-data gates are cleared. Never add this runner to
pull-request workflows.

## Editing secrets

```bash
cd /opt/ki-staging
export SOPS_AGE_KEY_FILE=/opt/ki-staging/.age-key
sops deploy/staging/.env.staging.sops   # decrypts in-editor, re-encrypts on save
git add deploy/staging/.env.staging.sops && git commit -m "chore(staging): update secrets"
```

The age public key that can decrypt this file is recorded in
`deploy/staging/.sops.yaml`. Staging and production use **different** keys.

## Mosquitto (IoT broker) notes

- TLS certs live in `config/mosquitto/certs/` (gitignored). The server cert
  MUST include `subjectAltName=DNS:localhost,IP:127.0.0.1` — the Docker
  healthcheck connects to localhost and rejects certs without it.
- Key files must be readable by the container's `mosquitto` user (uid 1883):
  `chmod 644 config/mosquitto/certs/*.key` on the host (bind-mount perms apply).
- The healthcheck identity (`healthcheck.crt` → CN=healthcheck) must appear
  in `config/mosquitto/acl`.
