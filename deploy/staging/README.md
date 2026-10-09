# KI Staging — cerberus

Staging environment for Kokonut Intelligence. Runs on the same host as CI
(cerberus) but in a fully isolated Compose project (`ki-staging`) with its
own data, ports, and secrets.

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
git clone <repo-url> /opt/ki-staging && cd /opt/ki-staging

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
